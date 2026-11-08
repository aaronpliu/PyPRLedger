## Context

The scope that exists today is a property of a **role assignment**, not of a person's data reach. `UserRoleAssignment` has `resource_type` / `resource_id` (`src/models/rbac.py:45-56`), and `RBACService.check_permission()` walks global → project → repository when a resource id is supplied (`src/services/rbac_service.py:124-136`). In practice no business endpoint supplies one, so the three levels never filter anything. Meanwhile the review list is filtered in Python by participation (`visible_to_username`), and the list cache key has no user dimension.

TREE (2026-11-08) — facts the design must fit:

| Primitive | State | Implication |
|---|---|---|
| `Repository.repository_slug` | Not unique; `001_initial_schema.py` only constrains `repository_id` | A slug alone cannot identify a repository across projects |
| `ProjectRegistry` | `uk_project_repo_unique(project_key, repository_slug)` (`src/models/project_registry.py:106-121`, `002_create_project_registry.py`) | This is the authoritative, deduplicated repository catalogue |
| `User` / `AuthUser` | `AuthUser.user_id → user.id` nullable (`src/models/auth_user.py:38-45`); `User.id` is the PK, `User.user_id` is an external business id (`src/models/user.py:29-35`) | Subject ids must use `id`, never `user_id` |
| Roles | `system_admin`, `review_admin`, `reviewer`, `viewer` (`src/models/role.py:22`); admin route guard is `system_admin` (`frontend/src/router/index.ts:250-261`) | Only `system_admin` should edit data reach |
| Permission dependencies | `RequireUserManage`, `RequireSystemAdmin` (`src/core/permissions.py:162-165`) | Reuse; do not invent a parallel auth path |
| Permission audit | `AuditService.log_action(auth_user_id, action, resource_type, resource_id, old_values, new_values, …)` (`src/services/audit_service.py:28-43`) | Grant changes get an audit row with before/after |
| Migrations | Single chain `001 → 039`, HEAD `039` (`alembic/versions/039_add_release_note_reactions.py:28-29`); `alembic/env.py` does not import `src.models` explicitly | Stage 0 adds `040`; ensure the model is imported so autogenerate sees it |
| Admin UI | `SystemUserManagementView.vue` role dialog carries the Scope radio + Resource input (`:187-236`, `:336-340`, `:571-573`); `GitUserManagementView.vue` has no scope UI | One dialog is removed, one page gains the new picker |
| Repository catalogue API | `GET /api/v1/projects/all`, `GET /api/v1/projects/key/{project_key}/repositories` (`src/api/v1/endpoints/projects.py:228-254, 544-706`), response includes `repository_slug` | No new catalogue endpoint is needed |
| Testing | `tests/conftest.py:21, 318-350` uses in-memory SQLite + `Base.metadata.create_all`; frontend Vitest mocks API modules with `vi.hoisted` (`frontend/tests/views/AdminDashboardView.test.ts:12-27`) | Tests must run on SQLite; do not rely on MySQL-only DDL in assertions |

The product decision that shapes everything: isolation must be **loose on launch**. No user may lose access on the day the feature ships. So this change builds the data and the controls but does not activate them; the activation is a separate, gated stage.

## Goals / Non-Goals

**Goals:**

- Express visibility as an explicit grant of `(project_key, repository_slug)` pairs to a subject.
- Let a `system_admin` read and atomically replace those grants for both system users and git users, with an audit trail.
- Backfill every current user with every current repository so enabling isolation later is non-breaking.
- Retire the misleading three-level Scope UI while keeping its stored columns and historical rows.
- Prove that no existing read behaviour changed.

**Non-Goals:**

- Enforcing isolation in any query, cache key, SSE event, notification, search or export.
- Implementing `ProjectScope`, `get_repository_scope`, `can_write` enforcement, or ORM-level `with_loader_criteria`.
- Authenticating the service-sync write channel (`POST/PUT/PATCH /reviews`) — that gets its own service credential work later.
- Changing `/auth/me`, frontend permission helpers, or route guards.
- Dropping `user_role_assignment.resource_type` / `resource_id`, or editing a migration an environment may already have applied.

## Decisions

### D1 — The authorisation unit is the pair `(project_key, repository_slug)`

