/**
 * SSE Service for real-time review notifications
 *
 * Features:
 * - JWT authentication via query parameter
 * - Automatic reconnection with exponential backoff (2s base, max 30s, ±20% jitter)
 * - Connection lifecycle management
 * - Type-safe event parsing
 * - Per-tab connection isolation (each tab gets its own instance)
 * - Visibility change handling — reconnects when tab becomes visible
 * - Fast recovery from 503 errors with shorter retry delay
 */

import router from '@/router'
import { useAuthStore } from '@/stores/auth'

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
  /** Maximum reconnection attempts before giving up (default: 15) */
  maxReconnectAttempts: number
  /** Base reconnection delay in ms, doubled each attempt (default: 2000) */
  reconnectBaseDelay: number
  /** Maximum reconnection delay in ms (default: 30000) */
  maxReconnectDelay: number
  /** Fast retry delay for 503 errors in ms (default: 1500) */
  fastRetryDelay: number
}

export class SSEService {
  private eventSource: EventSource | null = null
  private reconnectAttempts = 0
  private reconnectTimeout: ReturnType<typeof setTimeout> | null = null
  private options: SSEServiceOptions
  private isManualDisconnect = false
  private url: string | null = null
  private token: string | null = null
  /** Incremented on each connect() — stale callbacks check and abort */
  private connectionGeneration = 0

  /** Whether SSE is enabled by the user */
  private _enabled = true

  /** Stored last connect parameters for reconnection on enable */
  private lastToken: string | null = null
  private lastOnEvent: ((event: SSEReviewCreatedEvent) => void) | null = null
  private lastOnError: ((error: Event) => void) | null = null
  private lastOnOpen: (() => void) | null = null

  // Store current callbacks so they can be updated
  private currentOnEvent: ((event: SSEReviewCreatedEvent) => void) | null = null
  private currentOnError: ((error: Event) => void) | null = null
  private currentOnOpen: (() => void) | null = null

  /** Bound beforeunload handler reference for cleanup */
  private boundBeforeUnload: (() => void) | null = null

  /** Pending debounced disconnect timeout (set during page navigation) */
  private pendingDisconnectTimeout: ReturnType<typeof setTimeout> | null = null

  /** Debounce delay before actual disconnect on page navigation (ms) */
  private static readonly DISCONNECT_DEBOUNCE_MS = 2000

  /** Whether the last error was a 503 (triggers fast retry) */
  private _lastErrorWas503 = false

  /** Bound visibility change handler reference for cleanup */
  private boundVisibilityChange: (() => void) | null = null

  /** Bound pageshow handler reference for cleanup */
  private boundPageShow: ((event: PageTransitionEvent) => void) | null = null

  constructor(options: Partial<SSEServiceOptions> = {}) {
    this.options = {
      maxReconnectAttempts: 15,
      reconnectBaseDelay: 2000,
      maxReconnectDelay: 30000,
      fastRetryDelay: 1500,
      ...options,
    }
  }

