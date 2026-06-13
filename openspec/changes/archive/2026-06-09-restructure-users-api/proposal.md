## Why

The `/api/v1/users/` endpoint family mixes Git User (`User` model) and Auth User (`AuthUser` model) operations under a single ambiguous `{user_id}` path parameter. This causes confusion: `GET /api/v1/users/42` retrieves a Git user, but `PATCH /api/v1/users/42/deactivate` deactivates an Auth user with the same numeric ID. As the system grows, this ambiguity leads to bugs, documentation confusion, and difficulty adding new auth-specific operations. Additionally, there is currently no way to physically delete an Auth user — only soft-deactivation exists.

## What Changes

- **BREAKING** — Split `/api/v1/users/` into two sub-routers:
  - `/api/v1/users/git/` — all Git User operations (GET, POST, PUT, PATCH, DELETE)
  - `/api/v1/users/auth/` — all Auth User operations (GET, PATCH, DELETE, avatar)
- **Path parameters renamed**: `{user_id}` → `{git_user_id}` for Git router, `{auth_user_id}` for Auth router
- **NEW** — `DELETE /api/v1/users/auth/{auth_user_id}` — physical Auth user deletion (revokes sessions, cascades role assignments, audit logs, PATs; disassociates but does not delete linked Git user)
- **Legacy path removed**: `DELETE /api/v1/users/{user_id}` becomes `DELETE /api/v1/users/git/{git_user_id}`
- **No functional change** to Git User create/read/update operations — only the URL paths change

## Capabilities

### New Capabilities
- `auth-user-deletion`: Physical deletion of AuthUser records including session revocation, cascade cleanup, and Git user disassociation. Admin-only endpoint at `DELETE /api/v1/users/auth/{auth_user_id}`.

### Modified Capabilities
- `git-user-crud`: GET, POST, PUT, PATCH, DELETE operations for Git Users — path prefix changes from `/users/` to `/users/git/`, path parameter renamed from `user_id` to `git_user_id`
- `auth-user-management`: PATCH activate/deactivate, avatar operations for Auth Users — path prefix changes from `/users/` to `/users/auth/`, path parameter renamed from `user_id` to `auth_user_id`, `GET /auth-users` moves to `GET /`

## Impact

- **`src/api/v1/endpoints/users.py`** — Major restructuring: split single router into two sub-routers (`git_users` and `auth_users`), add `DELETE /auth/{auth_user_id}` endpoint
- **`src/api/v1/api.py`** — Update router inclusion to use sub-routers
- **`src/services/user_service.py` or `auth_service.py`** — Add `delete_auth_user()` service method with session revocation
- **`src/schemas/auth.py`** — May need response schema for auth user deletion
- **API consumers** — Breaking change: existing `DELETE /api/v1/users/{id}` callers must update to `DELETE /api/v1/users/git/{id}`
