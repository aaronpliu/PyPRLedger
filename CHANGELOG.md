# Changelog

All notable changes to the PRLedger project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Documentation
- `docs/DEPENDENCY_API_CONTRACT.md` writes down the interface the third-party dependency database must satisfy for the Release Dependency Graph and the App Diff: the request the two pages make (the repository resolved to an application through the project registry, then one call per ref), the response shape field by field with what each field is read as, how a two-level source - the module maps keyed by module name at the top level of the same object - folds into that shape at the endpoint rather than on this side, the status code that means "no record" rather than "broken", and a checklist for verifying an implementation against the canned data before the real database is reachable

---

## [1.26.3] - 2026-10-07

**Backend Version**: 1.26.3
**Frontend Version**: 1.21.3

### Changed
- The task assignment summary counts pull requests rather than review rows. Two of its cards could not disagree: reviews are created when a pull request is opened and nothing in the pipeline ever moves that status on, so "Active Reviews" - a count of rows marked open - reproduced the total exactly, under a badge claiming to be live. A review is also stored one row per source file, so a pull request reviewed file by file was counted more than once. Both cards now count distinct pull requests, "Active" meaning one that still has work outstanding - a reviewer assignment not completed, or nobody assigned yet, since nothing about such a request is done - and the badge has given way to the sentence defining it. Average assignments is per pull request with a reviewer counted once however many files they appear on, and the scoring rate is the share of pull requests that carry any score. What carries this is the reviewer assignment status, being the field that does move; pull request status is not consulted at all
- The trend charts show a window rather than all of history: the last 180 days, 26 weeks or 6 months, whichever period is selected. A window puts a period without reviews on the axis as a zero instead of leaving it out, so a quiet stretch reads as one rather than as a straight line drawn across it, and the axis has a length that still says something about time. The size lives in `frontend/src/config/analytics.ts` and can be overridden per call, so widening one is a number rather than a rewrite
- Two faults in the weekly axis went with it. The keys paired the calendar year with the ISO week number, which put 2025-12-29 and 2025-01-01 in the same bucket - a week that straddles new year belongs to its week-year, not to the year its days fall in; and being unpadded, `2026-W9` sorted after `2026-W10` as a string, so each January drew its weeks out of order. They are now the ISO week-year and a padded week number, and the buckets are built from the calendar in order rather than sorted as text, which is what keeps the two charts sharing the period selector on one axis
- The Link action in the Code Reviews table is an icon. It was a bordered button spelling "Link", which took a word's worth of width to say what a chain glyph says, and the column narrowed to suit. It is still a button element, so it still takes focus and answers the keyboard, and it carries an accessible name and a tooltip to replace the word it no longer shows
- The copyright notice widens by itself. It read "© 2026 Mobile, All rights reserved", held in a module constant and so fixed at build time - a deployment that outlived its year would go on claiming the old one - and it now reads `© 2026-2027` from the first of January, computed where it is rendered. The first year it covers is a single constant, and the range cannot run backwards whatever the clock says

### Fixed
- Creating a release tag prints its verification in the order it is meant to be read. The tag summary was written straight to stdout by a child process while the script still held buffered output, so it appeared above the lines introducing it; it is captured and indented along with the rest, and a failure to read the tag back is now reported instead of passing as silence

---

## [1.26.2] - 2026-10-06

**Backend Version**: 1.26.2
**Frontend Version**: 1.21.2

### Changed
- Banners take turns instead of stacking. Any number can be within their window at once, and the bar grew a row per banner, pushing whatever is below it down by 28px each time; it now keeps one row and moves through them every six seconds, with a dot per banner so the rest can be read without waiting. It holds while the pointer is over the bar or focus is inside it, so nothing changes under a reader part way through, pauses in a background tab, and gives a full turn to a banner picked by hand. One banner means no dots and no rotation. Each keeps its own level colour, and the one dismissed is the one on show
- Adding banners no longer grows the settings page. Every banner was an open form of six fields, so the page grew with each one and adding another meant opening another form in place; it is now a list of what matters about each banner, with the editing in a dialog and a switch on each row to take a banner in or out of service. Actions save as they are taken rather than collecting behind a single Save, and a write that fails leaves the switch showing what is stored instead of a state that was never saved, because the row follows the value the server accepted
- Banner settings now hold a list, and the single banner they used to hold is folded into that list on the first read, keeping its identity, so a banner scheduled before this is neither lost nor shown twice. Values that could not be rendered are refused at the boundary rather than stored
- The language switcher shows the writing system - `A` and `文` - rather than a flag. A flag names a country rather than a language, which is how Simplified and Traditional Chinese both ended up under the same one; the control now shows every script on offer at once in a fixed order, with the language in effect in full colour, and it is one component shared by the header and the three signed-out pages rather than a copy of the markup in each
- The release notes list shows a whole page. It was clamped to roughly seven entries with the rest scrolling inside it, which contradicted the page size the pagination beside it offers and left two ways to move through one list

### Fixed
- Creating a release tag prints the tags it was asked to verify. The check ran `git tag -l | tail -5` through a shell with the command given as a list, so only the first element was the command and the rest became arguments to the shell, and the listing never ran - the verification reported git's usage text instead of the tag list, and the tag summary after it was mangled the same way

---

## [1.26.1] - 2026-10-04

**Backend Version**: 1.26.1
**Frontend Version**: 1.21.1

### Added
- A login session now describes its device instead of guessing at it from the user agent, which no longer answers the question it appears to. Chromium freezes the browser build (`Chrome/140.0.0.0`), replaces the Android device model with the letter `K`, and reports Windows 11 as Windows 10, while Safari pins macOS at 10.15.7 and reports an iPad as a Macintosh. Each browser now reports what it can about itself - User-Agent Client Hints where they exist, the user agent string where they do not - alongside its requests, and the server stores that record on the session. The session list reads the record first and falls back to the user agent field by field, and marks a row as approximate when client hints were unavailable, so a value read from a user agent is not mistaken for a measured one. Client hints recover the real platform version, the full browser build and the device model, and an iPad - indistinguishable from a Macintosh in the user agent - is recognised by its touch points. Sessions created before this are upgraded on their next request. The record is supplied by the client and is therefore display metadata only: it is bounded in length, ignored when malformed, never allowed to cost anyone a login, and never used to authorise anything
- The accent colour of the interface is now the user's to choose, from the switcher in the header or the Appearance tab added to the profile page. Element Plus compiles its palette - the primary colour *and* the shades derived from it - into the stylesheet, so overriding that one variable would have recoloured buttons while leaving every hover, disabled, striped and selected state on the default blue; the whole ramp is therefore regenerated at runtime, using the same arithmetic Element Plus compiles from SCSS, which blends towards white on light surfaces and towards the dark surface on dark ones, with `dark-2` moving lighter in dark mode. Because the surface differs by mode, the ramp is rebuilt whenever the mode changes, and the stored choice is in place before the first paint. Eight presets and a colour picker are offered, the picker warns when a colour is too light for the white text drawn on it, and choosing the default again removes the override rather than rewriting it. The accent is stored per browser

### Changed
- Colours that were hardcoded across the interface now follow the accent: the palette's blue wherever it was a piece of the interface, the chart defaults, the reviewer avatars, the dashboard bars, the application node of the dependency graph, and the PDF and HTML exports, which bake the accent in as they are generated because a static document cannot follow a change made afterwards. Deliberately *not* migrated are the colours that encode meaning rather than brand - issue severity (`low`/`medium`/`high`/`critical`), score bands (`excellent`/`good`/`acceptable`) and the per-type colours of search results. Following the accent would let a red accent render a low-severity issue identically to a critical one, or collapse two entity types onto a single colour. Chart colours are read reactively, so a chart follows a change to the accent instead of freezing the value it was built with

### Fixed
- Leaving the Release Comparison page within the debounce window of a repository change left a timer running, which then fired a provider call for a component that no longer existed and wrote to state nothing was rendering any more. The pending ref-suggestion debounce is now cleared on unmount, beside the handoff timer that already was
- The test covering the Refresh action's cache bypass was passing for the wrong reason: it asserted that the automatic ref load had already happened, which could only be true if a timer left pending by an earlier test happened to fire in time, and it failed deterministically when run on its own. It now waits for the request it asserts on; the debounce behind that request is a real timer, so the wait is explicit rather than assumed

---

## [1.26.0] - 2026-10-04

**Backend Version**: 1.26.0
**Frontend Version**: 1.21.0

