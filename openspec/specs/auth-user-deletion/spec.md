# Auth User Deletion

## Purpose

Provide an endpoint for administrators to permanently delete AuthUser records, cascading to related records (role assignments, audit logs, personal access tokens) while preserving the linked Git user.

## Requirements

### Requirement: Admin can delete an auth user physically
The system SHALL provide an endpoint for administrators to permanently delete an AuthUser record. The deletion SHALL cascade to related records (role assignments, audit logs, personal access tokens) and revoke all active sessions, but SHALL NOT delete the linked Git user.

#### Scenario: Successful auth user deletion
- **WHEN** an admin sends `DELETE /api/v1/users/auth/{auth_user_id}`
- **THEN** the AuthUser record SHALL be deleted
- **AND** all role assignments for that auth user SHALL be deleted
- **AND** all audit logs for that auth user SHALL be deleted
- **AND** all personal access tokens for that auth user SHALL be deleted
- **AND** all active refresh sessions for that auth user SHALL be revoked from Redis
- **AND** the linked Git user (if any) SHALL NOT be deleted
- **AND** `AuthUser.user_id` (the link) ceases to exist with the row

#### Scenario: Deletion requires manage/users permission
- **WHEN** a user without `manage`/`users` permission sends `DELETE /api/v1/users/auth/{auth_user_id}`
- **THEN** the system SHALL return `403 Forbidden`

#### Scenario: Non-existent auth user returns 404
- **WHEN** `DELETE /api/v1/users/auth/{auth_user_id}` is called with an ID that does not exist
- **THEN** the system SHALL return `404 Not Found`

#### Scenario: Auth user deletion does not affect reviews or scores
- **WHEN** an auth user is deleted who has no linked git user
- **THEN** `pull_request_review_base`, `pull_request_review_assignment`, and `pull_request_score` records SHALL remain unchanged

### Requirement: Auth user deletion disassociates the linked Git user
The system SHALL break the link between the deleted AuthUser and its GitUser (if any), by deleting the AuthUser row which carries the `user_id` FK column.

#### Scenario: Linked Git user survives auth user deletion
- **WHEN** an auth user with `user_id = 42` is deleted
- **THEN** the Git user with `id = 42` SHALL remain in the `user` table
- **AND** no auth user SHALL reference git user id 42 after the deletion
