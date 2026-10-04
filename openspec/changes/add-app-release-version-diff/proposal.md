## Why

Release tooling compares **one repository** at a time, but what ships is an **application release**: one app tag that pins the version of every direct dependency. Answering "what moved between 1.0.0, 1.1.0 and 1.2.0" today means opening the Release Dependency Graph once per release and comparing version lists by eye. The application's own dependency record - what the Release Dependency Graph already reads from the dependency database - holds exactly that answer for every release, so the comparison can be made once, for the whole application.

## What Changes

- Add an **App Diff** page (`/releases/apps`): pick one application (project key + repository slug + provider), pick **two or more** of its releases, and read a **version matrix** - one column per release, one row per direct dependency - ordered along the release datetime timeline.
- Compare **adjacent releases** in that timeline with the vocabulary the repository comparison already uses for two refs of one repository: unchanged, changed (upgrade / downgrade / changed without a direction), added, removed - and summarize the counts per interval.
- Reuse the existing reads: the dependency database through `DependencyGraphService`, the repository's tags and branches through `POST /release/diff/refs`, and the repository-to-application resolution through the project registry. No new provider primitive, no file content read, no new configuration.
- State the scope in the UI: **direct dependencies of the application only**. The dependency-of-dependency closure is deliberately out of scope for this change.
- Be honest about missing data: a selected release the database holds no record for is marked as such and makes the whole comparison **incomplete** - it is never rendered as "nothing changed".
- Support **refresh**, which bypasses the cached reading, because a tag can be moved and the cached graphs are keyed by ref name.
- Add the **App Diff** entry to the Releases navigation. The existing three pages (`/releases`, `/releases/notes`, `/releases/dependency-graph`) keep their behaviour, their routes and their labels.
- Explicit non-goals: no transitive or closure comparison, no package-to-repository drill-down, no manifest reads through the git providers, no snapshot tables, no write-back to the dependency database, no change to the existing release pages.

## Capabilities

### New Capabilities

- `app-version-diff`: Comparing two or more releases of one application at direct-dependency level - release selection and ordering along the release datetime timeline, the version matrix, the adjacent-release classification with upgrade/downgrade direction, honesty about a release with no dependency record, refresh, shareable selection, and the navigation entry that distinguishes this page from the repository comparison.

### Modified Capabilities

<!-- None: no existing spec covers release tooling, and the three existing release pages keep their behaviour. -->

## Impact

- **Backend new**: `src/services/app_version_diff_service.py`, `src/schemas/app_version_diff.py`, `src/api/v1/endpoints/app_version_diff.py` (`POST /api/v1/release/apps/diff`), plus one registration line in `src/api/v1/api.py`.
- **Backend reused, not modified**: `DependencyGraphService` (the dependency database read, its per-ref cache and its node cap), `ProjectRegistryService.get_app_name` (repository to application), `ReleaseDiffService.list_refs` (the tag and branch list), the git provider `list_tags_with_commits` primitive (release dates), and the Redis cache and metrics utilities.
- **Frontend new**: `frontend/src/views/releases/AppDiffView.vue`, `frontend/src/api/appVersionDiff.ts`, `frontend/src/utils/appVersionDiff.ts` (the matrix and the classification, pure and testable).
- **Frontend changed, additively**: `frontend/src/router/index.ts` (one route), `frontend/src/layouts/DefaultLayout.vue` (one menu entry), `frontend/src/locales/{en,zh-CN,zh-TW}.json` (new keys only, no existing value changed).
- **API surface**: one new endpoint under `/api/v1/release/apps/`. No existing endpoint, payload, table or migration is touched, and no new environment variable is introduced.
- **Operational**: one page view costs one dependency database read per selected release (each cached per ref), one ref listing and one tag-with-commits listing. No commit scanning, so the cost does not grow with repository history.
