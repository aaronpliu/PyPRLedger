## Why

Release tooling today compares **one repository** at a time (`/releases` takes project + repository + two refs), but the thing that actually ships is an **application release**: one version of the app (its own tag) bundling 20+ pinned dependency versions (`1.2.0-rc.0`, `2.2602.1-demo-rc.2`, …). Release managers currently have to open 20+ repositories one by one to answer "what changed between 3.9.0 and 3.10.0", and an app that was **rebuilt under the same tag** (the tag was moved) is invisible today.

## What Changes

- Add an **app-first release comparison page** (`/releases/apps`): pick an application, pick two app releases, get a dependency matrix (added / removed / changed / downgraded) plus the code axis, and drill into any changed package's repository comparison.
- Add the **source primitives** the page needs — read an app's dependency manifest (`package.json`) at a resolved commit, and list an application's release tags together with their commit SHAs on Bitbucket Server, Bitbucket Cloud and GitHub Enterprise.
- Add **app release snapshots** (new tables): a release is identified by `(application, tag_name, commit_sha)`. The manifest is stored on first use and reused afterwards; history is never rewritten.
- Handle **moved tags** explicitly: an existing snapshot keeps its SHA, a re-resolve that sees a different SHA creates a new snapshot, marks the previous one superseded, and flags the release for an admin to confirm. Nothing is refreshed silently.
- Resolve every dependency back to **the repository and the exact revision it was published from**, using JFrog Artifactory first (its build information carries the VCS URL and revision), with tag lookup and a naming convention as fallbacks. Only locally hosted artifacts count as internal; proxied third-party packages stay external. Each conclusion records where it came from and how confident it is, with weak results queued for confirmation instead of being trusted.
- Rename the existing menu entry `Release Comparison` → `Repository Comparison` so the two entry points are not confusable, and give both pages **URL state** so a comparison (and a drill-down) can be linked and shared.
- Explicit non-goals for this change: no transitive dependencies (direct `package.json` entries only, no lockfile parsing), no application→repository navigation tree, no report/PNG/HTML export (deferred), no scheduled background sync, and no write access to Artifactory or the git providers.

## Capabilities

### New Capabilities

- `app-release-manifest`: Resolving an application's release tags to immutable commit identities, fetching its dependency manifest from the git provider, caching by content identity, persisting release snapshots with full history, and detecting/confirming moved tags.
- `package-repository-mapping`: Resolving a pinned package version to its source repository and published revision through the artifact source, keeping only locally hosted artifacts internal, recording provenance with confirmation for weak results, degrading safely when the artifact source is absent, and maintaining the mapping set in bulk.
- `app-release-diff`: Comparing two application release snapshots — dependency matrix with upgrade/downgrade classification, the code axis (commit delta), drill-down into the existing repository comparison, release selection with shareable URL state, per-application manifest configuration, and permission boundaries.

### Modified Capabilities

<!-- None: no existing spec covers release tooling (openspec/specs/ has no release capability). The menu rename is UI copy, captured as a requirement in `app-release-diff` instead of a modified capability. -->

## Impact

- **Backend providers**: `src/services/git_providers/{base,bitbucket_server,bitbucket_cloud,github_enterprise}.py` — two new primitives (`list_tags_with_commits()`, `get_file_content()`).
- **Backend new**: `src/models/app_release.py`, `src/models/package_repository.py`, `src/services/app_release_service.py` (resolve + snapshot), `src/services/app_release_diff_service.py` (pure diff), `src/services/artifactory_client.py`, `src/services/package_repository_service.py`, `src/api/v1/endpoints/app_releases.py`, `alembic/versions/033_create_app_release.py` (3 tables) and `alembic/versions/034_create_package_repository.py` (2 mapping tables).
- **Backend reused**: `ReleaseDiffService` for the code axis (its refs already accept any ref, including a commit SHA), the Redis cache utilities, the `system_settings` configuration pattern (LLM / JIRA settings) for the Artifactory connection, and the existing git provider credentials — **no new git credentials or base URLs are required**.
- **Frontend new**: `frontend/src/views/releases/AppReleasesView.vue`, `frontend/src/api/appReleases.ts`, route `/releases/apps`, plus an admin section for the artifact-source settings and the mapping review queue.
- **Frontend changed**: `frontend/src/router/index.ts` (new route + query prefill), `frontend/src/views/releases/ReleasesView.vue` (accept prefilled query state), `frontend/src/layouts/DefaultLayout.vue` (third menu entry + rename), `frontend/src/locales/{en,zh-CN,zh-TW}.json` (`menu.appReleases`, `menu.releaseComparison` → "Repository Comparison", mapping admin keys).
- **API surface**: new read-mostly endpoints under `/api/v1/release/apps/*`, with management-role endpoints for refresh, configuration and mapping administration; no changes to existing release endpoints or payloads.
- **External dependency**: JFrog Artifactory REST API (read-only). Optional at deploy time — without its settings, dependency resolution degrades to tag lookup and external labelling.
- **Operational**: new tables grow by ~(1 + N) rows per release (N = direct dependencies) plus one mapping row per distinct dependency; provider traffic is ~1 call per page view plus file reads cached permanently per commit SHA, and artifact-source queries are cached per package version.