A grant is never a slug by itself and never a project by itself. `project_key` is the coarse grouping (the Bitbucket / GitHub project), `repository_slug` is the repository inside it. TREE: `repository_slug` is not unique, and `ProjectRegistry` is unique on the pair, so the pair is the smallest identifier that is both unambiguous and already present on every review (`PullRequestReviewBase.project_key` / `repository_slug`, both non-null and indexed).

The Stage 1 resolver will produce `unrestricted`, `pairs`, `project_keys`, `can_write` and `reason`; Stage 0 only stores the data that resolver will read.

### D2 — One polymorphic grant table, with deliberate foreign-key omissions

`user_repository_access`: `id`, `subject_type` (`auth_user` | `git_user`), `subject_id`, `subject_username`, `project_key`, `repository_slug`, `granted_by`, `created_at`, `updated_at`. Unique on `(subject_type, subject_id, project_key, repository_slug)`; indexes on the subject pair and on the repository pair.

- **No FK on `subject_id`**: it points at two different tables depending on `subject_type`; a single FK is impossible. Deleting a user must call `delete_subject_access` from `users.py`'s `delete_auth_user` / `delete_git_user`.
- **No FK to `project_registry`**: grants must survive a registry row being removed or re-synced, and a project may be pre-authorised before its registry entry exists. The service validates that a submitted pair exists in `ProjectRegistry` and returns 422 otherwise, but never cascades a delete.
- `subject_username` is a deliberate denormalised snapshot: audits stay readable after a rename, and Stage 2 can match review usernames without a join.

**Alternative rejected:** separate `auth_user_repository_access` and `git_user_repository_access` tables. It doubles every query and makes the union rule in D3 a schema-level join instead of one index scan.

### D3 — A bound system user and its git user are one subject

When `AuthUser.user_id` points at a `User`, the effective grant set is the **union** of `auth_user` rows and `git_user` rows. A system account with no binding has only its own rows and is read-only (`can_write = false`); a pure git user has only its own rows. `can_write` therefore derives from `unrestricted or auth_user.user_id is not None`, with `system_admin` excepted. TREE: `review_validation_service.py` calls `review_service.upsert_review(...)` outside any user request, so write authority must be separated from data reach — a grant is not a write permission.

Stage 0 defines and stores this; it does not enforce it. The admin UI shows binding status as a read-only hint so an operator can predict the later `can_write` outcome.

### D4 — Loose launch: backfill, shadow, then enforce

The backfill grants every `AuthUser` and every `User` every distinct `(project_key, repository_slug)` from `ProjectRegistry`. It is dry-run by default, idempotent on `--apply`, and emits a report of user count, pair count, expected row count, users with no git binding, and subjects with no grants. The backfill is audited as a system action.

Stage sequence (only Stage 0 is this change):

| Stage | Outcome | Gate |
|---|---|---|
| 0 · Foundation | Table, API, UI, backfill, audit, gate defined | Read responses byte-identical to before |
| 1 · Shadow | `ProjectScope` computed per request, compared to current results, log only; fix `review_admin` full visibility and auth gaps | No unexplained divergence in the comparison log |
| 2 · Enforce | SQL + ORM criteria, scope-aware cache keys, ID/detail/search/export/SSE/notification bypasses, `can_write`, service credentials; gate on | Every bypass enumerated in Stage 1 has a regression test |
| 3 · Clean up | Retire three-level `check_permission` traversal, docs and types; `/auth/me` and frontend permission residue | No remaining caller of the deprecated scope path |

### D5 — `system_admin` is the only unrestricted subject

`review_admin` keeps its action permissions (`assign`, role management) but no longer implies "see every repository". TREE: `src/api/v1/endpoints/sse.py:155-156` currently grants both admin roles all events; Stage 1 replaces that with a scope check. `system_admin` remains unrestricted **even without a git-user binding**, and keeps write authority — the confirmed product decision, and the operational escape hatch when no account is bound yet.

### D6 — Service-sync writes stay a trusted channel

`POST/PUT/PATCH /reviews` and `review_service.upsert_review()` are webhook / sync paths, not user interactions. Stage 0 does **not** add `current_user` to them and does **not** route them through `can_write`. A separate later change introduces a service credential and scope validation for that channel. Mixing them into this change would either break ingestion or silently expand write authority.

### D7 — Retire the old Scope UI, keep the storage

