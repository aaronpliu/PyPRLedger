## Context

The release notes page is two columns: a navigator (`Column 1`) holding the releases of the current page and, on a second tab, the repository's tags; and a reading column (`Column 2`) whose header describes the current selection and whose body renders either the editor, the commits of the selected tag, or the selected release's notes.

What the page already holds:

| Piece | State |
|---|---|
| The releases of the page | `notes` - `GET /release/notes` with `limit` / `offset`, **bodies included**, newest first |
| The total | `notesTotal` (server), driving the pager |
| Page state | `notesPage`, `notesPageSize` (default 10, sizes 5 / 10 / 20 / 50), a pager in the navigator only |
| Selection | `selectedId` / `selectedNote` - the one release the reading column shows |
| Badges | latest / pre-release / draft, rendered in the reading column's header from the selection |
| Actions | edit / publish / push / delete (managing roles), export / copy (any reader), the provider link - in the reading column's header |

So a page of ten releases is already in memory when the page loads; what the layout does with it is the subject of this change.

## Goals / Non-Goals

**Goals:**

- Read a whole page of release notes without a click per version, and without losing the orientation the navigator gives.
- Keep a release actionable from where it is read.
- Cover the whole set with pagination that is reachable from the notes themselves.
- No backend change, no new dependency, and the tags tab and the editor flow left as they are.

**Non-Goals:**

- Merging the two columns into one (the navigator stays, as an index).
- Changing the tags tab, the editor, or the export/copy behaviour added by `add-release-note-export`.
- Collapsing long notes, full-text search inside a page, or virtualising the list.
- Reading releases across pages in one scroll (pagination stays the boundary).

## Decisions

### D1 - The reading column renders the page of releases it already has

`notes` is a page of releases with their bodies, ordered newest first, fetched in one request. The column renders every entry instead of `selectedNote`, so no additional request is needed and the two columns can never disagree about which releases the page holds.

### D2 - One page state, two pagers

`notesPage` / `notesPageSize` stay the single source of truth; a second `el-pagination` at the bottom of the reading column binds to the same state with the same layout (`total, sizes, prev, pager, next`) and the same page sizes. Changing either pager reloads the page and both stay in step, because there is only one value to change. **Both pagers stay**: the navigator keeps the one it has (a reader who works from the index should not have to cross the page to change page), and the reading column gets its own so the notes can be paged from where they are read.

### D3 - Each entry is complete on its own

```
┌──────────────────────────────────────────────────────────────┐
│ Login hardening   [v1.2.0] [Latest] [Pre-release] [Draft]    │  heading + badges
│                          Edit · Publish · Push · Delete ·     │  actions
│                          Export markdown · Copy markdown      │
│ @alice · 2026-09-20 · v1.1.0...v1.2.0                        │  meta
│                                                              │
│ <the notes>                                                  │  body
└──────────────────────────────────────────────────────────────┘
```

The badges and the actions move from the column header into the entry, so they describe the release they sit on rather than "the selection". The column header becomes a page-level title ("Releases" with the count of the page) - it describes a list, not a selection.

### D4 - The navigator jumps instead of replacing

Clicking a navigator entry scrolls the reading column to that release and marks it, instead of hiding the other entries. `selectedId` keeps its meaning as "the release in focus", which the editor and the provider link use; entries carry an anchor so the scroll can find them, and the scroll happens after the render (`nextTick`) because the render height of the notes is only known then.

### D5 - The editor still owns the column

While the editor is open the column renders the form (as today); closing it returns to the list of entries. Drafting a new release, editing one, and publishing keep working from a navigator entry, from a draft button, or from an entry's own action row.

### D6 - The tags tab is out of scope

Its column renders the commits of a tag, which is a different question with a different pagination (the tags page). Only the status of the editor / selection state that the two tabs share is left as it is.

### D7 - A page must not end up empty

Deleting the last release of a page (or shrinking the page size while on a later page) can leave `notesPage` beyond the last page that has releases. After a delete or a page-size change the page is clamped to the last page that still holds releases, so the reader never lands on an empty list while releases exist.

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| Ten notes rendered in full is heavier than one (long bodies, markdown rendering) | The page size is the reader's control (5 / 10 / 20 / 50); a collapse for long notes is a follow-up (open question), and the request count does not change |
| Scroll-to-entry lands wrong because the notes render asynchronously | The scroll runs after `nextTick` and targets an element anchor, not an offset |
| The column header loses the badges a reader learned to look at | The badges are per entry now (the release they describe), which is what GitHub does; the page-level header gains the count instead |
| Existing tests assert the single-release column (preview stub, header badges, action buttons) | They are updated with the layout, and the new tests assert the same behaviour through the entries |
| `selectedId` becomes "in focus" rather than "displayed", which is a subtle semantic change for the editor and the provider link | Both only ever act on one release, and an entry's own actions pass the release explicitly instead of relying on the selection |

### D8 - Long notes are collapsed behind a "Show more"

A page of full notes is heavy to read and to render when a few of them are long, so an entry whose
notes are long is rendered clamped (`max-height` with a fade at the bottom) with a control that
expands it. Expanding and collapsing is per entry, is not persisted, and resets when the page
changes; collapsing never touches what is stored, and an export still carries the whole body
(the document is built by the backend).

The threshold is decided from the note's text (more than 20 lines or more than 1500 characters),
not from the rendered height. A measured overflow check (`scrollHeight > clientHeight`) would be
more precise in a browser, but it cannot be tested - the test environment has no layout engine, so
`scrollHeight` is always 0 there and the control would silently never appear - and it would depend
on the renderer and the font. A rule that can be asserted beats a rule that is marginally more
accurate.
