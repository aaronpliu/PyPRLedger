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
import {
  backendSuspect,
  backendUnavailable,
  confirmBackendDown,
  markBackendAvailable,
  markBackendUnavailable,
} from '@/composables/useBackendAvailability'
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

  function probeFails() {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('down')))
  }

  function requestCannotReach() {
    request.defaults.adapter = async (config) => {
      throw Object.assign(new Error('Network Error'), { config })
    }
  }

  it('leaves the connection in doubt after one unanswered request', async () => {
    probeFails()
    requestCannotReach()

    await expect(request.get('/release/notes')).rejects.toThrow('Network Error')
    await vi.waitFor(() => expect(backendSuspect.value).toBe(true))
    // one request and one probe is a doubt about the connection, not a verdict
    expect(backendUnavailable.value).toBe(false)
  })

  it('calls the service unavailable when the next probe fails too', async () => {
    probeFails()
    requestCannotReach()

    await expect(request.get('/release/notes')).rejects.toThrow('Network Error')
    await vi.waitFor(() => expect(backendSuspect.value).toBe(true))
    await flushPromises()

    // the shell keeps asking while in doubt, and the second answer settles it
    await confirmBackendDown()

    expect(backendUnavailable.value).toBe(true)
  })

  it('keeps the page away when a request fails but the backend answers the probe', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ status: 200 }))
    requestCannotReach()

    await expect(request.get('/release/notes')).rejects.toThrow('Network Error')
    await vi.waitFor(() => expect(globalThis.fetch).toHaveBeenCalled())
    expect(backendSuspect.value).toBe(false)
    expect(backendUnavailable.value).toBe(false)
  })

  it('detects an outage from background traffic too', async () => {
    probeFails()
    requestCannotReach()

    await expect(request.get('/auth/heartbeat')).rejects.toThrow('Network Error')
    await vi.waitFor(() => expect(backendSuspect.value).toBe(true))
    await flushPromises()

    await confirmBackendDown()

    expect(backendUnavailable.value).toBe(true)
  })

  it('asks the probe when a gateway answers for a backend that is gone', async () => {
    probeFails()
    request.defaults.adapter = async (config) => {
      throw Object.assign(new Error('Bad Gateway'), {
        config,
        response: { status: 502, data: {} },
      })
    }

    await expect(request.get('/release/notes')).rejects.toThrow('Bad Gateway')
    await vi.waitFor(() => expect(globalThis.fetch).toHaveBeenCalled())
    expect(backendSuspect.value).toBe(true)
  })

  it('keeps the page away when a real 5xx is answered and the backend is healthy', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ status: 200 }))
    request.defaults.adapter = async (config) => {
      throw Object.assign(new Error('Server Error'), {
        config,
        response: { status: 500, data: {} },
      })
    }

    await expect(request.get('/release/notes')).rejects.toThrow('Server Error')
    await vi.waitFor(() => expect(globalThis.fetch).toHaveBeenCalled())
    expect(backendSuspect.value).toBe(false)
    expect(backendUnavailable.value).toBe(false)
  })

  it('a request that gets an answer ends the outage', async () => {
    markBackendUnavailable()
    request.defaults.adapter = async (config) => ({
      data: { ok: true },
      status: 200,
      statusText: 'OK',
      headers: {},
      config,
    })

    await request.get('/release/notes')

    expect(backendUnavailable.value).toBe(false)
    expect(backendSuspect.value).toBe(false)
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
