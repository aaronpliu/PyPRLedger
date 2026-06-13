## Why

Currently, every pull request review must be manually assigned to a reviewer by a `review_admin`. As the number of projects and reviews grows, this manual process becomes a bottleneck — admins must track who is available, who covers which project/repo, and assign each review one by one. This slows down the review cycle and creates unnecessary overhead.

Auto-assignment rules eliminate this bottleneck by letting `review_admin` define configurable rules ("if a review matches these conditions, assign it to these reviewers"). When a new review arrives, the system automatically assigns the right reviewers — no manual intervention needed.

## What Changes

- **New database table** `pull_request_review_auto_assignment_rule` — stores rule definitions (conditions, target reviewers, priority, temporal validity, enable/disable)
- **New API module** `auto-task-assignment` — CRUD endpoints for `review_admin` to manage rules
- **New service** `AutoTaskAssignmentService` — evaluates rules against incoming reviews and creates auto-assignments
- **Integration** into `ReviewService.create_review()` — when a review is created without an explicit reviewer, the auto-assignment engine fires
- Existing manual assignment flow remains unchanged — if a `reviewer` is explicitly provided, auto-assignment is skipped entirely

## Capabilities

### New Capabilities
- `auto-task-assignment`: Configurable rule-based auto-assignment of reviewers to pull request reviews, with priority-based matching, multi-project/repo/user conditions, temporal control, and enable/disable toggling

### Modified Capabilities
*(No existing specs to modify)*

## Impact

- **New API endpoints** under `/auto-task-assignment/` — CRUD for rules and toggle
- **New model** — `PullRequestReviewAutoAssignmentRule` in `src/models/auto_assign_rule.py`
- **New service** — `AutoTaskAssignmentService` with matching logic
- **Minimal changes** to `ReviewService` — ~5 lines added to `create_review()` to call auto-assign when no explicit reviewer
- **Alembic migration** — new table `pull_request_review_auto_assignment_rule`
- **Backend only** — no frontend changes required for v1 (review_admin uses API directly)
