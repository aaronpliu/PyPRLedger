## Context

Release tooling in this codebase is **repository-centric**. `/releases` (`ReleasesView.vue`) takes `project_key` + `repository_slug` + two arbitrary refs and calls `ReleaseDiffService` (`compare_releases`, `check_commits`, `list_refs`); `/releases/notes` manages per-tag release notes. Both are backed by the git provider adapters (`bitbucket_server`, `bitbucket_cloud`, `github_enterprise`) sharing `GitProviderBase`.

What actually ships, however, is an **application release**: an app tag whose repository declares 20+ **pinned** direct dependencies (`package.json`, no lockfile, values like `1.2.0-rc.0` / `2.2602.1-demo-rc.2`, no `^`/`~` ranges). Two facts shape the whole design:

1. The dependency manifest lives **in the app repository at the released ref** — no third-party API serves it; the git provider does (`raw` / `src` / `contents` endpoints). There is currently **no file-content capability** in `GitProviderBase`, and `list_refs()` returns ref **names only** (no SHA, no date).
2. **Tags move.** A publisher can retag the same version to a newer commit, so "the same version" can be built several times. A version string is therefore a human label, not an identity; `(tag_name, commit_sha)` is.

A third fact decides how the page hangs together: a dependency version can be walked **back** to the code it was built from, because the organization publishes its packages to **JFrog Artifactory**, whose build information carries the VCS URL and revision of every release. `project_registry` cannot serve this role — its rows are `(project_key, repository_slug)` → virtual grouping name, not a package index.

Existing building blocks to reuse: the app grouping in `project_registry.app_name` (with `GET /apps` + a per-app nav precedent in Task Assignment), the Redis cache and metrics utilities, the `system_settings` configuration pattern used by the LLM and JIRA settings, and the git provider credentials already configured.

## Goals / Non-Goals

**Goals:**

- Compare two **application releases** at manifest level (which dependency versions moved, which were added/removed/downgraded), and pair that with the **code axis** (what commits landed between the two snapshot commits).
- Serve the data from the git provider, **up to date at page-view time**, without hammering it: resolve refs cheaply on every view, cache file content permanently by commit SHA.
- Keep an **immutable snapshot history** per application release so a rebuild or a moved tag is a visible, reviewable event rather than a silent data mutation.
- Resolve every changed dependency back to **the repository and the exact revision it was published from** (Artifactory first, tag lookup as fallback), so a drill-down compares what actually shipped instead of a guess.
- Drill from a changed dependency into the existing repository comparison, prefilled, with a shareable URL.

**Non-Goals:**

- Transitive dependency closure (direct `package.json` entries only; SBOM or recursive expansion is a later change).
- Lockfile parsing (`package.json` is authoritative here because versions are pinned).
- A scheduled background catalogue sync — snapshots are written through on demand.
- Report/PNG/HTML export for the app view (the repository view keeps its existing export).
- Application→repository navigation tree or a redesign of the existing repository page (it gains query prefill only).
- Treating branches/commits as "published releases"; those stay in the repository comparison.
- Publishing or promoting artifacts, or writing anything back to Artifactory (read-only integration).

## Decisions

### D1. Release catalogue comes from git tags, not from the release REST API

`list_tags_with_commits()` (one paginated call per repository) returns `{name, sha, date}` per tag on all three providers — this is the version list, the SHA needed for snapshotting, and the tag-movement detector in a single call. The existing release REST API is *not* used in this change (it can be added later as optional enrichment for build numbers / release dates).

*Alternatives:* trusting the REST API catalogue was rejected because it cannot supply the manifest, and mixing two catalogues would require reconciliation rules for "tag without an API entry" / "API entry without a tag".

### D2. Snapshot identity is `(application, tag_name, commit_sha)`

