## 1. Database Model & Migration

- [x] 1.1 Create `PullRequestReviewAutoAssignmentRule` model in `src/models/auto_assign_rule.py` with fields: id, name, description, priority, conditions (JSON), assign_to (JSON), max_assignments, starts_at, expires_at, is_active, created_by, created_at, updated_at, and index on (is_active, priority)
- [x] 1.2 Register the new model in `src/models/__init__.py` by importing `PullRequestReviewAutoAssignmentRule`
- [x] 1.3 Generate and apply Alembic migration: `alembic revision --autogenerate -m "create auto_assign_rule table"` then `alembic upgrade head`
- [x] 1.4 Create Pydantic schemas for the rule: `AutoAssignRuleCreate`, `AutoAssignRuleUpdate`, `AutoAssignRuleResponse`, `AutoAssignRuleToggleResponse` in a new file `src/schemas/auto_assign_rule.py`

## 2. Auto-Assignment Service

- [x] 2.1 Create `AutoTaskAssignmentService` in `src/services/auto_assign_service.py` with `get_active_rules()` that queries rules where `is_active=True`, `starts_at <= now` (or null), `expires_at > now` (or null), ordered by `priority` ascending
- [x] 2.2 Implement `rule_matches(rule, review_data)` — evaluate conditions JSON against review: exact match for `project_key`/`repository_slug`/`pull_request_user`/`target_branch` (list OR), prefix match for `source_branch_prefix` (str starts_with), exact match for `pull_request_status` (list OR), all keys ANDed
- [x] 2.3 Implement `auto_assign(db, review_base, review_data)` — fetches active rules, finds first match, creates `PullRequestReviewAssignment` records for each reviewer (up to `max_assignments`), skips already-assigned, dispatches notifications
- [x] 2.4 Implement `_ensure_reviewer_exists(db, username)` — verify reviewer exists in User table before assigning, skip with warning if not found
- [x] 2.5 Add unit tests for `rule_matches()` covering all condition types, empty conditions, AND/OR logic, and edge cases (null fields, empty lists, prefix matching)

## 3. API Endpoints for Rule Management

- [x] 3.1 Create `auto_task_assignment.py` router in `src/api/v1/endpoints/auto_task_assignment.py` with permission guard using `check_permission("assign", "reviews")`
- [x] 3.2 Implement `POST /auto-task-assignment/rules` — create rule, return 201
- [x] 3.3 Implement `GET /auto-task-assignment/rules` — list rules ordered by priority, paginated
- [x] 3.4 Implement `GET /auto-task-assignment/rules/{rule_id}` — get single rule, 404 if not found
- [x] 3.5 Implement `PUT /auto-task-assignment/rules/{rule_id}` — update rule fields
- [x] 3.6 Implement `DELETE /auto-task-assignment/rules/{rule_id}` — delete rule, return 204
- [x] 3.7 Implement `PATCH /auto-task-assignment/rules/{rule_id}/toggle` — flip `is_active`, return updated rule
- [x] 3.8 Register the new router in `src/api/v1/api.py` with prefix `/auto-task-assignment` and tag `auto-task-assignment`

## 4. Integration into Review Creation

- [x] 4.1 In `ReviewService.create_review()` (line ~446), add an `else` branch after the manual `if reviewer:` block that calls `AutoTaskAssignmentService.auto_assign()` when no explicit reviewer is provided, before the commit
- [x] 4.2 Wrap auto-assignment call in try/except that logs errors but does NOT fail the review creation (non-fatal per spec)
- [x] 4.3 Verify that the existing SSE event dispatch in `upsert_review()` (line ~638) correctly fires after auto-assigned reviews — the assignments should already exist in the database when SSE fires

## 5. Notification & Audit

- [x] 5.1 In `AutoTaskAssignmentService.auto_assign()`, after creating each assignment, dispatch an in-app notification using the same pattern as `MultiReviewerService._dispatch_review_assigned_notification()` (or call it directly)
- [x] 5.2 Add structured logging with `extra` for: rule matched (rule_id, rule_name, pull_request_id), assignments created (reviewer count, pull_request_id), errors/warnings

## 6. Tests

- [x] 6.1 Write tests for the API endpoints: create/list/get/update/delete/toggle rules, permission checks (403 for non-admin), validation errors (422 for missing fields)
- [x] 6.2 Write integration tests for the full flow: create a rule, create a review without reviewer, verify auto-assignment created the assignment records with `assigned_by = "auto_assign"` and `status = "pending"`
- [x] 6.3 Write edge case tests: no matching rule (review stays unassigned), max_assignments limits, duplicate review creation (unique constraint handling), rule outside date range (not evaluated), disabled rule (not evaluated), explicit reviewer skips auto-assignment
