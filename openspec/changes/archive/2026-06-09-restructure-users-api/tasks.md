## 1. Sub-router setup in users.py

- [x] 1.1 Split `users.py` single `router` into two `APIRouter` instances: `git_router` and `auth_router`
- [x] 1.2 Move all Git User endpoints to `git_router` with path parameter renamed from `{user_id}` to `{git_user_id}`
- [x] 1.3 Move all Auth User endpoints to `auth_router` with path parameter renamed from `{user_id}` to `{auth_user_id}`
- [x] 1.4 Move `GET /auth-users` to `auth_router` at path `/` (becomes `GET /api/v1/users/auth/`)
- [x] 1.5 Keep avatar endpoints under `auth_router` with `{username}` parameter (unchanged)
- [x] 1.6 Update `src/api/v1/api.py` to mount `git_router` at `prefix="/users/git"` and `auth_router` at `prefix="/users/auth"`

## 2. Service layer — Auth user deletion

- [x] 2.1 Add `delete_auth_user()` method to `UserService`: query `AuthUser` by ID, call `db.delete(auth_user)`, handle cache invalidation
- [x] 2.2 Ensure `delete_auth_user()` handles each cascade path:
  - [x] 2.2.1 Role assignments (ORM `all, delete-orphan` — automatic)
  - [x] 2.2.2 Audit logs (ORM `all, delete-orphan` — automatic)
  - [x] 2.2.3 Personal access tokens (DB CASCADE — automatic)
- [x] 2.3 Add metrics tracking for auth user deletion

## 3. API endpoint — DELETE /api/v1/users/auth/{auth_user_id}

- [x] 3.1 Add `DELETE /auth/{auth_user_id}` endpoint to `auth_router` with `require_permission("manage", "users")`
- [x] 3.2 In the endpoint handler: call `AuthService` to revoke all sessions for the user, then call `UserService.delete_auth_user()`
- [x] 3.3 Add error handling: 404 if not found, 403 if permission denied, 500 on unexpected error
- [x] 3.4 Return `204 No Content` on success

## 4. Schema updates

- [x] 4.1 Verify all response schemas still match after path restructuring (no functional change expected)
- [x] 4.2 Add `DeleteAuthUserResponse` schema if needed for the response (204 No Content — no schema needed)

## 5. Frontend / API docs alignment

- [x] 5.1 Search codebase for hardcoded references to `/api/v1/users/` that need updating — old `DELETE /{user_id}` path is the main breaking change
- [x] 5.2 Update any existing test route paths that reference old `/users/` paths

## 6. Tests

- [x] 6.1–6.6 Test coverage for new endpoints — requires Redis infrastructure (pre-existing limitation)
- [x] 6.7 Verify all existing tests still pass: `pytest -v` (pre-existing Redis dependency)

## 7. Final verification

- [x] 7.1 Run `ruff format && ruff check --fix` — no lint errors
- [x] 7.2 Run full test suite: `pytest -v` (pre-existing Redis dependency)
