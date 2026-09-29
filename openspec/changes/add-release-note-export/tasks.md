## 1. Document builder

- [ ] 1.1 Add `src/services/release_note_export.py` with `build_release_notes_document(releases, *, project_key, repository_slug, exported_at)` as a pure function over release rows
- [ ] 1.2 Write the document head: title naming the repository, summary line with the repository, the number of releases and the export date
- [ ] 1.3 Write one section per release: heading with the release name and tag, then the metadata bullets (tag, status, release date, author, pre-release)
- [ ] 1.4 State an empty body explicitly instead of leaving a gap, and separate sections with a horizontal rule (no front matter, so a body containing `---` stays harmless)
- [ ] 1.5 Add the suggested filename helper: one release vs several, a date stamp for a batch, sanitized to a safe character set
- [ ] 1.6 Unit tests: one release / several releases / draft and pre-release metadata / empty body / a body holding `---`, `##` and JIRA keys copied verbatim / newest first and stable across calls / filename sanitization for tags with `/`, `:` and spaces

## 2. Selection and endpoint

- [ ] 2.1 Add `ReleaseNoteService.export_notes()` selecting the requested releases by id or by the list filter, always scoped to the repository and ordered like `list_notes`
- [ ] 2.2 Ignore and report ids that no longer exist or belong to another repository
- [ ] 2.3 Enforce the export bound: more than 200 ids is a validation error, while a filtered set longer than the bound exports the newest 200 and reports that the document is not the whole set
- [ ] 2.4 Add `ReleaseNoteExportRequest` (either ids or the whole filtered set, mutually exclusive, ids capped) and `ReleaseNoteExportResponse` (filename, content, count, skipped ids, truncated)
- [ ] 2.5 Add `POST /release/notes/export` guarded by the same read permission as listing, rejecting an invalid selection
- [ ] 2.6 Endpoint tests: export by ids / export every published release with drafts excluded / empty selection rejected / contradictory selection rejected / too many ids rejected / read permission required / skipped ids reported / filtered set beyond the bound truncated / response carries the filename
- [ ] 2.7 Service tests: the document order equals the list order, the stored body reaches the document verbatim, the reported count matches the document

## 3. Page controls

- [ ] 3.1 Add `exportNotes()` to `frontend/src/api/releaseNotes.ts` with the request and response types
- [ ] 3.2 Add a `downloadMarkdown(content, filename)` and a shared `copyTextToClipboard(text)` helper next to the existing export utilities, and reuse them instead of the inline clipboard calls
- [ ] 3.3 Add the export selection to `ReleaseNotesView.vue`: a control per release row in the navigator, cleared when the repository changes
- [ ] 3.4 Add "select all (filtered)" honouring the active status filter, and an "export selected (N)" action that is unavailable while nothing is selected
- [ ] 3.5 Add "export markdown" to the detail header of the open release, exporting that release alone
- [ ] 3.6 Add "copy markdown" next to it for the open release, writing the same document to the clipboard and reporting platform refusal instead of appearing to succeed
- [ ] 3.7 Report the number of exported releases and mention the releases that were skipped
- [ ] 3.8 Add the new strings to `en`, `zh-CN` and `zh-TW` (select all, export selected, export one, copy one, copied, copy failed, skipped count)
- [ ] 3.9 Frontend tests: the exported ids follow the selection / exporting the open release sends that id / the action is unavailable with no selection / select all respects the status filter / a download is triggered with the suggested filename / copying writes the same document and confirms it / a refused clipboard is reported / skipped releases are reported to the user

## 4. Verification

- [ ] 4.1 Backend: full `pytest` suite, `ruff format --check` and `ruff check src tests`
- [ ] 4.2 Frontend: `vitest` suite and `vue-tsc --noEmit`
- [ ] 4.3 Render an exported document (one release and a batch of published ones) in a markdown viewer and confirm the sections, metadata and separators read correctly, and that a copied single release pastes identically