  /**
   * Connect to the SSE stream
   * Closes any existing connection immediately before creating a new one.
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
    // If a pending disconnect exists, cancel it and reuse the current connection
    if (this.pendingDisconnectTimeout !== null) {
      console.log('[SSE] Cancelling pending disconnect — reusing existing connection')
      clearTimeout(this.pendingDisconnectTimeout)
      this.pendingDisconnectTimeout = null

      // Update callbacks for the current component
      this.currentOnEvent = onEvent
      this.currentOnError = onError || null
      this.currentOnOpen = onOpen || null

      // Restore reconnect capability
      this.isManualDisconnect = false
      this.reconnectAttempts = 0
      this._enabled = true

      // Update stored params — token may have been refreshed
      this.token = token
      this.lastToken = token
      this.lastOnEvent = onEvent
      this.lastOnError = onError || null
      this.lastOnOpen = onOpen || null

      // Also update the URL if token changed (for reconnection attempts)
      this.url = `/api/v1/sse/stream?token=${encodeURIComponent(token)}`

      // DO NOT increment connectionGeneration — existing event listeners
      // still reference currentOnEvent/OnError/OnOpen, which we just updated

      return
    }

    // Close existing connection immediately (if any)
    if (this.eventSource) {
      console.log('[SSE] Closing existing connection for new connect()')
      this.eventSource.close()
      this.eventSource = null
    }

    // Clear any pending reconnect — we're starting fresh
    if (this.reconnectTimeout !== null) {
      clearTimeout(this.reconnectTimeout)
      this.reconnectTimeout = null
    }

    // Store callbacks
    this.currentOnEvent = onEvent
    this.currentOnError = onError || null
    this.currentOnOpen = onOpen || null

    this.token = token
    this.url = `/api/v1/sse/stream?token=${encodeURIComponent(token)}`
    this.isManualDisconnect = false
    this.reconnectAttempts = 0
    this._lastErrorWas503 = false
    this._enabled = true

    // Save last connect params for reconnection on setEnabled(true)
    this.lastToken = token
    this.lastOnEvent = onEvent
    this.lastOnError = onError || null
    this.lastOnOpen = onOpen || null

    this.connectionGeneration++
    const myGeneration = this.connectionGeneration

    console.log('[SSE] Connecting to stream:', this.url.replace(/token=[^&]+/, 'token=***'))

    // Register beforeunload listener to disconnect immediately on refresh/close
    if (this.boundBeforeUnload) {
      window.removeEventListener('beforeunload', this.boundBeforeUnload)
    }
    this.boundBeforeUnload = () => this.disconnectImmediate()
    window.addEventListener('beforeunload', this.boundBeforeUnload)

    // Register visibility change listener — reconnect when tab becomes visible
    // and the connection is not active
    this._setupVisibilityListener()

    // Register pageshow listener for bfcache restoration
    this._setupPageShowListener()

    this.eventSource = new EventSource(this.url, { withCredentials: false })

    this.eventSource.addEventListener('open', () => {
      // Ignore if a newer connection has been created
      if (myGeneration !== this.connectionGeneration) {
        return
      }
      console.log('[SSE] Connection opened')
      this.reconnectAttempts = 0
      this._lastErrorWas503 = false
      this.currentOnOpen?.()
    })

    this.eventSource.addEventListener('review_created', (rawEvent: Event) => {
      // Ignore if a newer connection has been created
      if (myGeneration !== this.connectionGeneration) {
        return
      }
      if (this.currentOnEvent) {
        this.handleReviewCreated(rawEvent as MessageEvent, this.currentOnEvent)
      }
    })

    this.eventSource.addEventListener('error', (event: Event) => {
      // Ignore if a newer connection has been created
      if (myGeneration !== this.connectionGeneration) {
        return
      }
      this.handleError(event, this.currentOnError || undefined, this.currentOnEvent!)
    })
  }

  /**
   * Disconnect from the SSE stream with a debounce for page navigation.
   * Keeps the EventSource alive for DISCONNECT_DEBOUNCE_MS so that
   * rapid navigation between pages can reuse the same connection.
   *
   * Callbacks are preserved during the debounce window so that events
   * arriving before the actual close are still processed.
   */
  disconnect(): void {
    // Remove beforeunload listener (will be re-added on next connect)
    if (this.boundBeforeUnload) {
      window.removeEventListener('beforeunload', this.boundBeforeUnload)
      this.boundBeforeUnload = null
    }

    // Mark as manual disconnect to prevent reconnect logic from firing
    // but DO NOT null callbacks — EventSource is still alive during debounce
    this.isManualDisconnect = true

    // Schedule delayed disconnection so rapid navigation reuses connection
    if (this.pendingDisconnectTimeout === null) {
      console.log(`[SSE] Scheduling disconnect in ${SSEService.DISCONNECT_DEBOUNCE_MS}ms`)
      this.pendingDisconnectTimeout = setTimeout(() => {
        this.disconnectImmediate()
      }, SSEService.DISCONNECT_DEBOUNCE_MS)
    }
  }

  /**
   * Cancel a pending debounced disconnect without closing the connection.
   * Used when the user returns to a page before the debounce timer fires.
   */
  cancelPendingDisconnect(): void {
    if (this.pendingDisconnectTimeout !== null) {
      clearTimeout(this.pendingDisconnectTimeout)
      this.pendingDisconnectTimeout = null
      console.log('[SSE] Cancelled pending disconnect — connection preserved')
    }
    this.isManualDisconnect = false
  }

