import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Router } from 'vue-router'
import { ElMessageBox } from 'element-plus'

import i18n from '@/i18n'
import { installStaleChunkRecovery, isStaleChunkError } from '@/router/staleChunkRecovery'

vi.mock('element-plus', () => ({
  ElMessageBox: { confirm: vi.fn() },
}))

const confirm = ElMessageBox.confirm as unknown as ReturnType<typeof vi.fn>
const t = (key: string) => i18n.global.t(key)

const STALE_IMPORT = new TypeError(
  'Failed to fetch dynamically imported module: https://example.com/assets/js/TaskAssignmentView-abc123.js',
)

function fakeRouter() {
  let handler: ((error: unknown) => void) | null = null
  const onError = vi.fn((next: (error: unknown) => void) => {
    handler = next
    return () => {
      handler = null
    }
  })

  return {
    router: { onError } as unknown as Router,
    onError,
    failWith: (error: unknown) => handler?.(error),
    listening: () => handler !== null,
  }
}

const flush = () => new Promise((resolve) => setTimeout(resolve, 0))

beforeEach(() => {
  confirm.mockReset()
})

describe('isStaleChunkError', () => {
  it('recognises the ways a replaced chunk is reported', () => {
    expect(isStaleChunkError(STALE_IMPORT)).toBe(true)
    expect(isStaleChunkError('error loading dynamically imported module')).toBe(true)
    expect(isStaleChunkError('Importing a module script failed.')).toBe(true)
    expect(isStaleChunkError('Loading chunk 12 failed.')).toBe(true)
    expect(isStaleChunkError('Unable to preload CSS for /assets/css/a.css')).toBe(true)
  })

  it('leaves other failures to whoever raised them', () => {
    expect(isStaleChunkError(new Error('Request failed with status code 500'))).toBe(false)
    expect(isStaleChunkError(new Error('You can only score reviews explicitly assigned to you.'))).toBe(
      false,
    )
    expect(isStaleChunkError(undefined)).toBe(false)
    expect(isStaleChunkError({ message: 'not an error instance' })).toBe(false)
  })
})

describe('installStaleChunkRecovery', () => {
  it('asks the reader to reload, in their language, when a navigation chunk is gone', async () => {
    const { router, failWith } = fakeRouter()
    const reload = vi.fn()
    confirm.mockResolvedValue('confirm')
    const stop = installStaleChunkRecovery(router, reload)

    failWith(STALE_IMPORT)
    await vi.waitFor(() => expect(confirm).toHaveBeenCalledTimes(1))
    await vi.waitFor(() => expect(reload).toHaveBeenCalledTimes(1))

    const [message, title, options] = confirm.mock.calls[0]
    expect(message).toBe(t('common.new_version.message'))
    expect(title).toBe(t('common.new_version.title'))
    expect(options).toMatchObject({
      confirmButtonText: t('common.new_version.refresh'),
      cancelButtonText: t('common.new_version.later'),
      showClose: false,
      closeOnClickModal: false,
      closeOnPressEscape: false,
    })
    expect(options.confirmButtonText).not.toBe(options.cancelButtonText)

    stop()
  })

  it('leaves the page as it is when the reader chooses to stay', async () => {
    const { router, failWith } = fakeRouter()
    const reload = vi.fn()
    confirm.mockRejectedValue(new Error('cancel'))
    const stop = installStaleChunkRecovery(router, reload)

    failWith(STALE_IMPORT)
    await vi.waitFor(() => expect(confirm).toHaveBeenCalledTimes(1))
    await flush()

    expect(reload).not.toHaveBeenCalled()

    // Every click on a stale tab fails the same way; the question is not repeated.
    failWith(STALE_IMPORT)
    await flush()
    expect(confirm).toHaveBeenCalledTimes(1)

    stop()
  })

  it('does not ask twice while the question is still open', async () => {
    const { router, failWith } = fakeRouter()
    confirm.mockReturnValue(new Promise(() => {}))
    const stop = installStaleChunkRecovery(router, vi.fn())

    failWith(STALE_IMPORT)
    failWith(STALE_IMPORT)
    await vi.waitFor(() => expect(confirm).toHaveBeenCalledTimes(1))
    await flush()

    expect(confirm).toHaveBeenCalledTimes(1)
    stop()
  })

  it('leaves an ordinary navigation error alone', async () => {
    const { router, failWith } = fakeRouter()
    const reload = vi.fn()
    const stop = installStaleChunkRecovery(router, reload)

    failWith(new Error('Navigation cancelled'))
    await flush()

    expect(confirm).not.toHaveBeenCalled()
    expect(reload).not.toHaveBeenCalled()
    stop()
  })

  it('asks for a failed preload and stops Vite rethrowing it', async () => {
    const { router } = fakeRouter()
    const reload = vi.fn()
    confirm.mockResolvedValue('confirm')
    const stop = installStaleChunkRecovery(router, reload)

    const event = new Event('vite:preloadError', { cancelable: true })
    window.dispatchEvent(event)

    expect(event.defaultPrevented).toBe(true)
    await vi.waitFor(() => expect(confirm).toHaveBeenCalledTimes(1))
    await vi.waitFor(() => expect(reload).toHaveBeenCalledTimes(1))
    stop()
  })

  it('stops watching when torn down', async () => {
    const { router, listening } = fakeRouter()
    confirm.mockResolvedValue('confirm')
    const stop = installStaleChunkRecovery(router, vi.fn())

    stop()

    expect(listening()).toBe(false)
    window.dispatchEvent(new Event('vite:preloadError', { cancelable: true }))
    await flush()
    expect(confirm).not.toHaveBeenCalled()
  })
})
