/**
 * SSE Service for real-time review notifications
 *
 * Features:
 * - JWT authentication via query parameter
 * - Automatic reconnection with exponential backoff (3s base, max 30s, ±20% jitter)
 * - Connection lifecycle management
 * - Type-safe event parsing
 * - Per-tab connection isolation (each tab gets its own instance)
 */

export interface SSEReviewCreatedEvent {
  event: 'review_created'
  data: {
    review_id: number
    project_key: string
    repository_slug: string
    pull_request_id: string
    created_date: string
  }
}

export interface SSECallbackMap {
  review_created: (event: SSEReviewCreatedEvent) => void
}

export interface SSEServiceOptions {
  /** Maximum reconnection attempts before giving up (default: 5) */
  maxReconnectAttempts: number
  /** Base reconnection delay in ms, doubled each attempt (default: 3000) */
  reconnectBaseDelay: number
  /** Maximum reconnection delay in ms (default: 30000) */
  maxReconnectDelay: number
}

export class SSEService {
  private eventSource: EventSource | null = null
  private reconnectAttempts = 0
  private reconnectTimeout: ReturnType<typeof setTimeout> | null = null
  private refetchTimeout: ReturnType<typeof setTimeout> | null = null
  private options: SSEServiceOptions
  private isManualDisconnect = false
  private url: string | null = null
  private token: string | null = null
  private currentConnectionId = 0
  private disconnectTimeout: ReturnType<typeof setTimeout> | null = null
  private pendingConnect: (() => void) | null = null
  
  // Store current callbacks so they can be updated
  private currentOnEvent: ((event: SSEReviewCreatedEvent) => void) | null = null
  private currentOnError: ((error: Event) => void) | null = null
  private currentOnOpen: (() => void) | null = null

  constructor(options: Partial<SSEServiceOptions> = {}) {
    this.options = {
      maxReconnectAttempts: 5,
      reconnectBaseDelay: 3000,
      maxReconnectDelay: 30000,
      ...options,
    }
  }

  /**
   * Connect to the SSE stream
   *
   * @param token JWT access token from auth store
   * @param onEvent Callback when an event is received
   * @param onError Callback for connection errors
   * @param onOpen Callback when connection is established
   */
  connect(
    token: string,
    onEvent: (event: SSEReviewCreatedEvent) => void,
    onError?: (error: Event) => void,
    onOpen?: () => void,
  ): void {
    // If there's a pending disconnect, cancel it and reuse the connection
    if (this.disconnectTimeout !== null) {
      console.log('[SSE] Cancelling pending disconnect - reusing existing connection')
      clearTimeout(this.disconnectTimeout)
      this.disconnectTimeout = null
      
      // Update callbacks for the existing connection
      this.currentOnEvent = onEvent
      this.currentOnError = onError || null
      this.currentOnOpen = onOpen || null
      console.log('[SSE] Callbacks updated for existing connection')
      return
    }

    // Check if already connected with same callbacks
    if (this.eventSource && this.eventSource.readyState === EventSource.OPEN) {
      console.warn('[SSE] Already connected — skipping duplicate connect() call')
      // Still update callbacks in case they changed
      this.currentOnEvent = onEvent
      this.currentOnError = onError || null
      this.currentOnOpen = onOpen || null
      return
    }

    // If eventSource exists but is in CONNECTING or CLOSED state, close it first
    if (this.eventSource) {
      console.log('[SSE] Closing existing connection in non-OPEN state')
      this.eventSource.close()
      this.eventSource = null
    }

    // Store callbacks
    this.currentOnEvent = onEvent
    this.currentOnError = onError || null
    this.currentOnOpen = onOpen || null

    this.token = token
    this.url = `/api/v1/reviews/stream?token=${encodeURIComponent(token)}`
    this.isManualDisconnect = false
    this.reconnectAttempts = 0
    this.currentConnectionId++

    console.log('[SSE] Connecting to stream:', this.url.replace(/token=[^&]+/, 'token=***'))

    this.eventSource = new EventSource(this.url, { withCredentials: false })

    this.eventSource.addEventListener('open', () => {
      console.log('[SSE] Connection opened')
      this.reconnectAttempts = 0
      this.currentOnOpen?.()
    })

    this.eventSource.addEventListener('review_created', (rawEvent: Event) => {
      if (this.currentOnEvent) {
        this.handleReviewCreated(rawEvent as MessageEvent, this.currentOnEvent)
      }
    })

    this.eventSource.addEventListener('error', (event: Event) => {
      this.handleError(event, this.currentOnError || undefined, this.currentOnEvent!)
    })
  }