  /**
   * Immediate disconnect — closes EventSource and clears all state.
   */
  private disconnectImmediate(): void {
    console.log('[SSE] Immediate disconnect')
    this.isManualDisconnect = true
    this.pendingDisconnectTimeout = null
    this._lastErrorWas503 = false

    if (this.reconnectTimeout !== null) {
      clearTimeout(this.reconnectTimeout)
      this.reconnectTimeout = null
    }

    // Remove visibility/pageshow listeners
    this._teardownVisibilityListener()
    this._teardownPageShowListener()

    if (this.eventSource) {
      this.eventSource.close()
      this.eventSource = null
      console.log('[SSE] EventSource closed')
    }

    // Only null callbacks when the connection is actually closed
    this.currentOnEvent = null
    this.currentOnError = null
    this.currentOnOpen = null
    this.url = null
    this.token = null
  }

  /**
   * Enable or disable the SSE connection.
   * When disabled, the connection is closed immediately.
   * When enabled, reconnects using the last stored parameters.
   *
   * This is useful for the user-facing toggle that controls real-time updates.
   */
  setEnabled(enabled: boolean): void {
    this._enabled = enabled
    if (enabled) {
      console.log('[SSE] Enabling connection')
      if (this.lastToken && this.lastOnEvent) {
        this.connect(this.lastToken, this.lastOnEvent, this.lastOnError || undefined, this.lastOnOpen || undefined)
      }
    } else {
      console.log('[SSE] Disabling connection')
      // Cancel any pending debounced disconnect and close immediately
      if (this.pendingDisconnectTimeout !== null) {
        clearTimeout(this.pendingDisconnectTimeout)
        this.pendingDisconnectTimeout = null
      }
      this.disconnectImmediate()
    }
  }

  /**
   * Reconnect with a new token (after token refresh).
   * Updates the stored token and reconnects if currently connected or enabled.
   */
  reconnectWithToken(newToken: string): void {
    // Update stored token so reconnection attempts use the new token
    this.token = newToken
    this.lastToken = newToken

    // Also update the URL for reconnection
    this.url = `/api/v1/sse/stream?token=${encodeURIComponent(newToken)}`

    if (this._enabled && this.lastOnEvent) {
      console.log('[SSE] Reconnecting with refreshed token')
      this.reconnectAttempts = 0
      this._lastErrorWas503 = false
      // Use connect() to get full setup including visibility listeners
      this.connect(newToken, this.lastOnEvent, this.lastOnError || undefined, this.lastOnOpen || undefined)
    }
  }