### Added
- The **App Diff** page (`/releases/apps`): pick an application and two or more of its releases, and read a version matrix - one column per release in the order their datetimes put them, one row per compared entry. The application's own version is the first row, beside the dependencies it declares, so a release that moved its own version while every dependency stayed put reads as the change it is instead of as a comparison in which nothing happened. Every pair of adjacent releases is compared with the vocabulary the repository comparison already uses - unchanged, changed with a direction, added, removed - with pre-release precedence honoured (`1.2.0-rc.0 < 1.2.0`), a trailing build suffix read as build metadata (`1.0.0_10000` to `1.1.0_10000` is an upgrade; a build bump within one version is a change with no direction), and a version that cannot be ordered left as changed without a direction - never as an upgrade. The pair's summary also carries whether any *dependency* moved, so the rebuild reading below stays about the dependencies even when the application moved its own version
- The **code axis** beside the dependency axis: for every pair, the commits between the two release refs, read through the existing repository comparison rather than a new one. What the later release adds and what it does not contain of the earlier one are reported separately, with the counts exact and the rendered lists capped. This is what keeps a rebuilt release visible: a tag moved to a new commit while the versions it pins stayed identical yields no dependency change at all, and the page states that commits moved while the dependencies did not rather than leaving the empty axis to speak for itself
- `POST /api/v1/release/apps/diff`, which consolidates those reads: the repository is resolved to an application through the project registry - the dependency source holds what an *application* shipped - every release is read from the same dependency source the Release Dependency Graph draws from, and the whole answer is cached against the refs it was computed for. A `refresh` flag reads past that cache, because a tag can be moved and a cached reading is keyed by ref name
- Degradation that is per part rather than per page: a release the dependency source holds no record for is marked as such and makes the pairs that touch it **incomplete** - never "no changes" - while the pairs that can be compared are still reported; and a pair whose commits cannot be read (an unreachable provider, or a release ref the git provider does not know, which the dependency source's key for a release need not be) carries the reason instead of an empty commit list. A comparison with no records at all shows its empty state rather than an empty matrix. Reading is open to any authenticated user and nothing on the page writes anywhere
- The App Diff entry in the Releases menu, with the repository comparison, release notes and dependency graph entries left as they were, and the selection carried in the URL so a comparison can be linked and reopened

### Removed
- The `add-app-release-diff` proposal, replaced by `add-app-release-version-diff`. Its premise was that the dependency manifest lives in the application's repository and has to be read from the git provider through a new file-content primitive, a snapshot table per release, and a package-to-repository mapping maintained beside it. The dependency source answers for a release instead, so none of that machinery was needed for this comparison

---

## [1.25.0] - 2026-10-04

**Backend Version**: 1.25.0
**Frontend Version**: 1.20.0

### Added
- The Release Dependency Graph page (`/releases/dependency-graph`): it reads what one repository ref shipped and draws it, so the shape of a release line - and the cycles inside it - can be seen at a glance instead of reconstructed by hand. The repository is picked with the same coordinates as the Release Comparison and the Release Notes pages (project key, repository slug, git provider, and the Cloud workspace when the provider needs one), the ref picker groups the repository's tags and branches and takes any ref that can be typed, and both come from the endpoints those pages already call. A node is drawn by its category - the application, the packages of the workspace, and the packages a dependency file names but does not describe - the depth control and the transitive toggle narrow the canvas when a closure is too wide to read, and picking a node dims everything unrelated to it. The ref the graph was read at, and whether it is a tag or a branch, stay in the header while it is on screen
- Consolidate the dependency database into that graph: `POST /api/v1/release/dependency-graph/read` resolves the repository to an application through the project registry - the database holds what an *application* shipped, and the registry is what maps a repository to one - then asks it once and returns the merged answer as a dependency file. `DependencyApiClient` asks one question of one endpoint, and the answer already holds both what the application declared for its modules (an exact version each) and what every package the database knows declared for its own dependencies, so nothing on this side walks a graph: building the closure is the database's business, and a client that walked it would pay a call per level and stall on the first repository big enough to matter. An answer is cached in Redis under `CACHE_TTL_DEPENDENCY_GRAPH` (an hour by default, since a ref's graph only moves when the database is rebuilt for that ref), and a payload beyond 500 nodes is truncated rather than turned into an unreadable canvas. A ref the database holds no record for is a 404 naming the application and the ref, a database that cannot be reached is a 502, and while `DEPENDENCY_API_MOCK` is true (the default) the answer comes from canned data so the page works before the database is reachable - `scripts/mock_dependency_api.py` serves the same data over HTTP for an end-to-end run
- Resolve the git provider of a repository from the registry: a request no longer has to carry the provider itself for a repository to be read correctly, and a Cloud repository is not reached as Server because a payload happened to leave the field out. The registry entry for `(project_key, repository_slug)` decides, the payload stays the fallback for repositories that are not registered, and Server stays the last resort - the precedence the configuration already documented, now applied by the code on all five endpoints that talk to a provider (three of the Release Comparison, two of the Release Notes). The provider lists of those two pages come from one `GIT_PROVIDER_OPTIONS` constant instead of three hand-written options each, so the pages cannot drift apart, and Bitbucket Cloud carries a tag of its own rather than reading like a failure

### Changed
- One Bitbucket prefix per platform: `BITBUCKET_USER`, `BITBUCKET_PASSWORD` and `BITBUCKET_TOKEN` are now `BITBUCKET_SERVER_USER`, `BITBUCKET_SERVER_PASSWORD` and `BITBUCKET_SERVER_TOKEN`. The old names named neither platform while the Cloud fields fell back to them, so a Cloud-only deployment read "Bitbucket Server" in its own configuration and a token meant for Server could be sent to Cloud. The Cloud fields keep their fallback and now say which field they fall back to. `BITBUCKET_CLOUD` and `BITBUCKET_DEFAULT_WORKSPACE` are removed rather than renamed, because neither had a reader: the provider is decided per repository, which left a global switch saying only what the request already said, and it did not route traffic even when set - worse than not existing - while the default workspace was declared and never read. **Every environment updates its `.env` before it takes this release**: the old names are not read, so a deployment that keeps them finds no credentials and the provider answers 401

### Fixed
- Visiting the Release Dependency Graph took the whole application down: the handler that keeps the edge labels in step with the force layout read `chart.getModel()`, an ECharts internal the library documents as not meant for callers and that is absent on the first frames of a render. The handler runs on every frame of the layout animation, so the exception was thrown out of the render pipeline again and again, the canvas never finished drawing, and no other page could be opened afterwards - the menu answered and the routes did not. The model is now read only when it is there: labels are positioned exactly as before, and a frame that arrives before the graph is built does nothing instead of throwing

---

## [1.24.1] - 2026-10-01

**Backend Version**: 1.24.1
**Frontend Version**: 1.19.1

### Added
- Loading progress, global and per area: every request in flight raises a thin top progress bar - the axios client opens and closes one slot per request, and background traffic such as heartbeats and notification polling stays off it - the bar's fill eases open and closed rather than jumping - and a shared `ContentLoader` (a skeleton for list areas, a small spinner for inline waits, and a label naming what is asked) marks the areas that wait on the git provider: the tags and branches of the Release Diff page, and the tags, the releases and the tag commits of the Release Notes page. Both are suppressed for readers who asked for reduced motion
- Fold the repository coordinates of the Releases and the Release Notes pages away: the header of each page carries a toggle (open on arrival, with `aria-expanded` kept in step) and the coordinates are hidden rather than unmounted, so the repository that was picked stays picked
- Search the tag list of the Release Notes page by name: the search narrows the list before it is paged, says so when nothing matches (instead of looking like an empty repository), and a jump from a release to its tag clears a search that would have hidden it

### Changed
- Switching repository clears the comparison: the source, target and baseline fields are reset, and the verdict of the previous repository is dropped rather than left on screen, instead of carrying a stale ref into the repository that was just picked. A link that reopens a check still restores the selection it carries
- The handoff to the commit check is a strip, not a button: it leads with the number of missing SHAs and names where they land ("Deliver to card 2 - Check Commits"), and an arrow follows the direction of the cards - beside on the wide layout, down once they stack. Confirming it flies a token carrying the count into the check card's input and rings the card on arrival, so the delivery is confirmed where it lands instead of only in a toast. The flight is skipped when the destination is off screen, under `prefers-reduced-motion`, or without the animation API: the handover of the SHAs itself never depends on it
- The shared "Export Both (HTML)" and "Screenshot Both" actions moved into the header of the Releases card, vertically centred beside the fold toggle, instead of a toolbar of their own between the card and the two tools: they act on the results below, so they stay reachable with the coordinates folded away
- The baseline field of a comparison takes the full width of its row with a one-line help text, instead of half a row whose hint wrapped into a two-line block

### Removed
- The per-repository baseline store: the `release_check_baseline` table, its `GET` / `PUT` / `DELETE /release/diff/baseline` endpoints, the `release_diff` RBAC resource that guarded writes to it, the `use_stored_baseline` request flag and the `baseline_stored` response field. A baseline belongs to a release *line*, and one repository holds several - `feature/2026Oct` releases 2.2610.x while `feature/2026Dec` releases 2.2612.x - each with a fork point of its own, so a single stored baseline was wrong for every line but one. Applying it to a comparison that never asked for it was worse: the Baseline field read as "no baseline" while the comparison was silently narrowed. The baseline is now what the field says it is, an optional part of one comparison, carried in the request (and in the page URL) instead of in a table. The migrations are withdrawn rather than superseded: `033` was applied in the test environment only, which is rolled back to `032`, so no environment keeps the table and no migration is needed for the withdrawal. An environment that did apply `033` is rolled back to `032` **before** it takes this release, since `downgrade` needs the file it undoes; the sequence is in `docs/DEPLOYMENT_GUIDE.md`

### Fixed
- A first load of the tags tab looked like an empty repository: "No tags" was shown while the provider was still being asked. It now shows the loader instead, and so does the app's first paint, which sat on a blank page until the auth handshake finished - a boot indicator in `index.html` stands in until the app mounts
- Define the translation keys the source asks for but the locale files never carried, which rendered as the key itself - `releaseDiff.truncated_warning` and `releaseDiff.commit_set_bounded_title` in the exported release comparison report, `common.updating` on the forced password change button, `common.close` on the reviews banner, `common.enable_all` / `common.disable_all` on the notification preferences, and the whole `confirm` section (`confirm.delete_avatar`) on the avatar dialog. A test now checks that every `t('...')` literal of the source is defined and that the three locales hold the same keys, so a missing key fails the build instead of reaching a report nobody can correct afterwards; it also found `admin.delegations`, a key only the Chinese locales carried and nothing asked for

---

## [1.24.0] - 2026-09-29

**Backend Version**: 1.24.0
**Frontend Version**: 1.19.0

### Added
- Export release notes as one markdown document: `POST /release/notes/export` builds it from the stored releases and answers with the document, a suggested filename, how many releases it holds and an explicit report of anything it had to skip or cut. A selection is either explicit ids (what the page has ticked) or the whole filtered set, so exporting every published version of a repository no longer means paging the list in the browser first; the document has one shape and one author - the server writes the title, a summary line and one section per release (its heading, plus a draft / pre-release marker when one applies) with the stored body verbatim - so the page, an API consumer and CI produce byte-identical files. Bodies are copied as written: JIRA keys and author mentions are not rewritten, because linking them is a display concern the screen already handles. One export holds at most 200 releases, and reaching that bound is reported instead of quietly producing a partial document. The page gains a checkbox per release, "select all (filtered)" and "Export selected (N)" in the header, and "Export markdown" for the release that is open.
- Read a page of releases as a list instead of one release at a time: the reading column renders every release of the current page in full - title and tag, the latest / pre-release / draft badges, author and date, the released range and the notes - and each entry carries its own actions (edit, publish, push and delete for the managing roles; export and copy for any reader; the provider link when the release has one), so a release can be acted on without being selected first. The pagination now drives both columns and is reachable from the bottom of the list as well as from the navigator, and clicking a navigator entry scrolls the reading column to that release and marks it instead of replacing the column and hiding the other releases of the page: reviewing a quarter of a release train is one page instead of ten clicks.

