import { beforeEach, describe, expect, it, vi } from 'vitest'

// The preview is the one release note call that may carry an LLM pass, so what it is
// sent with is worth pinning: the client holds the answer, not the work.
const calls: unknown[][] = []

vi.mock('@/utils/request', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(async (...args: unknown[]) => {
      calls.push(args)
      return { data: { body: '# Fixed\n- One thing' } }
    }),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

import { releaseNotesApi } from '@/api/releaseNotes'

const payload = {
  project_key: 'CORE',
  repository_slug: 'app',
  version: 'v1.28.0',
}

/** The request the api sent, as `[url, payload, config]`. */
function sent(index = 0) {
  return calls[index] as [string, Record<string, unknown>, { timeout?: number }]
}

describe('releaseNotesApi.preview', () => {
  beforeEach(() => {
    calls.length = 0
  })

  it('asks the endpoint it always asked', async () => {
    await releaseNotesApi.preview(payload)

    expect(sent()[0]).toBe('/release/notes/preview')
    expect(sent()[1]).toMatchObject({ version: 'v1.28.0' })
  })

  it('is given a timeout of its own, longer than the server waits on the LLM', async () => {
    await releaseNotesApi.preview({ ...payload, summarize: true })

    // the summarizer may spend LLM_REQUEST_TIMEOUT_SECONDS (120s by default) on the
    // provider inside this request, while the timeout the rest of the app uses is 30s:
    // with that, the client gave up while the server was still writing, which the page
    // reported as a network error and the commit subjects fell back into place
    expect(sent()[2].timeout).toBeGreaterThan(120_000)
  })
})
