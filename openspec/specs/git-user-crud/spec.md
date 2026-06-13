# Git User CRUD

## Purpose

All Git User (Bitbucket user) CRUD operations are accessible under the `/api/v1/users/git/` path prefix with the path parameter named `git_user_id`.

## Requirements

### Requirement: Git user CRUD endpoints are served under /users/git/
All Git User (Bitbucket user) CRUD operations SHALL be accessible under the `/api/v1/users/git/` path prefix. The path parameter SHALL be named `git_user_id`.

**FROM:** `/api/v1/users/{user_id}`
**TO:** `/api/v1/users/git/{git_user_id}`

Affected endpoints:

| Operation | Old path | New path |
|---|---|---|
| Create | `POST /api/v1/users/` | `POST /api/v1/users/git/` |
| List | `GET /api/v1/users/` | `GET /api/v1/users/git/` |
| Login | `POST /api/v1/users/login` | `POST /api/v1/users/git/login` |
| Statistics | `GET /api/v1/users/statistics` | `GET /api/v1/users/git/statistics` |
| Active users | `GET /api/v1/users/active` | `GET /api/v1/users/git/active` |
| Reviewers | `GET /api/v1/users/reviewers` | `GET /api/v1/users/git/reviewers` |
| Get by ID | `GET /api/v1/users/{user_id}` | `GET /api/v1/users/git/{git_user_id}` |
| Get by username | `GET /api/v1/users/username/{username}` | `GET /api/v1/users/git/username/{username}` |
| Update | `PUT /api/v1/users/{user_id}` | `PUT /api/v1/users/git/{git_user_id}` |
| Toggle reviewer | `PATCH /api/v1/users/{user_id}/toggle-reviewer` | `PATCH /api/v1/users/git/{git_user_id}/toggle-reviewer` |
| Delete | `DELETE /api/v1/users/{user_id}` | `DELETE /api/v1/users/git/{git_user_id}` |

#### Scenario: Create git user under new path
- **WHEN** a `POST /api/v1/users/git/` request is sent with valid git user data
- **THEN** the system SHALL create a new Git user and return 201

#### Scenario: List git users under new path
- **WHEN** a `GET /api/v1/users/git/` request is sent
- **THEN** the system SHALL return a paginated list of Git users
- **AND** the response format SHALL be identical to the previous behavior

#### Scenario: Delete git user under new path
- **WHEN** an admin sends `DELETE /api/v1/users/git/{git_user_id}`
- **THEN** the Git user SHALL be deleted
- **AND** related review/score/assignment fields SHALL be set to NULL (via FK SET NULL)
- **AND** linked AuthUser's `user_id` SHALL be set to NULL (via FK SET NULL)

#### Scenario: Old path returns 404
- **WHEN** a `DELETE /api/v1/users/42` is sent (old path)
- **THEN** the system SHALL return `404 Not Found`
- **AND** the response SHALL indicate the new path in the error message
