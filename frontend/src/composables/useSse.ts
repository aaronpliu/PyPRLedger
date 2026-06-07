import { ref } from 'vue'
import { sseService, type SSEReviewCreatedEvent } from '@/utils/sse'
import { useAuthStore } from '@/stores/auth'

const SSE_ENABLED_KEY = 'sse_enabled'

// Module-level callback storage so toggleSse() can initiate first-time connection
let _onEvent: ((event: SSEReviewCreatedEvent) => void) | null = null
let _onError: ((error: Event) => void) | null = null
let _onOpen: (() => void) | null = null

/**
 * Composable for managing the SSE connection toggle.
 *
 * Provides a reactive `sseEnabled` ref and a `toggleSse` function
 * that persists the preference to localStorage and connects/disconnects
 * the SSE service accordingly.
 *
 * Designed to be called from component setup() — uses the singleton
 * sseService so only one actual EventSource exists at a time.
 */
export function useSse() {
  const authStore = useAuthStore()

  // Initialize from localStorage: disabled by default
  const sseEnabled = ref(
    localStorage.getItem(SSE_ENABLED_KEY) === 'true',
  )

  /**
   * Toggle the SSE connection on/off.
   * Persists preference to localStorage and connects/disconnects
   * the SSE service directly with stored callbacks.
   */
  function toggleSse(val: boolean) {
    sseEnabled.value = val
    localStorage.setItem(SSE_ENABLED_KEY, String(val))
    if (val) {
      // User enabled SSE — establish connection if we have callbacks and token
      if (_onEvent && authStore.accessToken) {
        sseService.connect(authStore.accessToken, _onEvent, _onError || undefined, _onOpen || undefined)
      }
    } else {
      // User disabled SSE — close immediately (use setEnabled false)
      sseService.setEnabled(false)
    }
  }

  /**
   * Connect SSE using provided callbacks (called from onMounted).
   * Respects the user's enabled/disabled preference.
   */
  function connectSse(
    onEvent: (event: SSEReviewCreatedEvent) => void,
    onError?: (error: Event) => void,
    onOpen?: () => void,
  ) {
    // Store callbacks at module level so toggleSse() can establish
    // first-time connection when user enables SSE
    _onEvent = onEvent
    _onError = onError || null
    _onOpen = onOpen || null

    if (sseEnabled.value && authStore.accessToken) {
      sseService.connect(authStore.accessToken, onEvent, onError, onOpen)
    }
  }

  /**
   * Disconnect SSE (called from onUnmounted).
   */
  function disconnectSse() {
    sseService.disconnect()
  }

  return {
    sseEnabled,
    toggleSse,
    connectSse,
    disconnectSse,
    isSseConnected: () => sseService.isConnected(),
  }
}