  /**
   * Disconnect from the SSE stream
   * Uses a debounce delay to prevent rapid connect/disconnect cycles during page navigation
   */
  disconnect(): void {
    // Clear any existing disconnect timeout
    if (this.disconnectTimeout !== null) {
      clearTimeout(this.disconnectTimeout)
    }

    // Debounce disconnect by 5 seconds - if reconnect happens within this window, cancel disconnect
    this.disconnectTimeout = setTimeout(() => {
      console.log('[SSE] Performing delayed disconnect')
      this.isManualDisconnect = true

      if (this.reconnectTimeout !== null) {
        clearTimeout(this.reconnectTimeout)
        this.reconnectTimeout = null
      }

      if (this.refetchTimeout !== null) {
        clearTimeout(this.refetchTimeout)
        this.refetchTimeout = null
      }

      if (this.eventSource) {
        this.eventSource.close()
        this.eventSource = null
        console.log('[SSE] Disconnected')
      }

      this.url = null
      this.token = null
      this.disconnectTimeout = null
    }, 5000) // 5 second debounce
  }

  /**
   * Check if currently connected to the SSE stream
   */
  isConnected(): boolean {
    return this.eventSource?.readyState === EventSource.OPEN
  }

  /**
   * Handle an incoming review_created SSE event
   */
  private handleReviewCreated(
    rawEvent: MessageEvent,
    onEvent: (event: SSEReviewCreatedEvent) => void,
  ): void {
    try {
      console.log('[SSE] Raw event received:', rawEvent.data)
      const data = JSON.parse(rawEvent.data)
      console.log('[SSE] Parsed event:', data)
      if (
        !data ||
        typeof data.review_id !== 'number' ||
        typeof data.project_key !== 'string' ||
        typeof data.repository_slug !== 'string' ||
        typeof data.pull_request_id !== 'string' ||
        typeof data.created_date !== 'string'
      ) {
        console.warn('[SSE] Received malformed review_created event — dropping:', rawEvent.data)
        return
      }
      onEvent(data)
    } catch (e) {
      console.error('[SSE] Failed to parse review_created event:', e, rawEvent.data)
    }
  }

  /**
   * Handle SSE connection errors with exponential backoff reconnection
   */
  private handleError(
    event: Event,
    onError?: (error: Event) => void,
    onEvent?: (event: SSEReviewCreatedEvent) => void,
  ): void {
    if (this.isManualDisconnect) {
      return
    }

    onError?.(event)

    if (this.eventSource?.readyState === EventSource.CLOSED) {
      this.attemptReconnect(onEvent, onError)
    }
  }

  /**
   * Attempt to reconnect with exponential backoff and ±20% jitter
   */
  private attemptReconnect(
    onEvent?: (event: SSEReviewCreatedEvent) => void,
    onError?: (error: Event) => void,
  ): void {
    if (this.reconnectAttempts >= this.options.maxReconnectAttempts) {
      console.error('[SSE] Max reconnection attempts reached — giving up')
      return
    }

    this.reconnectAttempts++

    // Exponential: base * 2^(attempt-1), clamped to max
    const exponentialDelay = this.options.reconnectBaseDelay * Math.pow(2, this.reconnectAttempts - 1)
    const cappedDelay = Math.min(exponentialDelay, this.options.maxReconnectDelay)

    // Add ±20% jitter to avoid thundering herd
    const jitter = cappedDelay * 0.2 * (Math.random() * 2 - 1)
    const delay = Math.max(0, Math.round(cappedDelay + jitter))

    console.log(`[SSE] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.options.maxReconnectAttempts})`)

    this.reconnectTimeout = window.setTimeout(() => {
      if (this.token) {
        this.connect(this.token, onEvent!, onError)
      }
    }, delay)
  }
}

/** Singleton SSE service instance — one instance per tab/window */
export const sseService = new SSEService()