### Changed
- Link the version title of a release to the tag it was cut from: the title of an entry is an anchor that opens the tags tab on that tag and loads the commits it released - the mirror of the note icon that walks from a tag to its release. The tag navigator is paginated in the browser, so the page holding the tag is opened before the item is scrolled to, and the tag name travels on the element itself rather than in a selector built out of it. The title keeps the weight of the entry it names and reads as a link only on hover and on focus.

### Documentation
- Two OpenSpec changes describe the work above: `add-release-note-export` (the export contract, the document shape and its bounds) and `list-release-notes-per-page` (reading a page of releases as a list, with the navigator as a jump index).

---

## [1.23.2] - 2026-09-29

**Backend Version**: 1.23.2
**Frontend Version**: 1.18.2

### Added
- Report why an AI summary did not happen instead of falling back silently: a preview that was asked for one answers with `summary_notice`, and the notes form says under the switch that the sections came from the commit subjects

### Fixed
- Call the configured LLM when it has no API key: a model served on localhost takes no credential, and demanding one kept the request from being made at all - the summary was skipped as "not configured" while the provider logged nothing; the `Authorization` header is now sent only when a key is set (an empty `Bearer ` is something providers refuse), and a pass that cannot be made names the piece of configuration that is missing
- Report why an AI summary failed instead of answering with a bare "did not come back": the completion client no longer throws the provider's response away (the status and body are what name the problem - an unknown model, a bad key, a prompt the model will not take - and the API key is taken out of them before they are logged or returned), the reason travels as `summary_notice` (`not_configured` | `provider_error` | `unreadable_answer` | `failed`) with the provider's own message in `summary_error`, and the notes form shows both; the request also carries only the messages, the model and `stream`, since a parameter a given model refuses (`temperature`, `max_tokens`) turns a question it can answer into a 400
- Keep the AI summary from failing on a release of any size: the model is asked only about the commits whose subject does not say what the change is - the rest of the scope stays in the prompt as the context of the summary - so it answers a handful of entries instead of one per commit, and the completion no longer puts a token limit of its own on the answer (800 was room for about 35 entries, so anything larger came back cut off mid-JSON and was reported as a failed call); an answer that does come back cut off is read pair by pair rather than dropped for a syntax error
- Leave merge commits out of the generated release notes: an integration is not a change of its own - what the release added is listed through the commits the merge brought in, in the same scope - so "Merge branch" and "Merge pull request" subjects no longer fill the "Other Changes" section; they are left out of the AI prompt for the same reason, and a scope that holds nothing else renders as the empty scope it is

---

## [1.23.1] - 2026-09-29

**Backend Version**: 1.23.1
**Frontend Version**: 1.18.1

### Added
- Preview the release notes while writing them: the editor toolbar toggles the rendered note (`preview`), the note alone (`preview-only`) and a table of contents, rendered with the same theme as a published note
- Group release notes into Keep a Changelog sections from the wording of a commit subject: a ticket key, a pull request number or a bracketed tag in front of it no longer hides the wording, and subjects that are not conventional commits (or not in English) are grouped instead of landing in "Other Changes" as one flat list
- Summarize a release with the configured LLM: an opt-in "AI summary" on the notes form adds a summary paragraph and a section per commit, answered through the existing LLM proxy configuration (System Settings -> LLM) and falling back to the deterministic notes when no LLM is enabled or the call fails
- Write the generated notes in the language of the caller (section titles and the summary; English, 简体中文, 繁體中文)

### Fixed
- Reverse the Bitbucket Server comparison direction: `/compare/commits` streams the commits reachable from `from` but not from `to` (`git log to..from`), so the provider now exchanges the two refs in the query to honour the documented `to_ref \ from_ref` contract; a newer release was previously reported as missing the commits it added, and a release note was built from the empty `previous \ version` difference ("No commits found")

---

## [1.23.0] - 2026-09-28

**Backend Version**: 1.23.0
**Frontend Version**: 1.18.0

### Added
- Resolve the release scope of a tag on the server: the predecessor is taken from the repository's tags (verified as an ancestor when one is found, otherwise the previous tag in version order), so the commits of a tag are a provider *difference* instead of everything reachable from it
- Add `list_tags_with_commits()` to every git provider (Bitbucket Server, Bitbucket Cloud, GitHub Enterprise), returning each tag with the commit it points to and, when the provider reports one, the commit date; an annotated tag is dereferenced by the provider so the tag object is never mistaken for a commit
- Report the scope behind a release preview (`previous_source`, `previous_verified`, `scope_reason`, `previous_sha`, `version_sha`) and show the short revision next to each ref of the tags panel
- Store the comparison baseline per repository (`release_check_baseline`, migration 033) and narrow a comparison against it, so a merge check only inspects the work of the release being checked
- Answer "does this commit belong to that release?" one commit at a time through the provider (`contains_commit`), so a release holding more commits than any listing cap is still judged exactly

### Fixed
- Report the merge check with a three-state verdict (`contained` / `missing` / `inconclusive`) derived from the provider-side difference: a comparison that was cut short is no longer presented as a pass
- Compute the missing direction as `source \ target`, so shared history cancels out and a repository with years of history no longer needs a commit listing to answer "was this merged?"
- Label a tag that has no predecessor as a first release (and an undeterminable scope as such) instead of reporting "the commit list reached Max Commits" - the old message described a listing limit, not the scope question that had actually gone unanswered
- Warn in the tags panel when the predecessor could only be inferred from the tag order, while still using that scope
- Ask the notes comparison with the resolved revisions, so a tag moved between resolving the scope and comparing cannot change what a release note was built from

### Improved
- Report the trimmed commit list of a release as a display limit ("showing the first N of M"): the count is the scope, and a scan that hit its cap is reported separately
- Prefill a drafted release with the predecessor the server resolved, and re-resolve the scope of the selected tag when the tag list is refreshed
- Restyle the reminder message shown in the release notes panel

### Documentation
- Add the OpenSpec changes `simplify-release-missing-check`, `enhance-release-note-scope` and `add-app-release-diff`

---

## [1.22.2] - 2026-09-27

**Backend Version**: 1.22.2
**Frontend Version**: 1.17.2

### Added
- Group the generated release notes by *Keep a Changelog* sections (Added, Changed, Deprecated, Removed, Fixed, Security), with one emoji per section
- Add `JIRA_BASE_URL` / `JIRA_PROJECT_KEYS` and publish them through `GET /api/v1/rbac/settings/jira`, so the generated notes and the UI link the same tickets
- Return the profile picture of a release author (`author_avatar_url`) with every release
- Return the provider account and profile page of a commit author (`author_username`, `author_url`) from every git provider

### Fixed
- Show the badges of the active tab only: the tag view no longer decorates a tag with the `vX` / `Latest` badges of the release selected on the releases tab
- Preselect the tag a release is drafted for (the tag clicked in the navigator, else the one selected there, else the newest) instead of a fixed version
- List the tags newest first in the version and ref pickers and drop repeated ref names (UI de-duplication plus a cleanup of the cached ref payload)

### Improved
- Link the JIRA ticket keys of commit messages in the commit tables, the commit check and the exported HTML report
- Mention commit authors as `@login` linked to their provider profile in the generated notes, the commit tables and the report
- Link the JIRA tickets of hand written release notes when they are displayed (code blocks and existing links are left untouched)
- Show the author profile picture next to the release notes and in the navigator

### Changed
- Rename the note sections to the Keep a Changelog vocabulary: Features → Added, Bug Fixes → Fixed, Performance / Refactoring / Maintenance → Changed, Reverts → Removed; Documentation and Tests keep a section of their own

---

## [1.22.1] - 2026-09-27

**Backend Version**: 1.22.1
**Frontend Version**: 1.17.1

### Added
- Link the `Full Changelog` range of a release to the revision comparison of the git provider (Bitbucket Cloud `{new}%0D{old}`, Bitbucket Server/Data Center `compare/commits?sourceBranch&targetBranch`, GitHub `base...head`)
- Split the release navigator into `Releases` and `Tags` tabs, each with its own pagination (server-side for releases, browser-side for tags)
- Map a tag to the commits it released, scoped against the next older tag of the repository
- Show a note icon on tags that already have a release, jumping to that note from any page of the list

### Fixed
- Reuse an already stored project / repository / user when the same remote entity is addressed through another business key, instead of failing with a duplicate key error on `POST /api/v1/reviews`
- Keep the original cause when a flush fails during an upsert: the failed payload is recorded in a fresh transaction instead of masking the error with a `PendingRollbackError`
- Look releases up by the payload business keys, so a retry through an aliased Cloud workspace updates its own review
- Keep the release tag index within the `GET /release/notes` limit of 200 rows per call

### Improved
- Follow the application theme in the rendered release note and the markdown editor (md-editor dark palette blended with the app surfaces)
- Open note links in a new tab so the release page is not replaced

### Changed
- Render the draft / edit release panel on demand instead of always showing the right column
- Move the read-only notice above the navigator so non-admins keep the full width

---

## [1.22.0] - 2026-09-26

**Backend Version**: 1.22.0
**Frontend Version**: 1.17.0

### Added
- Support Bitbucket Cloud (bitbucket.org) as a git provider next to Bitbucket Server/Data Center, resolved per project or per request
- Add dedicated Bitbucket Cloud credentials (`BITBUCKET_CLOUD_USER` / `BITBUCKET_CLOUD_APP_PASSWORD` / `BITBUCKET_CLOUD_TOKEN`) so both platforms can run side by side
- Add `workspace_slug` to PR reviews and release diff requests so the Cloud workspace can differ from the business project key
- Offer Bitbucket Cloud workspaces for selection, merged from `BITBUCKET_CLOUD_WORKSPACES`, the Cloud API and the workspaces already synced locally
- Add the Releases workspace: release comparison, commit membership check, commit lists and HTML/PNG export
- Add release notes management (new tables, API, permissions and view)
- Add a per-repository endpoint returning branches and tags for the release ref pickers

### Fixed
- Keep Server and Cloud credentials apart and log the resolved auth mode on provider startup
- Return actionable messages when Bitbucket Cloud authentication fails, including on a workspace the account cannot see
- Keep the payload project key as the business key while addressing the Cloud workspace remotely
- Strip the account name from Cloud clone URLs before persisting repository URLs
- Prevent stale analytics responses from overwriting newer data

