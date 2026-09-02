import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import { authApi } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'
import { useIdleSessionHeartbeat } from '@/composables/useIdleSessionHeartbeat'

vi.mock('@/api/auth', () => ({
  authApi: {
    heartbeat: vi.fn().mockResolvedValue(undefined),
  },
}))

function fireActivity(): void {
  window.dispatchEvent(new Event('mousedown'))
}

describe('useIdleSessionHeartbeat Composable', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('does not send heartbeats while logged out', () => {
    const authStore = useAuthStore()
    authStore.isInitialized = true

    useIdleSessionHeartbeat()

    fireActivity()
    fireActivity()

    expect(authApi.heartbeat).not.toHaveBeenCalled()
  })

  it('sends a throttled heartbeat on real user activity when authenticated', () => {
    const authStore = useAuthStore()
    authStore.isInitialized = true
    authStore.accessToken = 'token-123'

    useIdleSessionHeartbeat()

    // Rapid successive events must collapse into a single request (60s throttle).
    fireActivity()
    fireActivity()
    fireActivity()

    expect(authApi.heartbeat).toHaveBeenCalledTimes(1)
  })

  it('stops heartbeating after logout and resumes after re-login', async () => {
    const authStore = useAuthStore()
    authStore.isInitialized = true
    authStore.accessToken = 'token-123'

    useIdleSessionHeartbeat()

    fireActivity()
    expect(authApi.heartbeat).toHaveBeenCalledTimes(1)

    // Logout clears the token — the watcher detaches activity listeners.
    authStore.accessToken = ''
    await nextTick()
    fireActivity()
    fireActivity()
    expect(authApi.heartbeat).toHaveBeenCalledTimes(1)

    // Re-login re-attaches listeners — activity resumes heartbeating.
    authStore.accessToken = 'token-456'
    await nextTick()
    fireActivity()
    expect(authApi.heartbeat).toHaveBeenCalledTimes(2)
  })

  it('recovers silently when the heartbeat request fails', () => {
    vi.mocked(authApi.heartbeat).mockRejectedValueOnce(new Error('network down'))
    const authStore = useAuthStore()
    authStore.isInitialized = true
    authStore.accessToken = 'token-123'

    useIdleSessionHeartbeat()

    fireActivity()
    expect(authApi.heartbeat).toHaveBeenCalledTimes(1)
  })
})
