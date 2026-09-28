## 1. Provider primitives

- [ ] 1.1 Add `list_tags_with_commits(project_key, repository_slug)` to `GitProviderBase` returning `[{name, sha, commit_date}]`, documented as commit-resolving (annotated tags peeled)
- [ ] 1.2 Implement it on `bitbucket_server` (`/tags?orderBy=MODIFICATION` → `latestCommit`)
- [ ] 1.3 Implement it on `bitbucket_cloud` (`/refs/tags` → `target.hash`, paginated)
- [ ] 1.4 Implement it on `github_enterprise` (`/repos/{o}/{r}/tags` → `commit.sha`; never `/git/refs/tags` without dereferencing)
- [ ] 1.5 Add `get_file_content(project_key, repository_slug, path, ref)` to `GitProviderBase`, returning `None` when the file does not exist (404 / 204 are normal outcomes, not errors)
- [ ] 1.6 Implement `get_file_content` per provider: Server `/raw/{path}?at={ref}`, Cloud `/src/{ref}/{path}`, GitHub `/contents/{path}?ref={ref}` with the raw media type
- [ ] 1.7 Tests: tag listing returns commit SHAs (annotated tag case included), missing file returns `None`, path encoding for nested paths

## 2. Data model and migration

- [ ] 2.1 Add `src/models/app_release.py` — `Application` (name unique, manifest path, recorded dependency scopes)
- [ ] 2.2 Add `AppRelease` — `(application_id, tag_name, commit_sha)` unique, `commit_sha_short`, `commit_date`, `build_number`, `is_current`, `superseded_by_id`, `tag_moved_at`, `revision`, `manifest_content_hash`, `package_count`, `fetched_at`, `raw_manifest`
- [ ] 2.3 Add `AppReleasePackage` — `(release_id, package_key)` unique, `package_name`, `version`, `v_major`/`v_minor`/`v_patch`, `prerelease`, `is_prerelease`, `dep_scope`, `is_external`
- [ ] 2.4 Follow house conventions (`DateTime(timezone=True)` + `get_current_time`, `uk_*`/`idx_*` index names, index on `(package_key, v_major, v_minor, v_patch)`)
- [ ] 2.5 Add `alembic/versions/033_create_app_release.py` (`down_revision = "032"`) creating the three tables with a working downgrade
- [ ] 2.6 Register the models so `Base.metadata.create_all` in tests picks them up

## 3. Manifest acquisition and snapshot service

- [ ] 3.1 Add a tolerant version parser `parse_package_version(value)` returning `(major, minor, patch, prerelease, is_prerelease)` and empty components for unparseable values (accepts an optional leading `v`; pre-releases such as `2.2602.1-demo-rc.2`, `1.12.0-rc.1`)
- [ ] 3.2 Add `normalize_package_key(name)` (lower-case, trimmed, scope preserved) used by uniqueness, lookups and comparison
- [ ] 3.3 Add a manifest parser turning `package.json` text into `(package_name, version, dep_scope)` rows, honouring the application's configured scopes, ignoring ranges/overrides, and skipping malformed entries
- [ ] 3.4 Add `AppReleaseService.list_releases(app)` — resolve tags via the provider, annotate each tag with its stored snapshot state (current / superseded / moved / unsnapshotted)
- [ ] 3.5 Add `AppReleaseService.get_or_create_snapshot(app, tag_name)` — reuse an existing snapshot when the resolved commit matches, otherwise fetch the manifest, compute the content hash and insert an append-only snapshot with its dependency rows
- [ ] 3.6 Implement the moved-tag path: record `tag_moved_at`, never mutate the stored snapshot, expose `previous_sha` / `current_sha` for the warning
- [ ] 3.7 Add `AppReleaseService.confirm_moved_tag(app, tag_name)` — create the replacement snapshot, flip `is_current`, bump `revision`
- [ ] 3.8 Cache file content under `(provider, project, repo, path, sha)` with no expiry, and comparisons under `(sha_new, sha_old)`, reusing the existing Redis cache utilities; a cache write failure must never fail the request
- [ ] 3.9 Degrade gracefully when the provider is unreachable: serve stored snapshots and report `refresh_failed` in the response
- [ ] 3.10 Add `application` configuration read/write (manifest path, recorded scopes)

