## Context

Release tooling today is **repository-centric**: `/releases` (`ReleasesView.vue`) takes `project_key` + `repository_slug` + two refs and calls `ReleaseDiffService`; `/releases/notes` manages per-tag notes; `/releases/dependency-graph` (`ReleaseDependencyGraphView.vue`) draws what one ref shipped. All three resolve a repository to an *application* through `project_registry` (`ProjectRegistryService.get_app_name`).

What actually ships is an **application release**: one app ref whose dependency record pins the version of every direct dependency. That record already exists and is already read - `DependencyGraphService.build()` asks the dependency database once for `(app_name, ref)` and returns the application's declared versions in the root node's `dependencies` map, next to what the packages declared for theirs. Three facts shape this design:

1. **The comparison is a version comparison, and it is the same shape as the repository comparison.** The repository comparison takes two refs of one repository and answers what moved between them; this takes two releases of one application and answers the same question about the packages. The unit compared is "the same package at two versions", exactly analogous to "the same repository at two refs". That analogy is what lets the existing vocabulary - source and target, a summary of counts, a verdict - be reused rather than invented.

2. **Two or more releases are compared, and the releases form a timeline.** The user picks N releases (`1.0.0`, `1.1.0`, `1.2.0`, ..). Comparing every pair would be N*(N-1)/2 results nobody reads; comparing **adjacent** releases along the release datetime is N-1 results, each of which is an ordinary pairwise comparison. The matrix (rows = packages, columns = releases) is the reading; the adjacent comparisons are the findings.

3. **Direct dependencies are the scope.** The dependency-of-dependency closure is a different question (and a much bigger picture, which `/releases/dependency-graph` already answers for one ref). Comparing the closure here would also drag in declared *ranges* between packages, which are not orderable and would flood the result with "changed, direction unknown". The root node's `dependencies` map is exactly the direct set, so the scope costs nothing to enforce.

Existing building blocks to reuse: `DependencyGraphService` (dependency database read, per-ref Redis cache, node cap), `ReleaseDiffService.list_refs` (tags and branches), `list_tags_with_commits()` on all three providers (release dates), the `project_registry` resolution, and the locale files.

## Goals / Non-Goals

**Goals:**

- Compare two or more application releases at direct-dependency level, ordered along the release datetime timeline, and show what moved between adjacent releases - upgrade, downgrade, added, removed - without the reader having to open a page per release.
- Read everything from the source the Release Dependency Graph already trusts, so the two pages can never disagree about what a release contains.
- Never claim a conclusion the data does not support: a release with no dependency record makes the comparison incomplete, and a version that cannot be ordered is reported as changed without a direction.

**Non-Goals:**

- Transitive dependencies, closure comparison, or lockfile/SBOM parsing.
- Resolving a package back to its repository, and drilling from a changed package into a repository comparison.
- Reading `package.json` (or any file) through the git providers, and storing snapshots of manifests.
- Any change to `ReleasesView`, `ReleaseNotesView` or `ReleaseDependencyGraphView` behaviour, and any change to existing endpoints or payloads.
- Comparing arbitrary refs for an application release view; branches and commits stay in the repository comparison.
- Export or report generation for this page.

## Decisions

### D1. The source is the dependency database, not the app repository's `package.json`

The application's release record is the authority for "which versions did this release pin", and it is already read by the Release Dependency Graph through `DependencyGraphService.build()`. Reading `package.json` from the git provider instead would need a new file-content primitive on three providers, would have to resolve tag to commit before every read, and would create a second answer to a question the project already answers once.

*Alternatives:* reading the manifest through the provider (rejected: a new capability on three adapters, and two sources of truth for the same fact). Persisting our own snapshots (rejected: duplicates storage the database already owns).

### D2. N releases, compared as adjacent pairs along the timeline

The request carries an ordered list of refs. The response carries the matrix plus one comparison per adjacent pair. N-1 pairwise results are what a reader can act on; all-pairs is N*(N-1)/2 and unreadable beyond three releases.

