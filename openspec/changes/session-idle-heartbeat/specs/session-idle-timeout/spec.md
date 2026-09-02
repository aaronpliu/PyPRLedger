## ADDED Requirements

### Requirement: Session idle deadline extends only on real user activity
The idle deadline of an authenticated login session SHALL be extended only by an explicit heartbeat request that is triggered by real user input. Background traffic such as token refresh, periodic polling, or SSE-triggered reloads SHALL NOT extend the idle deadline, and SHALL NOT reset the session TTL to the full idle window.

#### Scenario: Active user's deadline slides with heartbeat
- **WHEN** an authenticated user performs real input (keyboard, mouse, touch, scroll) within the idle window
- **AND** the frontend sends `POST /api/v1/auth/heartbeat`
- **THEN** the session TTL SHALL be reset to the full `REFRESH_TOKEN_IDLE_TIMEOUT_MINUTES` window
- **AND** `last_activity_at` SHALL be updated

#### Scenario: Background polling does not keep a session alive
- **WHEN** a session receives only background requests (token refresh, notification polling) for longer than `REFRESH_TOKEN_IDLE_TIMEOUT_MINUTES`
- **AND** no real user input occurs in that period
- **THEN** the session SHALL expire when its remaining TTL elapses
- **AND** token refresh SHALL preserve the remaining TTL instead of resetting it

#### Scenario: Session without recent activity expires
- **WHEN** an authenticated session receives no real user activity for `REFRESH_TOKEN_IDLE_TIMEOUT_MINUTES`
- **THEN** the session SHALL expire in Redis
- **AND** the next authenticated request SHALL fail with `401` and direct the user to the login page

### Requirement: Heartbeat endpoint semantics
`POST /api/v1/auth/heartbeat` SHALL return `204 No Content` when the session is active and its idle deadline was extended. It SHALL return `401` when the `Authorization` header is missing or when the refresh session no longer exists. Heartbeat requests for Personal Access Token (`pat_*`) sessions SHALL return `204` without modifying anything.

#### Scenario: Valid heartbeat extends the deadline
- **WHEN** an authenticated user sends `POST /api/v1/auth/heartbeat` with a valid bearer access token
- **THEN** the response SHALL be `204 No Content`
- **AND** the session idle deadline SHALL be extended

#### Scenario: Heartbeat with an expired session
- **WHEN** an authenticated user sends `POST /api/v1/auth/heartbeat` after the idle deadline has passed
- **THEN** the response SHALL be `401 Unauthorized`

#### Scenario: Heartbeat without credentials
- **WHEN** a request is sent to `POST /api/v1/auth/heartbeat` without a bearer token
- **THEN** the response SHALL be `401 Unauthorized`

#### Scenario: Heartbeat for a personal access token session
- **WHEN** an authenticated user sends `POST /api/v1/auth/heartbeat` with a `pat_*` token
- **THEN** the response SHALL be `204 No Content`
- **AND** no session state SHALL be modified

### Requirement: Frontend heartbeats only on real user activity
The frontend SHALL send the heartbeat request only in response to real user input events (keyboard, mouse, touch, wheel, scroll, or returning to the visible tab). Heartbeats SHALL be throttled to at most one per 60 seconds. While logged out, the frontend SHALL NOT send heartbeats; logging in SHALL start activity monitoring and logging out SHALL stop it. Failed heartbeat requests SHALL be ignored by the frontend and handled by the shared authentication error flow.

#### Scenario: Input events trigger a throttled heartbeat
- **WHEN** an authenticated user interacts with the page
- **THEN** at most one heartbeat SHALL be sent per 60-second window regardless of event frequency

#### Scenario: No heartbeat while logged out
- **WHEN** the user is not authenticated
- **AND** input events occur
- **THEN** no heartbeat requests SHALL be sent

#### Scenario: Logout stops activity monitoring
- **WHEN** the user logs out or the session is cleared
- **THEN** subsequent user input SHALL NOT trigger heartbeat requests
- **AND** a later re-login SHALL resume activity monitoring

#### Scenario: Heartbeat failure is silent
- **WHEN** a heartbeat request fails (network error or expired session)
- **THEN** the frontend SHALL NOT surface an error dialog for the heartbeat itself
- **AND** session expiry SHALL be handled by the standard `401` → refresh → redirect flow