## 4. Comparison engine

- [ ] 4.1 Add `diff_snapshots(old_snapshot, new_snapshot) -> PackageDiff[]` as a pure function over the two dependency sets (added / removed / changed / unchanged, with both versions and keys)
- [ ] 4.2 Add direction classification (`upgrade` / `downgrade` / `unknown`) using the numeric components and semver pre-release precedence
- [ ] 4.3 Add the summary counters (changed, added, removed, downgraded)
- [ ] 4.4 Add the case where the dependency axis is empty but the snapshot commits differ, so the response can state it explicitly
- [ ] 4.5 Tests: the four states, downgrade detection, pre-release ordering, unparseable version neutrality, casing drift producing one changed entry, empty dependency set

## 5. API surface

- [ ] 5.1 `GET /api/v1/release/apps` — applications available for comparison (registry apps that have a manifest configuration)
- [ ] 5.2 `GET /api/v1/release/apps/{app}/releases` — tags with snapshot state (current / superseded / moved), including a `refresh_failed` signal
- [ ] 5.3 `POST /api/v1/release/apps/compare` — payload `{app, from, to, include_unchanged}` returning the dependency matrix, the summary, the resolution outcome per package and the code axis (commits between the two snapshot commits)
- [ ] 5.4 Code axis implemented by delegating to `ReleaseDiffService` with the two commit SHAs as refs (no new diff engine)
- [ ] 5.5 `POST /api/v1/release/apps/{app}/refresh` (management role) — re-resolve, and create/replace snapshots on explicit confirmation
- [ ] 5.6 `GET` / `PUT /api/v1/release/apps/{app}/config` (management role for write) — manifest path and recorded scopes
- [ ] 5.7 Schemas in `src/schemas/app_release.py`; authorization on the management routes using the existing RBAC helpers; document the endpoints in the module docstring like `release_diff.py` does
- [ ] 5.8 Endpoint tests: listing, comparison payload, `403` on unprivileged refresh, moved-tag warning payload, empty-manifest empty state

## 6. Frontend: application release comparison page

- [ ] 6.1 `frontend/src/api/appReleases.ts` — typed client for the endpoints above
- [ ] 6.2 `frontend/src/views/releases/AppReleasesView.vue` — application selector (reusing `projectRegistryApi.listApps()`), two release pickers (grouped by tag, superseded snapshots selectable) and a refresh action gated by the management role
- [ ] 6.3 Dependency matrix: state icons/labels, upgrade/downgrade highlighting, downgrade counted in the summary, external dependencies labelled without a link, unchanged rows hidden by default with a toggle
- [ ] 6.4 Code axis pane: commit list of the compared snapshots with counts, and the explicit "no dependency change but commits changed" message
- [ ] 6.5 Moved-tag warning banner showing old → new commit with the diff summary and a confirmation control for the management role
- [ ] 6.6 Drill-down link built from the resolved repository coordinates and the two resolved revisions (labelled as not drillable when external, unconfirmed or missing a revision), plus a breadcrumb back to the app comparison
- [ ] 6.7 URL state (`app`, `from`, `to`, `view`) read on mount and kept in sync on change
- [ ] 6.8 i18n keys for the page in `en`, `zh-CN`, `zh-TW`

## 7. Frontend: navigation and existing page prefill

