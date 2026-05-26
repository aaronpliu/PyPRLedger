import { ref } from 'vue'
import { sseService, type SSEReviewCreatedEvent } from '@/utils/sse'
import { useAuthStore } from '@/stores/auth'

const SSE_ENABLED_KEY = 'sse_enabled'

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

  // Initialize from localStorage: enabled by default
  const sseEnabled = ref(
    localStorage.getItem(SSE_ENABLED_KEY) !== 'false',
  )

  /**
   * Toggle the SSE connection on/off.
   * Persists preference to localStorage and calls sseService.setEnabled().
   */
  function toggleSse(val: boolean) {
    sseEnabled.value = val
    localStorage.setItem(SSE_ENABLED_KEY, String(val))
    sseService.setEnabled(val)
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
    if (sseEnabled.value && authStore.accessToken) {
      sseService.connect(authStore.accessToken, onEvent, onError, onOpen)
    }
  }

  /**
   * Disconnect SSE (called from onUnmounted).
   * But only if user didn't explicitly disable it (so next mount
   * with enabled=true will reconnect properly).
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
