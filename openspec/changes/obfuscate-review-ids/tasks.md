## 1. Backend — Core Obfuscation Utility

- [x] 1.1 Add `hashids` to `pyproject.toml` dependencies
- [x] 1.2 Add `ID_OBFUSCATOR_SALT` field to `src/core/config.py` and `.env.example`
- [x] 1.3 Create `src/utils/id_obfuscator.py` with `encode()`, `decode()`, `format_public_id()`, `parse_public_id()` functions
- [x] 1.4 Write unit tests for the obfuscator utility (encode→decode roundtrip, invalid input, prefix parsing)

## 2. Backend — API Changes

- [x] 2.1 Add `public_id: str` field to `ReviewResponse` schema; populate in endpoint handlers (via model_validator)
- [x] 2.2 Add `public_id: str` field to `ReviewRawResponse` schema (via model_validator)
- [x] 2.3 Add `GET /reviews/by-public-id/{public_id}` endpoint that decodes and delegates to existing lookup
- [ ] 2.4 Add `GET /reviews/by-public-id/{public_id}/pin` endpoints (check pin, pin, unpin) — deferred: existing pin endpoints used internally
- [ ] 2.5 Add `POST /reviews/by-public-id/{public_id}/associate/{target_public_id}` with decoded IDs — deferred: frontend uses real IDs internally
- [ ] 2.6 Add `DELETE /reviews/by-public-id/{public_id}/associate/{target_public_id}` with decoded IDs — deferred: frontend uses real IDs internally

## 3. Frontend — Display public_id

- [x] 3.1 Update `ReviewListView.vue` — replace `row.id` display with `public_id` (prefixed as `REV-{hash}`)
- [x] 3.2 Update `ReviewDetailView.vue` — replace `review.id` display with `public_id` in dialogs
- [x] 3.3 Update `ReviewValidationView.vue` — replace raw record `id` display with `public_id`
- [x] 3.4 Update `ReviewListView.vue` — replace numeric IDs in delete confirmation, associate dialog, and association list with `public_id`
- [x] 3.5 Update `frontend/src/router/index.ts` — review route param accepts both numeric and public_id strings

## 4. Frontend — Association Search

- [x] 4.1 Change associate dialog search from numeric ID lookup to PR-info text search
- [x] 4.2 Update `filterAssociateOptions` to search by project key, PR ID, repo slug, and PR user across current page + fallback to API search_query
- [x] 4.3 Update option label display to show PR info (no review IDs exposed)
- [x] 4.4 Update navigation in associate flows to use `public_id`-based API calls

## 5. Frontend — Navigation and URLs

- [x] 5.1 Update review detail navigation links to use `public_id` instead of numeric `id`
- [x] 5.2 Update task assignment views that navigate to review detail to pass `public_id` (no direct navigation exists — uses router)
- [x] 5.3 Update template references to use `public_id` for display

## 6. Configuration and Verification

- [x] 6.1 Generate a random salt and add to local `.env` for development (add `ID_OBFUSCATOR_SALT=<generated-hex>` to `.env`)
- [x] 6.2 Add `ID_OBFUSCATOR_SALT` to deployment environment configuration documentation
- [ ] 6.3 Manual verification: Load review list — IDs show `REV-*` format; click review — URL contains public_id; use association — search works without numeric IDs
- [x] 6.4 Run full test suite (`pytest` — 36 passed, `vue-tsc --noEmit` — clean)
