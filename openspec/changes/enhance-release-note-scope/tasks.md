## 1. Provider primitive: tags with revisions

- [ ] 1.1 Add `list_tags_with_commits(project_key, repository_slug, limit)` to `GitProviderBase` documenting the normalized entry shape (`name`, `sha`, `date`, `is_annotated`), the annotated-tag rule (never store the tag object id) and the "ordering is not release order" caveat
- [ ] 1.2 Implement it for Bitbucket Server (`/tags?orderBy=MODIFICATION`, `latestCommit`)
- [ ] 1.3 Implement it for Bitbucket Cloud (`/refs/tags`, `target.hash` / `target.date`)
- [ ] 1.4 Implement it for GitHub Enterprise (`/tags`, paged; resolve an annotated tag object through `/commits/{ref}`)
- [ ] 1.5 Provider tests with mocked transport: paging beyond one page, annotated vs lightweight tag, tag without a date, blank / duplicated names dropped
- [ ] 1.6 Note in the provider docstring that `add-app-release-diff` reuses this primitive instead of adding a second one

## 2. Release scope resolver

- [ ] 2.1 Add `src/services/release_note_scope_service.py` with a `ReleaseScope` result (`previous_ref`, `previous_sha`, `version_sha`, `source`, `verified`, `reason`)
- [ ] 2.2 Resolve in the defined order: explicit → verified ancestor (candidates by commit date desc, one `contains_commit` per candidate) → name-order neighbour → none
- [ ] 2.3 Scale the probe budget with the repository's tag count: `min(SCOPE_PROBE_MAX, max(SCOPE_PROBE_MIN, tag_count // 5))` with defaults 20 / 4, and fall through to the name order when the budget is exhausted
- [ ] 2.4 Implement the version-aware name comparator server-side (numeric-aware, descending) over the provider's full tag list, used only by the unverified fallback
- [ ] 2.5 Cache the resolution in Redis keyed by provider + project + repository + tag, with a TTL constant and a `refresh` bypass
- [ ] 2.6 Degrade on provider failure: log, return the unresolved result, never raise to the notes endpoint
- [ ] 2.7 Unit tests for the selection logic (pure): first candidate is an ancestor / ancestor found on a later probe / no candidate is an ancestor → name order / single tag → first release / empty tag list → first release / probe budget exhausted falls through
- [ ] 2.8 Tests for the scaled budget: a repository with many tags probes more candidates than one with few, and never exceeds `SCOPE_PROBE_MAX`
- [ ] 2.9 Service tests with a fake provider: ancestor path reports `verified`, name-order path reports unverified, provider failure reports unresolved, cache hit avoids the tag listing, `refresh` bypasses the cache

## 3. Preview integration

- [ ] 3.1 Extend `ReleaseNotePreviewResponse` with `previous_sha`, `version_sha`, `previous_source`, `previous_verified` and `scope_reason`, documenting each value
- [ ] 3.2 `generate_preview()` calls the resolver when no previous version is supplied (an explicit one keeps precedence) instead of relying on the caller's guess
- [ ] 3.3 Fence the full-history fallback to `first_release` / `unresolved`, and document `commit_count` as exact for a resolved scope and a lower bound for the fallback
- [ ] 3.4 Ask the difference with the resolved revisions on both ends when they are known, keeping the tag names as the labels
- [ ] 3.5 Tests: preview resolves a predecessor with no client input / labels `first_release` / labels `unresolved` / an explicit predecessor wins / the fallback reports a lower-bound count when trimmed / the difference is requested with the resolved revisions

## 4. Release notes UI

- [ ] 4.1 Update the `releaseNotes` API types for the new preview fields
- [ ] 4.2 `loadTagCommits()` stops sending a client-guessed predecessor (the server resolves it) and stores the scope that came back
- [ ] 4.3 Render the panel scope from the response: the range with its provenance when resolved, "no earlier tag" for a first release, "previous tag could not be determined" for an unresolved scope
- [ ] 4.4 Show the short revision next to each ref of the range (omitted when unknown)
- [ ] 4.5 Warn in the panel when the scope was inferred by tag order instead of verified by ancestry, while still using it
- [ ] 4.6 Show the trimming notice only when the rendered list was capped, phrased as a display limit (first N of M) rather than a repository problem
- [ ] 4.7 Prefill the draft form's previous tag from the same resolution when opening "Draft a release for this tag"
- [ ] 4.8 Add the new strings to `en`, `zh-CN` and `zh-TW` (range with revisions, inferred-scope warning, first release, unresolved, trimming notice)
- [ ] 4.9 Tests: resolved scope label with revisions, inferred-scope warning, first-release label, unresolved label, trimming notice only when capped, draft prefill, and no request relies on the client tag window

## 5. Verification

- [ ] 5.1 Backend: full `pytest` suite, `ruff format --check` and `ruff check src tests`
- [ ] 5.2 Frontend: `vitest` suite and `vue-tsc --noEmit`
- [ ] 5.3 Confirm on a repository with hundreds of tags and years of history that a tag outside any client-side window shows its release scope (no cap warning), that a tag whose predecessor could only be inferred raises the warning, and that a genuine first release is labelled as such
