## ADDED Requirements

### Requirement: review_admin can view all auto-assignment rules in a table
The system SHALL display a paginated table of all auto-assignment rules. The table SHALL show: rule name, priority, conditions (truncated with full JSON tooltip), assign-to reviewers (as tags), max assignments, active status (with toggle), created date, and action buttons (edit, delete).

#### Scenario: Rules table loads on page entry
- **WHEN** a review_admin navigates to `/task-assignment/rules`
- **THEN** the system fetches rules from `GET /auto-task-assignment/rules` and displays them in a table

#### Scenario: Empty state
- **WHEN** no rules exist
- **THEN** the system shows an empty table with a message "No auto-assignment rules configured" and a "Create Rule" button

### Requirement: review_admin can create a new rule
The system SHALL provide a "Create Rule" button that opens a dialog with form fields for name, description, priority, conditions (JSON textarea), assign-to (comma-separated usernames), max assignments, starts_at, expires_at, and is_active toggle.

#### Scenario: Create a valid rule
- **WHEN** a review_admin fills the create dialog and submits valid data
- **THEN** the system calls `POST /auto-task-assignment/rules`, closes the dialog, shows a success message, and refreshes the table

#### Scenario: Create with invalid JSON in conditions
- **WHEN** a review_admin enters invalid JSON in the conditions field and submits
- **THEN** the system shows a client-side validation error and does NOT submit the form

#### Scenario: Create with missing required fields
- **WHEN** a review_admin submits the form with empty name, empty conditions, or empty assign_to
- **THEN** the system shows validation errors on the required fields

### Requirement: review_admin can edit an existing rule
The system SHALL provide an "Edit" button per row that opens the same dialog prepopulated with the rule's current values.

#### Scenario: Edit and save a rule
- **WHEN** a review_admin edits a rule's fields and saves
- **THEN** the system calls `PUT /auto-task-assignment/rules/{id}`, closes the dialog, shows a success message, and refreshes the table

### Requirement: review_admin can toggle a rule's active status inline
Each row SHALL have an `el-switch` toggle that immediately enables or disables the rule.

#### Scenario: Toggle rule on
- **WHEN** a review_admin clicks the toggle on a disabled rule
- **THEN** the system calls `PATCH /auto-task-assignment/rules/{id}/toggle`, the toggle shows as active, and a success message is shown

#### Scenario: Toggle rule off
- **WHEN** a review_admin clicks the toggle on an active rule
- **THEN** the system calls `PATCH /auto-task-assignment/rules/{id}/toggle`, the toggle shows as inactive, and a success message is shown

### Requirement: review_admin can delete a rule with confirmation
The system SHALL provide a "Delete" button per row that shows a confirmation dialog before deleting.

#### Scenario: Delete a rule
- **WHEN** a review_admin clicks "Delete" and confirms in the dialog
- **THEN** the system calls `DELETE /auto-task-assignment/rules/{id}`, closes the dialog, shows a success message, and removes the row from the table

#### Scenario: Cancel delete
- **WHEN** a review_admin clicks "Delete" and cancels the confirmation dialog
- **THEN** no API call is made and the table remains unchanged

### Requirement: the rules view is accessible only to review_admin and system_admin
The `/task-assignment/rules` route SHALL be protected by the `requiresReviewAdmin` meta guard, consistent with other task assignment routes.

#### Scenario: Non-admin is blocked
- **WHEN** a user without `review_admin` or `system_admin` role tries to access `/task-assignment/rules`
- **THEN** the system redirects to `/403`

### Requirement: the rules view is accessible from the sidebar navigation
The sidebar menu under "Task Assignment" SHALL include a "Rules" link pointing to `/task-assignment/rules`.

#### Scenario: Sidebar shows rules link
- **WHEN** a review_admin opens the sidebar Task Assignment submenu
- **THEN** they see three items: "Task Assignment", "Rules", "Analytics"
