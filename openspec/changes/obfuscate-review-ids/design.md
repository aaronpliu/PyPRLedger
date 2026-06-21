## Context

The system exposes raw sequential integer primary keys (`id: int`) as user-facing identifiers for reviews, scores, and other entities. These IDs appear in table columns, detail pages, browser URLs, confirmation dialogs, and the associate-review search. Because they are auto-increment integers, they leak data volume/growth and enable trivial ID enumeration.

The associate-review feature complicates obfuscation: users currently type a numeric review ID to find and link reviews. Switching to an opaque hash would make this painful to type, so the association UX must change simultaneously.

The project already has `python-jose[cryptography]` (Fernet available) and Redis, but we choose `hashids` as the lightest-weight option that satisfies the requirements.

## Goals / Non-Goals

**Goals:**
- Replace all user-facing display of raw DB IDs with opaque encoded strings for reviews
- Maintain full reversibility — the system can always decode public_id → real_id without DB lookup
- Change the associate-review search from "type numeric ID" to "search by PR info" (project key, repo, PR number)
- Add zero database overhead — no migrations, no new columns, no indexes
- Keep backward compatibility — old numeric ID endpoints still work during transition
- Design for extension: other entities (scores, users, rules) should require minimal effort

**Non-Goals:**
- Non-deterministic IDs (UUID-style) — not required by internal policy; hashids determinism is acceptable
- Real-time ID rotation or key rotation — salt is static once set
- Full-text search for association — PR info search is sufficient for MVP
- Changing internal API calls between microservices — public_id is for user-facing boundaries only

## Decisions

### Decision 1: Use `hashids` for encoding

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| **Hashids** | ~15 lines, no DB, reversible, short output, URL-safe | Deterministic, not cryptographic | ✅ **Chosen** |
| Fernet encryption | Cryptographically strong | Long tokens (~60 chars), key management overhead | ❌ Overkill for internal policy |
| UUID column | Truly unpredictable | Migration, new column, index, storage | ❌ Too heavy for current requirements |
| Simple bijective math | Trivial to implement | Easily reverse-engineered | ❌ Fails compliance |

### Decision 2: Prefix-based entity scoping (`rev_`, `sco_`, etc.)

Encoded IDs use a 3-letter prefix so you can identify the entity type at a glance:

```
review:  rev_kM8xP31R
score:   sco_aB3xK7mQ
user:    usr_X9nC2V5b
rule:    rule_4kLp8nW2
```

The prefix is stripped before decoding. This prevents collisions between entity types (a review with id=42 and a score with id=42 would otherwise produce the same hash).

### Decision 3: Association search by PR info, not by ID

The current association dialog searches by numeric review ID only. We replace this with a text search that finds reviews by:

- Project key (e.g., `FE-Proj`)
- Pull request ID (e.g., `PR-123`)
- Repository slug (e.g., `PROJ-A`)
- PR user display name

The user selects from a dropdown list. The selected option's value is the real review ID (passed internally to the API). The user never sees or types any ID — neither real nor obfuscated.

### Decision 4: Add `by-public-id` endpoints alongside existing ones

New endpoints accept `public_id` strings, decode them, and delegate to existing logic:

```
GET /reviews/by-public-id/{public_id}    → new
GET /reviews/{id}                         → unchanged (still accepts int for backward compat)
```

