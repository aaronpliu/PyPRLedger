# Preserve Reviews on User Deletion

## Purpose

Ensure that pull request reviews, assignments, and scores survive the deletion of Git user records. Instead of cascading deletion, foreign key references are set to NULL so historical data is preserved.

## Requirements

### Requirement: Review base records SHALL survive git user deletion
When a row in the `user` table (git user) is deleted, the system SHALL retain all associated `pull_request_review_base` records. The `pull_request_user` column SHALL be set to NULL.

#### Scenario: Delete git user with authored reviews
- **WHEN** a `user` with authored `pull_request_review_base` records is deleted via `UserService.delete_user()`
- **THEN** the `pull_request_review_base` records SHALL remain in the database
- **AND** their `pull_request_user` column SHALL be NULL

#### Scenario: List reviews after author deletion
- **WHEN** a client calls GET `/api/v1/reviews/` after the author's user record has been deleted
- **THEN** reviews authored by the deleted user SHALL appear in the response with `pull_request_user: null`

### Requirement: Review assignments SHALL survive reviewer deletion
When a row in the `user` table is deleted, the system SHALL retain all associated `pull_request_review_assignment` records where the deleted user was the `reviewer`. The `reviewer` column SHALL be set to NULL.

#### Scenario: Delete git user who is a reviewer on assignments
- **WHEN** a `user` with reviewer entries in `pull_request_review_assignment` is deleted
- **THEN** the assignment records SHALL remain in the database
- **AND** their `reviewer` column SHALL be NULL

### Requirement: Review scores SHALL survive reviewer deletion
When a row in the `user` table is deleted, the system SHALL retain all associated `pull_request_score` records where the deleted user was the `reviewer`. The `reviewer` column SHALL be set to NULL.

#### Scenario: Delete git user who has submitted scores
- **WHEN** a `user` with `pull_request_score` records is deleted
- **THEN** the score records SHALL remain in the database
- **AND** their `reviewer` column SHALL be NULL

### Requirement: Assignments with assigned_by SHALL survive assignor deletion
The `assigned_by` column in `pull_request_review_assignment` already uses `ON DELETE SET NULL`. This requirement documents existing correct behavior.

#### Scenario: Delete git user who assigned reviews
- **WHEN** a `user` who has assigned reviews (referenced in `assigned_by`) is deleted
- **THEN** the assignment records SHALL remain in the database
- **AND** their `assigned_by` column SHALL be NULL

### Requirement: Auth user SHALL be disconnected from deleted git user
The `user_id` column in `auth_user` already uses `ON DELETE SET NULL` when the referenced `user.id` is deleted. This requirement documents existing correct behavior.

#### Scenario: Delete git user linked to an auth user
- **WHEN** a `user` record linked via `auth_user.user_id` is deleted
- **THEN** the `auth_user` record SHALL remain
- **AND** its `user_id` SHALL be NULL

### Requirement: Auth user deletion SHALL NOT cascade to reviews or scores
Currently there is no physical auth user deletion path (only deactivation). If one is introduced in the future, it SHALL NOT cascade to reviews, review assignments, or scores.

#### Scenario: Future auth user deletion (design intent)
- **WHEN** an `auth_user` record is physically deleted (if such a path is added later)
- **THEN** `pull_request_review_base`, `pull_request_review_assignment`, and `pull_request_score` records SHALL NOT be affected