### Improved
- Highlight missing release commits in red in the UI and in the exported HTML report
- Improve the commit tables: short SHAs with copy, per-commit links and clearer bounded-set hints
- Compare releases through the provider compare API and remove redundant provider requests

### Changed
- Rework the Releases page into a two-column layout (compare | check) and surface it in the main navigation
- Sync TypeScript compiler settings with the current toolchain
- Categorize scoped conventional commits correctly in the release tooling

---

## [1.21.1] - 2026-09-07

**Backend Version**: 1.21.1
**Frontend Version**: 1.16.1

### Added
- Add session idle heartbeat and enhance backend idle-session expiration handling
- Show PR author user info on Task Assignment detail view

### Fixed
- Fix PDF/Excel export: support Chinese fonts (i18n) and include missing PR metadata in exported files

### Changed
- Enhance score comments template used by quick score buttons and score range guide
- Improve user session management to keep idle timeout consistent

---

## [1.21.0] - 2026-09-02

**Backend Version**: 1.21.0
**Frontend Version**: 1.16.0

### Added
- Add user comment template
- Add comments template for score review
- Purge expired tokens older than 30 days automatically

### Changed
- Enhance analytics data retrieval and reduce the number of API requests
- Extend `.gitignore` to support more agent tooling
- Update `tsconfig.json` to fix CI issues
- Update GitHub CI workflow and fix git user info

---

## [1.20.6] - 2026-08-14

**Backend Version**: 1.20.6
**Frontend Version**: 1.15.6

### Added
- Support Bitbucket token access for git operations (configurable via env)
- Add unit-test-backend and unit-test-frontend skills for automated test generation
- Enhance git user query with flexible matching (username/display name/email)

### Fixed
- Update ScoreListView: simplify score display and remove redundant logic
- Fix frontend unit tests for language switcher, language composable, permission composable, and notification store

---

## [1.20.5] - 2026-07-23

**Backend Version**: 1.20.5
**Frontend Version**: 1.15.5

### Added
- Add `search_query` backend filter to Task Assignment page (search across PR ID, project, repo, reviewer)
- Display PR title and description from metadata in Review Information table
- Add `.github` project governance files (issue templates, PR template, CODEOWNERS, SECURITY.md, CONTRIBUTING.md, CI workflow)

### Fixed
- Fix session expiration: preserve remaining Redis TTL on token refresh to enforce 2-hour idle timeout
- Fix CSS cascade ordering for consistent N/A italic styling in review details

### Changed
- Enhance N/A display with italic font style when PR metadata fields are missing
- Update CI pipeline: add frontend vitest job, remove redundant type-check step, fix pytest command

### Documentation
- Enhance PRD.md with comprehensive endpoint audit and Git user auto-binding specification
- Add update-prd skill for automated PRD maintenance

---

## [1.20.4] - 2026-07-23

**Backend Version**: 1.20.4
**Frontend Version**: 1.15.4

### Added
- Pagination for task assignment details page

### Fixed
- SSE connection stability improvements
- Filter persistence: keep filter when navigating back, clear on explicit clear

### Changed
- [Refactor] SSE connection handling
- [Refactor] Git user retrieval logic
- Update banner behavior

---

## [1.20.3] - 2026-07-16

**Backend Version**: 1.20.3
**Frontend Version**: 1.15.3

### Added
- Unified interaction behavior for language and theme switcher
- Language switcher on auth page
- Updated background of login page
- Pagination handling for project registry

### Fixed
- update lang flag

### Dependencies
- update prompt in account registry
- upgrade page-agent

---

## [1.20.2] - 2026-07-15

**Backend Version**: 1.20.2
**Frontend Version**: 1.15.2

### Fixed
- update PR link of scores management page

### Changed
- [Refactor] enhance bitbucket service management
- [Refactor] validate git provider
- [Refactor] define enum to manage multiple git providers

### Documentation
- add docs to describe on how to increase git provider in future

---

## [1.20.1] - 2026-07-13

**Backend Version**: 1.20.1
**Frontend Version**: 1.15.1

### Changed
- [Refactor] enhance sse connections

### Documentation
- sync features change into AGENTS and README

### Other Changes
- 6bffad9 styles: enhanced task assignment details page layout

---

## [1.20.0] - 2026-07-10

**Backend Version**: 1.20.0
**Frontend Version**: 1.15.0

### Added
- support multiple git provider

---

## [1.19.3] - 2026-07-10

**Backend Version**: 1.19.3
**Frontend Version**: 1.14.3

### Fixed
- enhance the date range filter

### Changed
- [Refactor] enhance scoring rate

### Documentation
- update github
- handle github PR

---

## [1.19.2] - 2026-07-07

**Backend Version**: 1.19.2
**Frontend Version**: 1.14.2

### Added
- enhance redis connections
- record reviews deletion in audit log

### Fixed
- enhance review deletion

### Other Changes
- f8810ac styles: fix audit log details dialog layout issues
- 34ce5b1 Merge pull request #30 from aaronpliu/main
- c50d01d Merge pull request #29 from aaronpliu/feature/PRLedger_NewUI
- 47033e5 Merge pull request #28 from aaronpliu/feature/PRLedger_NewUI
- e27f9b0 Merge pull request #27 from aaronpliu/feature/PRLedger_NewUI
- fd72e17 Merge pull request #26 from aaronpliu/feature/PRLedger_NewUI
- 4ef7c77 Merge pull request #25 from aaronpliu/feature/PRLedger_NewUI

---

## [1.19.1] - 2026-06-30

**Backend Version**: 1.19.1
**Frontend Version**: 1.14.1

### Added
- add a banner in reviews page
- update page agent icon

### Fixed
- fix permission in 028 db migration script

---

## [1.19.0] - 2026-06-28

**Backend Version**: 1.19.0
**Frontend Version**: 1.14.0

### Added
- enhance the behavior of page agent
- enhance page agent style
- allow page agent to show
- setup llm proxy in backend
- integrate page agent into prledger system

### Fixed
- enhance the diff2html style

---

## [1.18.2] - 2026-06-25

**Backend Version**: 1.18.2
**Frontend Version**: 1.13.2

### Added
- add i18n for git user management
- manage git user in admin

### Fixed
- enhanced user add by admin
- remove review ID since it's hashed for now
- enhance git user creation and remove duplicate endpoint

### Dependencies
- rename UserManagementView

---

## [1.18.1] - 2026-06-21

**Backend Version**: 1.18.1
**Frontend Version**: 1.13.1

### Added
- take public id in url of review details
- enhance review ID for security requirement
- delete failed reviews in admin UI
- enhance permission for system admin
- add new columns in rules table

### Fixed
- upgrade element-plus to 2.14.2

### Documentation
- archied id-obfuscator
- handle ID with security approach
- remove app-name of openspec

---

## [1.18.0] - 2026-06-20

**Backend Version**: 1.18.0
**Frontend Version**: 1.13.0

### Added
- add "app name" as filter in scores page
- navigate to project as per app name from menu

### Documentation
- implement multiple app view and query

---

## [1.17.3] - 2026-06-18

**Backend Version**: 1.17.3
**Frontend Version**: 1.12.1

### Added
- handle metrics

### Fixed
- update env var

### Documentation
- archive wire-all-remaining-metrics
- implement the remaining tasks of wire-all-remaining-metrics
- archived fix-missing-metrics-at-startup
- archived observability

---

## [1.17.2] - 2026-06-15

**Backend Version**: 1.17.2
**Frontend Version**: 1.12.1

### Fixed
- Wired all MetricsCollector gauges to service/endpoint code (user stats, project stats, PR counts, backlog)
- Added system metrics collection background task (CPU, memory, disk via psutil every 60s)
- Added error tracking in middleware (errors_total on exceptions, rate limit errors)
- Fixed PR count queries: now counts distinct PRs correctly across all status types
- Initialized user/project/PR metrics with real database values at startup
- Fixed SQL incompatibility in `func.distinct()` for multi-column distinct counts

---

## [1.17.1] - 2026-06-14

**Backend Version**: 1.17.1
**Frontend Version**: 1.12.1

### Added
- Consolidated Prometheus, Grafana, and AlertManager into standalone `monitoring/` directory
- Standalone `monitoring/docker-compose.yml` for independent monitoring stack deployment
- AlertManager configuration with severity-based routing and optional Slack integration
- Prometheus alert rules for application health (API down, error rate, latency, backlog)
- Prometheus alert rules for infrastructure health (CPU, memory, disk, DB connections)
- Auto-provisioned Grafana dashboards: PRLedger Overview + Review Analytics

### Fixed
- Grafana container restart loop — fixed healthcheck timing and removed deprecated plugin
- AlertManager startup crash — fixed `--test.config` flag removed in AlertManager 0.25+
- AlertManager Slack integration — entrypoint script conditionally generates config
- Metrics exposure — merged MetricsCollector business metrics onto shared registry with Instrumentator
- Prometheus scrape target — entrypoint now handles env var substitution reliably
- Podman port binding — explicit `0.0.0.0:` for external network access
- Docker network consistency — all monitoring services use `code-review-network`

### Changed
- Refactored Prometheus config to use template + entrypoint for config generation
- Simplified Grafana healthcheck to avoid false restarts

### Documentation
- Updated README with monitoring stack deployment instructions
- Updated `monitoring/.env.example` with all configurable variables

### Dependencies
- add environment varaible for monitoring

### Other Changes
- c9ffd90 Merge pull request #24 from aaronpliu/main
- f598cf9 Merge pull request #23 from aaronpliu/feature/PRLedger_NewUI
- 25dafd0 Merge pull request #22 from aaronpliu/feature/PRLedger_NewUI

---

## [1.17.0] - 2026-06-13

**Backend Version**: 1.17.0
**Frontend Version**: 1.12.0

### Added
- optimize "create rule" dialog
- add auto assignment rule UI with openspec
- add auto assignmen rule
- add codegraph and openspec support

### Fixed
- enhance auto_assign

---

## [1.16.2] - 2026-06-10

**Backend Version**: 1.16.2
**Frontend Version**: 1.11.2

### Added
- openspec archive
- enhance review association
- add openspec

