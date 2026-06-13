## ADDED Requirements

### Requirement: review_admin can create auto-assignment rules
The system SHALL allow users with `assign` permission on `reviews` (review_admin role) to create auto-assignment rules. Each rule SHALL have a human-readable name, priority, match conditions, target reviewers list, optional max assignments cap, optional date range, and active status.

#### Scenario: Create a valid rule
- **WHEN** a review_admin sends `POST /auto-task-assignment/rules` with valid JSON body
- **THEN** the system creates a new rule and returns it with HTTP 201 and the rule's assigned ID

#### Scenario: Non-admin cannot create a rule
- **WHEN** a user without `assign` permission sends `POST /auto-task-assignment/rules`
- **THEN** the system returns HTTP 403 Forbidden

#### Scenario: Create rule with invalid fields
- **WHEN** a review_admin sends `POST /auto-task-assignment/rules` with missing `name` or missing `conditions` or missing `assign_to`
- **THEN** the system returns HTTP 422 Unprocessable Entity

### Requirement: review_admin can list, read, update, delete, and toggle rules
The system SHALL provide full CRUD for auto-assignment rules, plus a dedicated toggle endpoint for enable/disable. All operations require `assign` permission on `reviews`.

#### Scenario: List all rules
- **WHEN** a review_admin sends `GET /auto-task-assignment/rules`
- **THEN** the system returns all rules ordered by priority (ascending), with pagination

#### Scenario: Get a single rule by ID
- **WHEN** a review_admin sends `GET /auto-task-assignment/rules/{rule_id}`
- **THEN** the system returns the rule if found, or HTTP 404 if not found

#### Scenario: Update a rule
- **WHEN** a review_admin sends `PUT /auto-task-assignment/rules/{rule_id}` with updated fields
- **THEN** the system updates the rule and returns the updated object

#### Scenario: Delete a rule
- **WHEN** a review_admin sends `DELETE /auto-task-assignment/rules/{rule_id}`
- **THEN** the system deletes the rule and returns HTTP 204 No Content

#### Scenario: Toggle rule active status
- **WHEN** a review_admin sends `PATCH /auto-task-assignment/rules/{rule_id}/toggle`
- **THEN** the system flips `is_active` (true→false or false→true) and returns the updated rule

### Requirement: rules support priority-ordered, first-match-wins evaluation
Rules SHALL have an integer `priority` field (lower number = higher priority). When a review arrives without an explicit reviewer, the system SHALL evaluate active, non-expired rules in priority order and apply the first matching rule only.

#### Scenario: Highest-priority matching rule wins
- **WHEN** rule A (priority=10, conditions match PROJ-A/frontend) and rule B (priority=20, conditions match PROJ-A/*) both exist
- **AND** a review arrives for PROJ-A/frontend without an explicit reviewer
- **THEN** rule A is applied and rule B is ignored

#### Scenario: No rule matches
- **WHEN** no active rule's conditions match the incoming review
- **THEN** the review is created without any auto-assignments (remains unassigned)

### Requirement: conditions support project_key, repository_slug, PR user, branch, and status matching
The `conditions` JSON field SHALL support these optional keys. All present keys are ANDed. List values are ORed. Missing keys are wildcards.

#### Scenario: Match by project_key only
- **WHEN** a rule has conditions `{"project_key": ["PROJ-A", "PROJ-B"]}`
- **AND** a review arrives for PROJ-A
- **THEN** the rule matches

#### Scenario: Match by project_key AND repository_slug
- **WHEN** a rule has conditions `{"project_key": ["PROJ-A"], "repository_slug": ["frontend"]}`
- **AND** a review arrives for PROJ-A/frontend
- **THEN** the rule matches
- **AND** a review arrives for PROJ-A/backend
- **THEN** the rule does NOT match

#### Scenario: Match by source_branch_prefix
- **WHEN** a rule has conditions `{"source_branch_prefix": "hotfix/"}`
- **AND** a review arrives with source_branch `hotfix/critical-fix`
- **THEN** the rule matches
- **AND** a review arrives with source_branch `feature/new-thing`
- **THEN** the rule does NOT match

#### Scenario: Match by pull_request_user
- **WHEN** a rule has conditions `{"pull_request_user": ["alice", "bob"]}`
- **AND** a review arrives where pull_request_user is "alice"
- **THEN** the rule matches

#### Scenario: Match by pull_request_status
- **WHEN** a rule has conditions `{"pull_request_status": ["draft"]}`
- **AND** a review arrives with status "open"
- **THEN** the rule does NOT match

### Requirement: auto-assignment assigns all reviewers from the matched rule's list
When a rule matches, the system SHALL create `PullRequestReviewAssignment` records for ALL reviewer usernames in the rule's `assign_to` list. If `max_assignments` > 0, only that many reviewers from the list SHALL be assigned.

#### Scenario: Assign all reviewers from matched rule
- **WHEN** a rule with `assign_to: ["alice", "bob"]` and `max_assignments: 0` matches a review
- **THEN** both Alice and Bob get `PullRequestReviewAssignment` records with `assigned_by = "auto_assign"` and `assignment_status = "pending"`

#### Scenario: max_assignments limits how many are assigned
- **WHEN** a rule with `assign_to: ["alice", "bob", "carol"]` and `max_assignments: 2` matches
- **THEN** only Alice and Bob are assigned (first 2 from the list)

#### Scenario: Reviewer already assigned is skipped
- **WHEN** a rule matches but one reviewer already has an existing assignment for the same review
- **THEN** that reviewer is skipped (unique constraint prevents duplicate, the code checks before creating)

### Requirement: rules support date ranges and enable/disable
Rules SHALL support optional `starts_at` and `expires_at` timestamps (timezone-aware). Rules outside their date range SHALL be treated as inactive. The `is_active` boolean SHALL allow manual enable/disable without deleting the rule.

#### Scenario: Rule outside date range is not evaluated
- **WHEN** a rule has `starts_at` in the future or `expires_at` in the past
- **THEN** the system never considers that rule during auto-assignment

#### Scenario: Disabled rule is not evaluated
- **WHEN** a rule has `is_active: false`
- **THEN** the system never considers that rule during auto-assignment

### Requirement: auto-assignment fires automatically on review creation
When a review is created via `POST /api/v1/reviews` (or any path that calls `ReviewService.create_review()`) without an explicit `reviewer` field, the system SHALL evaluate auto-assignment rules and create assignments if a matching rule is found.

#### Scenario: Auto-assignment during review creation
- **WHEN** `POST /api/v1/reviews` is called with `reviewer: null`
- **AND** a matching auto-assignment rule exists
- **THEN** the system creates the review AND auto-assigns reviewers AND returns the response with the review created

#### Scenario: Explicit reviewer skips auto-assignment
- **WHEN** `POST /api/v1/reviews` is called with `reviewer: "alice"`
- **AND** matching auto-assignment rules exist
- **THEN** Alice is assigned manually and auto-assignment is NOT evaluated

### Requirement: auto-assignment failure does not prevent review creation
If the auto-assignment engine encounters an error (e.g., database failure, invalid rule data), the review SHALL still be created successfully without assignments. The error SHALL be logged.

#### Scenario: Auto-assign error is non-fatal
- **WHEN** the auto-assignment engine throws an exception during evaluation
- **THEN** the review is created successfully (no assignments), the exception is logged, and the API returns the review without error
