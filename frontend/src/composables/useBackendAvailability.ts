import { ref } from 'vue'

/**
 * Whether the backend cannot be reached.
 *
 * A single source of truth shared by the HTTP client (which flags an outage) and
 * the application shell (which shows the outage page for it). Kept in a plain
 * module rather than a store: the client runs outside the component tree, and a
 * module-level ref is the same instance for every importer.
 */
export const backendUnavailable = ref(false)

const HEALTH_TIMEOUT_MS = 8000

/**
 * The health endpoint, one level above the versioned API.
 *
 * The app talks to ``/api/v1`` while the health check lives at ``/api/health``,
 * so the version segment is dropped rather than appended to. An absolute base
 * (a deployed build pointed at another origin) keeps its scheme and host.
 */
export function healthEndpoint(): string {
  const base = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/+$/, '')
  const unversioned = base.replace(/\/v\d+(\.[^/]*)?$/, '')
  return `${unversioned}/health`
}

export function markBackendUnavailable(): void {
  backendUnavailable.value = true
}

export function markBackendAvailable(): void {
  backendUnavailable.value = false
}

/**
 * Ask the health endpoint whether the backend is up, and record the answer.
 *
 * The health check is unauthenticated, so it answers for a logged-out reader as
 * well as a logged-in one, and any HTTP response means the service is reachable
 * - only a network failure (or a non-2xx the proxy could not mask) reads as down.
 */
export async function checkBackend(): Promise<boolean> {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), HEALTH_TIMEOUT_MS)
  try {
    const response = await fetch(healthEndpoint(), { signal: controller.signal })
    const healthy = response.ok
    backendUnavailable.value = !healthy
    return healthy
  } catch {
    backendUnavailable.value = true
    return false
  } finally {
    clearTimeout(timeout)
  }
}

let confirming = false

/**
 * Confirm that the service itself is down before the outage page is shown.
 *
 * A request that gets no answer (or a 5xx that answers for a backend which is
 * not there) can also mean the reader's own connection went away; a browser that
 * reports itself offline is exactly that case and is left alone. Only when the
 * browser still believes it is online is the health endpoint asked, so one
 * dropped request - or a wifi hiccup - does not put the outage page up over a
 * service that is fine. Concurrent failures share a single probe.
 */
export async function confirmBackendDown(): Promise<void> {
  if (typeof navigator !== 'undefined' && navigator.onLine === false) {
    return
  }
  if (confirming) {
    return
  }
  confirming = true
  try {
    await checkBackend()
  } finally {
    confirming = false
  }
}
