## Context

The Release Notes page has two things to say about a tag: the note that was written for it, and the commits it released. The second one is the tag → commits mapping shown in the tags tab, and it is produced by `POST /release/notes/preview`.

`ReleaseNoteService.generate_preview()` has two paths today:

| `previous_version` | What it does | Cost / limit |
|---|---|---|
| given | `ReleaseDiffService.compare_releases(source=previous, target=version)` and take `added_commits` — a provider difference | bounded by `max_commits`, small by construction |
| missing | `ReleaseDiffService.list_release_commits(ref)` → `_fetch_release_commits(base_ref=None)` → `list_commits_until` — **every commit reachable from the tag** | capped at `max_commits` (500), `truncated` reported |

Which path runs is decided by the browser: `ReleaseNotesView.loadRefs()` requests at most 200 tags, and `previousTagFor()` returns the next entry of that (numerically descending) window. Outside the window there is no predecessor, so the second path runs and the panel shows "full history of {tag}" plus the *"The commit list reached Max Commits - older commits are not listed"* warning.

So the warning is a symptom: the scope question was never answered, and an unbounded enumeration was capped and presented as the answer. The same shape of defect was removed from the compare / check path in `simplify-release-missing-check`, where a provider difference replaced two capped commit sets.

Relevant existing primitives:

- `BaseGitProvider.list_refs()` — tag / branch **names** only.
- `BaseGitProvider.compare_commits()` / `compare_commits_complete()` — differences.
- `BaseGitProvider.contains_commit(ref, commit)` — one-call ancestry test (added by `simplify-release-missing-check`).

There is no tag → revision call yet, so the server cannot currently order tags by anything but their names.

## Goals / Non-Goals

**Goals:**

- The tag → commits panel shows the commits a tag released on repositories with years of history and hundreds of tags, without hitting a cap.
- A capped enumeration can no longer masquerade as a release scope: when the scope cannot be resolved, the response says so and the UI states it.
- One authority for the scope (the server), so the panel and the generated note body agree with each other.
- Predictable cost: a bounded number of provider calls per tag, cached, with a quiet fallback when the provider is unavailable.

**Non-Goals:**

- Patch-id / cherry-pick equivalence (a cherry-picked commit still counts as not released by the tag).
- Raising the tag picker's 200-entry cap or building a full tag browser.
- Persisting tag → revision in the database; that belongs to `add-app-release-diff`.
- Changes to the note body format or to the stored note fields.

## Decisions

### D1 - Provider primitive: `list_tags_with_commits()`

One call per repository returns every tag with its revision and date:

```
list_tags_with_commits(project_key, repository_slug, limit) ->
    [{"name": str, "sha": str, "date": int | None, "is_annotated": bool | None}]
```

| Provider | Call | Revision source |
|---|---|---|
| Bitbucket Server | `GET /projects/{k}/repos/{r}/tags` (no `orderBy`: we order ourselves) | `latestCommit` (already a commit) |
| Bitbucket Cloud | `GET /repositories/{ws}/{r}/refs/tags` | `target.hash` (dereferenced) |
| GitHub Enterprise | `GET /repos/{o}/{r}/tags` (paged) | `commit.sha`; when the payload points at a tag object, resolve with `/commits/{ref}` |

Annotated tags are dereferenced by the platform, so the tag object's own SHA is never mistaken for a commit. The provider's ordering is *not* relied upon: the resolver does its own ordering, and a tag without a date is ordered by name. Names are de-duplicated and trimmed the way `_ref_names()` / `_clean_refs()` already do.

### D2 - Resolution order (one authority, explicit provenance)

```
explicit previous_version  (caller-supplied, or the stored note's previous_tag)
   ↓ not given
verified ancestor          candidates ordered by commit date desc; the first one that is an
                           ancestor of the version wins (contains_commit, budget scaled by tag count)
   ↓ none found
name-order neighbour       numeric-aware descending order over the server-side tag list; UNVERIFIED
   ↓ no older tag at all
none                       the tag is the first release of its line
```

Rationale: backports and merged lines make "closest date" and "previous name" both imperfect. Verifying costs one cheap call in the common case and removes the guess; when verification cannot succeed (tags on diverged lines), the name-order neighbour is still a better answer than "the whole history", as long as the response marks it unverified.

### D3 - Verification is the existing ancestry test, with a budget that scales

`contains_commit(ref=version, commit=candidate.sha)` — the primitive already used to narrow comparisons. The walk starts at the newest candidate by commit date (a predecessor is usually recent), so the common case costs one probe.

The probe budget scales with the repository's tag count, because the number of probes needed grows with how many tags sit on *other* lines (backports, long-lived branches), not with the length of one line:

