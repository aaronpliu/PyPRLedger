import request from '@/utils/request'

/** A single-use ticket that authenticates one SSE connection. */
export interface SSETicket {
  ticket: string
  expires_in: number
}

export const sseApi = {
  /**
   * Ask for a stream ticket.
   *
   * `EventSource` cannot send an Authorization header, so the JWT is spent on
   * this ordinary authenticated request instead of being written into the
   * stream URL. The ticket it returns is single-use and expires within a minute.
   */
  createStreamTicket(): Promise<SSETicket> {
    return request.post('/sse/ticket', null, {
      _silent: true,
      _suppressGlobalError: true,
    } as any)
  },
}
