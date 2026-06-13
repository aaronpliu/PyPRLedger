## 1. API Client & Types

- [x] 1.1 Create `frontend/src/api/autoAssignRules.ts` with TypeScript interfaces `AutoAssignRule`, `AutoAssignRuleCreate`, `AutoAssignRuleListResponse` and API methods mirroring the backend endpoints: `listRules()`, `getRule()`, `createRule()`, `updateRule()`, `deleteRule()`, `toggleRule()`

## 2. Rules Management View

- [x] 2.1 Create `frontend/src/views/reviews/RulesManagementView.vue` with `el-card` wrapper, header with title "Auto-Assignment Rules" and "Create Rule" button, matching the Task Assignment view's layout pattern
- [x] 2.2 Implement rule table with columns: Name, Priority, Conditions (truncated JSON with `el-tooltip` showing full JSON), Assign To (`el-tag` for each username), Max Assignments, Status (`el-switch` for inline toggle), Created Date, Actions (Edit/Delete buttons)
- [x] 2.3 Implement data loading: `onMounted` calls `autoAssignRulesApi.listRules()`, pagination with `el-pagination`, loading state with `v-loading`
- [x] 2.4 Implement inline toggle: `el-switch` `@change` calls `autoAssignRulesApi.toggleRule()`, shows `ElMessage.success()`, refreshes the row
- [x] 2.5 Implement delete with confirmation: Delete button opens `ElMessageBox.confirm()`, on confirm calls `autoAssignRulesApi.deleteRule()`, refreshes table
- [x] 2.6 Implement create rule dialog: `el-dialog` with form fields for name, description (optional), priority (default 100), conditions (JSON textarea with syntax helper text), assign_to (comma-separated usernames), max_assignments (default 0), starts_at (optional date picker), expires_at (optional date picker), is_active (toggle)
- [x] 2.7 Implement edit rule dialog: same dialog component as create but prepopulated with existing rule values, changing the API call to `updateRule()` on save
- [x] 2.8 Add client-side JSON validation in the create/edit dialog: validate conditions field is valid JSON before submit, show inline error message if invalid
- [x] 2.9 Add empty state: when no rules exist, show "No auto-assignment rules configured" message with "Create Rule" button

## 3. Routing & Navigation

- [x] 3.1 Add route `/task-assignment/rules` in `frontend/src/router/index.ts` pointing to `RulesManagementView.vue`, with `meta: { requiresReviewAdmin: true }`, placed BEFORE the `/:id` route to prevent conflict
- [x] 3.2 Add sidebar menu item in `frontend/src/layouts/DefaultLayout.vue` under the Task Assignment submenu: `<el-menu-item index="/task-assignment/rules">{{ t('menu.autoRules') }}</el-menu-item>`

## 4. i18n

- [x] 4.1 Add `menu.autoRules` translation keys in `frontend/src/locales/en.json`, `frontend/src/locales/zh-CN.json`, and `frontend/src/locales/zh-TW.json`:
  - English: `"autoRules": "Rules"`
  - Chinese Simplified: `"autoRules": "规则"`
  - Chinese Traditional: `"autoRules": "規則"`
