## Why

Currently, deleting a git user (`user` table) triggers `ON DELETE CASCADE` on their authored reviews (`pull_request_review_base`), review assignments (`pull_request_review_assignment`), and scores (`pull_request_score`). This means removing a user — intentional or accidental — permanently destroys review history. In a code review system, review records are historical artifacts that should outlive the individuals who created them. This change severs that cascade so reviews, assignments, and scores survive user deletion.

## What Changes

- **`PullRequestReviewBase.pull_request_user`** — FK changes from `ondelete="CASCADE", nullable=False` to `ondelete="SET NULL", nullable=True`
- **`PullRequestReviewAssignment.reviewer`** — FK changes from `ondelete="CASCADE", nullable=False` to `ondelete="SET NULL", nullable=True`
- **`PullRequestScore.reviewer`** — FK changes from `ondelete="CASCADE"` (currently implicit in migration) to `ondelete="SET NULL", nullable=True`
- **Alembic migration** — generates a new revision altering these three FK constraints
- **Service/API layer** — handles nullable `pull_request_user` and `reviewer` fields gracefully (no crashes on `None`)
- **No change** to `assigned_by` in `PullRequestReviewAssignment` — already `SET NULL, nullable=True` ✅
- **No change** to `AuthUser.user_id` → `user.id` — already `SET NULL` ✅

## Capabilities

### New Capabilities
- `preserve-reviews-on-user-deletion`: FK constraints and application logic to retain review/assignment/score records when a git user or auth user is deleted from the system.

### Modified Capabilities

None — this is a new DB constraint and null-safety behavior, not a change to existing spec-level requirements.

## Impact

- **3 model fields** change type from `str` to `str | None` in SQLAlchemy + Pydantic schemas
- **1 Alembic migration** to alter FK constraints
- **Service layer** — all queries returning `pull_request_user`, `reviewer` must tolerate `None`
- **API responses** — these fields may now be `null`; downstream consumers (frontend, API clients) should handle nullable values
- **`UserService.delete_user()`** — no code change needed; DB-level cascade is the only thing keeping the old behavior
- Auth user deletion path (`deactivate`) is unaffected since it's soft-delete only