```
        app@1.0.0      app@1.1.0      app@1.2.0
packageA    1.0.0          1.0.0          1.1.0      ▲ 1.1.0 -> 1.2.0
packageB    1.0.0          1.0.1          1.0.1      ▲ 1.0.0 -> 1.1.0
packageC    1.1.0          1.1.0          1.1.0      -
packageF      -            0.9.0          0.9.0      + added at 1.1.0
packageD    1.1.0            -              -        - removed at 1.1.0
```

*Alternative:* comparing every pair (rejected), or a single baseline release compared against each other (rejected: hides movement between the later releases, which is the usual question).

### D3. Release order is the release datetime, and where it comes from is defined

Ordering is never the order the refs were typed in. The release datetime of a selected release is, in precedence:

1. the dependency record's `created_at`, which is the application release's own timestamp and already travels in the graph payload as `generated_at`;
2. failing that, the tag's date from the provider's `list_tags_with_commits()`, which also places a release the database holds no record for;
3. failing that (a branch with no record), the release keeps its position relative to the other unresolved releases as selected.

The order is visible in the column headers, so a reader can see why the columns sit where they do.

*Alternative:* ordering by semver (rejected: the refs are version-like strings, not versions, and a branch has none). Ordering by the tag date alone (rejected as the primary: it is the tag's creation time, not necessarily when the application release was recorded).

### D4. The compared set is the application's declared dependencies

Only the root node's `dependencies` map - what the application pinned - enters the matrix. Names declared in one release and absent from another are `added` / `removed`; names in several are `unchanged` or `changed`. The transitive packages the same payload carries are ignored by this page.

*Alternative:* including the closure (rejected: mixes pinned versions with declared ranges, which cannot be ordered, and duplicates what `/releases/dependency-graph` shows).

### D5. Version classification is tolerant, and never guesses a direction

A version is parsed into numeric components plus a pre-release part. Ordering follows semver precedence, including a pre-release sorting before its release (`1.2.0-rc.0 < 1.2.0`). A value that does not parse - a range, a tag-like string, `2.2602.1-demo-rc.2` in a form the parser cannot order - leaves the entry `changed` **without a direction**, and a downgrade is never rendered as an upgrade.

*Rationale:* the project publishes version-like refs and pre-release builds; a silent lexical comparison would render `2.9.0` as newer than `2.2601.0`.

### D6. Honesty about the horizon: a missing release makes the comparison incomplete

The dependency database answers `None` for a ref it holds no record of - an application that has not been built or scanned at that ref, or a repository that is not registered and therefore resolves to the `Unknown` application. In that case:

- the column exists and is marked as having no dependency record;
- the adjacent comparisons that touch it are reported as **incomplete** rather than as "no changes";
- the comparisons between the releases that do have records are still reported.

This mirrors the repository comparison's rule that a verdict is never derived from an incomplete scan. The reverse failure mode - a page that says "nothing changed" because one side was missing - is the specific error this decision exists to prevent.

### D7. One new endpoint; the existing pages are not touched

`POST /api/v1/release/apps/diff` takes the repository coordinates, the ordered refs and a `refresh` flag, resolves the application once, reads each ref through `DependencyGraphService` and returns the matrix with the adjacent comparisons. Nothing else changes: the three existing release pages, their endpoints and payloads keep their behaviour, and the only existing file edited is `api.py`, by one registration line.

*Alternative:* extending `/releases` with a mode switch (rejected: it is a repository-scoped page with its own context card, and the user asked for the existing functions to be left alone).

### D8. Refresh is explicit, and it is per request

The per-ref graphs live in the Release Dependency Graph's cache, keyed by ref name with a one-hour TTL. Because a tag can be moved, the page carries a refresh action that bypasses the cache for the refs it reads, exactly as the repository comparison does. A reader who suspects a moved tag can settle it without waiting for the TTL.

### D9. Navigation says "App Diff", and the repository comparison keeps its name

The Releases group gains **App Diff**. The existing `Release Comparison` entry is left named as it is, at the user's explicit request that other pages not be disturbed; the two labels are distinguishable because one names the application and the other the repository, and the new page states the application it compares in its heading.

### D10. Response shape (sketch)

```jsonc
{
  "project_key": "CORE",
  "repository_slug": "app",
  "app_name": "mylang",
  "git_provider": "bitbucket_server",

  "releases": [
    { "ref": "1.0.0", "generated_at": "2026-09-30", "has_record": true },
    { "ref": "1.1.0", "generated_at": "2026-10-05", "has_record": true },
    { "ref": "1.2.0", "generated_at": null,         "has_record": false }
  ],

  "verdict": "changed",          // identical | changed | incomplete
  "summary": { "changed": 2, "upgrade": 2, "downgrade": 0, "added": 1, "removed": 1 },

  "packages": [
    { "name": "packageA", "versions": ["1.0.0", "1.0.0", "1.1.0"],
      "states": ["unchanged", "upgrade"] },
    { "name": "packageF", "versions": [null, "0.9.0", "0.9.0"],
      "states": ["added", "unchanged"] },
    { "name": "packageD", "versions": ["1.1.0", null, null],
      "states": ["removed", "unchanged"] }
  ],

  "intervals": [
    { "from": "1.0.0", "to": "1.1.0", "complete": true,
      "summary": { "changed": 1, "upgrade": 1, "downgrade": 0, "added": 1, "removed": 1 },
      "changes": [ /* per package */ ] }
  ]
}
```

`states[i]` describes the move from release `i` to release `i+1`; `changes` carries the same information grouped per interval, so the view can read either way. `verdict` is `incomplete` as soon as any selected release has no record.

## Risks / Trade-offs

- [Direct dependencies only, so a transitive bump is invisible] -> Accepted and stated in the UI. The closure is a separate question, and the Release Dependency Graph answers it per ref.
- [Two releases that differ only in a range the application declares] -> Ranges are out of scope by D4; a version-like but unorderable value is `changed` without a direction rather than a guessed upgrade.
- [A moved tag makes a cached reading stale] -> D8's refresh, and the cache TTL is the existing one-hour window.
- [The database lags behind the repository, so a release exists as a tag long before it has a record] -> D6 renders that as `incomplete` with the column marked, which is the honest reading and points the reader at the database rather than at the page.
- [A repository that is not registered resolves to the `Unknown` application and therefore has no records] -> Same path as a missing record; `get_app_name` auto-registers the repository, so the second visit onward has an application (with no dependency data until the database is scanned for it).
- [Ordering a branch among tags] -> D3's third rule keeps it in place instead of inventing a date.
- [An application release that pins a package the later release dropped entirely] -> Reported as `removed` for that interval, which is the useful reading; the matrix keeps the earlier version visible in its column.

## Migration Plan

- Purely additive: one new service, one new schema module, one new endpoint, one registration line. No migration, no table, no configuration, no change to existing endpoints or payloads.
- Frontend changes are additive (one route, one menu entry, new locale keys). No existing route, label or component behaviour changes.
- Deployment order: backend first (the endpoint is inert until called), then frontend. Rollback = revert the deploy.

## Open Questions

- **Release datetime precedence.** D3 puts the dependency record's `created_at` first and the tag date second. If the database's `created_at` turns out to be a backfill or a scan timestamp rather than the release time, the order should be inverted. To confirm against a real record with a known release date.
- **Whether the code axis is wanted here.** The repository comparison's expensive half - the commits between two refs - is not part of this design; the dependency axis alone cannot prove that the code did not change when every version matches. If that case matters, one `compare_releases` call per adjacent interval would answer it, and a requirement would be added.
- **How many releases the page should accept at once.** The matrix stays readable for a handful of releases; the practical cap (and what the picker defaults to beyond the two most recent) is a UI decision to settle during implementation.
