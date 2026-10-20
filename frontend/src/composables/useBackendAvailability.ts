import { onScopeDispose, ref, watch } from 'vue'

/**
 * Whether the backend cannot be reached, in two steps.
 *
 * A request that gets no answer is not proof of anything: a wifi link that dropped
 * one connection, a proxy that gave up on a single socket and a service that is
 * restarting all look the same from here. So the first probe that fails only says
 * the connection is in doubt - the page keeps working, its state untouched, and a
 * banner says what is being checked - and the service is only called unavailable
 * once probes fail twice in a row. Both flags are one module-level ref, because the
 * HTTP client runs outside the component tree and a store would be a detour.
 */
export const backendSuspect = ref(false)
export const backendUnavailable = ref(false)

const HEALTH_TIMEOUT_MS = 8000
/** Failures this close together are one finding; further apart they are two. */
const CONSECUTIVE_WINDOW_MS = 30000
/** Failed probes before the service is called unavailable. */
const CONFIRMATIONS = 2
/** Answers that mean the gateway stood in for a backend that is not there. */
const GATEWAY_STATUSES = new Set([502, 503, 504])

let failures = 0
let lastFailureAt = 0
let probing: Promise<boolean> | null = null
let confirming = false

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

/**
 * Whether an answer means the service is there.
 *
 * Everything but a gateway's own answer is: a 500 says the service is up and
 * broken, which is not the same as gone, and a 404 or a 403 says the endpoint is
 * not where this build thinks it is rather than that the service is down. Reading
 * those as an outage would raise a page whose retry can never succeed, so a
 * misconfigured deployment stays silent instead of locking the reader out.
 */
function isReachable(status: number): boolean {
  return !GATEWAY_STATUSES.has(status)
}

function record(reachable: boolean): void {
  if (reachable) {
    markBackendAvailable()
    return
  }

  const now = Date.now()
  failures = now - lastFailureAt <= CONSECUTIVE_WINDOW_MS ? failures + 1 : 1
  lastFailureAt = now
  backendSuspect.value = true
  backendUnavailable.value = failures >= CONFIRMATIONS
}

export function markBackendAvailable(): void {
  if (!backendSuspect.value && !backendUnavailable.value && failures === 0) {
    return
  }
  failures = 0
  backendSuspect.value = false
  backendUnavailable.value = false
}

export function markBackendUnavailable(): void {
  failures = CONFIRMATIONS
  backendSuspect.value = true
  backendUnavailable.value = true
}

async function probe(): Promise<boolean> {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), HEALTH_TIMEOUT_MS)
  try {
    const response = await fetch(healthEndpoint(), { signal: controller.signal })
    const reachable = isReachable(response.status)
    record(reachable)
    return reachable
  } catch {
    record(false)
    return false
  } finally {
    clearTimeout(timeout)
  }
}

/**
 * Ask the health endpoint whether the backend is up, and record the answer.
 *
 * The health check is unauthenticated, so it answers for a logged-out reader as
 * well as a logged-in one. Callers that overlap share the probe already out
 * rather than adding to it.
 */
export function checkBackend(): Promise<boolean> {
  if (!probing) {
    probing = probe().finally(() => {
      probing = null
    })
  }
  return probing
}

function browserIsOffline(): boolean {
  return typeof navigator !== 'undefined' && navigator.onLine === false
}

/**
 * Confirm that the service itself is down before anything is said about it.
 *
 * A browser that reports itself offline is exactly the other case - the reader's
 * own connection - and is left alone. Concurrent failures share a single probe, so
 * one dropped request - or a wifi hiccup - does not add up to an outage on its own;
 * the second probe comes from the shell, which keeps asking while in doubt.
 */
export async function confirmBackendDown(): Promise<void> {
  if (browserIsOffline() || confirming) {
    return
  }
  confirming = true
  try {
    await checkBackend()
  } finally {
    confirming = false
  }
}

/** How often the shell asks while the connection is in doubt or confirmed gone. */
const REACHABILITY_PROBE_MS = 5000

/**
 * Keep asking while the connection is in doubt, and stop asking once it is settled.
 *
 * One interval is what turns a single failed probe into a verdict, and what ends the
 * outage by itself: the reader is not asked to press Retry for a service that has
 * come back, and a page that was never taken away is simply read again.
 */
export function useBackendReachabilityProbe(intervalMs: number = REACHABILITY_PROBE_MS): void {
  let timer: ReturnType<typeof setInterval> | null = null

  const stop = () => {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  }

  watch([backendSuspect, backendUnavailable], ([suspect, unavailable]) => {
    if (suspect || unavailable) {
      timer ??= setInterval(() => void confirmBackendDown(), intervalMs)
    } else {
      stop()
    }
  })

  onScopeDispose(stop)
}
