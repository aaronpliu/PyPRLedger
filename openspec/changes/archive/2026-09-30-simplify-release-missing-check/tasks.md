## 1. Provider primitives

- [x] 1.1 Add `contains_commit(project_key, repository_slug, ref, commit) -> bool` to `GitProviderBase`, documenting the per-provider containment strategy and that short SHAs are resolved by the provider
- [x] 1.2 Implement it on `bitbucket_server` — `compare/commits?from={ref}&to={commit}`, contained when the result set is empty (shared default in `GitProviderBase`)
- [x] 1.3 Implement it on `bitbucket_cloud` — `commits?include={commit}&exclude={ref}`, contained when the result set is empty (same shared default)
- [x] 1.4 Implement it on `github_enterprise` — `compare/{ref}...{commit}`, contained when `ahead_by == 0`
- [x] 1.5 Make the difference fetch completeness-aware: `compare_commits_complete()` returns `(commits, complete)`, with a conservative default plus Server (`isLastPage` / `nextPageStart`) and GitHub (`total_commits`, paging the 100-per-page cap) overrides
- [x] 1.6 Tests per provider in `tests/test_git_provider_containment.py`: containment direction, empty / non-empty difference, last page vs full page, GitHub paging reaching `total_commits`, cap reached → `complete = False`, short SHA resolution

## 2. Missing check service

- [x] 2.1 Add `check_missing(request)` computing the difference in the source → target direction, with the source base ref as optional narrowing only
- [x] 2.2 Derive the three-state verdict (`contained` / `missing` / `inconclusive`) with a complete-or-inconclusive guarantee; never return `contained` from an incomplete scan
- [x] 2.3 Implement the details-free default mode (no reverse-direction compare, no detail payloads returned) and the enriched mode (details for the difference only, capped for rendering)
- [x] 2.4 Rewrite `check_commits` to per-commit containment via `contains_commit`; the listing was demoted to enrichment and no longer decides the verdict
- [x] 2.5 Include the scan limit in the cache key, bump the cache version segment (`release_diff:v2:…`) so old capped entries are never served, and emit `inconclusive` in the `release_diff` metrics
- [x] 2.6 Tests: contained / missing / scan limit → inconclusive / narrowing by a base ref / stored baseline / identical refs / shared history not reported / capped previews and capped listings no longer change the verdict / provider failure propagates

## 3. API and schemas

- [x] 3.1 Add `POST /api/v1/release/diff/missing` with `{source_ref, target_ref, source_base_ref?, scan_limit?, render_limit?, include_commits, use_stored_baseline}` returning the verdict, the missing commits, the completeness flag and the limit that was hit
- [x] 3.2 Extend `ReleaseCompareResponse` with `verdict` / `missing_scan_complete` / `missing_scan_limit` (and `status = inconclusive`), document `missing_commits` as complete-or-lower-bounded, keep the existing fields and their documented meaning
- [x] 3.3 Add baseline endpoints: `GET` / `PUT` / `DELETE /release/diff/baseline` (writes require the `release_diff:manage` permission)
- [x] 3.4 Endpoint tests: verdict propagation, `inconclusive` fields, stored-baseline use, baseline round trip with project-key normalization, `403` on an unprivileged write while reading stays open

## 4. Baseline storage

- [x] 4.1 Add `src/models/release_check_baseline.py` — `(git_provider, project_key, repository_slug)` unique, `baseline_ref`, `note`, `updated_by`, timestamps
- [x] 4.2 Add `alembic/versions/033_create_release_check_baseline.py` (`down_revision = "032"`, the head at implementation time) with a working downgrade, plus the `release_diff` role permissions
- [x] 4.3 Add `ReleaseCheckBaselineService` (get / get_ref / save / clear, project key normalized) and register the model so tests pick it up

## 5. Frontend

- [x] 5.1 Verdict card on the releases page: contained / missing (with the count) / inconclusive (never a success style), including the scan limit and how to raise it
- [x] 5.2 Missing commit list (reusing `CommitTable`) with identity, provider link, and the "showing first M of N" note when the rendered list is capped
- [x] 5.3 Merge check preset (third tool card): source release tag + editable, savable baseline + target release tag, runnable without re-entering the baseline; the repository and refs are kept in the URL
- [x] 5.4 The compare verdict now drives the alert colour/text (inconclusive is a warning, never a pass), the check truncation notice explains that only the details are limited, and the cherry-pick equivalence note is part of the preset help
- [x] 5.5 i18n for the new verdict, preset and help strings in `en`, `zh-CN`, `zh-TW`
- [x] 5.6 Tests: verdict rendering per state, inconclusive never rendered as a pass, stored-baseline narrowing with the effective baseline echoed, capped missing list note, baseline buttons restricted to the managing roles, URL state

## 6. Verification

- [x] 6.1 Backend: full `pytest` suite (267 passed), `ruff format --check` and `ruff check src tests`
- [x] 6.2 Frontend: `vitest` suite (160 passed), `vue-tsc --noEmit` (exit 0). No lint script or ESLint config exists in `frontend/`, so there is nothing to run for that step
- [ ] 6.3 Manual check on a repository with a forked release line: a contained commit inside a release larger than the old caps is reported contained, a real gap is listed as missing, and `scan_limit=1` produces an inconclusive verdict that is not rendered as a pass — **needs live Bitbucket access, cannot be done in this session**

## 11. Merge the two tools into one (folded in after review)

The two cards / two endpoints shipped by the tasks above turned out to be one question asked twice: users could not tell "Compare" from "Merge check". This group folds them into a single comparison (see design D5/D6).

- [x] 11.1 Fold `check_missing` into `compare_releases`: one request and one response carrying the verdict, the missing commits **and** the added commits; `POST /release/diff/missing` removed (supersedes task 3.1)
- [x] 11.2 Rename the comparison inputs to one vocabulary (`source_ref`, `target_ref`, `baseline_ref`, `scan_limit`, `render_limit`) and drop `old_release_base_ref` / `new_release_base_ref` / `max_commits` / `commit_preview_limit` / `missing_scan_limit` (supersedes tasks 3.2 and 5.3)
- [x] 11.3 Drop the scoped commit previews (`old_release_commits` / `new_release_commits`, `*_commits_truncated`, `summary`) and the two provider calls they cost; both directions narrow through the same baseline (supersedes task 5.4)
- [x] 11.4 Frontend: a single "Release Diff" card — source, target, optional baseline (stored/savable, manage role), verdict banner, missing and added lists, report export; the separate merge-check card is removed
- [x] 11.5 Rebuild the HTML report from the verdict, the counts and the missing / added lists
- [x] 11.6 i18n: one vocabulary across `en`, `zh-CN`, `zh-TW`; drop the keys of the removed tool and the preview counts
- [x] 11.7 Tests: backend (verdict + added, symmetric baseline narrowing, inconclusive, no `/missing` route) and frontend (single card, verdict rendering per state, baseline flow, URL state)
