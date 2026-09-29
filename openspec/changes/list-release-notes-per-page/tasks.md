## 1. The reading column renders the page

- [ ] 1.1 Render every release of the current page in the reading column instead of the selected one, each as its own entry
- [ ] 1.2 Give each entry its identity: release name and tag as the entry heading, plus the latest / pre-release / draft badges that apply to it
- [ ] 1.3 Move the per-release meta into the entry (author with avatar, released or updated date, released range) and keep the notes below it
- [ ] 1.4 Turn the column header into a page-level title (the number of releases on the page) so it no longer describes a selection
- [ ] 1.5 Collapse the notes of a long entry behind an expand control, decided from the note's text (over 20 lines or over 1500 characters) so the rule is testable, with the clamp and fade in CSS
- [ ] 1.6 Keep the loading skeleton and the empty state, and cover a repository without releases
- [ ] 1.7 Add the new strings to `en`, `zh-CN` and `zh-TW` (page title with the count, show more, show less)

## 2. Per-entry actions

- [ ] 2.1 Move the release actions from the column header into each entry: edit, publish, push, delete for the managing roles, the provider link when the release has one
- [ ] 2.2 Put the export and copy actions of `add-release-note-export` in the entry as well, so a reader can act on any visible release
- [ ] 2.3 Pass the entry's release explicitly to those actions instead of reading the selection

## 3. Pagination

- [ ] 3.1 Add a pager to the reading column bound to the same page and page size as the navigator, with the same layout and page sizes, and keep the navigator's pager as it is
- [ ] 3.2 Make sure both pagers stay in step and that changing either reloads the page once
- [ ] 3.3 Clamp the page after a delete and after a page-size change so a page with no releases is never shown while releases exist

## 4. The navigator as a jump index

- [ ] 4.1 Anchor each entry so the navigator can target it
- [ ] 4.2 On activating a navigator entry, load its page when needed and scroll the reading column to that entry after the render, marking it as the release in focus
- [ ] 4.3 Keep the editor's use of that focus (the provider link and the editor act on it) working when the entry is not on the current page

## 5. Tests and verification

- [ ] 5.1 Update the existing release-note view tests that describe the single-release column (preview stub, header badges, action buttons) to the entry list
- [ ] 5.2 New tests: several entries rendered with their notes / badges per entry / an action on an entry that is not in focus / the reading column's pager reloads the page / the navigator scrolls to an entry instead of replacing the column / a long note is collapsed and expands on demand while a short one is not / a repository without releases / deleting the last release of a page clamps the page
- [ ] 5.3 Frontend: `vitest` suite and `vue-tsc --noEmit`
- [ ] 5.4 Confirm on a repository with several pages of releases that a page reads as a list, that the pager works from either column, that long notes expand, and that the tags tab is unaffected
