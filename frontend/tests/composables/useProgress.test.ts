import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  PROGRESS_MIN_VISIBLE_MS,
  PROGRESS_SHOW_DELAY_MS,
  beginProgress,
  endProgress,
  resetProgress,
  useProgress,
} from '@/composables/useProgress'

describe('useProgress', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    resetProgress()
  })
  afterEach(() => {
    resetProgress()
    vi.useRealTimers()
  })

  it('stays hidden for a call answered within the delay', () => {
    const { visible, active } = useProgress()
    const id = beginProgress()
    expect(active.value).toBe(true)
    expect(visible.value).toBe(false)

    endProgress(id)
    vi.advanceTimersByTime(PROGRESS_SHOW_DELAY_MS + 10)
    expect(visible.value).toBe(false)
  })

  it('appears after the delay', () => {
    const { visible } = useProgress()
    const id = beginProgress()
    vi.advanceTimersByTime(PROGRESS_SHOW_DELAY_MS + 1)
    expect(visible.value).toBe(true)
    endProgress(id)
  })

  it('stays long enough to be read once it has appeared', () => {
    const { visible } = useProgress()
    const id = beginProgress()
    vi.advanceTimersByTime(PROGRESS_SHOW_DELAY_MS + 1)
    expect(visible.value).toBe(true)

    endProgress(id)
    // answered instantly, but the bar is held for the floor
    vi.advanceTimersByTime(PROGRESS_MIN_VISIBLE_MS / 2)
    expect(visible.value).toBe(true)
    vi.advanceTimersByTime(PROGRESS_MIN_VISIBLE_MS)
    expect(visible.value).toBe(false)
  })

  it('ends only the work its own id opened', () => {
    const { pending } = useProgress()
    const a = beginProgress()
    const b = beginProgress()
    expect(pending.value).toBe(2)

    endProgress(a)
    endProgress(a) // an answer that arrived twice must not end b's work
    expect(pending.value).toBe(1)

    endProgress(b)
    expect(pending.value).toBe(0)
  })
})
