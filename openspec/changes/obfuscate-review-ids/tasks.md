## 1. Backend — Core Obfuscation Utility

- [ ] 1.1 Add `hashids` to `pyproject.toml` dependencies
- [ ] 1.2 Add `ID_OBFUSCATOR_SALT` field to `src/core/config.py` and `.env.example`
- [ ] 1.3 Create `src/utils/id_obfuscator.py` with `encode()`, `decode()`, `format_public_id()`, `parse_public_id()` functions
- [ ] 1.4 Write unit tests for the obfuscator utility (encode→decode roundtrip, invalid input, prefix parsing)

## 2. Backend — API Changes

- [ ] 2.1 Add `public_id: str` field to `ReviewResponse` schema; populate in endpoint handlers
- [ ] 2.2 Add `public_id: str` field to `ReviewRawResponse` schema
- [ ] 2.3 Add `GET /reviews/by-public-id/{public_id}` endpoint that decodes and delegates to existing lookup
- [ ] 2.4 Add `GET /reviews/by-public-id/{public_id}/pin` endpoints (check pin, pin, unpin)
- [ ] 2.5 Add `POST /reviews/by-public-id/{public_id}/associate/{target_public_id}` with decoded IDs
- [ ] 2.6 Add `DELETE /reviews/by-public-id/{public_id}/associate/{target_public_id}` with decoded IDs

## 3. Frontend — Display public_id

- [ ] 3.1 Update `ReviewListView.vue` — replace `row.id` display with `row.public_id` (prefixed as `REV-{public_id}`)
- [ ] 3.2 Update `ReviewDetailView.vue` — replace `review.id` display with `public_id` in header and dialogs
- [ ] 3.3 Update `ReviewValidationView.vue` — replace raw record `id` display with `public_id`
- [ ] 3.4 Update `ReviewListView.vue` — replace numeric IDs in delete confirmation and bulk preview with `public_id`
- [ ] 3.5 Update `frontend/src/router/index.ts` — change review route param from numeric `id` to `public_id` string

## 4. Frontend — Association Search

- [ ] 4.1 Change associate dialog search from numeric ID lookup to PR-info text search
- [ ] 4.2 Update `filterAssociateOptions` to search by project key, PR ID, repo slug, and PR user across the current page data
- [ ] 4.3 Update option label display to show `project_key/pull_request_id — user` (no review IDs)
- [ ] 4.4 Update navigation in associate flows to use `public_id`-based API calls

## 5. Frontend — Navigation and URLs

- [ ] 5.1 Update all review detail navigation links to use `public_id` instead of numeric `id`
- [ ] 5.2 Update task assignment views that navigate to review detail to pass `public_id`
- [ ] 5.3 Update any remaining template references to `review.id` or `row.id` used for display or navigation

## 6. Configuration and Verification

- [ ] 6.1 Generate a random salt and add to local `.env` for development
- [ ] 6.2 Add `ID_OBFUSCATOR_SALT` to CI/CD environment configuration documentation
- [ ] 6.3 Manual verification: Load review list — IDs show `REV-*` format; click review — URL contains public_id; use association — search works without numeric IDs
- [ ] 6.4 Run full test suite (`pytest` + `vue-tsc --noEmit`) to ensure no regressions
