## Context

The release tooling answers two questions with the same pair of inputs (`old_release_ref` + optional `old_release_base_ref`, `new_release_ref` + optional `new_release_base_ref`):

1. **What changed between the releases** — answered by the set difference in the new direction (`new \ old`).
2. **Is the old release fully contained in the new one** — the missing check, which is the question that actually matters for a per-build routine.

The problem is that the current implementation answers (2) by *enumeration*:

```
  compare_releases:  old_commits = list/compare(old_base → old_ref)   # capped: commit_preview_limit = 200
                     behind_ids  = compare(new_ref → old_ref)         # capped: max_commits = 1000
                     missing     = [c for c in old_commits if c.id in behind_ids]   # ← intersection of two capped sets
  check_commits:     release_commits = list/compare(target_base → target_ref)  # capped: max_commits = 1000
                     included = supplied ids matched against that in-memory lookup
```

A repository with several years of history and one release line forked from another (v1.0.0 → v1.x and v2.x developed in parallel for a month) makes both caps bite: the missing list can come back empty because the *capped* old set did not reach the commits that are genuinely absent, and a commit that is present can be reported as `not_found_in_release_scope` because the target release listing was capped.

What makes this easy to fix is git's own semantics. The set difference in the missing direction is *small by construction* (`source \ target` = the un-merged work — the older shared history is excluded because it is reachable from the target as well), while the expensive direction (`new \ old`) is the one that grows with the repository. The providers already expose exactly this difference: Bitbucket Server `compare/commits?from&to`, Bitbucket Cloud `commits?include&exclude`, GitHub `compare/{base}...{head}`.

## Goals / Non-Goals

**Goals:**

- Make the per-build merge check **definitive or explicitly inconclusive** — never a silent pass, never a false "missing".
- Remove the enumeration-and-match logic from every verdict path; use provider-side set arithmetic instead.
- Keep the check cheap enough to run on every build (ids only, one paginated scan of the difference).
- Make the routine usable: a preset on the releases page with a saved baseline per repository.

**Non-Goals:**

- Cherry-pick / squash-merge equivalence (a fix cherry-picked into the target creates a new commit id and will still be listed as missing). Deferred: it needs patch-id comparison over commit diffs, which is a different and much heavier primitive. The verdict reports what git can prove about commit identity.
- Reworking the "added" set semantics (`added_commits` currently filters the new-release scope, which under-reports a two-release delta) — tracked as follow-up work, not part of this change.
- Any change to the app-level release comparison (`add-app-release-diff`) or to release note generation; the code axis of that change simply consumes a trustworthy commit range.
- Detect "merged and later reverted" (the commit is still reachable, so containment holds) — that is a code-level question, not a history-containment question.

## Decisions

### D1. The verdict is a set difference, not an intersection of capped sets

`missing = commits reachable from the source ref but not from the target ref`, obtained from the provider's compare in that single direction.

```
   source ref  (e.g. v1.1.5)          target ref  (e.g. v2.3.0)
        │                                   │
        └──────── source \ target ──────────┘        ← the verdict: usually a handful of commits
        ▲                                   ▲
    reachable from source            reachable from target
    (shared history cancels out: everything both sides have is excluded automatically)
```

Consequences:
- The source base ref is **no longer needed for the verdict**; when supplied it only narrows the answer ("check just this release's own commits") and the response states which mode was used.
- The old-release commit preview never takes part in the verdict; it remains display material only.

*Alternative rejected:* keep the intersection but raise the caps — the failure mode is inherent (any cap can silently hide a missing commit), and the cap would have to be the size of the repository history.

### D2. Three-state verdict, and truncation can never pass

`Verdict = contained | missing | inconclusive`.

- `contained` — the difference scan ran to completion and returned nothing.
- `missing` — the scan ran to completion and returned N commits.
- `inconclusive` — the scan hit its limit (or the provider capped a page). The response carries the scan limit, the count found so far as a lower bound, and the hint to raise the limit.

A response with `inconclusive` MUST NOT be rendered as a pass, and the UI MUST NOT show a success state for it. This replaces today's behaviour where `truncated` was informational while `status`/`all_included` still claimed a verdict.

### D3. Paginate the difference to completeness, with an explicit scan limit

The difference fetch pages through the provider until exhausted or until `missing_scan_limit` (default 2000, max 10000, request-overridable) and reports `complete: bool`:

| Provider | Paging signal |
|---|---|
| Bitbucket Server | `/compare/commits?from&to` paged: `isLastPage` / `nextPageStart` |
| Bitbucket Cloud | `/commits?include&exclude` paged: `next` |
| GitHub | `/compare/{base}...{head}`: `total_commits` + 250-per-page cap; `behind_by` as a cheap total for the missing direction |

Because the missing direction is small by construction, completeness is normally reached in one or two calls; the limit exists to bound a pathological case (a target line that never took the source line at all), and hitting it is reported rather than hidden.

### D4. Per-commit containment is a provider query, not a lookup

`check_commits` (a supplied list of ids) asks the provider whether the target ref contains each commit, one call per commit:

| Provider | Call | Contained when |
|---|---|---|
| Bitbucket Server | `compare/commits?from={target}&to={commit}` | the result page is empty |
| Bitbucket Cloud | `commits?include={commit}&exclude={target}` | the result page is empty |
| GitHub | `compare/{target}...{commit}` | `ahead_by == 0` (the commit adds nothing the target lacks; status is then `behind` or `identical`) |

