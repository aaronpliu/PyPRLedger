import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { effectScope } from 'vue'
import {
  backendSuspect,
  backendUnavailable,
  checkBackend,
  confirmBackendDown,
  healthEndpoint,
  markBackendAvailable,
  markBackendUnavailable,
  useBackendReachabilityProbe,
} from '@/composables/useBackendAvailability'

function setOnline(online: boolean) {
  Object.defineProperty(window.navigator, 'onLine', {
    value: online,
    configurable: true,
    writable: true,
  })
}

function answerWith(status: number) {
  const fetchMock = vi.fn().mockResolvedValue({ status })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function networkFailure() {
  const fetchMock = vi.fn().mockRejectedValue(new Error('down'))
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('useBackendAvailability', () => {
  beforeEach(() => {
    markBackendAvailable()
    setOnline(true)
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
    expect(backendSuspect.value).toBe(true)
    markBackendAvailable()
    expect(backendUnavailable.value).toBe(false)
    expect(backendSuspect.value).toBe(false)
  })

  it('reads a healthy answer as available', async () => {
    answerWith(200)

    await expect(checkBackend()).resolves.toBe(true)
    expect(backendSuspect.value).toBe(false)
    expect(backendUnavailable.value).toBe(false)
  })

  it('reads a gateway answer as the backend being gone', async () => {
    answerWith(502)

    await expect(checkBackend()).resolves.toBe(false)
    // one answer is a doubt about the connection, not a verdict on the service
    expect(backendSuspect.value).toBe(true)
    expect(backendUnavailable.value).toBe(false)
  })

  it('reads any other answer as the service still being there', async () => {
    // A 404 or a 403 says the endpoint is not where this build thinks it is, and a
    // 500 says the service is up and broken. Reading either as an outage would raise
    // a page whose retry can never succeed.
    for (const status of [404, 403, 500]) {
      markBackendAvailable()
      answerWith(status)

      await expect(checkBackend()).resolves.toBe(true)
      expect(backendSuspect.value).toBe(false)
    }
  })

  it('reads a network failure as the connection being in doubt', async () => {
    networkFailure()

    await expect(checkBackend()).resolves.toBe(false)
    expect(backendSuspect.value).toBe(true)
    expect(backendUnavailable.value).toBe(false)
  })

  it('calls the service unavailable once probes fail twice in a row', async () => {
    networkFailure()

    await checkBackend()
    await checkBackend()

    expect(backendUnavailable.value).toBe(true)
  })

  it('an answer between two failures keeps the page away', async () => {
    networkFailure()
    await checkBackend()

    answerWith(200)
    await checkBackend()

    networkFailure()
    await checkBackend()

    expect(backendSuspect.value).toBe(true)
    expect(backendUnavailable.value).toBe(false)
  })
})

describe('confirmBackendDown', () => {
  beforeEach(() => {
    markBackendAvailable()
    setOnline(true)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('does not probe while the browser reports offline', async () => {
    setOnline(false)
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    await confirmBackendDown()

    expect(fetchMock).not.toHaveBeenCalled()
    expect(backendSuspect.value).toBe(false)
  })

  it('leaves the connection in doubt after a single failed probe', async () => {
    networkFailure()

    await confirmBackendDown()

    expect(backendSuspect.value).toBe(true)
    expect(backendUnavailable.value).toBe(false)
  })

  it('calls it an outage when the next probe fails too', async () => {
    networkFailure()

    await confirmBackendDown()
    await confirmBackendDown()

    expect(backendUnavailable.value).toBe(true)
  })

  it('keeps the page away when the backend answers the probe', async () => {
    answerWith(200)

    await confirmBackendDown()

    expect(backendSuspect.value).toBe(false)
    expect(backendUnavailable.value).toBe(false)
  })

  it('asks once however many failures arrive together', async () => {
    const fetchMock = networkFailure()

    await Promise.all([confirmBackendDown(), confirmBackendDown(), confirmBackendDown()])

    expect(fetchMock).toHaveBeenCalledTimes(1)
    // three requests sharing one probe is still one finding, not three
    expect(backendUnavailable.value).toBe(false)
  })
})

describe('useBackendReachabilityProbe', () => {
  beforeEach(() => {
    markBackendAvailable()
    setOnline(true)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.useRealTimers()
  })

  it('asks on its own while in doubt, and stops once the answer is good', async () => {
    vi.useFakeTimers()
    const fetchMock = answerWith(502)
    const scope = effectScope()
    scope.run(() => useBackendReachabilityProbe(1000))

    // nothing is wrong, so there is nothing to ask
    await vi.advanceTimersByTimeAsync(3000)
    expect(fetchMock).not.toHaveBeenCalled()

    // one failed probe puts the connection in doubt, which starts the asking
    await confirmBackendDown()
    expect(backendSuspect.value).toBe(true)

    // the asking is what turns the doubt into a verdict
    await vi.advanceTimersByTimeAsync(1000)
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(backendUnavailable.value).toBe(true)

    // and a good answer ends it without the reader doing anything
    fetchMock.mockResolvedValue({ status: 200 })
    await vi.advanceTimersByTimeAsync(1000)
    expect(backendUnavailable.value).toBe(false)
    expect(backendSuspect.value).toBe(false)

    const asked = fetchMock.mock.calls.length
    await vi.advanceTimersByTimeAsync(5000)
    expect(fetchMock.mock.calls.length).toBe(asked)

    scope.stop()
  })
})