This allows a gradual migration: the frontend switches to `by-public-id` while old API consumers continue using `/{id}`.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Data Flow                                      │
│                                                                       │
│   API Request (public_id)                                             │
│       │                                                               │
│       ▼                                                               │
│   ┌──────────────────────────────────────┐                            │
│   │  Endpoint Handler                    │                            │
│   │                                      │                            │
│   │  1. Receive public_id (string)      │                            │
│   │  2. Strip prefix ("rev_")           │                            │
│   │  3. hashids.decode → real_id (int)  │                            │
│   │  4. Look up by real_id (existing)   │                            │
│   │  5. Populate public_id in response  │                            │
│   └──────────────────────────────────────┘                            │
│       │                                                               │
│       ▼                                                               │
│   ┌──────────────────────────────────────┐                            │
│   │  id_obfuscator.py                    │                            │
│   │                                      │                            │
│   │  encode(real_id) → "kM8xP31R"       │                            │
│   │  decode("kM8xP31R") → 42            │                            │
│   │  format("rev", 42) → "rev_kM8xP31R" │                            │
│   │  parse("rev_kM8xP31R") → ("rev",42) │                            │
│   └──────────────────────────────────────┘                            │
│       │                                                               │
│       ▼                                                               │
│   ┌──────────────────────────────────────┐                            │
│   │  Database (unchanged)                │                            │
│   │  id=42 (still auto-increment int PK) │                            │
│   └──────────────────────────────────────┘                            │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

## Files Changed

### Backend (6 files)

| File | Change |
|---|---|
| `src/utils/id_obfuscator.py` | **NEW** — encode/decode/format/parse functions |
| `src/core/config.py` | **MODIFY** — add `ID_OBFUSCATOR_SALT` field |
| `src/schemas/pull_request.py` | **MODIFY** — add `public_id: str` to `ReviewResponse` |
| `src/api/v1/endpoints/reviews.py` | **MODIFY** — add `GET /by-public-id/{public_id}`; decode and delegate |
| `src/api/v1/endpoints/reviews.py` | **MODIFY** — update associate endpoint to accept text search |
| `pyproject.toml` | **MODIFY** — add `hashids` dependency |

### Frontend (3+ files)

| File | Change |
|---|---|
| `frontend/src/views/reviews/ReviewListView.vue` | **MODIFY** — replace `row.id` with `row.public_id`; change associate search |
| `frontend/src/views/reviews/ReviewDetailView.vue` | **MODIFY** — replace ID displays |
| `frontend/src/views/admin/ReviewValidationView.vue` | **MODIFY** — replace raw record ID display |
| `frontend/src/router/index.ts` | **MODIFY** — update review route to accept `public_id` param |

## Risks / Trade-offs

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Salt leak (source control exposure) | Low | High — IDs become reversible | Store salt in `.env` only; add to `.env.example` without value; audit that salt never committed |
| Collision across entity types | Low | Medium — different entities share hash | Prefix (`rev_`, `sco_`) disambiguates; separate salt segments per prefix |
| Association search regression | Medium | High — users can't link reviews | Build and test the PR-info search thoroughly before deploying; add search endpoint if needed |
| Old bookmarks with numeric IDs break | Medium | Low — users with saved `/reviews/42` links | Keep old numeric endpoints alive indefinitely; redirect `/reviews/{int}` to public_id variant |
| Hashids determinism allows tracking | Low | Low — same review always shows same public_id | Acceptable for internal policy; upgrade path to UUID if requirements change |

## Migration Plan

1. **Deploy order** (no-downtime):
   - Deploy backend changes first (utility, config, new endpoints — additive, nothing breaks)
   - Deploy frontend changes second (templates, router, association dialog)
   - Old numeric endpoints remain functional indefinitely

2. **Rollback**:
   - Frontend: revert to old templates; users see numeric IDs again
   - Backend: `by-public-id` endpoints are additive — revert any time

3. **Verification**:
   - Manual: load list page, verify all IDs show `rev_xxxx` format
   - Manual: click a review, verify URL contains `public_id`
   - Manual: use association search, verify PR-info search works
   - API: hit `/reviews/by-public-id/{valid_hash}` → 200; hit `/reviews/by-public-id/xyz` → 404

## Open Questions

1. Should we add a backend search endpoint for the association dialog (search reviews by text), or can the frontend filter the current page's data client-side?
   - Client-side: simple, no API change, but limited to loaded page
   - API search: more powerful, new endpoint needed
   - **Recommendation**: Client-side for now (search across the current page data); if users need cross-page search, add endpoint later
