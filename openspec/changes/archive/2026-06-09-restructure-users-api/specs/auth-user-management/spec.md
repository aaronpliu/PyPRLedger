## MODIFIED Requirements

### Requirement: Auth user management endpoints are served under /users/auth/

All Auth User (system login user) management operations SHALL be accessible under the `/api/v1/users/auth/` path prefix. The path parameter SHALL be named `auth_user_id`.

**FROM:** `/api/v1/users/{user_id}`
**TO:** `/api/v1/users/auth/{auth_user_id}`

Affected endpoints:

| Operation | Old path | New path |
|---|---|---|
| List auth users | `GET /api/v1/users/auth-users` | `GET /api/v1/users/auth/` |
| Activate | `PATCH /api/v1/users/{user_id}/activate` | `PATCH /api/v1/users/auth/{auth_user_id}/activate` |
| Deactivate | `PATCH /api/v1/users/{user_id}/deactivate` | `PATCH /api/v1/users/auth/{auth_user_id}/deactivate` |
| Upload avatar | `POST /api/v1/users/{username}/avatar` | `POST /api/v1/users/auth/{username}/avatar` |
| Delete avatar | `DELETE /api/v1/users/{username}/avatar` | `DELETE /api/v1/users/auth/{username}/avatar` |

#### Scenario: Activate auth user under new path

- **WHEN** an admin sends `PATCH /api/v1/users/auth/{auth_user_id}/activate`
- **THEN** the AuthUser SHALL be activated
- **AND** the linked Git user (if any) SHALL also be activated
- **AND** the response format SHALL be identical to the previous behavior

#### Scenario: Deactivate auth user under new path

- **WHEN** an admin sends `PATCH /api/v1/users/auth/{auth_user_id}/deactivate`
- **THEN** the AuthUser SHALL be deactivated
- **AND** the linked Git user (if any) SHALL also be deactivated
- **AND** the response format SHALL be identical to the previous behavior

#### Scenario: List auth users under new path

- **WHEN** a `GET /api/v1/users/auth/` request is sent
- **THEN** the system SHALL return a list of AuthUser records with role summaries
- **AND** the response format SHALL be identical to the previous `/auth-users` response

#### Scenario: Avatar operations under new path

- **WHEN** a user uploads or deletes an avatar via `/api/v1/users/auth/{username}/avatar`
- **THEN** the operation SHALL succeed with identical behavior to the previous path