> Implementation note: the containment test is `commits(commit) \ commits(target)`
> being empty, i.e. the commit is an ancestor of the target. Both compare sides
> matter - the first draft of this table had them swapped, which would have
> answered "is the target an ancestor of the commit" instead.

This is exact regardless of how large the target release is, answers short SHAs (the provider resolves them), and removes the `_build_commit_lookup` / `_match_commit` path from the verdict. Commit details for the *matched* ones are fetched only when the caller asks for them (`include_commits`), in one enriched difference call rather than a release listing.

*Alternative rejected:* keep the in-memory lookup and raise `max_commits` — that is exactly the false-`not_found_in_release_scope` bug reported by the users.

### D5. One operation: verdict, missing, and added in a single comparison

There is exactly **one** tool and one endpoint. A comparison takes a source release, a target release and an optional baseline, and returns:

- the **verdict** (`contained` / `missing` / `inconclusive`) from the missing direction `source \ target`;
- the **missing commits** (source side work absent from the target);
- the **added commits** (`target \ source`, i.e. what the target has that the source does not) with their own completeness flag;
- the effective baseline, whether it came from the repository store, and how many difference commits it filtered out.

Both directions are two provider compares; neither needs a release commit listing, so the old scoped previews (`old_release_commits` / `new_release_commits`, capped at 200 with `*_truncated` flags) are **removed** rather than kept for display. Commit details come with the compare payloads, so `include_commits` only decides whether they are serialized, and the rendered detail lists are capped by `render_limit` while the counts stay complete.

*Why merged:* a separate "merge check" endpoint and card answered a question that the comparison already answers (it is the same difference scan, in one direction), and users could not tell the two apart. One vocabulary - source / target / baseline / verdict - replaces "old / new / old base / new base / missing check".

*Alternatives rejected:* a `mode` flag on the comparison (still two behaviours to understand, and the cheap mode is not actually different - it is the same two scans); keeping the scoped previews (they cost two extra provider calls per comparison and only exist for a report section that the missing / added lists render better).

### D6. The baseline is a field of the comparison, stored per repository

The comparison accepts **one** optional `baseline_ref`. When it is omitted and `use_stored_baseline` is true, the baseline stored for the repository is used, and the response says so (`baseline_ref` + `baseline_stored`). Narrowing is symmetric: the baseline drops difference commits that already existed at it, in **both** directions, which is what "the work this line did since the fork point" means.

The baseline is stored in `release_check_baseline`, keyed by `(git_provider, project_key, repository_slug)`, holding `baseline_ref`, `note`, `updated_by`, timestamps, and is editable from the tool itself with the manage permission. Storing it server-side (rather than in the browser) makes the routine identical for every release engineer on the team.

*Alternative considered:* a `system_settings` key per repository (zero migration) — rejected because the value would be unqueryable and awkward to list per repository.

### D7. Response and cache compatibility

- The comparison payload is deliberately **not** backward compatible with the old compare response: `status`, `old_commits_included`, `summary`, the scoped commit sets and the `*_truncated` display flags are gone, replaced by `verdict`, `missing_count` / `added_count` and per-direction completeness flags. The only consumers are the releases page (updated in this change) and the HTML report builder.
- The cache key is rebuilt around `(source, target, effective baseline, scan limit, render limit, include_commits)` and the version segment is bumped to `release_diff:v3:`, so entries written by either earlier implementation are never served with a different meaning.
- Metrics: the `release_diff` counters carry the verdict, so an inconclusive comparison is visible in monitoring instead of looking like a pass.

## Risks / Trade-offs

- [The difference set is genuinely huge (a line that never took the other line's work)] → Reported as `missing` with a capped list and a complete count; the operator sees "N missing (showing first M)" with the scan limit, which is the honest answer.
- [Cherry-picked fixes appear as missing] → Documented limitation and shown in the UI help: the check answers commit identity, not patch equivalence. Mitigation for the operator is comparing the missing commits' subjects / ticket keys. Patch-id equivalence is an explicit follow-up.
- [Per-commit containment costs one call per id] → Bounded by the existing `max_length=200` on the supplied list and by caching; the id-only per-build routine uses the single difference scan instead, so the per-commit path is only for hand-supplied lists.
- [A provider's compare endpoint changes paging semantics] → Completeness is derived from the provider's own paging signal, and any parse failure degrades to `inconclusive` rather than to a pass.
- [Verdict changes break existing UI expectations (`status = included`)] → The UI is updated in the same change; the API keeps the old field with a documented meaning, and `inconclusive` is additive.

## Migration Plan

- Backend-first, additive: new endpoint, new provider primitive, one new table (`alembic/versions/035_create_release_check_baseline.py`, `down_revision = "034"` if the app-release change is deployed, otherwise "032").
- The cache version segment bump invalidates old comparison entries; nothing else is persisted in a form that needs migrating.
- Frontend: the verdict card and preset replace the "truncated → maybe" presentation on the compare/check panels; the rest of the page is untouched.
- Rollback: revert the deploy; the baseline table can stay unused. Old cached entries are simply not read (version segment) and expire naturally.

## Open Questions

- **Scan limit default.** 2000 is a guess based on "a month of parallel development"; if a real repository routinely produces larger differences, the default (and the cap) should be revisited — the number is a request field, so this is a tuning question rather than a design one.
- **Baseline semantics.** Whether the stored baseline should be the fork point (check the whole other line) or the previous release of that line (check only that release's own commits) — the preset supports both, and the UI should state which one is in use rather than silently picking one.
- **Patch-id equivalence.** If cherry-picked fixes turn out to be a frequent source of false "missing" in practice, a follow-up can compare patch ids for the missing commits against the target's recent history.
