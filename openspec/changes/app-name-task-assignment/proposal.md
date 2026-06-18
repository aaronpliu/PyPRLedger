## Why

As the number of projects grows, reviews from different applications (e.g., "member", "tv", "football") are mixed together in the task assignment page. Users must open the filter popover and manually select app names to focus on their area. Auto-assignment rules must enumerate every `(project_key, repository_slug)` pair individually, so adding a new project to an app requires updating every rule. Making `app_name` a first-class concept in task assignment simplifies both the UX and rule management.

## What Changes

- Add a prominent app selector bar at the top of the Task Assignment page with tabs for each app (including "Unknown")
- Sync selected app to URL query parameter (`/task-assignment?app=member`) for bookmarkable deep links
- Add `app_name` as a supported condition key in auto-assignment rules, resolving it from ProjectRegistry during rule matching
- Add `app_names` filter to the Task Assignment Analytics page
- Add `app_name` as a condition option in the auto-assignment rules admin UI

## Capabilities

### New Capabilities
*None — all changes are modifications to existing capabilities.*

### Modified Capabilities
- `auto-task-assignment`: Add `app_name` as a supported condition key in auto-assignment rules, alongside the existing `project_key`, `repository_slug`, `pull_request_user`, `source_branch`, `target_branch`, and `pull_request_status` conditions

## Impact

- Backend: `auto_assign_service.py` — resolve `app_name` in `auto_assign()`, add condition handling in `rule_matches()`
- Backend: Analytics API endpoint — add `app_names` query parameter support
- Frontend: `TaskAssignmentView.vue` — add app selector bar, URL sync
- Frontend: `TaskAssignmentAnalyticsView.vue` — add app filter
- Frontend: `RulesManagementView.vue` — add `app_name` to condition builder
