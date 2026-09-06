import { watch } from 'vue'
import { authApi } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'

/**
 * Keep the JWT session alive only while the user is genuinely active.
 *
 * The server idle timeout (REFRESH_TOKEN_IDLE_TIMEOUT_MINUTES) only slides
 * when this heartbeat is sent, and the heartbeat is only sent in response to
 * REAL user input (mouse, keyboard, touch, scroll) — never on background
 * polling. A user who stops interacting is therefore logged out after the
 * configured idle period, while an active user is never force-logged-out.
 *
 * Requests are throttled to at most one per HEARTBEAT_MIN_INTERVAL_MS.
 * Session-expiry handling (401 -> refresh -> redirect to login) is done by
 * the shared request interceptor, so failures here are intentionally silent.
 */

// Minimum gap between consecutive heartbeat requests (60s).
const HEARTBEAT_MIN_INTERVAL_MS = 60_000

const ACTIVITY_EVENTS = [
  'mousedown',
  'keydown',
  'touchstart',
  'wheel',
  'scroll',
  'mousemove',
] as const

export function useIdleSessionHeartbeat() {
  const authStore = useAuthStore()

  let listenersAttached = false
  let lastHeartbeatAt = 0
  let heartbeatInFlight = false

  async function sendHeartbeat(): Promise<void> {
    const now = Date.now()
    if (heartbeatInFlight || now - lastHeartbeatAt < HEARTBEAT_MIN_INTERVAL_MS) {
      return
    }
    if (!authStore.accessToken) {
      return
    }
    heartbeatInFlight = true
    lastHeartbeatAt = now
    try {
      await authApi.heartbeat()
    } catch {
      // 401 (idle timeout reached) is handled by the request interceptor,
      // which redirects to the login page. Other failures are transient and
      // will be retried on the next user activity.
    } finally {
      heartbeatInFlight = false
    }
  }

  function onUserActivity(): void {
    void sendHeartbeat()
  }

  function attachListeners(): void {
    if (listenersAttached) {
      return
    }
    listenersAttached = true
    ACTIVITY_EVENTS.forEach((event) => {
      window.addEventListener(event, onUserActivity, { passive: true })
    })
    // Returning to the tab may be the first sign of activity after a pause.
    document.addEventListener('visibilitychange', onUserActivity)
  }

  function detachListeners(): void {
    if (!listenersAttached) {
      return
    }
    listenersAttached = false
    ACTIVITY_EVENTS.forEach((event) => {
      window.removeEventListener(event, onUserActivity)
    })
    document.removeEventListener('visibilitychange', onUserActivity)
    lastHeartbeatAt = 0
    heartbeatInFlight = false
  }

  // Start heartbeating only while an authenticated session is active.
  watch(
    () => authStore.isAuthenticated && authStore.isInitialized,
    (active) => {
      if (active) {
        attachListeners()
      } else {
        detachListeners()
      }
    },
    { immediate: true },
  )
}