### Fixed
- add i18n for prompt of add score button

### Changed
- [Refactor] update git user and auth user endpoints
- [Refactor] enhance system function on user cascaded deletion

### Documentation
- archived /users endpoint refactor

---

## [1.16.1] - 2026-06-07

**Backend Version**: 1.16.1
**Frontend Version**: 1.11.1

### Added
- enhanced associated reviews dialog to quickly look up from candidate reviews

### Changed
- [Refactor] enhance database connection and update default value
- [Refactor] optimize sse connection and enhance exception handling

### Other Changes
- 6ec1cb8 Merge pull request #21 from aaronpliu/main
- 596d5de Merge pull request #20 from aaronpliu/feature/PRLedger_NewUI
- 70fbda2 Merge pull request #19 from aaronpliu/feature/PRLedger_NewUI

---

## [1.16.0] - 2026-06-06

**Backend Version**: 1.16.0
**Frontend Version**: 1.11.0

### Added
- Show review ID in reviews page
- Support to deassociate reviews
- Support to associate any 2 of reviews for comparison

### Fixed
- Align card size for scores and associated reviews consistently

---

## [1.15.2] - 2026-06-03

**Backend Version**: 1.15.2
**Frontend Version**: 1.10.1

### Added
- add a pin to mark the reviews
- enhance the archive for task assignment
- add archived filter for task assignment

### Fixed
- sorting issue as per severity
- fix sse connection

---

## [1.15.1] - 2026-05-31

**Backend Version**: 1.15.1
**Frontend Version**: 1.10.0

### Added
- support date range filter in reviews and task assignement page
- enhance sse event handling

### Fixed
- enhance the lable of time period in task assignment analytics
- enhance the chart lable display in dashboard
- enhance redis connection
- enhance the filter
- applied fix for CVE-2026-48710
- update html  issue
- enhance the chart display in full screen

### Changed
- [Refactor] enhance score table to display
- [Refactor] enhance review information table to show PR meta info

---

## [1.15.0] - 2026-05-28

**Backend Version**: 1.15.0
**Frontend Version**: 1.9.5

### Added
- fine-tune chart in full screen
- add chart to show issues as per severity and enhance charts with full screen
- enhance to take screenshot for AI review result
- enhanced global search

### Fixed
- fix style issue of PR meta info in screenshot
- optimize error handling for sse connection
- fix filter of severity issue in task assignment page
- enhance API request
- fix filter of severity issue in reviews
- enhance notification polling
- enhanced sse connection and exception handling
- update field name
- enhance database connection and logging

---

## [1.14.1] - 2026-05-22

**Backend Version**: 1.14.1
**Frontend Version**: 1.9.1

### Fixed
- **SSE connection tracking**: Fixed admin user connection cleanup — `_sse_event_generator` now receives the correct `tracking_username` from `stream_reviews`, preventing stale connection accumulation and 429 errors for admin users
- **SSE filter for non-admin users**: Removed 403 block; any authenticated user can now connect. Non-admin users without a linked Bitbucket account receive no events silently instead of being rejected
- **ECharts initialization**: Fixed `LineChart.vue` to wait for `onMounted` before rendering, eliminating DOM width/height warnings on the Task Assignment Analytics page
- **ECharts grid API**: Replaced deprecated `grid.containLabel: true` with modern `grid.outerBounds` in `BarChart.vue` and `LineChart.vue` (ECharts v6 compatibility)

### Other Changes
- 487e657 Import SSEReviewCreatedEvent type in TaskAssignmentView

---

## [1.14.0] - 2026-05-21

**Backend Version**: 1.14.0
**Frontend Version**: 1.9.0

### Added
- add SSE for reviews and task assignment page
- add agent team for the system

### Other Changes
- c7536fc Merge pull request #18 from aaronpliu/main
- c7f089c Merge pull request #17 from aaronpliu/feature/PRLedger_NewUI
- 5481125 Merge pull request #16 from aaronpliu/feature/PRLedger_NewUI
- cbc0645 Merge pull request #15 from aaronpliu/feature/PRLedger_NewUI
- bbb5c6f Merge pull request #14 from aaronpliu/feature/PRLedger_NewUI
- 7b85f93 Merge pull request #13 from aaronpliu/feature/PRLedger_NewUI

---

## [1.13.5] - 2026-05-20

**Backend Version**: 1.13.5
**Frontend Version**: 1.8.5

### Added
- hide swagger in prod
- update table index for /reviews to identify duplicate rows
- update PR URL
- add statement and tips for task assignment analytics charts

### Fixed
- update source_branch length
- update GET /users query parameters

---

## [1.13.2] - 2026-05-12

**Backend Version**: 1.13.2
**Frontend Version**: 1.8.2

### Fixed
- enhance performance issue to handle timezone
- fix line color for line chart when theme change
- enhance exceptions
- fix frontend build issue
- enhance auth user and git user status

---

## [1.13.1] - 2026-05-10

**Backend Version**: 1.13.1
**Frontend Version**: 1.8.1

### Added
- activate or deactive user
- add a refresh button in PAT page

### Fixed
- enhance git user
- continue to enhance permission for users
- enhance permission for /users endpoint
- enhance timezone for PAT

### Dependencies
- enhance profile window size

---

## [1.13.0] - 2026-05-10

**Backend Version**: 1.13.0
**Frontend Version**: 1.8.0

### Added
- add personal access token
- add avatar in admin page

### Fixed
- optimize the statistics card in task assignment analytics page
- add i18n for system settings button
- add i18n for review validation

---

## [1.12.0] - 2026-05-08

**Backend Version**: 1.12.0
**Frontend Version**: 1.7.0

### Added
- support avatar in profile

---

## [1.11.1] - 2026-05-07

**Backend Version**: 1.11.1
**Frontend Version**: 1.6.1

### Fixed
- enhance background pic display with high quality
- update import error
- expand git_code_diff to medium text
- enhance the error message popup when multiple error occurred

---

## [1.11.0] - 2026-05-06

**Backend Version**: 1.11.0
**Frontend Version**: 1.6.0

### Added
- [may] add background pic for login
- [may] enhance the statistics chart of task assignment
- [may] add task assignment analytics

### Fixed
- fix i18n nesting mismatch issue
- [may] Better cross-browser compatibility

---

## [1.10.1] - 2026-05-05

**Backend Version**: 1.10.1
**Frontend Version**: 1.5.1

### Bug Fixes
- **Multiple Reviewers Display** - Enhanced multiple reviewers display in task assignment page
- **i18n for Score List & Analytics** - Enhanced internationalization for score list and analytics page
- **Null/Undefined Handling** - Fixed null and undefined issue for notifications
- **Reviewer Comments** - Fixed reviewer comments issue
- **Notification Indicator** - Enhanced indicator display for notifications
- **AI Review Results i18n** - Enhanced internationalization for AI review results

### Improvements
- **Unassigned Filter** - Enhanced "unassigned" filter
- **Scores Page Avatars** - Enhanced avatars for PR user and reviewer in Scores management page

---


## [1.10.0] - 2026-05-05

**Backend Version**: 1.10.0
**Frontend Version**: 1.5.0

### Features
- **Review Scores** - Added scores for each review
- **Notifications** - Implemented notifications system

### Bug Fixes
- **i18n for Score List & Analytics** - Enhanced internationalization
- **No AI Review Result UI** - Enhanced display when no AI review result
- **Import Error** - Resolved import error (amy)
- **Review Navigation** - Fixed navigation in review details
- **Pagination Optimization** - Optimized pagination in backend
- **Unassigned Task** - Enhanced "Unassigned" task by review admin
- **Single/Multiple Reviewer Scoring** - Enhanced scoring for single or multiple reviewers

### Improvements
- **Unscored Reviews Priority** - Refactored to show unscored reviews in priority
- **Implementation Docs** - Consolidated phase4 implementation documentation

---


## [1.9.1] - 2026-05-03

**Backend Version**: 1.9.1
**Frontend Version**: 1.4.1

### Features
- **Toggle for Scored Reviews** - Added toggle button to hide/show scored reviews
- **Bulk Task Assignment** - Added bulk operation for task assignment

### Bug Fixes
- **Remove Change PR Status** - Removed the "Change PR Status" feature
- **Bulk Operation Enhancements** - Enhanced bulk operation for reviews
- **Multiple Reviewers Display** - Enhanced display for multiple reviewers on same PR
- **i18n Enhancements** - Enhanced internationalization for all pages
- **Chart Labels & Axes** - Enhanced labels and x/y axis display
- **Dark Theme Dashboard** - Enhanced dashboard in dark theme
- **Score Calculation Fix** - Fixed score issue on first-time scoring
- **Create Tag Script** - Fixed create_tag script issues

---


## [1.9.0] - 2026-05-02

**Backend Version**: 1.9.0
**Frontend Version**: 1.4.0

### Features
- **PR Review Validation** - Added validation for pull request reviews
- **Release Manager Skill** - Automated release workflow integration
  - New `release-manager` skill for consistent version management
  - Automated changelog generation and dependency synchronization
  - Git tag creation with proper annotations

### Bug Fixes
- **Audit Logs** - Enhanced audit logging functionality
- **Admin Theme & Filtering** - Fixed theme issues and improved admin page filtering
- **PR Review Validation** - Enhanced validation of PR review insertions
- **Code Diff Display** - Improved code diff display styling
- **Theme & Code Diff** - Enhanced theme and code diff styling (multiple improvements)
- **Web Directory Cleanup** - Removed obsolete `web/` directory
- **Console Element Issues** - Fixed console issues with Element Plus component sliding

---

### Added
- **Release Manager Skill** - Automated release workflow integration
  - New `release-manager` skill for consistent version management
  - Automated changelog generation and dependency synchronization
  - Git tag creation with proper annotations

- **Admin Password Reset** - Enhanced admin user management
  - Admins can now reset passwords for other users
  - New endpoint `POST /api/v1/admin/users/{user_id}/reset-password`
  - Force password change on next login option

- **Enhanced Score Management** - Improved score display and analytics
  - Enhanced score table with better filtering and sorting
  - Improved score analytics dashboard with advanced charts
  - Better score visualization in review details

- **Timezone Support** - Comprehensive timezone handling
  - Added `timezone.py` utility module for timezone conversions
  - Proper UTC timestamp handling across all models
  - Enhanced datetime display with timezone awareness

