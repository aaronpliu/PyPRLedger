## 1. The comparison result

- [x] 1.1 Add `src/schemas/app_version_diff.py` with the request: repository coordinates (project key, repository slug, provider, workspace), an ordered list of release refs (at least two, de-duplicated), and the refresh flag
- [x] 1.2 Add the response models: the ordered releases with their date and whether a record was found, the package rows with one version per release and one state per adjacent pair, the per-interval comparison with its summary, and the overall verdict
- [x] 1.3 Add the tolerant version reader: numeric components plus pre-release, ordering per semver precedence (a pre-release before its release), and an explicit "cannot be ordered" result instead of an exception
- [x] 1.4 Add `src/services/app_version_diff_service.py` that resolves the application through the project registry and reads each release through `DependencyGraphService.build()`, treating a release with no record as an ordinary outcome rather than an error
- [x] 1.5 Order the releases by release datetime - the record's own timestamp first, the tag date from the provider's `list_tags_with_commits()` second, and the selection's relative position last - and never by the order the refs were supplied
- [x] 1.6 Build the matrix from the union of the direct dependencies of every release that has a record, with a stable row order and an empty cell where a release does not declare the package
- [x] 1.7 Classify every adjacent pair into unchanged / changed (upgrade, downgrade, or changed without a direction) / added / removed, and summarize the counts per interval
- [x] 1.8 Derive the verdict: incomplete when any selected release has no record, otherwise identical or changed - never "nothing changed" over missing data
- [x] 1.9 Cache the consolidated result per application and release list, reusing the existing Redis utilities, and read through the cache when the request asks to refresh
- [x] 1.10 Log and count the comparison with the existing metrics collector: application, release count, and the per-state totals

## 2. The endpoint

- [x] 2.1 Add `src/api/v1/endpoints/app_version_diff.py` exposing `POST /release/apps/diff`, authenticated, resolving the application through the project registry the way the dependency graph endpoint does
- [x] 2.2 Register the new router in `src/api/v1/api.py` with a tag of its own, and touch nothing else in that file
- [x] 2.3 Reject a request with fewer than two releases, and collapse repeated refs so the same release cannot appear twice

## 3. The App Diff page

- [x] 3.1 Add `frontend/src/api/appVersionDiff.ts` with the request and response types and the read call
- [x] 3.2 Add `frontend/src/utils/appVersionDiff.ts` that turns the response into the row model the table draws (cells in column order, one move marker per boundary, an explicit empty cell) - pure and unit-testable, with no classification of its own so the backend stays the single authority
- [x] 3.3 Add `frontend/src/views/releases/AppDiffView.vue` with the repository coordinates, following the pattern the three existing release pages use
- [x] 3.4 Load the tags and branches through the existing refs endpoint, grouped as the dependency graph page groups them
- [x] 3.5 Let the user pick two or more releases (defaulting to the two most recent), add and remove one, and never offer a manual reorder - the order comes from the dates
- [x] 3.6 Render the matrix: a row per package, a column per release, the version in each cell, and the move marker on the boundary between adjacent columns
- [x] 3.7 Highlight a downgrade as a risk signal, and render a change with no direction as exactly that - no arrow, no colour that reads as an upgrade
- [x] 3.8 Mark a release with no dependency record in its column, and mark every interval that touches it as incomplete
- [x] 3.9 Render the header: the application, the release count, the per-interval summaries, and the statement that only the application's direct dependencies are compared
- [x] 3.10 Add a refresh action that asks for the comparison again with the cache bypassed
- [x] 3.11 Keep the selection in the URL and restore it when such a URL is opened
- [x] 3.12 Cover the waits and the empty states: coordinates not chosen, fewer than two releases, and an application with no records at all
- [x] 3.13 Render the code axis of each pair: the commits the later release adds and the commits it does not contain of the earlier one, capped, with the reason shown where it could not be read
- [x] 3.14 State it when the dependencies of a pair did not move but its commits did, and mark a pair whose commits could not be read instead of showing it as a pair without commits

## 4. Navigation and copy

- [x] 4.1 Add the `/releases/apps` route in `frontend/src/router/index.ts`
- [x] 4.2 Add the App Diff entry to the Releases group in `frontend/src/layouts/DefaultLayout.vue`, leaving the existing entries and their labels untouched
- [x] 4.3 Add the new keys to `en`, `zh-CN` and `zh-TW`: the menu label, the page title, the scope statement, the interval headings, the state labels, the risk wording for a downgrade, and the empty states

## 5. Tests and verification

- [x] 5.1 Backend: the version reader - numeric ordering, pre-release precedence, and an unorderable value
- [x] 5.2 Backend: the matrix and the classification - every state produced, and an unorderable change never counted as an upgrade
- [x] 5.3 Backend: ordering by release datetime, including both fallbacks and a branch that has neither
- [x] 5.4 Backend: a release with no record - the column marked, the intervals touching it incomplete, and the other intervals still reported
- [x] 5.5 Backend: the dependency source unreachable, and a repository that resolves to the placeholder application
- [x] 5.6 Backend: the endpoint contract - fewer than two releases rejected, repeated refs collapsed, and the response shape
- [x] 5.7 Frontend: the matrix, the downgrade highlight, the change without a direction, the missing-record column, and the incomplete interval
- [x] 5.8 Frontend: selection (the two most recent by default, add and remove), the URL state, and the refresh action
- [x] 5.9 Run the backend suite with `pytest`, then `vitest` and `vue-tsc --noEmit` for the frontend
- [ ] 5.10 Confirm against a real application with at least three releases that the column order matches the release dates, that a package untouched across all of them reads as unchanged, and that the three existing release pages are unaffected
- [x] 5.11 Backend: the code axis runs for the complete pairs only, both directions are reported, a provider that cannot answer degrades that pair alone, and the axis is skipped when the request does not ask for it
- [x] 5.12 Frontend: the commit lists per pair, the "dependencies unchanged but commits changed" statement, and the pair whose commits could not be read

## 6. The code axis

- [x] 6.1 Extend the response with the code axis of a pair: the verdict of the repository comparison, what the later release adds, what it does not contain of the earlier one, the commits themselves, and whether either list was capped
- [x] 6.2 Read it once per adjacent pair whose releases both have a record, through the existing `ReleaseDiffService.compare_releases`, passing the two release refs and the request's refresh flag, and changing nothing in that service
- [x] 6.3 Degrade per pair: record why a pair's commits could not be read - an unreachable provider, a release ref the provider does not know - instead of failing the request, and never report such a pair as one with no commits
- [x] 6.4 Skip the whole code axis when the request does not ask for it, and cache it with the comparison it belongs to

## 7. The application's own version

- [x] 7.1 Read each release's own version alongside the dependencies it declares, and make it the first row of the matrix
- [x] 7.2 Classify that row exactly as a dependency row is, and count it in each pair's summary, while `dependencies_moved` reports the dependency rows alone
- [x] 7.3 Read a trailing `_<digits>` build suffix as build metadata, so `1.0.0_10000` to `1.1.0_10000` is an upgrade and a build bump within one version has no direction
- [x] 7.4 Render the application's row first and distinguish it from the dependency rows, in all three locales
- [x] 7.5 Tests, backend: the application's row and its direction, a build bump with no direction, `dependencies_moved` ignoring the application's own move, and the summary counting it
- [x] 7.6 Tests, frontend: the application's row rendered first and marked, and the rebuild statement still driven by the dependency rows alone
