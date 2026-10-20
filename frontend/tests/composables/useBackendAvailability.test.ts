import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  backendUnavailable,
  checkBackend,
  confirmBackendDown,
  healthEndpoint,
  markBackendAvailable,
  markBackendUnavailable,
} from '@/composables/useBackendAvailability'

function setOnline(online: boolean) {
  Object.defineProperty(window.navigator, 'onLine', {
    value: online,
    configurable: true,
    writable: true,
  })
}

describe('useBackendAvailability', () => {
  beforeEach(() => {
    markBackendAvailable()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('derives the health endpoint from the versioned API base', () => {
    const endpoint = healthEndpoint()
    expect(endpoint).toMatch(/\/health$/)
    // the version segment (/v1) is dropped, whatever the base is
    expect(endpoint).not.toContain('/v1')
  })

  it('flags and clears the outage state by hand', () => {
    expect(backendUnavailable.value).toBe(false)
    markBackendUnavailable()
    expect(backendUnavailable.value).toBe(true)
    markBackendAvailable()
    expect(backendUnavailable.value).toBe(false)
  })

  it('reads a healthy answer as available', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true }))

    await expect(checkBackend()).resolves.toBe(true)
    expect(backendUnavailable.value).toBe(false)
  })

  it('reads a non-2xx answer as unavailable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 503 }))

    await expect(checkBackend()).resolves.toBe(false)
    expect(backendUnavailable.value).toBe(true)
  })

  it('reads a network failure as unavailable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('down')))

    await expect(checkBackend()).resolves.toBe(false)
    expect(backendUnavailable.value).toBe(true)
  })
})

describe('confirmBackendDown', () => {
  beforeEach(() => {
    markBackendAvailable()
    setOnline(true)
  })

  it('does not probe while the browser reports offline', async () => {
    setOnline(false)
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    await confirmBackendDown()

    expect(fetchMock).not.toHaveBeenCalled()
    expect(backendUnavailable.value).toBe(false)
  })

  it('shows the outage once the probe confirms the backend is unreachable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('down')))

    await confirmBackendDown()

    expect(backendUnavailable.value).toBe(true)
  })

  it('keeps the page away when the backend answers the probe', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true }))

    await confirmBackendDown()

    expect(backendUnavailable.value).toBe(false)
  })
})