- **UI Navigation Enhancements** - Improved user experience
  - Added floating navigation in review details page
  - Better AI review result styling
  - Improved data lazy loading performance

### Fixed
- **Reviewer Visibility** - Fixed visible reviews filtering for reviewer role
- **Database Connection** - Enhanced connection handling and error recovery
- **AI Review Integration** - Fixed AI review ID handling and theme compatibility
- **Platform Compatibility** - Added tzdata dependency for cross-platform stability

### Technical Details
- **Backend Version**: 1.8.0 (FastAPI service)
- **Frontend Version**: 1.3.0 (Vue 3 application)
- **Database Migrations**: New migration for admin password reset functionality
- **Dependencies**: Added tzdata for timezone support

---

## [1.7.1] - 2026-04-26

### Changed
- **Version Bump**: Backend updated to v1.7.1, Frontend updated to v1.2.1
- **Configuration**: Removed unused `PROJECT_VERSION` field from `Settings` and `.env.example` to prevent future drift

---

## [1.7.0] - 2026-04-22

### Added
- **System Settings Management** - Centralized system configuration
  - New `system_setting` table for storing system-wide settings
  - Admin UI for managing system settings
  - Backend CRUD endpoints for system settings

- **Enhanced Admin Dashboard** - Comprehensive admin overview
  - New admin dashboard view with key metrics
  - Project registry management in admin page
  - Enhanced delegation query and management

- **Session Management** - User login session tracking
  - Manage user login sessions by user and admin
  - Enhanced session info display
  - Enhanced logged token and refresh mechanism

- **PR ID Hyperlinks** - Quick navigation to pull requests
  - Hyperlink for PR ID in task assignment page
  - Enhanced PR URL handling with `usePrUrl` composable

- **Code Diff Enhancements** - Improved diff visualization
  - Show code diff with diff2html in task assignment details page
  - Enhanced code diff styles referencing theme color
  - Optimized UI display for user-agent

- **Score Analytics Dashboard** - Enhanced analytics visualization
  - Improved score distribution charts
  - Better performance metrics display

- **i18n Enhancements** - Expanded internationalization support
  - Updated translations for en, zh-CN, zh-TW
  - Enhanced search for audit logs and sessions

- **Multi-Git Provider Support** - Broader Git provider compatibility
  - Replaced specific prefix of git provider to support more providers

### Changed
- **Task Assignment Workflow** - Improved task assignment experience
  - Enhanced sequence for task assignment
  - Highlight unassigned tasks with obvious tags
  - Allow PR user to view self-raised PR
  - Show more recent reviews
  - Add "next" button in reviews detail page for quick navigation
  - Enable switching reviews in details page

- **Filter Enhancements** - Better filtering capabilities
  - Optimize user filter
  - Add app_name as filter
  - Enhance filter styles and fix app name display

- **UI/UX Improvements** - Visual refinements across the application
  - Update styles of login and registry page
  - Optimize dashboard display
  - Optimize banner in code reviews page
  - Optimize records display as per resolution
  - Update menu style in admin layout

- **Permission Updates** - Refined access control
  - Enhance admin page access
  - Update permission for TAM page
  - Fix permission and score for reviewer
  - Update permission to view task assignment

### Fixed
- **Deprecated API Parameters** - Updated deprecated `Query()` parameter usage
- **Docker Configuration** - Fixed Dockerfile and nginx.conf issues
- **User Role Management** - Resolved user role management issues
- **Admin Route** - Fixed admin route issue after rename
- **Pagination** - Resolved pagination issues
- **Build Issues** - Fixed frontend build problems
- **Dependency Vulnerabilities** - Replaced xlsx with exceljs to avoid vulnerabilities
- **Delegation Status** - Handle delegation status transition with lifespan
- **Comments Component** - Fixed comments component display issue
- **PR User/Reviewer Filter** - Updated filter logic
- **Copyright/Version Display** - Fixed copyright and version info show in pages

### Technical Details
- **Backend Version**: 1.7.0 (FastAPI service)
- **Frontend Version**: 1.2.0 (Vue 3 application)
- **Database Migrations**: Added system settings table (migration 015), project registry permissions (migration 013), AI review ID column (migration 014)
- **Dependencies**: Replaced xlsx with exceljs for security

---

## [1.6.0] - 2026-04-13

### Added
- **Multi-Reviewer Review Architecture** - Split review persistence into base review and reviewer assignment tables
  - Added `pull_request_review_base` for shared PR review data
  - Added `pull_request_review_assignment` for reviewer-specific assignment state
  - Added migration coverage for the new review model and permission updates

- **Review Assignment and Delegation Flows** - Expanded review administration workflow across backend and UI
  - Added reviewer assignment tracking with assignment status and reviewer comments
  - Added frontend task assignment and role delegation management support
  - Added backend support for delegated review administration flows

### Changed
- **Backend Review Mapping** - Refactored ORM and service layers to use the new base-plus-assignment schema
  - Updated review, project, repository, and user relationships to target the new tables
  - Flattened base and assignment data at the service boundary to preserve the existing API response shape
  - Updated project statistics and assignment endpoints for the new schema

- **Release Metadata** - Aligned backend and frontend version surfaces for the new release
  - Backend version bumped to 1.6.0
  - Frontend version bumped to 1.1.0
  - Documentation updated to reflect the new release

### Fixed
- **Legacy Review Compatibility** - Removed stale single-table review assumptions after the schema refactor
  - Fixed assignment flows that previously depended on `pull_request_review.reviewer IS NULL`
  - Fixed mixed review model imports after consolidating canonical models
  - Fixed review statistics queries against the refactored tables

### Technical Details
- **Backend Version**: 1.6.0 (FastAPI service)
- **Frontend Version**: 1.1.0 (Vue 3 application)
- **Database Migrations**: Added multi-reviewer and permission updates through migrations 011 and 012

---

## [1.5.0] - 2026-04-08

### Added
- **Vue.js Frontend Application** - Complete rewrite using modern Vue 3 framework
  - Full TypeScript support with Vue 3 Composition API
  - Element Plus UI component library integration
  - Vue Router for SPA navigation
  - Pinia state management
  - Internationalization (i18n) support
  - Responsive design for all screen sizes
  
- **Enhanced Code Diff Viewer** - Professional diff visualization with Diff2Html
  - Side-by-side and unified view modes
  - Syntax highlighting for multiple languages
  - Line number synchronization
  - Sticky line numbers during horizontal scroll
  - Dark theme support
  
- **Advanced Review Management**
  - Multi-reviewer score tracking
  - Real-time review status updates
  - Comprehensive filtering and search
  - Export capabilities (PDF, Excel)
  
- **Analytics Dashboard**
  - Interactive charts with ECharts
  - Score distribution analysis
  - Review trends over time
  - Performance metrics

### Changed
- **Frontend Architecture** - Migrated from vanilla JS to Vue 3
  - Modern build system with Vite 7.x
  - Component-based architecture
  - Type-safe development with TypeScript
  - Improved code organization and maintainability
  
- **API Integration** - Enhanced backend communication
  - Axios for HTTP requests with interceptors
  - Automatic token refresh
  - Better error handling and user feedback
  - WebSocket support for real-time updates

### Fixed
- **Diff Rendering Issues** - Resolved line number scrolling problems
  - Fixed `position: absolute` causing line numbers to detach
  - Implemented `position: relative` for proper document flow
  - Synchronized scrolling in side-by-side mode
  
- **Router Deprecation Warnings** - Updated to Vue Router 5 best practices
  - Replaced deprecated `next()` calls with return values
  - Cleaner navigation guard implementation

### Removed
- **PWA Support** - Removed vite-plugin-pwa and related configurations
  - Simplified build configuration
  - Reduced bundle size
  - Focused on core functionality

### Technical Details
- **Backend Version**: 1.5.0 (FastAPI service)
- **Frontend Version**: 1.0.0 (Vue 3 application)
- **Build Tools**: Vite 7.3.2, TypeScript 6.0.2
- **UI Framework**: Element Plus 2.13.6
- **State Management**: Pinia 3.0.4
- **Routing**: Vue Router 5.0.4

---

## [1.4.0] - 2026-04-06

### Added
- **Diff2HTML Integration** - Enhanced code diff visualization in the review UI
  - Integrated diff2html library for syntax-highlighted, interactive diff display
  - Added `web/lib/diff2html-ui.min.js` and `web/lib/diff2html.min.css`
  - New `scripts/update_diff2html.sh` script for library updates
  - Improved readability of code changes during code review

- **Score Deletion Functionality** - Ability to delete review scores
  - New endpoint for removing scores from reviews
  - Database migration: `alembic/versions/005_add_active_and_deletion_tracking_to_score.py`
  - Added `is_active` flag for soft deletion support

### Changed
- **UI Material Design Upgrade** - Complete visual overhaul with Material Design principles
  - Refactored UI with material design styles (`web/css/material-design.css`)
  - Enhanced component styles: buttons, cards, chips, forms, typography
  - Added Ripple effect component (`web/js/components/Ripple.js`)
  - Improved theme support for light/dark modes
  - Enhanced visual hierarchy and spacing across all components

- **Cache Enhancement** - Improved cache handling for different themes
  - Cache now accounts for theme selection
  - Better cache invalidation strategy for UI-related data

### Fixed
- **Score Logic Enhancement** - Corrected score behavior for first-time reviewer updates
  - Fixed edge case when reviewer updates score for the first time
  - Improved score calculation accuracy in multi-reviewer scenarios

- **Cache Cleanup Script** - Enhanced `clear_cache.py` reliability
  - Improved error handling and logging
  - Better support for selective cache clearing patterns

---

## [1.3.2] - 2026-04-05

### Added
- **Review UI Testing Page** - Interactive web interface for API testing and review visualization
  - New `web/index.html` page for manual testing of review endpoints
  - Support for multiple themes (light/dark mode)
  - Enhanced parameter controls for GET /reviews endpoint with additional filtering options
  - Real-time score display and editing capabilities
  - Visual representation of reviewer comments and suggestions
  
- **Cache Management Script** - Utility for clearing Redis cache
  - New `scripts/housekeeping/clear_cache.py` for cache cleanup operations
  - Supports selective cache clearing by key patterns
  - Logging integration for audit trail
  - Helps maintain cache consistency during development and production

