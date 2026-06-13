## Context

The auto-assignment rule backend is complete with endpoints under `/auto-task-assignment/rules`. However, there is no frontend UI — admins must use curl or REST clients to manage rules. The Task Assignment section already has multiple sub-views (main view at `/task-assignment`, analytics at `/task-assignment/analytics`, detail at `/task-assignment/:id`), creating a natural location for a rule management view.

The frontend uses Vue 3 Composition API with `<script setup lang="ts">`, Element Plus component library, and a `request` utility wrapping Axios. Route guards use `meta.requiresReviewAdmin` to restrict access to `review_admin` and `system_admin` roles.

## Goals / Non-Goals

**Goals:**
- Provide a tabular view listing all auto-assignment rules with name, priority, conditions, assign-to, and active status
- Allow `review_admin` to create new rules via a dialog form
- Allow `review_admin` to edit existing rules via the same dialog form
- Provide inline enable/disable toggle for each rule
- Provide delete with confirmation dialog
- Add a `/task-assignment/rules` route with `requiresReviewAdmin` guard
- Add a sidebar navigation link under the Task Assignment menu
- Follow the same UI patterns as the existing Task Assignment view

**Non-Goals:**
- Backend API changes (all endpoints already exist)
- Complex inline JSON condition builders — conditions are entered as JSON text with helper formatting
- Round-robin or load-balancing UI (the backend assigns all matched reviewers)
- Rule match history or audit log display
- Real-time SSE updates for the rules view

## Decisions

### 1. Separate view at `/task-assignment/rules`
A new view rather than a tab within the existing TaskAssignmentView keeps the codebase clean and follows the established pattern (the analytics view is already a separate route). The sidebar navigation will link to all three: Task Assignment, Rules, Analytics.

### 2. JSON textarea for conditions
Conditions are stored as JSON with a flexible schema (`project_key`, `repository_slug`, `pull_request_user`, `source_branch_prefix`, `target_branch`, `pull_request_status`). Rather than building individual form fields for each condition key (which would need updating if new condition types are added), v1 uses a labeled JSON textarea with a syntax example below it. The formatted JSON is displayed in the table as a truncated summary with a tooltip showing the full JSON.

Alternative considered: Individual form fields for each supported condition key. Rejected for v1 because the conditions schema may evolve and a textarea is simpler to maintain. Can be enhanced later.

### 3. Assign To as a tag-style multi-input
Usernames are entered as comma-separated text in an `el-input` and displayed as `el-tag` elements in the table. No autocomplete from the user list for v1 simplicity — the admin knows the usernames.

### 4. Inline toggle for enable/disable
Each row has an `el-switch` wired to the `PATCH /auto-task-assignment/rules/{id}/toggle` endpoint. No confirmation dialog for toggle — it's a quick action with immediate visual feedback.

### 5. Shared dialog for create and edit
A single `el-dialog` component renders different content based on whether creating or editing. The same form fields are used for both operations. This follows the pattern seen in other admin interfaces.

### 6. Route ordering
The `/task-assignment/rules` route must be registered BEFORE `/task-assignment/:id` in the router, otherwise `rules` would be captured as `:id`.

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| **JSON textarea is error-prone** | Add client-side JSON validation with user-friendly error messages before submit. The backend also validates on receipt |
| **User mistypes a username in assign_to** | The backend skips non-existent usernames. The rule still works for valid ones |
| **New route conflicts with detail view** | Route order matters — `rules` must come before `:id` in the route definition. Documented in tasks |
| **No confirmation on toggle** | Toggle is low-risk (rule can be toggled back immediately). Delete has a confirmation dialog |
