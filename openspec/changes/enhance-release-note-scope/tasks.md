## 1. Provider primitive: tags with revisions

- [x] 1.1 Add `list_tags_with_commits(project_key, repository_slug, limit)` to `BaseGitProvider` documenting the normalized entry shape (`name`, `sha`, `date`, `is_annotated`), the annotated-tag rule (never store the tag object id) and the "ordering is not release order" caveat
- [x] 1.2 Implement it for Bitbucket Server (`/tags`, `latestCommit` + `type` + `latestCommitTimestamp`)
- [x] 1.3 Implement it for Bitbucket Cloud (`/refs/tags`, `target.hash` / `target.date`)
- [x] 1.4 Implement it for GitHub Enterprise (`/tags`, paged; the listing already reports the commit an annotated tag points to)
- [x] 1.5 Provider tests with mocked transport: paging beyond one page, annotated vs lightweight tag, tag without a date, blank / duplicated names dropped
- [x] 1.6 Note in the provider docstring that `add-app-release-diff` reuses this primitive instead of adding a second one

## 2. Release scope resolver

- [x] 2.1 Add `src/services/release_note_scope_service.py` with a `ReleaseScope` result (`previous_ref`, `previous_sha`, `version_sha`, `source`, `verified`, `reason`)
- [x] 2.2 Resolve in the defined order: explicit → verified ancestor (candidates by commit date desc, one `contains_commit` per candidate) → name-order neighbour → none
- [x] 2.3 Scale the probe budget with the repository's tag count: `min(SCOPE_PROBE_MAX, max(SCOPE_PROBE_MIN, tag_count // 5))` with defaults 20 / 4, and fall through to the name order when the budget is exhausted
- [x] 2.4 Implement the version-aware name comparator server-side (numeric-aware, descending) over the provider's full tag list, used only by the unverified fallback
- [x] 2.5 Cache the resolution in Redis keyed by provider + project + repository + tag, with a TTL constant and a `refresh` bypass (an unresolved result is deliberately not cached)
- [x] 2.6 Degrade on provider failure: log, return the unresolved result, never raise to the notes endpoint
- [x] 2.7 Unit tests for the selection logic (pure): first candidate is an ancestor / ancestor found on a later probe / no candidate is an ancestor → name order / single tag → first release / empty tag list → unresolved / probe budget exhausted falls through
- [x] 2.8 Tests for the scaled budget: a repository with many tags probes more candidates than one with few, and never exceeds `SCOPE_PROBE_MAX`
- [x] 2.9 Service tests with a fake provider: ancestor path reports `verified`, name-order path reports unverified, provider failure reports unresolved, cache hit avoids the tag listing, `refresh` bypasses the cache

## 3. Preview integration

- [x] 3.1 Extend `ReleaseNotePreviewResponse` with `previous_sha`, `version_sha`, `previous_source`, `previous_verified` and `scope_reason`, documenting each value
- [x] 3.2 `generate_preview()` calls the resolver when no previous version is supplied (an explicit one keeps precedence) instead of relying on the caller's guess
- [x] 3.3 Fence the full-history fallback to `first_release` / `unresolved`, and document `commit_count` as exact for a resolved scope and a lower bound for the fallback
- [x] 3.4 Ask the difference with the resolved revisions on both ends when they are known, keeping the tag names as the labels
- [x] 3.5 Tests: preview resolves a predecessor with no client input / labels `first_release` / labels `unresolved` / an explicit predecessor wins / the fallback reports a lower-bound count when trimmed / the difference is requested with the resolved revisions

## 4. Release notes UI

- [x] 4.1 Update the `releaseNotes` API types for the new preview fields
- [x] 4.2 `loadTagCommits()` stops sending a client-guessed predecessor (the server resolves it) and stores the scope that came back
- [x] 4.3 Render the panel scope from the response: the range with its provenance when resolved, "no earlier tag" for a first release, "previous tag could not be determined" for an unresolved scope
- [x] 4.4 Show the short revision next to each ref of the range (omitted when unknown)
- [x] 4.5 Warn in the panel when the scope was inferred by tag order instead of verified by ancestry, while still using it
- [x] 4.6 Show the trimming notice only when the rendered list was capped, phrased as a display limit (first N of M) - with a separate wording for a capped scan that trimmed nothing
- [x] 4.7 Prefill the draft form's previous tag from the same resolution when opening "Draft a release for this tag"
- [x] 4.8 Add the new strings to `en`, `zh-CN` and `zh-TW` (range with revisions, inferred-scope warning, first release, unresolved, trimming notice)
- [x] 4.9 Tests: resolved scope label with revisions, inferred-scope warning, first-release label, unresolved label, trimming notice only when capped, draft prefill, and no request relies on the client tag window

## 5. Verification

- [x] 5.1 Backend: full `pytest` suite (293 passed), `ruff format --check` and `ruff check src tests`
- [x] 5.2 Frontend: `vitest` suite (161 passed) and `vue-tsc --noEmit`
- [ ] 5.3 Confirm on a repository with hundreds of tags and years of history that a tag outside any client-side window shows its release scope (no cap warning), that a tag whose predecessor could only be inferred raises the warning, and that a genuine first release is labelled as such