- [ ] 7.1 Add route `/releases/apps` (`name: AppReleases`) and keep `/releases` untouched apart from prefill
- [ ] 7.2 Add the menu entry and rename `menu.releaseComparison` to "Repository Comparison" / 本地化文案 in all three locales, keeping the i18n key
- [ ] 7.3 Read `project_key`, `repository_slug`, `git_provider`, `old_release_ref`, `new_release_ref` from the query in `ReleasesView.vue` and prefill the existing forms without changing their behavior
- [ ] 7.4 Ensure the existing `/release-diff` redirect and all existing route names keep working

## 8. Package to repository resolution

- [ ] 8.1 Add `src/services/artifactory_client.py` — query artifacts by package name and version, read artifact properties and build information (`vcsUrl`, `vcsRevision`, build name/number); read-only token; timeouts and error handling consistent with the existing HTTP clients
- [ ] 8.2 Add `ARTIFACTORY_BASE_URL`, `ARTIFACTORY_TOKEN`, `ARTIFACTORY_LOCAL_REPOS` to `src/core/config.py` and `.env.example`, surfaced through the existing `system_settings` pattern and the admin settings endpoint
- [ ] 8.3 Add `src/models/package_repository.py` — `PackageRepository` (`package_key` unique, `git_provider`, `project_key`, `repository_slug`, `tag_template`, `source`, `confidence`, `artifactory_repo`, `note`, timestamps)
- [ ] 8.4 Add `PackageVersionRef` — `(package_key, version)` unique, `tag_name`, `commit_sha`, `resolved_source`, `resolved_at`
- [ ] 8.5 Add `alembic/versions/034_create_package_repository.py` (`down_revision = "033"`) with a working downgrade
- [ ] 8.6 Parse a VCS URL into `(git_provider, project_key, repository_slug)` for the three supported providers, reporting nothing for unrecognised hosts
- [ ] 8.7 Add the resolution service implementing the order manual → artifact source (locally hosted repositories only count as internal) → tag lookup (exact, `v`-stripped, repository-name prefixed) → naming convention → external, recording `source`, `confidence` and `artifactory_repo`
- [ ] 8.8 Cache resolutions per `(package_key, version)` in Redis, and degrade to cache / tag lookup / unresolved when the artifact source is unconfigured or unreachable
- [ ] 8.9 Tests: locally hosted vs remote/virtual hit, build information present/absent, legacy `1.12.0-rc.1` tag fallback, `v`-prefixed and repository-prefixed tag matching, no candidate yielding external, manual rows never overwritten, cache reuse and outage degradation

## 9. Mapping administration

- [ ] 9.1 `GET /api/v1/release/apps/packages` (review list of unresolved and low-confidence entries, paginated) and `POST /api/v1/release/apps/packages/confirm` (bulk confirmation, management role)
- [ ] 9.2 `POST` / `PUT /api/v1/release/apps/packages/mapping` for manual repository coordinates and tag-template overrides (management role); a manual edit sets `source = manual` and is excluded from automatic resolution
- [ ] 9.3 CSV export and import of the mapping set (duplicates resolved in favour of manually maintained rows)
- [ ] 9.4 Admin panel section following the `ProjectRegistryManagementView` pattern: review queue with source/confidence columns, bulk confirm, manual coordinate entry, CSV import/export, localized in `en` / `zh-CN` / `zh-TW`
- [ ] 9.5 Tests: authorization on the management routes, bulk confirmation flipping confidence, manual override protection, artifact source settings round trip, CSV round trip

## 10. Verification

- [ ] 10.1 Backend: full `pytest` suite, `ruff format --check` and `ruff check src tests`
- [ ] 10.2 Frontend: `vitest` suite (new view tests: matrix states, downgrade highlight, moved-tag banner, URL restore, prefill; mapping queue and settings tests), `vue-tsc --noEmit` and lint
- [ ] 10.3 Manual check against a real repository on both Bitbucket Server and Bitbucket Cloud: tag listing, manifest read, comparison, dependency resolution with the artifact source both configured and absent, and the drill-down into the repository page
