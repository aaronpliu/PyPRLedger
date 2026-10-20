import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
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

// The outage flagging path shows a message, but the message itself is not what the
// test reads - keep Element Plus out of the way.
vi.mock('element-plus', () => ({
  ElMessage: { error: vi.fn(), warning: vi.fn(), closeAll: vi.fn(), info: vi.fn(), success: vi.fn() },
}))

import request from '@/utils/request'
import { resetProgress, useProgress } from '@/composables/useProgress'
import { backendUnavailable, markBackendAvailable } from '@/composables/useBackendAvailability'
import { CLIENT_DEVICE_HEADER } from '@/utils/deviceInfo'

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

describe('service outage detection', () => {
  beforeEach(() => {
    markBackendAvailable()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('flags the backend as unavailable after the probe confirms it is down', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('down')))
    request.defaults.adapter = async (config) => {
      throw Object.assign(new Error('Network Error'), { config })
    }

    await expect(request.get('/release/notes')).rejects.toThrow('Network Error')
    await vi.waitFor(() => expect(backendUnavailable.value).toBe(true))
  })

  it('keeps the page away when a request fails but the backend answers the probe', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true }))
    request.defaults.adapter = async (config) => {
      throw Object.assign(new Error('Network Error'), { config })
    }

    await expect(request.get('/release/notes')).rejects.toThrow('Network Error')
    await vi.waitFor(() => expect(globalThis.fetch).toHaveBeenCalled())
    expect(backendUnavailable.value).toBe(false)
  })

  it('detects the outage from background traffic too', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('down')))
    request.defaults.adapter = async (config) => {
      throw Object.assign(new Error('Network Error'), { config })
    }

    await expect(request.get('/auth/heartbeat')).rejects.toThrow('Network Error')
    await vi.waitFor(() => expect(backendUnavailable.value).toBe(true))
  })

  it('confirms an outage when a 5xx answers for a backend that is gone', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('down')))
    request.defaults.adapter = async (config) => {
      throw Object.assign(new Error('Bad Gateway'), {
        config,
        response: { status: 502, data: {} },
      })
    }

    await expect(request.get('/release/notes')).rejects.toThrow('Bad Gateway')
    await vi.waitFor(() => expect(backendUnavailable.value).toBe(true))
  })

  it('keeps the page away when a real 5xx is answered and the backend is healthy', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true }))
    request.defaults.adapter = async (config) => {
      throw Object.assign(new Error('Server Error'), {
        config,
        response: { status: 500, data: {} },
      })
    }

    await expect(request.get('/release/notes')).rejects.toThrow('Server Error')
    await vi.waitFor(() => expect(globalThis.fetch).toHaveBeenCalled())
    expect(backendUnavailable.value).toBe(false)
  })
})

describe('device reporting on requests', () => {
  it('carries the device record on every request, the login included', async () => {
    const seen: Array<Record<string, unknown>> = []
    request.defaults.adapter = async (config) => {
      seen.push((config.headers ?? {}) as Record<string, unknown>)
      return { data: { ok: true }, status: 200, statusText: 'OK', headers: {}, config }
    }

    // The login is the request that creates the session, so it matters most.
    await request.post('/auth/login', { username: 'tester', password: 'secret' })
    await request.get('/release/notes')

    expect(seen).toHaveLength(2)
    seen.forEach((headers) => expect(headers[CLIENT_DEVICE_HEADER]).toBeTruthy())
  })
})
