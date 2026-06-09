## Context

The database currently defines three foreign keys from review/score tables to `user.username` with `ON DELETE CASCADE`:

| Table | FK Column | Current FK | Nullable |
|---|---|---|---|
| `pull_request_review_base` | `pull_request_user` | `CASCADE` | `NOT NULL` |
| `pull_request_review_assignment` | `reviewer` | `CASCADE` | `NOT NULL` |
| `pull_request_score` | `reviewer` | `CASCADE` (via migration `004`) | `NOT NULL` |

`PullRequestReviewAssignment.assigned_by` is already correctly `SET NULL` + nullable.

When `UserService.delete_user()` calls `db.delete(user)`, the ORM emits a single `DELETE FROM user WHERE id=?`. The database engine then cascades to all three child tables, destroying review history. There is no application-level lock or safety check — the cascade is silent and total.

## Goals / Non-Goals

**Goals:**
- Change all three FK constraints from `CASCADE` to `SET NULL`
- Make the three FK columns nullable
- Generate and validate an Alembic migration
- Ensure all service and API code handles the now-nullable fields without crashing
- Update Pydantic response schemas to reflect `str | None`

**Non-Goals:**
- Changing the `assigned_by` FK (already correct)
- Changing `AuthUser.user_id → user.id` FK (already `SET NULL`)
- Adding soft-delete for users (separate concern)
- Adding cascade for auth user deletion (no physical auth user delete exists yet)
- Purposely nulling out references at the ORM level before deletion (DB `SET NULL` handles this)

## Decisions

### Decision 1: `SET NULL` over `NO ACTION` / `RESTRICT`

| Option | Consequence |
|---|---|
| `SET NULL` | User deleted → FK column becomes `NULL`. Review/score records survive with "unknown author". |
| `NO ACTION` / `RESTRICT` | Prevents user deletion if any review references them. Blocks legitimate cleanup. |
| `SET DEFAULT` | Requires a default user ID, which is artificial. |

**Chosen: `SET NULL`** — balances data preservation with administrative freedom to remove users.

### Decision 2: Model-first definition, migration to reconcile

The `PullRequestScore.reviewer` column currently uses `Column()` style (older pattern) and doesn't specify `ondelete` in the model file — the CASCADE was set only in the migration (`004`). We'll update the model to explicitly declare `ondelete="SET NULL"` so the model and DB are in sync. This also means Alembic autogenerate will detect the change correctly.

### Decision 3: No application-level NULL-out before delete

We considered explicitly setting `pull_request_user = None` on all authored reviews before calling `db.delete(user)`, to avoid relying on DB-level `SET NULL`. However:
- The DB constraint is simpler and atomic
- `SET NULL` is standard SQL and well-tested across MySQL and SQLite (test DB)
- No intermediate state where reviews reference a deleted user
- No extra queries needed

**Chosen: Rely on `ON DELETE SET NULL`** at the DB level, consistent with how `assigned_by` already works.

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| **Orphaned reviews** — `pull_request_user` shows `NULL` in UI, confusing users | Display "Deleted user" or "Unknown" fallback in API responses and frontend. |
| **Testing** — SQLite used in tests must support `ON DELETE SET NULL`. It does (PRAGMA foreign_keys = ON). | Ensure `foreign_keys` pragma is enabled in test fixtures. |
| **Race condition** — Review created between user delete check and actual delete | Not a new risk — cascade scenario had the same window. `SET NULL` is safer (data survives). |
| **Alembic autogenerate** — may not detect FK `ondelete` changes reliably | Write migration manually, test with `alembic upgrade && alembic downgrade`. |
| **Backwards compatibility for API consumers** — `pull_request_user` goes from `str` to `str \| None` | Semver: minor bump. Document in changelog. |
