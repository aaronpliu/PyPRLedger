## 1. Auto-assignment: add `app_name` condition support

- [ ] 1.1 Add `ProjectRegistryService` import to `auto_assign_service.py`
- [ ] 1.2 In `AutoTaskAssignmentService.auto_assign()`, resolve `app_name` via `ProjectRegistryService.get_app_name(project_key, repository_slug, db)` before the rule-matching loop
- [ ] 1.3 Pass resolved `app_name` to `rule_matches()` as a new parameter
- [ ] 1.4 In `rule_matches()`, add `app_name` condition key handling: if `app_name` is in `rule.conditions`, match against the resolved `app_name` using the same list-OR pattern as other conditions
- [ ] 1.5 Ensure "Unknown" reviews never match `app_name` conditions

## 2. Task Assignment page: app selector bar

- [ ] 2.1 Fetch available apps from `GET /api/v1/apps` on page mount (already done in `loadAvailableApps()`)
- [ ] 2.2 Add horizontal tab bar at the top of TaskAssignmentView with: "All", each app name, and "Unknown"
- [ ] 2.3 On tab selection, set `appFilter` to the selected app name (single string) and trigger `loadReviews()`
- [ ] 2.4 Read `?app=` from the URL query on mount and pre-select the corresponding tab
- [ ] 2.5 Sync tab selection back to URL via `router.replace({ query: { app: selectedApp } })`
- [ ] 2.6 Handle "All" tab (clear filter) and "Unknown" tab (pass `app_names=Unknown` to API)

## 3. Analytics page: add `app_names` filter

- [ ] 3.1 Add `app_names` query parameter support to the analytics API endpoint (similar to task-assignment pattern)
- [ ] 3.2 Add app dropdown filter to `TaskAssignmentAnalyticsView.vue`, replacing or alongside the project filter
- [ ] 3.3 Wire the app selection to the API call

## 4. Rules Management UI: add `app_name` condition

- [ ] 4.1 Add `app_name` as an option in the auto-assignment rule conditions builder in `RulesManagementView.vue`
- [ ] 4.2 Fetch available apps from `GET /api/v1/apps` for the condition dropdown options

## 5. Verify

- [ ] 5.1 Run `ruff format && ruff check --fix` on changed backend files
- [ ] 5.2 Run `pytest -v` to confirm no regressions
- [ ] 5.3 Verify frontend builds without errors: check `npm run build` or `npm run lint`
