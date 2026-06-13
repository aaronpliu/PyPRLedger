## Why

The auto-assignment backend is complete — `review_admin` can manage rules via the API. But there's no UI to view, create, edit, enable/disable, or delete rules. Requiring admins to use curl or a REST client is a poor experience and limits adoption. Adding a rule management UI inside the existing Task Assignment section gives admins a single place to manage both manual assignments and auto-assignment rules.

## What Changes

- **New frontend view** `RulesManagementView.vue` at `/task-assignment/rules` — a tabular view listing all auto-assignment rules with inline enable/disable toggles, create/edit dialogs, and delete confirmation
- **New API client module** `autoAssignRules.ts` — typed methods for all `/auto-task-assignment/rules` endpoints
- **New route** under `/task-assignment/rules` with `requiresReviewAdmin` guard in the router
- **Navigation tabs** added to the Task Assignment page header to switch between "Assignments" and "Rules" views
- No backend changes required — the API was built in the previous change

## Capabilities

### New Capabilities
- `auto-assign-rule-ui`: Browser-based management of auto-assignment rules for review admins, including rule listing, creation, editing, enable/disable toggling, and deletion — integrated into the existing Task Assignment area

### Modified Capabilities
*(No existing specs to modify)*

## Impact

- **New view**: `src/views/reviews/RulesManagementView.vue`
- **New API module**: `src/api/autoAssignRules.ts`
- **Modified view**: `src/views/reviews/TaskAssignmentView.vue` — add navigation tabs in the header
- **Modified router**: `src/router/index.ts` — add `/task-assignment/rules` route
- **No backend changes** — consumes existing `/auto-task-assignment/rules` endpoints
