# User repository access — Stage 0 task plan

> Status: 2026-11-08 — all product decisions settled (D1–D10 in `design.md`); no `DECISION` items remain. No implementation code has started.
> Scope of this change is **Stage 0 only**: build the grant data, the management surface and the backfill while leaving every read path exactly as it is. Stages 1–3 are listed at the end for context and are **out of scope**.
> Items marked `TREE` record a fact verified against the current codebase that constrains the task. Tree facts are as of 2026-11-08: HEAD migration `039`, `user_repository_access` has zero matches in the repo, `project_registry.uk_project_repo_unique` is the repository catalogue, `AuditService.log_action` is the audit primitive.

## Delivery stages

| Stage | Groups | Outcome | Gate before the next stage |
|---|---|---|---|
| 0 | 1–9 | Grants, admin API/UI, backfill, audit and old-Scope retirement exist; nothing reads them | `alembic heads = 040` reversible; review list response byte-identical; all tests green; gate `False` |
| 1 | out of scope | Shadow `ProjectScope` comparison, `review_admin` visibility fix, auth-gap closure | No unexplained divergence in the comparison log |
| 2 | out of scope | Enforced SQL/ORM filtering, scope-aware cache keys, bypass closure, `can_write`, service credentials; gate on | Every bypass has a regression test |
| 3 | out of scope | Retire three-level `check_permission`, docs/types, `/auth/me` and frontend permission residue | No caller of the deprecated scope path remains |

Groups within Stage 0 can proceed in parallel where they do not read each other's files.

---

## Stage 0

### 1. Model and migration — `design.md` D1, D2

- [ ] 1.1 Add `src/models/user_repository_access.py`: `Mapped` / `mapped_column` model with `id`, `subject_type` (`Enum("auth_user","git_user")` — house style, cf. `src/models/rbac.py:45-51`), `subject_id`, `subject_username`, `project_key` (`String(32)`), `repository_slug` (`String(128)`), `granted_by`, `created_at` / `updated_at` using `src.utils.timezone.get_current_time`.
- [ ] 1.2 Add `UniqueConstraint("subject_type","subject_id","project_key","repository_slug", name="uq_user_repository_access")` plus `Index("ix_ura_subject", "subject_type", "subject_id")` and `Index("ix_ura_repo", "project_key", "repository_slug")` in `__table_args__`. TREE: precedent is `src/models/release_note_reaction.py:66-71` and `src/models/project_registry.py:106-121`.
- [ ] 1.3 **Do not add foreign keys** on `subject_id` (polymorphic) or to `project_registry`; put the reason in a column comment. TREE: `AuthUser.id` and `User.id` are different tables, and `User.user_id` is a separate business id (`src/models/user.py:29-35`).
- [ ] 1.4 Export the model from `src/models/__init__.py` (imports at `:7-26`, `__all__` at `:29-49`).
- [ ] 1.5 Ensure `alembic/env.py` imports the models package so autogenerate sees the table. TREE: `env.py:25,36` sets `target_metadata = Base.metadata` but does not import `src.models` explicitly.
- [ ] 1.6 Add `alembic/versions/040_create_user_repository_access.py` with `revision="040"`, `down_revision="039"`, `op.create_table` + `op.create_index` in `upgrade()`, and a single `op.drop_table` in `downgrade()`. TREE: `039_add_release_note_reactions.py:34-89` is the template; dropping indexes first fails on MySQL when an FK index exists.
- [ ] 1.7 Verify `alembic heads` is the single `040`, and that `upgrade head → downgrade 039 → upgrade head` leaves no residue.

### 2. Configuration, schemas and service — D2, D3, D8, D9

