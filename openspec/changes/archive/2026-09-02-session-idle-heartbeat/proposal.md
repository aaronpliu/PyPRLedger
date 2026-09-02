## Why

A logged-in user is currently force-logged-out after `REFRESH_TOKEN_IDLE_TIMEOUT_MINUTES` (2h) of wall-clock time, even when they are actively working — while background polling traffic can inadvertently keep an idle session alive. The idle deadline should slide on **real user activity** only: active users never get force-logged-out, and truly idle users are logged out after the configured period.

## What Changes

- Add `AuthService.touch_session(token)` — validates the access token, verifies the refresh session still exists, and resets the session TTL to the full idle timeout.
- Add `POST /api/v1/auth/heartbeat` — the **only** API path that extends the idle deadline. Returns `204` on success; `401` when the session is gone (idle timeout reached) or auth headers are missing.
- Keep token **refresh and ordinary API traffic from extending the TTL** — they preserve the remaining idle window (fixes the pre-existing background-polling keeps-alive loophole).
- Add `useIdleSessionHeartbeat` composable on the frontend — listens only for real input (mouse, keyboard, touch, wheel, scroll, tab visibility) and fires the heartbeat at most once per 60s; wiring it in `App.vue` attaches listeners only while an authenticated session is active.
- Personal Access Token sessions are unaffected (no idle semantics, heartbeat no-ops).
- No new configuration or schema changes; reuses the existing `REFRESH_TOKEN_IDLE_TIMEOUT_MINUTES` setting.

## Capabilities

### New Capabilities
- `session-idle-timeout`: Sliding idle-timeout semantics for JWT login sessions — the deadline is extended only by real-activity heartbeats, never by background traffic, and expired sessions fail closed with `401`.

### Modified Capabilities
<!-- None: no existing spec currently defines session/TTL behavior. -->

## Impact

- Backend: `src/services/auth_service.py` (+`touch_session`), `src/api/v1/endpoints/auth.py` (+`POST /auth/heartbeat`).
- Frontend: `frontend/src/composables/useIdleSessionHeartbeat.ts` (new), `frontend/src/api/auth.ts` (+`heartbeat`), `frontend/src/App.vue` (mount).
- Tests: `tests/test_idle_session.py` (new, service semantics + route registration), `frontend/tests/composables/useIdleSessionHeartbeat.test.ts` (new).
- API surface: one new endpoint; no breaking changes to existing endpoints or payloads.
- Behavior: sessions of active users no longer expire mid-work; idle users are still logged out after `REFRESH_TOKEN_IDLE_TIMEOUT_MINUTES` with no input.
