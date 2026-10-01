## Why

The release notes page is a master-detail view: the navigator lists the releases (a page of ten) and the reading column renders **one** of them. A repository with a release train of dozens of versions can therefore only be read one version at a time - to review a quarter, a reader clicks through ten navigator entries, and to compare two versions they have to remember the first one. The page already fetches a whole page of releases (bodies included) in a single request, so the restriction is in the layout, not in the data.

A release page people know from GitHub reads the other way round: a paginated list of releases, each entry complete on its own (tag, title, date, author, notes, its own actions). That is what this change brings to the reading column.

## What Changes

- **The reading column lists every release of the current page**, each entry complete: title and tag, the latest / pre-release / draft badges, author and date, the released range, and the notes. Reading the page no longer requires a click per version.
- **Pagination moves into the reading column as well**: the same page state drives both columns, the pager is reachable from the notes themselves (bottom of the list) and from the navigator, and changing it anywhere reloads the page.
- **Every entry carries its own actions** (edit, publish, push, delete for the managing roles; export and copy for any reader; the provider link when the release has one), so a release can be acted on without selecting it first.
- **The navigator becomes a jump index**: clicking an entry scrolls the reading column to that release and marks it, instead of replacing the column and hiding the others.
- **The editor still takes over the column** when drafting or editing, and closing it returns to the list - that flow is unchanged.
- **The tags tab is untouched**: its column still shows the commits of the selected tag.

## Capabilities

### New Capabilities

- `release-note-list`: reading a page of releases as a list - every release of the current page rendered in full, the pagination that covers the whole set, the per-entry identity and actions, and the navigator as a jump index.

### Modified Capabilities

<!-- None: the reading of a single release is part of this capability (no spec under openspec/specs/ covers it today). -->

## Impact

- **Frontend only**: `frontend/src/views/releases/ReleaseNotesView.vue` (the reading column and the per-entry actions, the navigator click behaviour, a second pager bound to the shared page state) and three locale files (`en`, `zh-CN`, `zh-TW`).
- **No backend change**: `GET /release/notes` already returns the releases of a page with their bodies and the total; the page size and the pager already exist.
- **Tests**: the existing release-note view tests describe the single-release reading column (the preview stub, the header badges, the action buttons) and are updated to the list; new tests cover the multi-entry page, the jump index and the pager.
- **Related**: `add-release-note-export` (in flight) adds per-release export and copy actions - they are rendered inside each entry, so the two changes touch the same action row.