- [ ] 2.1 Add `REPOSITORY_ISOLATION_ENABLED: bool = Field(default=False)` to `src/core/config.py` (existing `*_ENABLED` pattern at `:44, 212, 221, 382`) and the matching line to `.env.example`. **No request path reads it in this change.**
- [ ] 2.2 Add `src/schemas/repository_access.py`: `RepositoryAccessItem`, `RepositoryAccessReplaceRequest` (`items`, optional `reason`), `RepositoryAccessResponse` (`subject_type`, `subject_id`, `subject_username`, `items`, `total`, binding-status hint); `model_config = {"from_attributes": True}` and `Field(..., description=...)`.
- [ ] 2.3 Add `src/services/repository_access_service.py` with `list_access`, `replace_access`, `validate_pairs`, `resolve_subject`, `delete_subject_access`; return schemas, never ORM objects.
- [ ] 2.4 Implement `replace_access` as delete + insert inside one transaction, with pair deduplication before persistence and identical results on repeated identical calls.
- [ ] 2.5 Validate: unknown `subject_type` → 422, missing subject → 404, pair absent from `ProjectRegistry` → 422, all errors via the `AppException` hierarchy with structured `detail`.
- [ ] 2.6 Implement `resolve_subject` to return the union of `auth_user` and linked `git_user` grants and the `can_write` / `unrestricted` derivation, but **do not call it from any endpoint or query** in this change; document it as the Stage 1 seam.
- [ ] 2.7 **Do not add Redis caching** for grants. TREE: `reviews:list:*` keys already lack a user dimension; an unscoped grant cache now would leak across users in Stage 2. Add `MetricsCollector` counters (`repository_access.replaced`) and structured logging with `extra`.
- [ ] 2.8 Never use `User.user_id` as a subject id, in the service or in tests.

### 3. Endpoints, permissions and audit — D5, D9, D10

- [ ] 3.1 Add `src/api/v1/endpoints/repository_access.py` with `GET /{subject_type}/{subject_id}` and `PUT /{subject_type}/{subject_id}`, using `Annotated[AsyncSession, Depends(get_db_session)]`.
- [ ] 3.2 Mount it in `src/api/v1/api.py:4-25,31-83` with `prefix="/repository-access"` and add the module to `src/api/v1/endpoints/__init__.py`.
- [ ] 3.3 GET uses `RequireUserManage`; PUT uses `RequireSystemAdmin` **and** an explicit `system_admin` role check via `RBACService.get_user_roles()`. TREE: both dependencies exist at `src/core/permissions.py:162-165`; role names are `system_admin` / `review_admin` (`src/models/role.py:22`).
- [ ] 3.4 Log every replacement with `AuditService.log_action(auth_user_id=current_user.id, action="update", resource_type="repository_access", resource_id=f"{subject_type}:{subject_id}", old_values=..., new_values=...)`. TREE: signature at `src/services/audit_service.py:28-43`; note it commits internally.
- [ ] 3.5 Confirm unauthenticated requests return 401 and non-`system_admin` PUT returns 403 without changing any row.
- [ ] 3.6 Add `delete_subject_access` calls to `delete_auth_user` / `delete_git_user` in `src/api/v1/endpoints/users.py` (`:767, :829`). TREE: no FK exists on `subject_id`, so cleanup is explicit.
- [ ] 3.7 **Do not add a catalogue endpoint** by default. The picker reuses `GET /api/v1/projects/all` and `GET /api/v1/projects/key/{project_key}/repositories` (`src/api/v1/endpoints/projects.py:228-254, 544-706`). If a one-shot catalogue is later required, open a separate task with its own permission review.
- [ ] 3.8 **Do not** add `current_user` to `POST/PUT/PATCH /reviews` or to `review_service.upsert_review()` (D6); record the service-credential work as a Stage 2 task.

### 4. Loose-launch backfill — D4

- [ ] 4.1 Add `scripts/backfill_user_repository_access.py`: source distinct `(project_key, repository_slug)` from `ProjectRegistry` (TREE: `uk_project_repo_unique` at `src/models/project_registry.py:106-121`), subjects from all `AuthUser` and all `User` rows.
- [ ] 4.2 Default to `--dry-run` writing nothing; `--apply` performs the writes. Make both repeatable (`INSERT … ON DUPLICATE KEY` or equivalent) and idempotent.
- [ ] 4.3 Emit a JSON/CSV reconciliation report: subject count, pair count, expected row count, accounts where `AuthUser.user_id IS NULL`, and subjects with no grants.
- [ ] 4.4 Record the apply step as a system audit action (`auth_user_id=None`) with timestamp and expected row count.
- [ ] 4.5 Document the deployment order in `docs/DEPLOYMENT_GUIDE.md`: `alembic upgrade head` → dry run → report review → `--apply` → verification; the gate stays `False`.
- [ ] 4.6 Do not enable isolation or alter any read path as part of the backfill.