The tag name is what a user selects; the SHA is what the manifest was read from. Unique index on the triple, plus `is_current` (the tag's latest known snapshot) and `superseded_by_id`. Writes are **append-only**: refreshing never rewrites an existing row, so "what did 3.10.0 contain last week" stays answerable.

*Alternatives:* keying by version string (`3.10.0_20000`) was rejected — it cannot express a rebuild, and parsing business keys duplicates work the provider already did. `build_number` is kept as an optional, non-identifying attribute.

### D3. Annotated tags are dereferenced by the provider, not by us

GitHub's `/git/refs/tags/*` returns a tag **object** SHA, which is not the commit. The provider primitives therefore use commit-resolving endpoints (`/repos/{o}/{r}/tags` for listing, `/contents?ref=` or `/commits/{ref}` for reads) so the adapter can never store a tag object SHA as a commit. Bitbucket Server (`/tags` → `latestCommit`) and Cloud (`/refs/tags` → `target.hash`) already return the commit.

### D4. Cache granularity follows git semantics: refs are volatile, content is immutable

- **Ref resolution:** no long-lived cache. `list_tags_with_commits()` runs per page view (1 call) — this is what keeps the page up to date when a tag moves.
- **File content:** cached permanently under `(provider, project, repo, path, sha)`. A blob for a given SHA can never change, so there is no invalidation logic and no stale-data risk.
- **Computed diffs:** cached under `(shaA, shaB)`. A diff is a pure function of two snapshots, so the key is exact and never needs invalidation; a content-hash mismatch (same SHA → different manifest, i.e. a re-write inside the same commit) simply misses and rewrites the snapshot.

This split removes the classic "cache by ref name" bug class entirely.

### D5. Manifest scope is direct dependencies, read from `package.json`

With pinned versions there is nothing to resolve, so parsing `package.json` is sufficient and no lockfile parser is needed. `dependencies`, `devDependencies`, `optionalDependencies` and `peerDependencies` are recorded with a `dep_scope` so the UI can filter; `overrides`/`resolutions` are ignored in this change. A missing manifest is a normal outcome (`None`), surfaced as an explicit empty state rather than an error. `declared_spec` is deliberately **not** stored — with pinned versions it would always equal `version`.

*Alternatives:* requiring an SBOM was deferred (needs CI cooperation) and is the natural input for the future transitive closure work.

### D6. Version comparison is tolerant semver, and never guesses

`v_major` / `v_minor` / `v_patch` / `prerelease` are parsed and stored so ordering never relies on string comparison (`"2.9.0" > "2.2601.0"` lexically), with an optional leading `v` accepted. Pre-release identifiers follow semver precedence (`1.2.0-rc.0 < 1.2.0`, `2.2602.1-demo-rc.2` parses as identifiers `demo-rc` + `2`). A value that does not parse leaves the numeric columns `NULL` and the row is reported as **changed without a direction** — a downgrade must never be rendered as an upgrade.

### D7. Two axes, always reported together

The dependency matrix alone can be misleading: a moved tag with an unchanged `package.json` yields an empty dependency axis while the shipped code actually changed. The response therefore carries both the package diff **and** the commit delta between `shaA` and `shaB` (reusing `ReleaseDiffService`, whose refs already accept any ref including a SHA), and the UI must render the "no dependency change but N commits" case explicitly instead of showing "nothing changed".

### D8. Moved tags are marked and confirmed, never silently refreshed

Refreshing an existing snapshot is a privileged action: a re-resolve that returns a different SHA for an already stored tag records `tag_moved_at`, keeps the old row untouched, and surfaces the change to `review_admin` / `system_admin` for confirmation (the confirmation creates the new snapshot and flips `is_current`). Viewing is unprivileged.

### D9. New app-first page; the repository page becomes the drill-down layer

`/releases/apps` is a new view; `/releases` is **not** restructured into a mode-switching workbench (it is already a ~1300-line page with a repository-scoped context card that would be meaningless in app mode). The matrix row links into `/releases` with the coordinates prefilled, and shows a breadcrumb back.

*Alternatives:* a mode switch inside the existing page (rejected: two unrelated input models in one form) and an app→repo navigation tree (rejected: disproportionate refactor for this change).

### D10. Both pages get URL state

`/releases/apps?app=&from=&to=&view=deps|code` makes an app comparison linkable (and lets superseded snapshots be compared explicitly — "what changed in the rebuild"). The repository page gains `project_key` / `repository_slug` / `git_provider` / `old_release_ref` / `new_release_ref` query prefill using its existing form field names, so the drill-down link is a plain navigation and no shared state machinery is needed.

### D11. Menu naming

`Releases` submenu becomes **Application Releases** (new) → **Repository Comparison** (renamed from "Release Comparison") → **Release Notes**. Two entries both named "Release Comparison" was acceptable while only one comparison existed; it is not once there are two. The i18n key `menu.releaseComparison` is kept (only its value changes) to avoid churn across three locales.

### D12. Application release data model (sketch)

```
application                          per-app manifest configuration
  id, name(uk), display_name
  manifest_path      e.g. "package.json"      (monorepo: path to the app's manifest)
  dep_scopes         runtime | runtime+dev     (which scopes are recorded)
  is_active, created_date, updated_date

app_release                          one row per (tag, resolved commit)
  application_id FK, tag_name String(128), commit_sha String(64), commit_sha_short
  commit_date, build_number String(32) '', is_current, superseded_by_id FK(self)
  tag_moved_at, revision, manifest_content_hash String(64), package_count
  fetched_at, raw_manifest JSON|NULL, created_date, updated_date
  uk(application_id, tag_name, commit_sha)   idx(application_id, tag_name, is_current)

app_release_package                  one row per direct dependency
  release_id FK(cascade), package_key, package_name, version
  v_major, v_minor, v_patch (nullable), prerelease (nullable), is_prerelease
  dep_scope, is_external
  uk(release_id, package_key)   idx(package_key, v_major, v_minor, v_patch)
```

`package_key` (lower-cased, trimmed, scope preserved for `@org/pkg`) is what uniqueness and lookups use, so `Package_A` / `package-a` drift cannot produce phantom add/remove pairs. The package's **repository** is not duplicated on these rows — it is resolved separately (D13) and joined at read time, so a repository rename never rewrites history.

### D13. Package → repository resolution prefers Artifactory, and only local repositories count as internal

Package names are **unique across all applications**, so the mapping is a single **global** table (`package_repository`, `package_key` unique) with an optional `tag_template` fallback — no per-application override, no `scope_key`. Resolution order:

1. an existing `manual` row wins and is never overwritten by automatic resolution;
2. the artifact source (Artifactory, queried by package name + version) supplies the repository and the revision;
3. tag lookup by version in that repository (exact → leading `v` stripped → repository-name prefix);
4. package name matched against the repository name (naming convention);
5. nothing resolved → the package is `external`, no drill-down, no error.

A hit found only in a **remote or virtual** repository is a proxied third-party artifact (`react`, `lodash` and friends) and MUST be treated as external; only `local` repositories produce an internal mapping. Every automatic resolution records `source` and `confidence`, and a low-confidence result stays non-authoritative until a user confirms it.

*Alternatives:* deriving the mapping from `project_registry` was rejected — its rows are `(project_key, repository_slug)` → virtual grouping name (`uk_project_repo_unique` allows exactly one row per repository), which cannot express "20 packages → N repositories", and the registry is not a package index. Naming convention as the *primary* source was rejected: it silently misses renames and typos.

### D14. A package version resolves to an immutable revision, not to a tag

For a released artifact, Artifactory's build information carries the VCS identity (`vcsUrl` + `vcsRevision`), which identifies both the repository and the exact commit that was published. That revision is preferred over any tag: it is unaffected by tag naming conventions (legacy `1.12.0-rc.1` included) and immune to later tag movement. Tag lookup is the fallback when build information is absent, and `tag_template` the last resort. Resolutions are cached per `(package_key, version)`; when one side of a comparison has no resolved revision, the row renders as not drillable while its version difference is still displayed.

```
package_a @ 2.2601.0
   ├─ Artifactory: artifact in a local repo  →  build info → vcsUrl + vcsRevision
   │                                                        → (provider, project, repo) + commit sha
   ├─ fallback: tag lookup in the resolved repo (2.2601.0 / v2.2601.0 / pkg-a-2.2601.0)
   └─ fallback: naming convention → low confidence, needs confirmation
```

### D15. Artifact source configuration lives with the other integrations

Artifactory settings (base URL, **read-only** token, the ordered list of repository keys that count as `local`) are stored in `system_settings` with environment fallback — the same pattern as the LLM and JIRA settings — and edited from the admin area. Degradation is deliberate: without configuration, or when the artifact source is unreachable, resolution falls back to tag lookup and then to "unresolved"; the comparison page is served from snapshots and never fails because of it.

### D16. Mapping provenance is part of the data, and maintenance is a queue

`package_repository` carries `source` (`manual` | `artifactory` | `tag_lookup` | `convention`), `confidence` (`high` | `medium` | `low`), the `artifactory_repo` that produced the conclusion, and `resolved_at`. The admin area lists low-confidence and unresolved packages as a review queue with bulk confirmation, CSV import/export for initial onboarding, and manual coordinate entry; a manually edited row switches to `source = manual` and is thereafter excluded from automatic resolution.

*Rationale:* the existing `ProjectRegistryService.auto_register_project()` shows how auto-registration without provenance ages badly (it fell back to an `'Unknown'` application name). The queue keeps the automatic path useful without letting unverified mappings become authority.

## Risks / Trade-offs

- [Direct dependencies only → a transitive bump shows as "no change"] → Accepted scope for v1: the page states its scope in the UI; the follow-up is SBOM ingestion or recursive expansion (feasible precisely because versions are pinned, and Artifactory can serve the published tarballs' manifests).
- [Provider rate limits on repeated page views] → Ref resolution is 1 call per view, file reads are permanently cached per SHA, diffs are cached per `(shaA, shaB)`; failures degrade to "could not refresh, showing stored snapshot" instead of an error page.
- [Tag moved without anyone noticing until the next view] → Because snapshots are append-only, the older content is still comparable; the drift is surfaced on view and confirmed by an admin.
- ["Arbitrary valid versions" that are not semver] → Neutral "changed" rendering; the comparison remains useful, only the direction arrow is withheld.
- [Monorepo / multiple manifests in one repository] → `application.manifest_path` makes the choice explicit per app; a missing file is an empty state, not a 500.
- [A third-party package resolves to a proxied copy inside a remote/virtual repository] → Only `local` repositories produce internal mappings; remote/virtual hits are labelled external, so no drill-down link is ever built from a proxied artifact.
- [An automatic mapping is wrong and silently used] → Every row carries `source`/`confidence`; low-confidence results require confirmation, manual rows are never overwritten, and the review queue exposes what was inferred.
- [Artifact source unavailable or unconfigured] → Fall back to cached mappings, then tag lookup, then unresolved; the comparison itself is served from snapshots.
- [A released artifact version is re-deployed with different content] → The cached resolution refreshes `resolved_at`, so the drill-down may point at the newer revision; acceptable because app snapshots record only the version, and the admin area shows when a mapping was last resolved.
- [Storing `raw_manifest` grows the table] → Bounded by ~1 KB per release and valuable for auditing re-parses; can be dropped later without touching the normalized rows.
- [Duplicated work if a user compares the same pair on every page load] → Diff cache keyed by snapshots makes repeat views a cache hit; snapshot rows are reused, never re-fetched.

## Migration Plan

- Purely additive on the backend: three application-release tables (`alembic/versions/033_create_app_release.py`) and two mapping tables (`alembic/versions/034_create_package_repository.py`, `down_revision = "033"`), plus new service/endpoint modules. No changes to existing tables, endpoints or payloads.
- Frontend changes are additive except the menu **label** change (`Release Comparison` → `Repository Comparison`) and the new query prefill on `/releases`, both backward compatible (no route paths change; `/release-diff` keeps redirecting to `/releases`).
- Deployment order: backend first (new endpoints inert until called), then frontend. Rollback = revert the deploy; the new tables can stay unused, or be dropped by downgrading revisions `034` then `033`.
- No configuration is required to deploy: git provider credentials are reused. Artifactory is **optional enrichment** — until its settings are filled in, dependency resolution falls back to tag lookup, then to "unresolved", and packages without a repository render as external.

## Open Questions

- **Artifactory repository keys and precedence.** Which keys count as `local` (e.g. `npm-local`, `npm-release`) and in what order they are consulted has to be confirmed when the settings are filled in; a wrong list silently pushes internal packages to "external".
- **Re-deploy policy for an already released artifact version.** Whether a re-deployed version should raise an admin warning instead of silently refreshing the cached resolution.
- **Build numbers.** If the internal release REST API (all versions of an app) is added later, it can enrich snapshots with build numbers and publish dates; today a rebuild is identified by SHA + `revision`.
- **Frozen vs live manifests.** If the platform ever changes a manifest for an already-released tag without moving the tag (same SHA), the content-hash mismatch path creates a new revision of the same snapshot; confirm that this is acceptable versus treating it as a conflict.