```
probe_limit = min(SCOPE_PROBE_MAX, max(SCOPE_PROBE_MIN, tag_count // 5))
              defaults: SCOPE_PROBE_MIN = 4, SCOPE_PROBE_MAX = 20
```

| Tags in the repository | Probe budget | Reasoning |
|---|---|---|
| 12 | 4 | one or two lines; a handful of probes is already generous |
| 60 | 12 | several lines → more recent non-ancestor tags to skip over |
| 200+ | 20 | capped: beyond this the name-order fallback (rendered as unverified) is a better use of the request's latency budget |

The budget is per request (not persisted), and reaching it falls through to the name-order neighbour rather than failing.

### D4 - Compare by revision, label by name

The scope is a `(ref, sha)` pair on both ends. When a revision is known, the difference is asked with the **sha**: it keeps a tag that is moved later from silently redefining what a scope used to contain, and it makes the compared range reproducible. The tag name stays the human label, and the short revision is shown next to it (`v3.9.0 (3f2a1b) → v3.10.0 (9d4c8e)`) so a moved tag is visible rather than inferred. Both revisions come from the tag listing the resolver already holds, so displaying them costs no extra call.

### D5 - Response contract (additive)

```
previous_version     resolved predecessor (may differ from what the caller sent)
previous_sha         revision the predecessor was pinned to (when known)
version_sha          revision the released tag was pinned to (when known)
previous_source      explicit | ancestor | name_order | none
previous_verified    true only for explicit / ancestor
scope_reason         provided | resolved | first_release | unresolved
commit_count         exact for a resolved scope (a difference); a LOWER BOUND for the fallback
truncated            the rendered list was capped at max_commits (a display limit)
```

The distinction between "the list was trimmed for display" and "the scope is unknown" is the point of the change; the fields are additive so existing clients keep working.

### D6 - The full-history fallback is fenced, not deleted

A first release genuinely has no predecessor, so `list_release_commits()` stays — but it is only reachable when `scope_reason` is `first_release` or `unresolved`. In those cases the panel must say "no earlier tag" (or "the previous tag could not be determined"), and a cap there is presented as "showing the newest N of M", not as a data problem.

### D7 - Caching and degradation

- Redis key: `release_note_scope:{provider}:{project}:{repo}:{tag}`, TTL-bounded; `refresh` in the preview request bypasses it (mirrors the ref-listing behaviour).
- The resolution is derived data: no DB table, and it does not touch the compare / check caches.
- Provider failure while listing tags is logged and degraded to `unresolved` (never a 5xx for the notes page).

### D8 - Frontend stops guessing

- `previousTagFor()` leaves the request path: `loadTagCommits()` no longer decides the scope from a page-sized list.
- The panel renders `previous_version` / `scope_reason` from the response, with copy per reason (range / first release / unresolved), and the truncation alert only when the rendered list was capped.
- **Short revisions are shown next to the refs** in the range label (`v3.9.0 (3f2a1b) → v3.10.0 (9d4c8e)`), and a missing revision is simply omitted rather than rendered empty.
- **An unverified resolution raises a warning** in the panel: it is a legitimate answer (the scope is still used), but the user must know it was inferred from tag order rather than proven by ancestry. The warning names the ref it inferred and keeps the form field editable, so it can be corrected.
- "Draft a release for this tag" prefills `previous_tag` from the same resolution, so the generated body uses the verified scope too.

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| Backported tags carry newer commit dates than the release they are based on, so a date-ordered walk may probe several candidates | Probe budget scaled by tag count (`min(20, max(4, tags // 5))`), name-order fallback, and `previous_source` / `previous_verified` exposed so the UI can say the scope was inferred |
| Diverged lines: the "previous tag by name" can sit on another line | Ancestry verification runs first and therefore wins in exactly this case; when it degrades to the name order, the panel warns instead of presenting it as fact |
| Extra provider calls (tag listing + up to the probe budget) | One listing + usually one probe; the worst case is bounded by `SCOPE_PROBE_MAX` (20) and the resolution is cached per repository + tag |
| A tag is moved after the resolution | The difference is asked with the resolved revisions on both ends and they are displayed, so a stale or moved scope is visible instead of silently different |
| Providers disagree on tag paging, ordering, and whether a date is present (GitHub returns 100 per page; Cloud may omit a date) | The primitive pages through the shared helper, normalizes the shape, and orders by name when a date is missing |
| The resolved scope differs from what the user expects (e.g. an unverified name-order neighbour) | The unverified case is a panel warning, the short revisions are visible, and the form field stays editable |