### 5. Frontend API and types — D9

- [ ] 5.1 Add `frontend/src/api/repositoryAccess.ts` with `getAccess(subjectType, subjectId)` and `replaceAccess(subjectType, subjectId, items)`, using the shared `request` wrapper. TREE: `frontend/src/api/users.ts:1, 44-45` shows the `response.items || []` convention.
- [ ] 5.2 Export `RepositoryAccessItem`, `RepositoryAccessResponse`, `SubjectType` from that module; only add to `frontend/src/types/index.ts` if a cross-module consumer needs them.
- [ ] 5.3 Reuse `projectsApi.getAllProjects()` / `getProjectRepositories(projectKey)` from `frontend/src/api/projects.ts:63-102` as the picker data source.

### 6. Frontend assignment UI — D1, D3, D9

- [ ] 6.1 Add shared `frontend/src/components/admin/RepositoryAccessDialog.vue`: project multi-select → per-project repository multi-select → confirm "N repositories will be granted" → save → re-fetch and display current grants. Show explicitly that saving replaces the whole set.
- [ ] 6.2 In `frontend/src/views/admin/SystemUserManagementView.vue`, add a "Repositories" action button and a granted-repository summary column; pass `subject_type='auth_user'` and the row's `id`. Display git-user binding status as a read-only hint (D3).
- [ ] 6.3 In `frontend/src/views/admin/GitUserManagementView.vue`, add the same button and column; pass `subject_type='git_user'` and `GitUser.id` — **not** `GitUser.user_id` (TREE: local interface at `:186-196` has both).
- [ ] 6.4 Follow the existing `.admin-page` card styling introduced for admin pages; do not add bespoke `el-card` overrides.
- [ ] 6.5 Add keys to `frontend/src/locales/en.json`, `zh-CN.json`, `zh-TW.json` under the `"admin"` block (`:745-915`), keeping the three locales in sync.

### 7. Retire the old Resource Scope UI — D7

- [ ] 7.1 In `SystemUserManagementView.vue`, remove the Scope radio group and Resource input (`:187-236`, `:220-236`), normalise `roleForm` to `resource_type:'global'` / `resource_id:''` (`:336-340`), and fix submit / reset / revoke payloads (`:571-573, 588-589, 612-613, 637-638`).
- [ ] 7.2 In `frontend/src/components/delegation/DelegationForm.vue`, remove the scope selector and resource-id input (`:94-108, 260-261, 270, 481-482`) and always submit `global`.
- [ ] 7.3 Normalise `assignRole` / `revokeRole` in `frontend/src/api/rbac.ts:81-95` to `global`; mark `ResourceType` in `frontend/src/types/index.ts:111` deprecated and remove it only after confirming zero references.
- [ ] 7.4 In `src/schemas/rbac.py:42-74`, keep both fields for legacy clients, default to `global` / `None`, and add a deprecation note. Do **not** change `src/services/rbac_service.py`'s three-level traversal behaviour — only add a comment pointing at Stage 3.
- [ ] 7.5 Mark `resource_id_param` in `src/core/permissions.py:84-143` as pending removal (TREE: zero callers), but leave the signature intact in this change.
- [ ] 7.6 Mark Resource Scope deprecated in `docs/PRD.md:524, 692`, `docs/features/phase1_auth_rbac_audit.md`, `docs/features/phase3_1_role_task_assignment.md`, and `docs/features/phase3_2_user_role_delegation.md`, pointing at this capability.
- [ ] 7.7 **Do not write a migration that drops** `user_role_assignment.resource_type` / `resource_id`. TREE: `alembic/versions/006_create_auth_and_rbac_tables.py:99-133` created them; an applied migration must be downgraded on every environment before its file leaves the tree (`docs/DEPLOYMENT_GUIDE.md`, troubleshooting 6).

### 8. Documentation — D4, D7, D8

