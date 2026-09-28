## Why

The Release Notes page answers "what did this tag release?" by comparing the tag with the tag released just before it. That predecessor is currently guessed **in the browser**, from the tag list the page happens to hold:

- `ReleaseNotesView.loadRefs()` requests at most 200 tags, and `previousTagFor()` looks only inside that window.
- For any tag outside the window (the repository's earliest tags, or any tag whose older neighbour was not loaded) the predecessor is unknown, so `loadTagCommits()` sends `previous_version: undefined`.
- `ReleaseNoteService.generate_preview()` then falls back to `list_release_commits()`, which enumerates **every commit reachable from the tag** instead of a difference. On a multi-year repository that always reaches the cap and reports `truncated` — the message users see: *"The commit list reached Max Commits - older commits are not listed"*.

Two problems hide behind that warning, and neither is really about the repository being large:

1. **The panel is wrong, not just long.** When the predecessor is unknown the panel shows "full history of {tag}", i.e. everything reachable from the tag, not the commits the tag released. A maintenance tag in the middle of the history renders as if it had released years of unrelated work.
2. **It is the same defect the compare / check path just lost.** That work replaced "enumerate two capped commit sets and intersect them" with a provider difference. The notes scope still enumerates, so it still caps, and the cap is presented as a data problem instead of a question that was never answered.

The fix belongs on the server: the git provider already knows the tags and their revisions, so the release scope can be *resolved and verified* instead of guessed from a page-sized list.

## What Changes

- **New provider primitive** `list_tags_with_commits(project, repo, limit)`: one call returns every tag with its revision and date (Bitbucket Server `/tags` with `latestCommit`, Bitbucket Cloud `/refs/tags` with `target`, GitHub `/tags` with `commit`). Annotated tags are dereferenced by the platform, so a tag object's SHA is never mistaken for a commit.
- **Server-side release scope resolution.** Given a version tag, the previous release ref is resolved in a defined order: explicit input → **verified ancestor** (tags ordered by commit date, each candidate confirmed with one `contains_commit` call, bounded probe count) → **name-order neighbour** (server-side list, numeric-aware ordering — explicitly *unverified*) → **none** (a first release genuinely has no predecessor).
- **The response says which path was used.** `previous_version`, `previous_source`, `previous_verified` and `scope_reason` (`provided` / `resolved` / `first_release` / `unresolved`) travel with the preview, so the UI states the scope instead of guessing it.
- **Honest truncation.** A capped result is reported as "showing the newest N of M" for the `first_release` / `unresolved` fallback, and the fallback is only reachable in those two cases — never because a page-sized tag list ran out.
- **The notes page stops guessing.** The client-side `previousTagFor()` leaves the request path; the panel renders the resolved scope, and opening "Draft a release for this tag" prefills the previous tag from the resolution.
- **Resolution is cached** (per repository + tag) and degrades quietly: if the provider cannot list tags, the request still succeeds through the fallback with `scope_reason: unresolved`.

## Capabilities

### New Capabilities

- `release-note-scope`: how the released commits of a tag are scoped — resolving the previous release ref on the server, verifying it, reporting the provenance of the resolution, and keeping a truncated listing from being mistaken for a release scope.

### Modified Capabilities

<!-- None: no existing capability under openspec/specs/ covers the release note page. -->

## Impact

- **Providers**: `GitProviderBase` + `bitbucket_server` / `bitbucket_cloud` / `github_enterprise` gain `list_tags_with_commits()`; `contains_commit()` (added by `simplify-release-missing-check`) is reused for verification.
- **Backend services**: `ReleaseNoteService` gains release scope resolution (with Redis caching) and `generate_preview()` consumes it instead of the caller's guess.
- **API / schemas**: `ReleaseNotePreviewResponse` gains `previous_source`, `previous_verified` and `scope_reason`; `ReleaseNotePreviewRequest.max_commits` keeps its meaning as the render cap. The endpoint contract stays backward compatible (new fields are additive).
- **Frontend**: `ReleaseNotesView.vue` (tag commits panel, draft prefill, scope-aware warning), `frontend/src/api/releaseNotes.ts` types, three locale files.
- **No database migration**: the resolution is derived data, cached in Redis only. Persisting tag → revision belongs to `add-app-release-diff`.
- **Related changes**: reuses `contains_commit()` from `simplify-release-missing-check` and shares `list_tags_with_commits()` with `add-app-release-diff` (task 1 group), which should not implement it twice.
