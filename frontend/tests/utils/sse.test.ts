import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'

vi.mock('@/router', () => ({
  default: { currentRoute: { value: { path: '/' } }, replace: vi.fn() },
}))

const clearAuth = vi.fn()
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ clearAuth }),
}))

const createStreamTicket = vi.fn()
vi.mock('@/api/sse', () => ({
  sseApi: { createStreamTicket: () => createStreamTicket() },
}))

import router from '@/router'
import { SSEService } from '@/utils/sse'

/** The smallest stand-in that satisfies what SSEService touches. */
class FakeEventSource {
  static CONNECTING = 0
  static OPEN = 1
  static CLOSED = 2
  static instances: FakeEventSource[] = []

  url: string
  readyState = FakeEventSource.CONNECTING
  closed = false
  private listeners: Record<string, Array<(event: Event) => void>> = {}

  constructor(url: string) {
    this.url = url
    FakeEventSource.instances.push(this)
  }

  addEventListener(type: string, handler: (event: Event) => void): void {
    ;(this.listeners[type] ||= []).push(handler)
  }

  close(): void {
    this.closed = true
    this.readyState = FakeEventSource.CLOSED
  }

  open(): void {
    this.readyState = FakeEventSource.OPEN
    this.emit('open')
  }

  fail(): void {
    this.readyState = FakeEventSource.CLOSED
    this.emit('error')
  }

  /** Deliver a named SSE event carrying a JSON payload. */
  message<T>(type: string, payload: T): void {
    const event = { type, data: JSON.stringify(payload) } as unknown as Event
    for (const handler of this.listeners[type] || []) {
      handler(event)
    }
  }

  private emit(type: string): void {
    for (const handler of this.listeners[type] || []) {
      handler(new Event(type))
    }
  }
}

let service: SSEService

beforeEach(() => {
  vi.useFakeTimers()
  FakeEventSource.instances = []
  createStreamTicket.mockReset()
  clearAuth.mockReset()
  vi.mocked(router.replace).mockClear()
  localStorage.clear()
  vi.stubGlobal('EventSource', FakeEventSource)
  service = new SSEService({ reconnectBaseDelay: 1000, fastRetryDelay: 10 })
})

afterEach(() => {
  service.setEnabled(false)
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('SSEService stream authentication', () => {
  it('connects with a one-shot ticket instead of the JWT', async () => {
    createStreamTicket.mockResolvedValue({ ticket: 'ticket-1', expires_in: 60 })

    service.connect('jwt-value', vi.fn())
    await flushPromises()

    expect(createStreamTicket).toHaveBeenCalledTimes(1)
    expect(FakeEventSource.instances).toHaveLength(1)
    expect(FakeEventSource.instances[0].url).toBe('/api/v1/sse/stream?ticket=ticket-1')
    expect(FakeEventSource.instances[0].url).not.toContain('jwt-value')
  })

  it('asks for a new ticket for every reconnection, closing the spent one', async () => {
    createStreamTicket
      .mockResolvedValueOnce({ ticket: 'ticket-1', expires_in: 60 })
      .mockResolvedValueOnce({ ticket: 'ticket-2', expires_in: 60 })

    service.connect('jwt-value', vi.fn())
    await flushPromises()

    const first = FakeEventSource.instances[0]
    first.open()
    first.fail()
    await flushPromises()

    expect(first.closed).toBe(true)

    await vi.advanceTimersByTimeAsync(1000)
    await flushPromises()

    expect(createStreamTicket).toHaveBeenCalledTimes(2)
    expect(FakeEventSource.instances).toHaveLength(2)
    expect(FakeEventSource.instances[1].url).toBe('/api/v1/sse/stream?ticket=ticket-2')
  })

  it('stops and signs out when the ticket request is unauthorised', async () => {
    createStreamTicket.mockRejectedValue({ response: { status: 401 } })

    service.connect('jwt-value', vi.fn())
    await flushPromises()

    expect(FakeEventSource.instances).toHaveLength(0)
    expect(clearAuth).toHaveBeenCalled()
    expect(router.replace).toHaveBeenCalledWith('/login')
  })

  it('keeps retrying with backoff when the ticket request fails otherwise', async () => {
    createStreamTicket.mockRejectedValueOnce(new Error('network down'))
    createStreamTicket.mockResolvedValueOnce({ ticket: 'ticket-late', expires_in: 60 })

    service.connect('jwt-value', vi.fn())
    await flushPromises()

    expect(FakeEventSource.instances).toHaveLength(0)

    await vi.advanceTimersByTimeAsync(1300)
    await flushPromises()

    expect(createStreamTicket).toHaveBeenCalledTimes(2)
    expect(FakeEventSource.instances[0].url).toBe('/api/v1/sse/stream?ticket=ticket-late')
  })
})

describe('SSEService event names', () => {
  it('refreshes on review_updated as well as review_created', async () => {
    createStreamTicket.mockResolvedValue({ ticket: 'ticket-1', expires_in: 60 })
    const onEvent = vi.fn()

    service.connect('jwt-value', onEvent)
    await flushPromises()

    const payload = {
      review_id: 7,
      project_key: 'BAR',
      repository_slug: 'pyrag',
      pull_request_id: '1203',
      created_date: '2026-11-16T18:00:00+00:00',
    }
    FakeEventSource.instances[0].message('review_created', payload)
    FakeEventSource.instances[0].message('review_updated', payload)

    expect(onEvent).toHaveBeenCalledTimes(2)
    expect(onEvent).toHaveBeenNthCalledWith(1, payload)
    expect(onEvent).toHaveBeenNthCalledWith(2, payload)
  })
})
