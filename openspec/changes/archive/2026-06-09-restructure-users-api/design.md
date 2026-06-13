## Context

The `users.py` file currently defines a single `APIRouter()` with no prefix. It's mounted in `api.py` as `include_router(users.router, prefix="/users")`. All 16 endpoints share this single router, mixing Git User and Auth User operations under the ambiguous `{user_id}` path parameter.

`UserService` handles both models: it directly operates on `User` (git) for create/read/update/delete, and imports `AuthUser` internally for activate/deactivate. There is no existing `delete_auth_user` method.

Auth user deletion will cascade via existing ORM relationships: `role_assignments` (all-delete-orphan), `audit_logs` (all-delete-orphan), `personal_access_tokens` (CASCADE). The linked Git user's `AuthUser.user_id` will be auto-set to NULL by the FK constraint (`ondelete="SET NULL"`).

## Goals / Non-Goals

**Goals:**
- Split the single `/users` router into two sub-routers: `git_router` and `auth_router`
- Mount them as `/users/git/` and `/users/auth/` respectively
- Rename path parameters from `user_id` to `git_user_id` / `auth_user_id` for clarity
- Add physical Auth user deletion at `DELETE /users/auth/{auth_user_id}`
- Auth user deletion revokes all active Redis sessions, deletes the AuthUser row, lets ORM cascades clean up roles/audit/PATs
- All non-deleted endpoints retain identical business logic

**Non-Goals:**
- Changing the data model (no table changes, no migrations)
- Adding soft-delete to AuthUser (deactivation already exists)
- Cascading deletion from AuthUser to linked GitUser (intentionally kept separate)
- Renaming non-delete path parameters outside of the split (e.g., `/{username}/avatar` keeps `username`)

## Decisions

### Decision 1: Single file with two routers vs. Split into two files

| Option | Pro | Con |
|---|---|---|
| Two files: `git_users.py` + `auth_users.py` | Cleaner separation | More files; shared logic duplicated or imported |
| Single file: two `APIRouter()` instances | Less diff noise; shared schemas/deps in one place | Longer file |

**Chosen:** Single file, two routers. The endpoints share `get_user_service()`, `get_db_session`, the same schemas, and the same metrics/error patterns. Keeping them in one file avoids cross-file imports and makes the diff scannable.

### Decision 2: `AuthService` vs. `UserService` for auth user deletion

`UserService` already handles `activate_user` and `deactivate_user` for AuthUser (with internal `from src.models.auth_user import AuthUser`). It also has `redis_client` for cache operations. The new `delete_auth_user` method fits naturally there — consistent with the existing pattern.

However, session revocation requires access to `AuthService._delete_refresh_session()`. Two options:
- **Option A**: Add session revocation to the new endpoint before calling the service
- **Option B**: Inject a Redis cleanup step into UserService

**Chosen:** Option A — the endpoint handler revokes sessions via an AuthService call before delegating to UserService. This keeps service responsibilities clean: UserService handles DB operations, the endpoint orchestrates cross-cutting concerns.

### Decision 3: Cascade behavior on auth user deletion

The ORM already defines:
- `AuthUser.role_assignments` → `cascade="all, delete-orphan"` ✅
- `AuthUser.audit_logs` → `cascade="all, delete-orphan"` ✅
- `AuthUser.personal_access_tokens` → `relationship` with DB-level `ondelete="CASCADE"` ✅
- `UserPinnedReview.user_id` → DB-level `ondelete="CASCADE"` ✅
- `ReviewAssociation.created_by` → DB-level `ondelete="SET NULL"` ✅

No additional cascade configuration is needed. Deleting the AuthUser row via `db.delete(auth_user)` will trigger all of these automatically.

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| **Breaking change** — API consumers using `/users/{id}` must update paths | Document in changelog; this is an internal tool; version bump |
| **Forgotten references** — Swagger/schema examples may hardcode old paths | Search for `/users/` in docs/examples after re-routing |
| **Race condition** — User deletes AuthUser while active sessions exist | Revoke sessions first (in Redis), then delete DB row; if DB delete fails, sessions are already revoked (acceptable) |
| **Accidental delete** — No soft-delete safety net | Require `manage`/`users` permission; consider a confirmation flag if desired |