### Changed
- **Score Architecture Refactoring [BREAKING]** - Separated score data from review results into dedicated table
  - Created new `review_score` table with proper normalization for better data organization
  - Database migration: `alembic/versions/004_refactor_score_to_separate_table.py`
  - Scores can now be managed independently at PR level or file level
  - Removed score fields from `create_review` endpoint to simplify API contract
  - New `ReviewScoreService` for dedicated score management operations
  - Updated score summary logic for better aggregation and reporting
  - **Migration Note**: Existing review data automatically migrated to new schema
  
- **Enhanced Review Query Logic** - Improved data retrieval and filtering
  - Fixed reviewer_comments field population in GET /reviews responses
  - Optimized review score queries with proper JOIN strategies
  - Enhanced statistics calculation accuracy for dashboard metrics
  - Better handling of multi-reviewer scenarios with independent scoring
  
- **Schema Unification** - Standardized Pydantic schemas across services
  - Unified schema configurations in all service layers (project, user, review)
  - Consistent response models with proper type annotations
  - Improved type safety and validation across API boundaries
  - Reduced code duplication through shared schema definitions
  
- **Folder Structure Optimization** - Reorganized scripts for better maintainability
  - Moved utility scripts to `scripts/housekeeping/` directory for better organization
  - Renamed `scripts/deployment/clear_cache.py` → `scripts/housekeeping/clear_cache.py`
  - Renamed `scripts/cleanup_database.py` → `scripts/housekeeping/clear_database.py`
  - Moved `scripts/review_ui.html` → `web/index.html` for clear separation of concerns
  
- **Deprecated Method Replacement** - Updated SQLAlchemy model definitions
  - Replaced deprecated column definition patterns in Project, Repository, and User models
  - Ensured compatibility with latest SQLAlchemy 2.0 standards
  - Improved model initialization and relationship definitions

### Fixed
- **Cache Error on Score Updates** - Resolved cache invalidation issues
  - Fixed cache key mismatch when updating scores in multi-reviewer scenarios
  - Proper cache refresh after score modifications to prevent stale reads
  - Eliminated stale data problems in review queries
  
- **User Cache Issues** - Corrected user data caching behavior
  - Fixed cache serialization/deserialization for user objects
  - Improved cache hit rates for frequently accessed user data
  - Prevented cache corruption from improper object storage
  
- **Type Errors** - Multiple type annotation fixes across codebase
  - Fixed type mismatches in review service methods
  - Corrected return type annotations in API endpoints (reviews, users)
  - Improved type safety in user and review operations
  - Enhanced IDE support and static analysis accuracy
  
- **Exception Handling** - Enhanced error output and logging
  - Better error messages for debugging with contextual information
  - Improved exception propagation in middleware layer
  - More informative stack traces for faster issue resolution

### Technical Details
- **Database Schema**: New `review_score` table separates scoring from review content, enabling independent score management
- **Caching Strategy**: Fixed composite key usage `(project_key, repository_slug, pull_request_id)` for consistent cache behavior
- **API Design**: Simplified create_review by removing score parameters; use dedicated score endpoints instead
- **UI Enhancement**: Modern responsive design with theme support, accessible via `/web/index.html`
- **Code Quality**: Unified schema patterns reduce duplication by ~30% and improve maintainability
- **Backward Compatibility**: Migration script ensures existing data works seamlessly with new schema

---

## [1.3.1] - 2026-03-31

### Added
- **Multi-Reviewer Score Support** - Complete independent scoring workflow for multiple reviewers
  - UPSERT pattern for review scores: creates new record if reviewer hasn't scored, updates if exists
  - Each reviewer maintains independent score history with separate iteration tracking
  - Per-reviewer `is_latest_review` flag ensures correct latest score identification
  - Supports unlimited reviewers per PR/file combination without conflicts
  
- **Enhanced Score Update Logic** - Intelligent create-or-update behavior
  - New `upsert_review_score()` method replaces update-only approach
  - Automatic base data reuse: New reviewers inherit AI review data (diff, suggestions, metadata)
  - Proper error handling: Distinguishes between "no AI review yet" vs "new reviewer needs record"
  - Clear guidance messages direct users to submit AI review first if missing
  
- **Score Iteration Management** - Per-reviewer version tracking
  - Each reviewer's iterations tracked independently (reviewer A iteration 1, 2, 3...; reviewer B iteration 1, 2...)
  - Iteration calculation scoped to specific reviewer, not global across all reviewers
  - Maintains complete audit trail of score changes per reviewer
  
- **Comprehensive API Documentation** - Multi-reviewer workflow clearly explained
  - Endpoint docstrings detail UPSERT behavior and prerequisites
  - Example workflows show how multiple reviewers interact with same PR/file
  - Error scenarios documented with resolution steps

### Changed
- **Service Method Signature** - Renamed and refactored score update method
  - `update_review_score()` → `upsert_review_score()` to reflect create-or-update behavior
  - Enhanced logging shows which reviewer is updating/creating score
  - Improved error messages specify when reviewer hasn't submitted review yet
  
- **Database Query Strategy** - Optimized for multi-reviewer lookups
  - Queries filter by complete composite key including `reviewer` field
  - Separate query paths for UPDATE (find existing reviewer record) vs CREATE (find any base review)
  - Eager loading of relationships (`project`, `repository`, `user` rels) for enrichment
  
- **API Response Enrichment** - Consistent entity information across all score operations
  - `app_name` resolution integrated into upsert flow
  - Full nested objects returned: `project`, `repository`, `pull_request_user_info`, `reviewer_info`
  - Updated timestamp set on both create and update operations

### Improved
- **Multi-Reviewer Architecture** - Production-ready team review support
  - No breaking changes to existing single-reviewer workflows
  - Backward compatible: Existing callers continue to work unchanged
  - Forward looking: Enables future features like score averaging, consensus analysis
  
- **Error Handling & Validation** - Precise failure messages and recovery guidance
  - `ReviewNotFoundException` includes context about missing AI review vs missing reviewer record
  - `ValueError` for missing required parameters with clear field list
  - Warning logs when operations fail due to missing prerequisite data
  
- **Data Model Clarity** - Clear separation of concerns in review records
  - Base review data (AI suggestions, diff) separated from reviewer-specific data (score, comments)
  - Multiple reviewers can share same base data while maintaining independent scores
  - Composite unique constraint enforces one score per reviewer per file

### Technical Details
- **UPSERT Implementation**: Two-path logic - UPDATE existing reviewer record or CREATE new one
- **Base Data Reuse**: New reviewers copy `pull_request_commit_id`, `git_code_diff`, `ai_suggestions` from existing reviews
- **Iteration Calculation**: `SELECT MAX(review_iteration) WHERE reviewer = :reviewer` per reviewer
- **Cache Invalidation**: Uses composite key `(project_key, repository_slug, pull_request_id)` shared across all reviewers
- **Enrichment Flow**: Calls `_enrich_review_with_entities()` which resolves `app_name` from project registry

---

## [1.3.0] - 2026-03-29

### Added
- **Project Registry System** - Revolutionary virtual app_name architecture for multi-project management
  - New `project_registry` table mapping `(project_key, repository_slug)` pairs to application names
  - Virtual column pattern: `app_name` computed at query time, not stored in review table
  - Default app assignment: "Unknown" for unregistered projects
  - Auto-registration mechanism creates entries on first access
  - Support for logical grouping of multiple projects under single applications
  - Database migration: `alembic/versions/002_create_project_registry.py`
  
- **Multi-App Query Support** - Enhanced filtering capabilities
  - New query parameter `app_names` accepts comma-separated values (e.g., `?app_names=member,tv,football`)
  - Batch resolution of app_names for optimal performance
  - Single query loads reviews from multiple applications simultaneously
  - Automatic injection of `app_name` field into all review responses
  
- **Project Registry Service** - Comprehensive CRUD operations
  - New service: `ProjectRegistryService` with full lifecycle management
  - Methods:
    - `get_app_name()` - Resolve app for single project pair
    - `get_app_names_batch()` - Batch resolution for multiple projects (performance optimized)
    - `list_projects_by_app()` - Retrieve all projects in an application
    - `register_project()` - Register project-repo pair to app
    - `unregister_project()` - Remove from registry
    - `update_project_app()` - Move project to different app
    - `list_all_apps()` - List all apps with project counts
    - `auto_register_project()` - Automatic registration with default app
  
- **Admin API Endpoints** - Registry management interfaces (authentication TODO)
  - `GET /api/v1/apps` - List all registered applications with project counts
  - `GET /api/v1/apps/{app_name}/projects` - List projects in specific app
  - `GET /api/v1/projects/{project_key}/{repository_slug}/app-name` - Get app for project
  - `POST /api/v1/admin/registry/register` - Register project to app (admin only)
  - `PUT /api/v1/admin/registry/update` - Move project to different app (admin only)
  - `DELETE /api/v1/admin/registry/unregister` - Remove project from registry (admin only)
  
- **Enhanced Review Response Schema** - Complete entity information
  - New `app_name` field in `ReviewResponse` schema (virtual, resolved at runtime)
  - Positioned before nested objects for consistent response structure
  - Default value "Unknown" ensures field always present
  - Includes full entity enrichment: `project`, `repository`, `pull_request_user_info`, `reviewer_info`
  
- **Database Models & Relationships**
  - New model: `ProjectRegistry` with proper foreign keys and indexes
  - Unique constraint on `(project_key, repository_slug)` ensures one-to-one app mapping
  - Composite index on `(app_name, project_key, repository_slug)` for fast app-based queries
  - Updated `Project` model with `registry_entries` relationship
  - Bidirectional associations enable efficient navigation

### Changed
- **Review Service Enhancement** - App-aware filtering and enrichment
  - `list_reviews()` method now accepts optional `app_names` parameter
  - Intelligent query building:
    1. If `app_names` provided: Query registry for matching project-repo pairs
    2. Build OR conditions for all matching pairs
    3. Execute single optimized SQL query (no N+1 problem)
  - `list_reviews_with_entities()` injects `app_name` into each enriched review dict
  - Batch resolution prevents repeated database lookups
  - Cache strategy: Disabled for app-filtered queries to ensure fresh data
  
