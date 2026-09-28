## 1. Provider primitives

- [ ] 1.1 Add `contains_commit(project_key, repository_slug, ref, commit) -> bool` to `GitProviderBase`, documenting the per-provider containment strategy and that short SHAs are resolved by the provider
- [ ] 1.2 Implement it on `bitbucket_server` — `compare/commits?from={commit}&to={ref}`, contained when the result set is empty
- [ ] 1.3 Implement it on `bitbucket_cloud` — `commits?include={ref}&exclude={commit}`, contained when the result set is empty
- [ ] 1.4 Implement it on `github_enterprise` — `compare/{commit}...{ref}`, contained when `behind_by == 0`
- [ ] 1.5 Make the difference fetch completeness-aware: page through the provider's paging signal (Server `isLastPage` / `nextPageStart`, Cloud `next`, GitHub `total_commits` and the 250-per-page cap) until exhausted or the scan limit is reached, returning `(commits, complete)`
- [ ] 1.6 Tests per provider: empty difference, non-empty difference, contained commit in a release larger than any preview cap, cap reached → `complete = False`, short SHA resolution

## 2. Missing check service

- [ ] 2.1 Add `check_missing(request)` computing the difference in the source → target direction, with the source base ref as optional narrowing only
- [ ] 2.2 Derive the three-state verdict (`contained` / `missing` / `inconclusive`) with a complete-or-inconclusive guarantee; never return `contained` from an incomplete scan
- [ ] 2.3 Implement the payload-free default mode (ids only, no reverse-direction compare) and the enriched mode (details for the difference only, capped for rendering)
- [ ] 2.4 Rewrite `check_commits` to per-commit containment via `contains_commit`, and remove `_build_commit_lookup` / `_match_commit` from the verdict path
- [ ] 2.5 Include the mode and the scan limit in the cache key, bump the cache version segment so old capped entries are never served, and emit `inconclusive` in the `release_diff` metrics
- [ ] 2.6 Tests: contained / missing / scan limit → inconclusive / narrowing by a source base ref / a contained commit inside a >1000-commit release (regression for the false `not_found_in_release_scope`) / 200 supplied ids / shared history not reported as missing

## 3. API and schemas

- [ ] 3.1 Add `POST /api/v1/release/diff/missing` with `{source_ref, target_ref, source_base_ref?, scan_limit?, include_commits}` returning the verdict, the missing commits, the completeness flag and the limit that was hit
- [ ] 3.2 Extend `ReleaseCompareResponse` with `verdict` and the scan fields, document `missing_commits` as complete (or lower-bounded when inconclusive), keep the existing fields and their documented meaning
- [ ] 3.3 Add baseline endpoints: read, save and clear the stored baseline for a repository
- [ ] 3.4 Endpoint tests: verdict propagation, `inconclusive` fields, baseline round trip, authorization and validation errors

## 4. Baseline storage

- [ ] 4.1 Add `src/models/release_check_baseline.py` — `(git_provider, project_key, repository_slug)` unique, `baseline_ref`, `note`, `updated_by`, timestamps
- [ ] 4.2 Add the migration (`down_revision` set to the current head at implementation time — `032`, or `034` when the app-level release change is deployed first) with a working downgrade
- [ ] 4.3 Add the read/write service for baselines and register the model so tests pick it up

## 5. Frontend

- [ ] 5.1 Verdict card on the releases page: contained / missing (with the count) / inconclusive (never a success style), including the scan limit and how to raise it
- [ ] 5.2 Missing commit list with identity, provider link, and the "showing first M of N" note when the rendered list is capped
- [ ] 5.3 Merge check preset: source release tag + editable, savable baseline + target release tag, runnable without re-entering the baseline; keep the selection in the URL
- [ ] 5.4 Replace the truncation-driven messaging on the compare and check panels with the verdict-based presentation, and add the cherry-pick equivalence note to the help text
- [ ] 5.5 i18n for the new verdict, preset and help strings in `en`, `zh-CN`, `zh-TW`
- [ ] 5.6 Tests: verdict rendering per state, inconclusive never rendered as a pass, preset flow with a stored baseline, capped missing list note

## 6. Verification

- [ ] 6.1 Backend: full `pytest` suite, `ruff format --check` and `ruff check src tests`
- [ ] 6.2 Frontend: `vitest` suite, `vue-tsc --noEmit` and lint
- [ ] 6.3 Manual check on a repository with a forked release line: a contained commit inside a release larger than the old caps is reported contained, a real gap is listed as missing, and `scan_limit=1` produces an inconclusive verdict that is not rendered as a pass
