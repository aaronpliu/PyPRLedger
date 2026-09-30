import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import type { AxiosRequestConfig } from 'axios'

vi.mock('@/router', () => ({
  default: { currentRoute: { value: { path: '/' } }, replace: vi.fn() },
}))
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    isAuthenticated: true,
    isInitialized: true,
    user: null,
    clearAuth: vi.fn(),
    refreshSession: vi.fn(),
  }),
}))

import request from '@/utils/request'
import { resetProgress, useProgress } from '@/composables/useProgress'

/** An adapter that holds the request open until ``release`` is called, so a test
 * can look at the progress state while the request is still in flight. */
function installGatedAdapter() {
  let release!: () => void
  const gate = new Promise<void>((resolve) => {
    release = resolve
  })
  request.defaults.adapter = async (config) => {
    await gate
    return { data: { ok: true }, status: 200, statusText: 'OK', headers: {}, config }
  }
  return () => release()
}

describe('request progress wiring', () => {
  beforeEach(() => {
    resetProgress()
    localStorage.clear()
  })

  it('opens and closes the progress slot around a request', async () => {
    const release = installGatedAdapter()
    const { active } = useProgress()

    const pending = request.get('/release/notes')
    await flushPromises()
    expect(active.value).toBe(true)

    release()
    await pending
    expect(active.value).toBe(false)
  })

  it('never raises the bar for background traffic', async () => {
    const release = installGatedAdapter()
    const { active } = useProgress()

    const pending = request.get('/notifications/unread-count')
    await flushPromises()
    expect(active.value).toBe(false)

    release()
    await pending
    expect(active.value).toBe(false)
  })

  it('a silent flag keeps a request off the bar', async () => {
    const release = installGatedAdapter()
    const { active } = useProgress()

    const pending = request.get('/release/notes', { _silent: true } as AxiosRequestConfig)
    await flushPromises()
    expect(active.value).toBe(false)

    release()
    await pending
    expect(active.value).toBe(false)
  })
})
