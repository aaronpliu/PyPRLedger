## Context

Pull request reviews are submitted via `POST /api/v1/reviews` which calls `ReviewService.upsert_review()`. Currently, a reviewer can only be assigned in two ways:

1. **Explicit in the API call** — the caller passes a `reviewer` field in the request body
2. **Manual assignment** — a `review_admin` uses `POST /task-assignment/{review_id}/assign` after the review exists

Both require human intervention. The system has no concept of rules or automated dispatching. The existing `PullRequestReviewAssignment` model already supports `assigned_by` tracking, and the notification infrastructure (`MultiReviewerService._dispatch_review_assigned_notification()`) is in place.

The RBAC system uses `check_permission("assign", "reviews")` to gate assignment operations, which we reuse for the new endpoints.

## Goals / Non-Goals

**Goals:**
- Allow `review_admin` to define rules that auto-assign reviewers when new reviews arrive
- Support matching on: project_key, repository_slug, pull_request_user, branch patterns, and PR status
- Support priority-ordered rules (first matching rule wins)
- Support assignment of multiple reviewers per rule (all matched reviewers get assigned)
- Support temporal validity (date range) and enable/disable toggling per rule
- Integrate cleanly into the existing review creation flow with minimal code changes
- Notifications fire for auto-assigned reviewers (same as manual assignments)

**Non-Goals:**
- Round-robin or load-balanced assignment (all matched reviewers are assigned)
- Admin UI (rules are managed via API only for v1)
- Re-evaluation of rules on review updates (only fires on new review creation)
- Project-scoped RBAC enforcement for rules (existing RBAC is sufficient)
- Rule match audit log beyond the `assigned_by = "auto_assign"` sentinel

## Decisions

### 1. Table name: `pull_request_review_auto_assignment_rule`
The suffix `_rule` clarifies that each row is a rule definition, not an individual assignment event. This avoids confusion with `pull_request_review_assignment` which stores per-reviewer assignments.

### 2. Conditions stored as JSON
A single JSON column (`conditions`) stores all match criteria. This provides flexibility to add new condition types without schema migrations. The structure uses optional keys where:
- Present keys are ANDed together (all must match)
- List values are ORed (any value in the list matches)
- Missing keys are wildcards (no filter on that dimension)

Alternative considered: A separate `rule_condition` table with rows for (field, operator, value). This was rejected for v1 because JSON matching is simpler and rules are expected to be low-volume (tens, not thousands).

### 3. First-match-wins by priority
Rules are evaluated in ascending priority order. The first matching rule is applied and evaluation stops. This makes behavior predictable and easy to reason about — the most specific rule (lowest number) takes precedence.

Alternative considered: Evaluate all matching rules and union the reviewers. Rejected because it makes debugging unpredictable and allows conflicting rules to produce unexpected assignments.

### 4. Auto-assignment only fires on review creation
The hook is placed in `ReviewService.create_review()` — which is called both standalone and from `upsert_review()`'s create path. The update path (existing review updated) does not trigger auto-assignment. This prevents retroactive assignment when rules change.

### 5. `assigned_by = "auto_assign"` sentinel
Auto-created `PullRequestReviewAssignment` records set `assigned_by` to `"auto_assign"` (not a username). This distinguishes them from manual assignments in queries and the admin view, without needing a new column. If rule-level tracking is needed later, a `auto_assign_rule_id` foreign key can be added to the assignment table.

### 6. Assignment status: `"pending"` for auto-assignments
Manual assignments use `"assigned"` as the initial status. Auto-assignments use `"pending"` (the column's `server_default` value). This aligns with the existing priority sorting in `MultiReviewerService.get_reviews()` which surfaces reviews with no "active" reviewers (status != "pending") at higher priority in the admin queue.

### 7. Notification dispatch reuses existing pattern
The `MultiReviewerService._dispatch_review_assigned_notification()` method handles in-app notification dispatch. The new `AutoTaskAssignmentService` calls the same pattern (or the notification service directly) to ensure auto-assigned reviewers receive the same notification experience as manually assigned ones.

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| **Race condition**: Two concurrent create calls for the same PR both trigger auto-assignment | The `(review_base_id, reviewer)` unique constraint on `PullRequestReviewAssignment` prevents duplicate assignments. The second attempt silently skips already-assigned reviewers |
| **Rule accidentally assigns wrong person** | `max_assignments` caps the number of auto-assignments. The `review_admin` can always manually remove or replace assignments |
| **Rule changes don't affect existing reviews** | Explicit design choice. Existing reviews keep their assignments. The admin can manually reassign if needed |
| **Empty assign_to list in a matched rule** | Skip the rule (no assignments created), log a warning, and continue to evaluate next rule? Or stop and leave unassigned? **Decision**: If a rule matches but has an empty assign_to, log a warning and STOP (first-match-wins still applies — the rule matched, it just produces no assignments) |
| **Reviewer username doesn't exist in Git users table** | Skip that username, log a warning, assign the rest. If none could be assigned, log an error but don't fail the review creation |
