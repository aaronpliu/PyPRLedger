## Context

Login sessions are opaque refresh tokens stored in Redis (`auth:refresh_session:{session_id}`) with a TTL equal to `REFRESH_TOKEN_IDLE_TIMEOUT_MINUTES` (2h). The access token carries the session id (`sid`). Current behavior:

- At login the TTL is set to the full idle window, but nothing ever slides it — an active user is force-logged-out once 2h of wall-clock time pass.
- Since the v1.20.5 fix, token refresh preserves the *remaining* TTL rather than resetting it, so background polling (notification stats every 30s, SSE-triggered reloads) no longer keeps idle sessions alive by accident.

The desired semantics: the deadline slides only on **real user activity**; users who keep working never get logged out, users who stop interacting are logged out after the configured idle period. Frontend activity is detected browser-side; Redis is the source of truth for expiry (enforced on the next request via `401`).

## Goals / Non-Goals

**Goals:**
- Active users are never force-logged-out mid-work.
- Truly idle sessions still expire after `REFRESH_TOKEN_IDLE_TIMEOUT_MINUTES` with no input.
- Background/polling traffic must never extend the idle deadline.
- The idle window remains centrally configurable via the existing `REFRESH_TOKEN_IDLE_TIMEOUT_MINUTES` setting.

**Non-Goals:**
- No absolute session ceiling (no "force logout after N hours regardless of activity"); explicitly deferred.
- No server-side definition of "activity" (e.g. page-visibility tracking on the backend).
- No change to PAT (Personal Access Token) semantics.
- No change to the `last_activity_at` semantics of other consumers (list-sessions UI already reads it).

## Decisions

### D1. A dedicated heartbeat endpoint is the ONLY TTL-extension path
`POST /api/v1/auth/heartbeat` → `AuthService.touch_session(token)`: decode the access token, re-read the refresh session; if absent → `TokenExpiredException` (mapped to `401`, same failure the refresh flow surfaces); otherwise rewrite the session with the full idle TTL and bump `last_activity_at`.

- *Alternative considered:* extend TTL on every authenticated request. Rejected — background polling would keep idle sessions alive, reintroducing the exact loophole v1.20.5 fixed.
- *Alternative considered:* JWT exp with sliding signing key. Rejected — heavier than needed; refresh sessions in Redis are already the source of truth.

### D2. Refresh and ordinary API traffic preserve the remaining TTL
Already the case since v1.20.5; locked in by a regression test (`test_token_refresh_does_not_extend_ttl`) so future changes cannot silently reintroduce polling-driven keep-alive.

### D3. Frontend fires the heartbeat only on real user input
`useIdleSessionHeartbeat` (Vue composable, mounted once in `App.vue`) listens on `mousedown`, `keydown`, `touchstart`, `wheel`, `scroll`, `mousemove` (all `passive: true`) plus `visibilitychange` (returning to the tab is often the first sign of activity after a pause). Anything else — timers, polling, SSE callbacks — never triggers it.

- Throttled to one request per 60s (`HEARTBEAT_MIN_INTERVAL_MS`), with in-flight coalescing, so mousemove storms cost nothing.
- Listeners attach only while an authenticated session is active (watch on `isAuthenticated && isInitialized`) and detach on logout — no heartbeats leak past sign-out.
- Heartbeat failures are silent locally: the shared axios interceptor still runs its 401 → refresh → redirect flow (which ends at the login page when the idle timeout actually hit), so errors need no duplicate handling.

### D4. PATs bypass idle semantics
The endpoint returns `204` no-op for `pat_*` tokens since PAT sessions have no idle TTL.

### D5. Config reuse, no new knobs
Reuses `REFRESH_TOKEN_IDLE_TIMEOUT_MINUTES`. Heartbeat cadence lives in the composable as a constant (not env-configurable) to keep the runtime contract simple.

## Risks / Trade-offs

- [User is active but produces no input events (watches a report, video)] → Logged out after the idle window. Accepted: matches the agreed definition of "idle"; documented in the UI-facing proposal summary.
- [Idle past timeout, then heartbeat 401s] → Interceptor redirects to login (session is genuinely gone; Redis was the authority). No retry storm: errors are silent and the redirect happens once through the standard 401 path.
- [mousemove/scroll rate] → Throttle + passive listeners + in-flight coalescing keep it to ≤1 req/min.
- [Multiple tabs] → Any tab's real input extends the shared session — consistent, since sessions are per-user, not per-tab.
- [Redis TTL readback has sub-second truncation (int floor)] → Tests assert on tolerance ranges rather than exact equality.

## Migration Plan

- Additive only: one endpoint, one service method, one composable mounted in `App.vue`. No schema, config, or migration changes.
- Deployment order irrelevant (backend first or together) — the new endpoint is inert until the frontend calls it; an older frontend simply never slides its deadline, preserving today's behavior.
- Rollback: revert the commit; nothing persisted except transient Redis TTL behavior.

## Open Questions

- None blocking. Optional future work (explicitly deferred): an absolute session ceiling or server-driven activity signals.
