## 1. Backend: session service

- [x] 1.1 Add `AuthService.touch_session(token)` — decode access token, re-read refresh session, raise `TokenExpiredException` when the session no longer exists, otherwise reset TTL to the full idle window and bump `last_activity_at`
- [x] 1.2 Keep token refresh TTL-preserving (no reset to full idle window)

## 2. Backend: heartbeat endpoint

- [x] 2.1 Add `POST /api/v1/auth/heartbeat` returning `204` on success and `401` for missing/expired sessions
- [x] 2.2 No-op `204` for Personal Access Token (`pat_*`) requests
- [x] 2.3 Sync request client context (IP/user-agent) on heartbeat like other auth flows

## 3. Frontend: real-activity heartbeat

- [x] 3.1 Add `authApi.heartbeat()` call with suppressed global error toasts
- [x] 3.2 Add `useIdleSessionHeartbeat` composable — listens to real input events only, throttled to ≤1/60s with in-flight coalescing, attaches while authenticated and detaches on logout
- [x] 3.3 Mount the composable in `App.vue`

## 4. Tests & verification

- [x] 4.1 Backend tests: TTL reset on touch, expired session raises, non-access-token rejection, refresh preserves TTL (regression), route registration
- [x] 4.2 Frontend tests: no heartbeat while logged out, throttling, logout stops / re-login resumes, silent failure
- [x] 4.3 Full backend suite (`pytest`), frontend suite (`vitest`), `ruff check` and `vue-tsc` type-check pass