- **API Endpoint Updates** - Backward compatible enhancements
  - `GET /api/v1/reviews` now supports optional `app_names` query parameter
  - All review responses include complete entity information (no more null values)
  - Fixed eager loading: Added missing `repository` relationship with `selectinload`
  - Dual-path enrichment logic handles both ORM objects and cached dictionaries
  
- **Router Configuration** - Expanded API surface
  - New router: `project_registry` included in main API
  - Updated `src/api/v1/api.py` to register new endpoints
  - Proper tag categorization for OpenAPI documentation
  
- **Alembic Migration Fix** - Corrected Path usage in env.py
  - Fixed `Path.parent` property access (was incorrectly called as method)
  - Changed from `Path.parent(Path.parent(__file__))` to `str(Path(__file__).parent.parent)`
  - Ensures proper Python path resolution for migration scripts

### Improved
- **Performance Optimizations**
  - Batch app_name resolution reduces database round trips
  - Composite indexes enable efficient app-based filtering
  - Eager loading with `selectinload` prevents N+1 query problem
  - Strategic caching disabled for dynamic app assignments
  
- **Data Integrity** - Strong referential constraints
  - Foreign key to `project.project_key` with CASCADE delete
  - Unique constraint prevents duplicate app assignments
  - Automatic population during migration ensures no orphaned projects
  
- **Developer Experience** - Intuitive multi-project management
  - Logical application boundaries without physical table proliferation
  - Simple admin APIs for registry management
  - Clear separation between configuration (registry) and data (reviews)

### Technical Details
- **Virtual Column Pattern**: `app_name` not stored in `pull_request_review` table
- **Query-Time Resolution**: App name computed via JOIN or application logic
- **Default Behavior**: Unregistered projects → "Unknown" app
- **Auto-Registration**: Enabled on first access, configurable default
- **Multi-App Queries**: Comma-separated parameter supports unlimited apps
- **Backward Compatibility**: Existing APIs function without `app_names` parameter
- **Migration Strategy**: Existing data auto-populated to "Unknown" app during upgrade

---

## [1.2.0] - 2026-03-25

### Added
- **Enhanced Review Score Update Endpoint** - New composite key-based score update functionality
  - New `PUT /api/v1/reviews/score` endpoint for precise review score updates
  - Uses complete business key combination for record identification:
    - `project_key` - Project identifier
    - `repository_slug` - Repository slug  
    - `pull_request_id` - Pull request ID
    - `source_filename` - Source filename being reviewed (mandatory)
    - `reviewer` - Reviewer username
  - In-place score update without creating new iterations
  - Prevents cross-project and cross-repository data collisions
  - All parameters mandatory to ensure precise record targeting

- **Version Management Improvements**
  - Direct version reading from `pyproject.toml` using Python's built-in `tomllib`
  - No longer requires package installation (`pip install -e .`) for version detection
  - Works seamlessly in pure development mode with `uvicorn src.main:app --reload`
  - Single source of truth maintained in `pyproject.toml`
  - Automatic fallback to `1.0.0-dev` if file read fails

### Changed
- **SQLAlchemy Boolean Query Syntax** - Updated all boolean column comparisons
  - Changed from `column == True` to `column.is_(True)` across all service methods
  - Ensures proper SQL generation for boolean identity checks
  - Improves compatibility with nullable boolean columns
  - Applied to all `is_latest_review` queries in review service
  - Fixed "Review not found" errors caused by incorrect boolean comparison

- **API Route Ordering** - Reorganized review endpoints for correct route matching
  - Moved `/score` endpoint before parameterized routes like `/{pull_request_id}`
  - Prevents FastAPI from treating "score" as a path parameter value
  - Ensures deterministic route resolution

- **Review Service Method Signature** - Made `source_filename` mandatory
  - Changed from `source_filename: str | None` to `source_filename: str`
  - Enforces complete composite key lookup for all score updates
  - Aligns with database unique constraint requirements

### Technical Details
- **Composite Key Pattern**: Full business key ensures data integrity across multi-tenant deployments
- **Performance**: Single UPDATE query, no INSERT operations or iteration increments
- **Type Safety**: Proper SQLAlchemy `.is_()` usage for boolean comparisons
- **Development Workflow**: Simplified version management without package installation overhead

---

### Changed
- **Consolidated Review Endpoints** - Merged `POST /api/v1/reviews` and `POST /api/v1/reviews/upsert` into a single upsert endpoint
  - Removed separate `create_review` endpoint to simplify API design
  - Kept only `upsert_review` endpoint at `POST /api/v1/reviews` which handles both create and update operations
  - The endpoint now automatically detects if a review exists and creates or updates accordingly
  - Returns HTTP 201 Created for new reviews, HTTP 200 OK for updated reviews
  - Updated documentation in README.md and PROJECT_STRUCTURE.md

### Technical Details
- Single endpoint reduces API surface area and maintenance overhead
- Upsert logic handled by `ReviewService.upsert_review()` method
- Backward compatible behavior - existing clients can continue using the endpoint

---

## [1.0.1] - 2026-03-21

### Added
- **Logging System** - Comprehensive logging configuration with daily rotation and 30-day retention
  - New `src/conf/logging.yaml` for centralized logging configuration
  - New `src/utils/log.py` utility module with `setup_logging()` and `get_logger()` functions
  - Dual log files: `logs/app.log` (all INFO+ logs) and `logs/error.log` (ERROR logs only)
  - Detailed log format including timestamp, logger name, level, message, filename, and line number
  - Component-specific log levels (uvicorn, sqlalchemy, application)
  - Automatic log directory creation
  - Support for custom config paths and environment files
  - Documentation: `src/conf/LOGGING_GUIDE.md`

- **PyYAML Dependency** - Added `pyyaml>=6.0` to support YAML-based logging configuration

### Fixed
- **SQLAlchemy Model Circular Dependency** - Resolved critical startup error preventing application initialization
  - Fixed circular reference between `PullRequestReviewBase` and `User` models
  - Removed duplicate `Base` class definition in `src/models/user.py`
  - Unified all models to use single `Base` from `src/core/database.py`
  - Used string-free relationship definitions to enable lazy loading
  - Removed explicit `poolclass=QueuePool` from async engine configuration
  - Applied SQLAlchemy 2.0 compatibility fixes (using `text()` for raw SQL)

- **Pydantic v2 Compatibility** - Updated all schema validators to use Pydantic v2 syntax
  - Replaced deprecated `@validator` with `@field_validator` across all schemas
  - Fixed field name mismatch in `ReviewFilter` (`pull_request_status` instead of `status`)
  - Corrected parameter order in service layer method calls

- **Parameter Order Issues** - Fixed function signature violations in service methods
  - Ensured database session parameter comes before optional pagination parameters
  - Aligned API endpoint calls with corrected service method signatures

### Changed
- **Main Application** - Updated `src/main.py` to use new centralized logging system
  - Replaced basic logging config with `setup_logging()` from `src.utils.log`
  - Now uses `get_logger(__name__)` for consistent logger instances

---

## [1.0.0] - 2026-03-21

### Added
- Initial release of PRLedger
- Complete RESTful API for pull request code review result storage management
- User, project, repository, and review management endpoints
- Async database operations with SQLAlchemy 2.0
- Redis caching integration
- Prometheus metrics collection
- Grafana dashboard configuration
- Alembic database migration support
- Docker and docker-compose deployment configuration
- Comprehensive API documentation with OpenAPI/Swagger

---

## Version History Summary

| Version | Date | Key Changes |
|---------|------|-------------|
| 1.7.0 | 2026-04-22 | System settings, admin dashboard, session management, PR hyperlinks, diff enhancements, i18n updates |
| 1.6.0 | 2026-04-13 | Multi-reviewer review table split, assignment workflow, role delegation, release metadata alignment |
| 1.5.0 | 2026-04-08 | Vue.js frontend application, advanced review management, analytics dashboard |
| 1.4.0 | 2026-04-06 | Diff2HTML integration, score deletion, Material Design UI overhaul, cache enhancements |
| 1.3.2 | 2026-04-05 | Score architecture refactoring, review UI testing page, cache management, schema unification |
| 1.3.1 | 2026-03-31 | Multi-reviewer score support with UPSERT pattern, independent iteration tracking |
| 1.3.0 | 2026-03-29 | Project registry system, multi-app query support, virtual app_name architecture |
| 1.2.0 | 2026-03-25 | Enhanced score update endpoint, version management improvements, SQLAlchemy boolean query fixes |
| 1.0.1 | 2026-03-21 | Logging system, critical bug fixes, Pydantic v2 migration |
| 1.0.0 | 2026-03-21 | Initial release with core functionality |

## Upgrade Notes

### Breaking Changes in 1.0.1

#### 1. Logging System Integration
If you have custom logging configurations, you may need to merge them with the new centralized logging system:

```bash
# The logging system now requires PyYAML
pip install pyyaml>=6.0
```

#### 2. Database Configuration
The database connection pool configuration has changed. Update your `.env` file if needed:

```env
# Old configuration (if explicitly set)
DATABASE_POOL_CLASS=QueuePool  # No longer supported

# New behavior - automatic based on DATABASE_POOL_SIZE
DATABASE_POOL_SIZE=20  # Set to 0 to disable pooling
```

#### 3. Schema Validators
All Pydantic validators have been migrated to v2 syntax. If you have custom schemas:

```python
# Old (deprecated)
from pydantic import validator

@validator('field')
def validate_field(cls, v):
    return v

# New (required)
from pydantic import field_validator

@field_validator('field')
def validate_field(cls, v):
    return v
```

### Migration Guide

1. **Update dependencies**:
   ```bash
   pip install pyyaml>=6.0
   ```

2. **Run database migrations** (if applicable):
  ```bash
  alembic upgrade head
  ```

3. **Restart application** to pick up new logging configuration:
   ```bash
   uvicorn src.main:app --reload
   ```

4. **Verify logs** are being written correctly:
   ```bash
   tail -f logs/app.log
   tail -f logs/error.log
   ```

## Known Issues

- None at this time

## Contributors

- Core development and maintenance
- Bug fixes and feature enhancements

---

For more information about the logging system, see `src/conf/LOGGING_GUIDE.md`.

For API documentation, visit `/api/docs` when the application is running.

For deployment instructions, see `DEPLOYMENT_GUIDE.md` and `README.md`.
