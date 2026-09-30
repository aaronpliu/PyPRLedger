import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  PROGRESS_MIN_VISIBLE_MS,
  PROGRESS_SHOW_DELAY_MS,
  beginProgress,
  endProgress,
  progressLabelFor,
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

  it('names the calls that leave the backend', () => {
    expect(progressLabelFor('/release/diff/refs')).toBe('common.loading_refs')
    expect(progressLabelFor('/release/diff/compare')).toBe('common.loading_compare')
    expect(progressLabelFor('/release/diff/check')).toBe('common.loading_compare')
    expect(progressLabelFor('/release/notes/preview')).toBe('common.loading_preview')
    expect(progressLabelFor('/release/notes')).toBeNull()
    expect(progressLabelFor(undefined)).toBeNull()
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

  it('appears after the delay and counts the seconds', () => {
    const { visible, elapsedSeconds } = useProgress()
    const id = beginProgress('common.loading_refs')
    vi.advanceTimersByTime(PROGRESS_SHOW_DELAY_MS + 1)
    expect(visible.value).toBe(true)

    vi.advanceTimersByTime(3000)
    expect(elapsedSeconds.value).toBe(3)
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

  it('reports the latest label and clears it on reset', () => {
    const { label } = useProgress()
    beginProgress('common.loading_refs')
    expect(label.value).toBe('common.loading_refs')
    resetProgress()
    expect(label.value).toBeNull()
  })
})
