## Why

PyPRLedger is about to host reviews for several project teams (initially around five projects), but it has no working data-scope boundary. The three-level scope that was designed for role assignments never reached the read path, so today a `review_admin` sees every project's reviews. Team A and Team B cannot be separated, and an administrator has no way to express "this account may see these repositories".

Facts verified against the tree on 2026-11-08:

| Observation | Where |
|---|---|
| `UserRoleAssignment` stores `resource_type = global\|project\|repository` and `resource_id`, but business endpoints never pass a resource id to the permission check | `src/models/rbac.py:45-56`, `src/core/permissions.py:84-143` |
| `check_permission()` walks the three levels, yet callers ask only for an action on `reviews` | `src/services/rbac_service.py:34-36, 124-136`, `src/api/v1/endpoints/reviews.py` |
| `review_admin` holds `assign` on `reviews` and is treated as "see everything"; `sse.py` grants both admin roles all events | `alembic/versions/012_fix_review_admin_assign_permission.py`, `src/api/v1/endpoints/sse.py:121-156` |
| The review list SQL has no scope predicate; `visible_to_username` filtering in Python is about participation, not tenancy | `src/services/review_service.py` |
| `reviews:list:*` cache keys contain no user or scope dimension | `src/services/review_service.py` |
| `repository_slug` alone is not unique: the unique key is `(project_key, repository_slug)` | `src/models/project_registry.py:106-121`, `alembic/versions/002_create_project_registry.py` |
| A system account binds to a git user through the nullable `AuthUser.user_id` | `src/models/auth_user.py:38-45` |
| `POST/PUT/PATCH /reviews` have no `current_user` dependency; service-side sync also writes through `upsert_review` | `src/api/v1/endpoints/reviews.py`, `src/services/review_validation_service.py` |

Fixing all of those in one step would change what every user sees on the day it ships. Instead the rollout is deliberately loose: first make the authorisation data, the management surface and a full backfill exist **without changing any read behaviour**; then run a shadow comparison; only then turn isolation on. This change is the first step.

## What Changes

- **A dedicated access table.** `user_repository_access` records `(subject_type, subject_id, project_key, repository_slug)` grants. Data scope becomes its own concept instead of being inferred from a role's `resource_type`.
- **An admin API.** Read the grants of a system user or a git user, and replace them atomically. Writes require `system_admin`, are idempotent, and are audited.
- **An assignment UI.** Both admin user pages get a shared repository picker backed by the existing project/repository catalogue endpoints.
- **A loose-launch backfill.** Every existing user is granted every existing repository, so the day isolation is enabled nobody loses access they had before. The backfill is dry-run by default and reports missing git-user bindings.
- **A gate that is defined but not consumed.** `REPOSITORY_ISOLATION_ENABLED` defaults to `False`; no request path reads it in this change.
- **The old Resource Scope UI is retired.** `SystemUserManagementView.vue` and `DelegationForm.vue` stop offering Global/Project/Repository and always submit `global` with a null resource id. The database columns and historical rows stay intact.
- **A readability guarantee.** No review list SQL, cache key, SSE fan-out, notification query, search, export or auth response changes. A before/after response snapshot must be identical.

Explicitly **not** in this change: `ProjectScope` / `get_repository_scope`, ORM-level `with_loader_criteria` filtering, scope-aware cache keys, `can_write` enforcement, authentication on the service sync write channel, the `/auth/me` response shape, or any change to who can currently see a review. Those belong to later stages listed in `design.md`.

## Capabilities

### New Capabilities

- `user-repository-access`: how a subject (system user or git user) is granted visibility of `(project_key, repository_slug)` pairs — the grant model, bound-identity semantics, administrator read/replace operations, permission and audit rules, the loose-launch backfill, orphan-row integrity, the retirement of the old Resource Scope UI, and the guarantee that Stage 0 does not alter read behaviour.

### Modified Capabilities

<!-- None: existing capabilities keep their requirements. Deleting a user still deletes that user; the new capability simply requires its access rows to go too. -->

## Impact

- **Models / migration**: new `src/models/user_repository_access.py`, exported from `src/models/__init__.py`; new single-head migration `alembic/versions/040_create_user_repository_access.py` (`down_revision = "039"`). No existing table or column is altered or dropped.
- **Config**: `REPOSITORY_ISOLATION_ENABLED: bool = Field(default=False)` in `src/core/config.py` and `.env.example`. Defined only; no consumer in this change.
- **Schemas / services**: new `src/schemas/repository_access.py` and `src/services/repository_access_service.py`. No Redis cache is introduced at this stage.
- **API**: new `src/api/v1/endpoints/repository_access.py`, mounted at `/api/v1/repository-access` in `src/api/v1/api.py`. `users.py` deletion handlers gain a cleanup call. Existing endpoint contracts are unchanged.
- **Frontend**: new `frontend/src/api/repositoryAccess.ts` and `frontend/src/components/admin/RepositoryAccessDialog.vue`; `SystemUserManagementView.vue` and `GitUserManagementView.vue` gain a button, a summary column and the shared dialog; `locales/*.json` gain keys. The old Scope radio group and resource-id input are removed.
- **Tooling**: `scripts/backfill_user_repository_access.py` with `--dry-run` / `--apply` and a reconciliation report.
- **Docs**: `docs/PRD.md`, `docs/DEPLOYMENT_GUIDE.md`, `.env.example`, and the phase-1/phase-3 feature notes are updated; the three-level Resource Scope is marked deprecated but its columns remain.
- **Tests**: backend `tests/test_repository_access.py`, `tests/test_repository_access_backfill.py`, plus a response-snapshot regression; frontend `RepositoryAccessDialog.test.ts` and API tests.
- **Operational**: after deployment an operator runs the backfill in dry-run, reviews the report, then applies it. `REPOSITORY_ISOLATION_ENABLED` stays `False` until Stage 2.
