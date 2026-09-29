## Context

What already exists around release notes:

| Piece | Where | Relevant property |
|---|---|---|
| Stored release | `src/models/release_note.py` | `tag_name`, `name` (title), `body` (markdown), `previous_tag`, `status` (draft / published), `is_prerelease`, `author`, `published_date`, `external_url` |
| List endpoint | `GET /release/notes` | newest first, `status` filter, `limit` ≤ 200 with `offset` paging, needs the `release_note` *read* permission; the newest published non pre-release row is flagged `is_latest` |
| Page | `frontend/src/views/releases/ReleaseNotesView.vue` | a navigator of releases (`.nav-item`) and of tags, paginated server-side (10 per page), plus a detail column that renders one release |
| Existing export | `frontend/src/utils/export/releaseReport.ts` | the *comparison* report: built in the browser from data it already holds, downloaded through a Blob, plus screenshots |

So the notes page holds children of one page of releases at a time, and the markdown that is worth exporting only exists on the server for the other pages.

## Goals / Non-Goals

**Goals:**

- Export one or many releases into **one markdown document**, with the versions chosen by the user.
- Produce the same document for every consumer: the page, an API client, a CI job.
- Deterministic ordering and metadata, and an honest report when something was skipped or cut.
- No migration, no new dependency, no change to how notes are stored or displayed.

**Non-Goals:**

- HTML / PDF / DOCX exports, or a zip of one file per release: one markdown file per export is the chosen shape, because a batch is read as a document rather than unpacked as an archive.
- Sending the document anywhere (mail, provider release, another repository) - this change only produces it.
- Rewriting the stored bodies: linkifying JIRA keys or author mentions (a display concern), reformatting, or re-generating notes from commits.
- Exporting what is currently being typed in the editor but has not been saved.
- Changing the notes list, the tags navigator or the comparison report.

## Decisions

### D1 - The backend formats the document; the browser downloads it

`POST /release/notes/export` returns `{filename, content, count, skipped_ids, truncated}` and the page downloads `content` through a Blob, the way `downloadReleaseReport` already does.

Rationale: the formatting rules (order, headings, metadata, separators) belong in one place; a document that only exists for consumers of our UI cannot be produced by a script; and a text document is exactly what an API should hand out. The browser also cannot assemble it while holding one page of releases, unless it pages through the list itself.

### D2 - Two selection modes, one of them required

```jsonc
{ "project_key": "...", "repository_slug": "...",
  "ids": [12, 9, 4] }          // exactly the versions the page selected (1..200)
{ "select_all": true, "status": "published" }   // every matching release of the repository
```

The two are mutually exclusive (a model validator rejects a request with neither, or with both). `ids` is the primary contract - the user chooses versions - while `select_all` covers "export every published version" without asking the browser to page through the list.

### D3 - Ordering matches the list, so the document is what the user saw

Newest first, by `coalesce(published_date, updated_date) desc` - the exact expression `list_notes` uses today. A draft has no `published_date`, so the fallback keeps drafts in a stable position instead of pushing them to one end. Newest at the top is deliberate: the newest release is what a reader looks for first, and the document then reads in the same order as the page it came from.

### D4 - One document shape

```md
# Alpha API - release notes

> ALPHA/alpha-api - 3 releases - exported from PyPRLedger on 2026-09-29

## Login hardening (v1.2.0)

- Tag: `v1.2.0`
- Status: published
- Released: 2026-09-20 10:00
- Author: Jane Doe
- Pre-release: no

<the stored body, verbatim>

---

## Session timeout (v1.1.0)
...
```

- A section per release, separated by `---`, so a document can be read as a whole and split mechanically.
- The metadata is a bullet list rather than YAML front matter: a note body may itself contain `---`, and sections must not depend on a marker the content can produce.
- An empty body says so explicitly (`_No notes were written for this release._`) instead of leaving a gap that reads like a bug.

### D5 - Bodies are copied verbatim

No JIRA linkification and no author-mention rewriting, although the page does both when it renders. The stored body is the source of truth: rewriting it would make the export depend on the local JIRA settings, stop being diffable against the stored notes, and make two exports of the same release differ.

### D6 - Bounded, and the bound is reported

- `ids` longer than 200 is a validation error: the caller chose them, so it can choose fewer.
- `select_all` caps at 200 releases (newest first) and returns `truncated: true`, so a partial document is never mistaken for the whole history.

Worst case size is bounded by the same cap (200 × the 60000-character body limit); if that ever becomes a problem the response can be streamed as `text/markdown` without changing the selection contract.

### D7 - A stale selection is reported, not fatal

Ids that no longer exist or belong to another repository are ignored and returned in `skipped_ids`. A page left open while a release was deleted must not fail a bulk export, and the user still learns that one of the chosen versions is missing.

### D8 - Suggested filename

```
releasenotes-ALPHA-alpha-api-v1.2.0.md          (one release)
releasenotes-ALPHA-alpha-api-3-releases-20260929.md   (several)
```

Both are sanitized to `[A-Za-z0-9._-]` so a tag holding `/`, `:` or a space cannot produce an invalid filename. The browser uses the returned name; the server owns it so an API client gets the same one.

### D9 - Exporting reads

The endpoint requires the same `release_note` read permission as listing, touches no stored row, and does not include the editor buffer - only saved releases can be exported.

### D10 - The page gains selection, not a second list

- A checkbox per release row in the navigator (the row keeps its click-to-select behaviour), a "select all (filtered)" control in the list header honouring the current status filter, and an "Export selected (N)" action next to it, disabled while nothing is selected.
- The detail header of an open release gets "Export markdown", which exports that one release - the single-version half of the feature, without going through the navigator.
- The selection lives in page state and is cleared when the repository changes; the export action reports the number of releases written and mentions anything skipped.

### D12 - The open release can also be copied to the clipboard

Besides the download, the release that is currently open SHALL offer a copy action that puts the
same document on the clipboard, because pasting one release's notes into a wiki or a ticket is the
common next step. The copy uses the same server-built document as the download - never the editor
buffer - so the two cannot disagree.

The clipboard is only offered for a single release: a batch is a file, not something to paste. The
platform API is not always available (a non-secure context, a denied permission), so a failed copy
must report it instead of looking like it worked; the download stays available as the fallback. The
frontend gains one shared `copyTextToClipboard` helper next to the download helper - today the text
copy is repeated inline in several views, while only an image copy exists in `utils/screenshot.ts`.

### D11 - No migration, no new dependency

The export is a read over existing rows; nothing is stored about it.

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| A bulk export of long bodies produces a large response | The 200-release cap bounds it; the response can later be streamed as `text/markdown` without touching the selection contract |
| `select_all` silently exports a subset on a repository with more than 200 releases | The cap is applied deterministically (newest first) and reported as `truncated`; the UI says it |
| The selection on screen drifts from the database (a release deleted concurrently) | Skipped ids are reported and the export still succeeds |
| Drafts leak into a published change log | Drafts are only exported when they are selected or when `select_all` is asked for them explicitly with `status: draft` / no filter; each section states its status |
| A body containing `---` or `##` breaks the section structure | Metadata is a bullet list, not front matter, and bodies are copied verbatim into a section that starts with its own `##` heading; the separator is a plain horizontal rule, so nested content cannot be mistaken for a section |
| Users expect the export to match the *rendered* page (linked tickets, avatars) | Documented as verbatim bodies; the difference is a display concern that the page already handles |
| The clipboard API is unavailable (non-secure context) or denied | The copy action reports the failure and says the download can be used instead |
