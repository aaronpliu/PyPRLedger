## Why

Every release build needs one trustworthy answer: **"is anything from the release we are building on missing here?"** Today both paths that answer it enumerate commits and then match in memory:

- `compare_releases` derives `missing_commits` as `old_release_commits ∩ behind_ids`, where the old release commit set is capped by `commit_preview_limit` (200) and the ref compares are capped by `max_commits` (1000).
- `check_commits` lists the target release's commits (capped by `max_commits`) and matches the supplied ids against that in-memory lookup.

On a repository with years of history both paths silently lose data: the comparison can report **"no missing"** from truncated sets, and `check_commits` can report a genuinely included commit as **`not_found_in_release_scope`**. A check that can silently pass (or silently fail) is worse than no check at all — and the per-build merge check depends on it.

## What Changes

- Derived from a **provider-side set difference** instead of enumeration: missing = commits reachable from the source release but not from the target release (`source \ target`), which the git provider computes natively and which is normally **small** (it is the un-merged work, not the repository history).
- The source base ref becomes **optional narrowing only**. It no longer gates the verdict, so a narrow base can no longer hide un-merged commits.
- The verdict becomes **three-state** — `contained` / `missing(n)` / `inconclusive` (scan limit reached) — and MUST NOT be derived from truncated data. No more "no missing" from a capped set.
- The scan is **paginated to completeness** within a configurable scan limit, respecting each provider's paging (Bitbucket Server `isLastPage`, Bitbucket Cloud `next`, GitHub `total_commits` / `per_page` caps).
- `check_commits` (supplied commit ids) stops enumerating the release and answers **per commit** with a containment query (one provider call per commit), so it is exact regardless of release size.
- Add a **verdict-only mode** (ids, no commit payloads) so the check is cheap enough to run for every build, and fetch commit details only for the difference, for display.
- Add a **"merge check" preset** to the releases page: source release ref + saved baseline + target release ref → one verdict card with the missing commits as the actionable list. The baseline is stored per repository so the routine check is two clicks.
- Explicit non-goals: no cherry-pick / squash-merge equivalence (patch-id matching), no rework of the "added" set semantics, no change to release note generation, and no change to how the app-level release comparison consumes the commit range.

## Capabilities

### New Capabilities

- `release-missing-check`: Determining whether a target release contains a source release, using a provider-side difference scan that is complete or explicitly inconclusive, answering per-commit containment exactly, and exposing the routine per-build check as a preset with a saved baseline.

### Modified Capabilities

<!-- None: release diffing has no spec in openspec/specs/ (the app-level comparison lives in the separate change add-app-release-diff). -->

## Impact

- **Backend changed**: `src/services/release_diff_service.py` (`compare_releases` verdict path, `check_commits` rewritten, removal of the in-memory lookup/match path from verdicts), `src/schemas/release_diff.py` (missing-check payloads, three-state verdict), `src/api/v1/endpoints/release_diff.py` (new endpoint + baselines).
- **Backend added**: `contains_commit()` on `src/services/git_providers/{base,bitbucket_server,bitbucket_cloud,github_enterprise}.py`, a paginated completeness-aware difference fetch, `src/models/release_check_baseline.py`, `alembic/versions/035_create_release_check_baseline.py`.
- **Frontend changed**: `frontend/src/views/releases/ReleasesView.vue` (verdict card, merge check preset, baseline save), `frontend/src/api/releaseDiff.ts`, `frontend/src/locales/{en,zh-CN,zh-TW}.json`.
- **API surface**: additive — a new missing-check endpoint and baseline endpoints; existing compare/check request shapes stay valid, their verdict fields become trustworthy (and gain `inconclusive`).
- **Behavior**: checks that used to be silently capped now either return a definitive verdict or state that they are inconclusive; a commit contained in a huge release is no longer reported missing.
- **Cost**: one paginated scan of the difference set per check (typically a handful of commits), replacing two capped previews plus two full ref compares; the verdict-only mode fetches no commit payloads.
