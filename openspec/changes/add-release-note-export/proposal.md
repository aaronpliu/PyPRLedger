## Why

A release note can be read in the app, one version at a time, but it cannot be taken out of it. There is no export anywhere on the release notes page and no export endpoint for notes: the only export in the project is the repository comparison report (`frontend/src/utils/export/releaseReport.ts`, HTML + PNG), which answers a different question. Teams that publish what they wrote elsewhere - an internal wiki, a mail, an app store listing, a `CHANGELOG.md` in another repository - copy the markdown out of the editor by hand, once per version, and a release train of ten versions turns into ten copy/paste operations.

The material is already markdown (`ReleaseNote.body`), so the gap is **selection and packaging**, not rendering: which versions, in what order, wrapped in what document.

## What Changes

- **A backend export** (`POST /release/notes/export`) that returns one markdown document built from stored releases, with a suggested filename, the number of releases it holds, and an explicit report of anything it had to skip or cut.
- **Two selection modes**, validated as one or the other: explicit release ids (what the page has selected), or the whole filtered set (every published release of the repository, optionally drafts too). "Export every published version" must not require the browser to page through the list.
- **The document has one shape and one author.** The backend formats it - title, a summary block, one section per release with its metadata, the stored body verbatim - so the UI, an API consumer and CI produce byte-identical files.
- **Selection in the UI**: a checkbox per release in the navigator, "select all (filtered)" and "Export selected (N)" in the list header, plus "Export markdown" for the release that is open. The page reports how many releases were exported and warns when part of a selection could not be.
- **Markdown only**, verbatim bodies: the stored body is copied as it is, without rewriting JIRA keys or author mentions, so an export stays reproducible and diffable (linking them is a display concern, already handled on screen).
- **Bounded by construction**: one export holds at most 200 releases, and reaching that bound is reported instead of silently producing a partial document.

## Capabilities

### New Capabilities

- `release-note-export`: packaging the stored release notes of one or more chosen versions into a single markdown document - the selection contract, the document shape and ordering, the bounds and the reporting of what was skipped - plus the page controls that choose the versions.

### Modified Capabilities

<!-- None: the release note capabilities of previous changes only cover reading, drafting and publishing notes. -->

## Impact

- **Backend**: new export endpoint in `src/api/v1/endpoints/release_notes.py`; a document builder in `src/services/release_note_service.py` (or a small `release_note_export.py` next to it) kept as a pure function over `ReleaseNote` rows; new request/response schemas in `src/schemas/release_note.py`; a query that selects the requested releases by id or by the list filter.
- **Frontend**: `frontend/src/views/releases/ReleaseNotesView.vue` (selection state, header actions, per-release checkbox, export of the open release), `frontend/src/api/releaseNotes.ts`, a `downloadMarkdown` helper next to the existing export utilities, three locale files.
- **No migration, no new dependency**: the export reads what is already stored.
- **Permissions**: unchanged - exporting is reading, so it needs the same `release_note` read permission as listing.
- **Related**: the comparison report export stays where it is (it renders HTML/PNG from data the browser already holds); this change adds the text export the notes page was missing.
