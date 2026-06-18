## Context

The ProjectRegistry maps `(project_key, repository_slug)` pairs to logical `app_name` values (e.g., "member", "tv", "football"). New projects are auto-registered as "Unknown" until an admin assigns them via the Admin UI. Currently:

- **Task Assignment page**: `app_name` filter exists but is inside a `FilterPopover` — not prominent
- **Auto-assignment rules**: Must enumerate `project_key` + `repository_slug` pairs; no `app_name` condition
- **Analytics page**: No `app_name` filter at all
- **URL**: No deep-linking by app

## Goals / Non-Goals

**Goals:**
- Make `app_name` a first-class navigation concept in Task Assignment (prominent selector, URL sync)
- Add `app_name` as a supported condition key in auto-assignment rules
- Add `app_names` filter to the Analytics page
- Add `app_name` to the rule conditions builder in the Rules Management UI

**Non-Goals:**
- Not changing how ProjectRegistry works (auto-register to "Unknown", admin-curated)
- Not changing the existing `project_key`/`repository_slug` conditions (backward compatible)
- Not adding a global "current app" context across all pages (app selector is scoped to Task Assignment section)
- Not modifying the existing FilterPopover behavior (it remains for advanced filtering)

## Decisions

### Decision 1: App selector as tab bar at top of Task Assignment page

A horizontal tab bar renders app options fetched from `GET /api/v1/apps`. Each tab shows the app name. An "Unknown" tab is always included (hardcoded, no app_name needed). An "All" tab shows everything. Selecting a tab sets `appFilter` and triggers a review reload.

**Why tabs instead of dropdown?**
- Zero-click switching — one tap filters
- "Unknown" gets equal visual weight as a triage tool
- Tabs are naturally exclusive (single-app focus), matching the use case of "I want to work on Member today"
- Multi-app selection still possible via the existing FilterPopover for advanced queries

### Decision 2: URL sync via query parameter

The selected app is synced to `?app=name` in the URL. On page mount, the URL is read and applied. This enables:
- Bookmarking `/task-assignment?app=member`
- Linking from notifications or reports
- Browser back/forward navigation

**Why query param instead of route param?**
- No new routes needed; stays under `/task-assignment`
- Multiple apps can be comma-separated: `?app=member,tv`
- The FilterPopover's multi-select can override tab selection

### Decision 3: `app_name` resolved once in `auto_assign()`, passed to `rule_matches()`

In `AutoTaskAssignmentService.auto_assign()`, resolve `app_name` using `ProjectRegistryService.get_app_name()` before the rule-matching loop. Pass it as a new parameter to `rule_matches()`. Inside `rule_matches()`, check for `app_name` in the condition dict alongside existing keys.

**Why resolve before the loop instead of inside `rule_matches()`?**
- Single DB query instead of N queries (one per active rule)
- `rule_matches()` stays synchronous (no `async`)
- Clean separation: resolution at the service layer, matching at the condition layer

**Backward compatibility:**
- Rules with `project_key`/`repository_slug` conditions continue working unchanged
- Rules with `app_name` conditions resolve via ProjectRegistry
- A rule can combine both (AND semantics)
- "Unknown" reviews never match an `app_name` condition (by design)

### Decision 4: Analytics page gets an `app_names` query parameter

The analytics API endpoint gets the same `app_names` filter pattern used by the task assignment endpoint. The frontend adds an app dropdown that replaces the existing project filter.

**Why replace project filter with app filter?**
- Apps are the logical grouping users think in
- A single app maps to multiple projects — filtering by app is more useful than filtering by individual project
- The project filter can remain available in the advanced filter popover

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| **Many apps cause horizontal overflow in tab bar** | Use `el-scrollbar` or a "more" dropdown for overflow; tabs scroll horizontally |
| **`app_name` resolution adds a DB query per review creation** | Single query per `create_review()` call, not per rule — negligible overhead |
| **Rule with both `app_name` and `project_key` could be confusing** | AND semantics are consistent with existing condition behavior; document clearly in UI |
| **"Unknown" tab shows unconfigured projects** — could be noisy if many | It's intended as a triage tool; once admin assigns apps, those reviews disappear from Unknown |