  /**
   * Check whether SSE is currently enabled by the user.
   */
  getEnabled(): boolean {
    return this._enabled
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
   * Handle SSE connection errors with exponential backoff reconnection.
   *
   * Does NOT redirect to login on token expiry — the token was valid at
   * connection time. The request interceptor handles token refresh for
   * API calls. If reconnection consistently fails, the user can manually
   * toggle SSE or refresh the page.
   */
  private handleError(
    event: Event,
    onError?: (error: Event) => void,
    onEvent?: (event: SSEReviewCreatedEvent) => void,
  ): void {
    if (this.isManualDisconnect || !this._enabled) {
      return
    }

    // Detect 503 errors — EventSource doesn't expose HTTP status directly,
    // but when readyState goes to CLOSED immediately after CONNECTING,
    // it's typically a server rejection (503, 429, etc.)
    // We use a heuristic: if the connection never opened and is now closed,
    // treat it as a fast-retry candidate.
    if (
      this.eventSource?.readyState === EventSource.CLOSED &&
      this.reconnectAttempts === 0
    ) {
      this._lastErrorWas503 = true
    }

    // If the EventSource is already closed by the browser, attempt reconnection
    if (this.eventSource?.readyState === EventSource.CLOSED || !this.eventSource) {
      onError?.(event)
      this.attemptReconnect(onEvent, onError)
    }
  }

  /**
   * Check if a JWT token is expired by decoding its payload
   */
  private isTokenExpired(token: string): boolean {
    try {
      const payload = JSON.parse(atob(token.split('.')[1]))
      if (!payload.exp) return false
      const now = Math.floor(Date.now() / 1000)
      return payload.exp < now
    } catch {
      return false
    }
  }

  /**
   * Handle authentication failure (expired or invalid token)
   *
   * Disconnects SSE, clears auth state, and redirects to the login page.
   * Also persists the disabled state to localStorage so SSE stays off
   * after page reload.
   */
  private handleAuthFailure(): void {
    console.error('[SSE] Authentication failed — token expired')
    this.disconnectImmediate()
    this._enabled = false
    localStorage.setItem('sse_enabled', 'false')

    try {
      const authStore = useAuthStore()
      authStore.clearAuth()
    } catch (e) {
      console.warn('[SSE] Failed to clear auth store:', e)
    }

    // Navigate to login page (avoid loops by checking current path)
    if (window.location.pathname !== '/login') {
      router.replace('/login')
    }
  }

  /**
   * Attempt to reconnect with exponential backoff and ±20% jitter.
   * Uses the current stored token and callbacks for reconnection.
   * Uses faster retry delay for 503 errors.
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

    let delay: number
    if (this._lastErrorWas503) {
      // Fast retry for 503 errors — the server may recover quickly
      delay = this.options.fastRetryDelay
      console.log(`[SSE] Fast retry for 503 error in ${delay}ms`)
    } else {
      // Exponential: base * 2^(attempt-1), clamped to max
      const exponentialDelay = this.options.reconnectBaseDelay * Math.pow(2, this.reconnectAttempts - 1)
      const cappedDelay = Math.min(exponentialDelay, this.options.maxReconnectDelay)

      // Add ±20% jitter to avoid thundering herd
      const jitter = cappedDelay * 0.2 * (Math.random() * 2 - 1)
      delay = Math.max(0, Math.round(cappedDelay + jitter))
    }

    console.log(`[SSE] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.options.maxReconnectAttempts})`)

    this.reconnectTimeout = setTimeout(() => {
      if (this.lastToken) {
        this.connect(this.lastToken, this.lastOnEvent || onEvent!, this.lastOnError || onError)
      } else if (this.token) {
        this.connect(this.token, onEvent!, onError)
      }
    }, delay)
  }

  /**
   * Set up visibility change listener to reconnect when tab becomes visible.
   * Browsers throttle or kill EventSource connections when the tab is hidden.
   * When the user returns, we check if the connection is still alive and
   * reconnect if needed.
   */
  private _setupVisibilityListener(): void {
    this._teardownVisibilityListener()
    this.boundVisibilityChange = () => {
      if (document.visibilityState === 'visible' && this._enabled && !this.isManualDisconnect) {
        // Check if connection is dead and needs reconnection
        if (!this.eventSource || this.eventSource.readyState === EventSource.CLOSED) {
          console.log('[SSE] Tab became visible — connection dead, reconnecting')
          this.reconnectAttempts = 0
          this._lastErrorWas503 = false
          if (this.lastToken) {
            this.connect(this.lastToken, this.lastOnEvent!, this.lastOnError || undefined, this.lastOnOpen || undefined)
          }
        } else if (this.eventSource.readyState === EventSource.CONNECTING) {
          // Connection is trying to reconnect — reset attempts to give it more chances
          console.log('[SSE] Tab became visible — connection reconnecting, resetting attempts')
          this.reconnectAttempts = 0
        }
      }
    }
    document.addEventListener('visibilitychange', this.boundVisibilityChange)
  }

  /**
   * Tear down visibility change listener.
   */
  private _teardownVisibilityListener(): void {
    if (this.boundVisibilityChange) {
      document.removeEventListener('visibilitychange', this.boundVisibilityChange)
      this.boundVisibilityChange = null
    }
  }

  /**
   * Set up pageshow listener for bfcache restoration.
   * When the browser restores a page from bfcache, the EventSource
   * may be in a broken state.
   */
  private _setupPageShowListener(): void {
    this._teardownPageShowListener()
    this.boundPageShow = (event: PageTransitionEvent) => {
      if (event.persisted && this._enabled && !this.isManualDisconnect) {
        // Page was restored from bfcache — check connection
        if (!this.eventSource || this.eventSource.readyState !== EventSource.OPEN) {
          console.log('[SSE] Page restored from bfcache — reconnecting')
          this.reconnectAttempts = 0
          this._lastErrorWas503 = false
          if (this.lastToken) {
            this.connect(this.lastToken, this.lastOnEvent!, this.lastOnError || undefined, this.lastOnOpen || undefined)
          }
        }
      }
    }
    window.addEventListener('pageshow', this.boundPageShow)
  }

  /**
   * Tear down pageshow listener.
   */
  private _teardownPageShowListener(): void {
    if (this.boundPageShow) {
      window.removeEventListener('pageshow', this.boundPageShow)
      this.boundPageShow = null
    }
  }
}

/** Singleton SSE service instance — one instance per tab/window */
export const sseService = new SSEService()