- [ ] 8.1 Add a `docs/PRD.md` functional requirement for per-subject repository visibility, with the data model and the new API endpoint table.
- [ ] 8.2 Document `REPOSITORY_ISOLATION_ENABLED` in `.env.example` and `README.md`: default `False`, no consumer in Stage 0, activated in Stage 2.
- [ ] 8.3 Add the Stage 0 deployment and rollback sequence to `docs/DEPLOYMENT_GUIDE.md`.
- [ ] 8.4 State in the docs that `review_admin` no longer implies full visibility **from Stage 1 onward**, so Stage 0 operators are not surprised by current behaviour.

### 9. Tests and stage gate — D8, D10

- [ ] 9.1 Add `tests/test_repository_access.py`: GET returns grants, PUT full replacement and idempotency, duplicate deduplication, unknown `subject_type` → 422, missing subject → 404, unknown pair → 422, unique constraint, 401 unauthenticated, 403 for non-`system_admin` PUT with no row change. TREE: fixtures are `db_session` / `async_client` at `tests/conftest.py:318-350` on in-memory SQLite, so assertions must not depend on MySQL-only DDL.
- [ ] 9.2 Add a bound-subject test that creates one `AuthUser.user_id → User.id` link, grants different pairs on each side, verifies the union from `resolve_subject`, and asserts `User.id` was used rather than `User.user_id`.
- [ ] 9.3 Add `tests/test_repository_access_backfill.py`: dry run writes nothing, apply produces `subjects × pairs` rows, a second apply does not increase the count, and the report lists unbound accounts.
- [ ] 9.4 Add the **read-behaviour regression**: capture a representative set of `GET /api/v1/reviews` responses before the change and assert items, order, total and payload are identical afterwards; also assert no request path reads `REPOSITORY_ISOLATION_ENABLED`.
- [ ] 9.5 Add `frontend/tests/views/RepositoryAccessDialog.test.ts` using the `vi.hoisted` + `vi.mock` + `flushPromises` pattern from `frontend/tests/views/AdminDashboardView.test.ts:12-27`: project load → repository load → save → re-fetch, empty selection, load failure, and the replace-warning copy.
- [ ] 9.6 Add `frontend/tests/api/repositoryAccess.test.ts`; update any admin-view snapshots affected by the new button/column.
- [ ] 9.7 Run the full gate: `ruff format && ruff check --fix`, `pytest -v`, `vue-tsc`, Vitest, `npm run build`. Fix any regression before marking Stage 0 complete.

---

## Stage 0 acceptance gate

- [ ] `alembic heads` = single `040`; upgrade/downgrade/upgrade is clean and touches no existing table.
- [ ] `ruff`, `pytest`, `vue-tsc`, Vitest and `npm run build` are all green; all new code has type hints and awaits every DB operation.
- [ ] Review list, cache, SSE, notification, search and export responses are byte-identical to before (9.4).
- [ ] New endpoints return 401 / 403 as specified, and every grant change has an audit row with old and new pair sets.
- [ ] Backfill report is reviewed and every current subject holds every current repository pair.
- [ ] `REPOSITORY_ISOLATION_ENABLED=False` and no request path consumes it.
- [ ] Old Scope controls are gone from the UI, while `resource_type` / `resource_id` columns and historical rows remain.

## Rollback

- [ ] Revert the code and run `alembic downgrade 039` **before** the `040` file leaves the tree; Stage 0 changed no read path, so there is no business data to reconcile.

## Out of scope — later stages

| Stage | Work | Depends on |
|---|---|---|
| 1 | `ProjectScope` / `get_repository_scope`, shadow comparison logging, `review_admin` visibility fix, auth gaps on read endpoints | Stage 0 gate |
| 2 | Review SQL + `with_loader_criteria` fallback, cache keys with `user_id + scope_hash`, ID/detail/search/export/SSE/notification bypasses, close `page_size=0` export path, `can_write` enforcement, service credential for sync writes, gate on | Stage 1 comparison clean |
| 3 | Deprecate three-level `check_permission` traversal, clean docs/types, extend `/auth/me` with `visible_repositories` / `can_view_all` / `can_write`, unify frontend permission checks, fix `clearAuth()` residue | Stage 2 stable |