The radio group and free-text `resource_id` in `SystemUserManagementView.vue` and `DelegationForm.vue` are removed; submissions are normalised to `resource_type='global'` and `resource_id=None` in the frontend API layer. Backend `RoleAssignmentRequest` keeps both fields for old clients but defaults them the same way and is marked deprecated. `RBACService.check_permission()` keeps its three-level traversal for now with a deprecation note — changing it here would be a read-behaviour change. **No migration drops the columns**: an applied migration must not be edited or removed (see `docs/DEPLOYMENT_GUIDE.md`, troubleshooting 6).

### D8 — Stage 0 red lines: no read path, no cache

No change to `review_service.py`, `reviews.py`, `search.py`, `sse.py`, `notifications.py`, `task_assignment.py`, `get_current_user_with_token`, `require_permission`, `/auth/me`, `stores/auth.ts`, `usePermission.ts` or route guards. No `ProjectScope` dependency, no ORM event hook, no scope-aware cache. In particular **no Redis cache is added for the new grants**: an unscoped cache key now would become a cross-user leak the moment Stage 2 turns isolation on. Cache keys are designed in Stage 2 as `user_id + scope_hash`.

### D9 — API surface and permission split

`GET /api/v1/repository-access/{subject_type}/{subject_id}` uses `RequireUserManage`; `PUT` on the same path uses `RequireSystemAdmin` **plus** an explicit `system_admin` role check from `RBACService.get_user_roles()`, so a drifted permission row cannot widen data reach. `PUT` is a full replacement (delete + insert in one transaction), idempotent, and returns the resulting grants. Validation: unknown `subject_type` or missing subject → 422 / 404, pair absent from `ProjectRegistry` → 422, duplicate pairs deduplicated.

The repository picker reuses `GET /api/v1/projects/all` and `GET /api/v1/projects/key/{project_key}/repositories`; a dedicated `GET /repository-access/catalog` is an optional optimisation, not part of the contract.

### D10 — Audit, integrity and rollback

Every replacement writes `AuditService.log_action(...)` with `resource_type='repository_access'`, `resource_id='{subject_type}:{subject_id}'`, and full old/new pair lists. The backfill is audited with `auth_user_id=None`. Deleting a user removes that subject's rows.

Rollback is `alembic downgrade 039` plus reverting the code: Stage 0 created one new table and touched no existing read path, so there is no business data to reconcile. Follow the house rule — downgrade on every environment **before** the migration file leaves the tree; `stamp` would leave the table behind.

**Alternative rejected:** enabling isolation in the same change as the schema. A single missed bypass (ID-based detail lookup, `page_size=0` export, SSE, cached list) would leak another team's reviews, and the failure would only be visible after users complain.

## Risks / Mitigations

| Risk | Mitigation |
|---|---|
| Backfill silently misses a subject or a repository | Dry-run reconciliation report with explicit counts plus `tests/test_repository_access_backfill.py` asserting rows = subjects × pairs |
| `User.id` confused with `User.user_id` in the UI or API | Called out in D2, in the spec, and covered by a bound-subject test using both ids |
| A hidden read path changes inadvertently | Before/after `GET /api/v1/reviews` snapshot comparison as a stage gate (task 9.4) |
| Old Scope removal breaks a client still sending `resource_id` | Backend keeps both fields and defaults to `global`; no column is dropped |
| MySQL rejects a `downgrade` that drops indexes before FKs | `downgrade()` drops the table in one statement, matching `039_add_release_note_reactions.py:78-89` |
| Autogenerate misses the new table | `alembic/env.py` explicitly imports the models package; task 1.3 verifies `alembic heads` and table creation |

## Verification

- `alembic heads` is a single `040`; `upgrade head → downgrade 039 → upgrade head` succeeds with no residual table or index.
- `pytest -v`, `vue-tsc`, `npm run build`, Vitest and `ruff format && ruff check` all pass.
- Before/after review list responses (items, total, order) are identical.
- Unauthenticated access → 401; non-`system_admin` PUT → 403; every grant change has an audit row with old/new values.
- `REPOSITORY_ISOLATION_ENABLED=False` and no request path reads it.
- Backfill report reviewed: all current users hold all current repository pairs; unbound accounts are listed explicitly.

## Open Questions

None. All product decisions (pair-level grants, bound-identity union, read-only unbound accounts, loose launch, old Scope removal, `system_admin` write authority, trusted service-sync channel) were confirmed on 2026-11-08 and are recorded above.
