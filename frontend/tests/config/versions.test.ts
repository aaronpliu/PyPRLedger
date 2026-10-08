import { afterEach, describe, expect, it, vi } from 'vitest'
import { copyrightNotice } from '@/config/versions'

// Every date below is built in local time, so the year asserted is the reader's
// year whatever zone the tests run in.
describe('copyrightNotice', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('claims the single year it started in', () => {
    expect(copyrightNotice(new Date(2026, 0, 1))).toBe('© 2026 Mobile, All rights reserved')
  })

  it('widens to a range once the year turns', () => {
    expect(copyrightNotice(new Date(2027, 0, 1))).toBe('© 2026-2027 Mobile, All rights reserved')
  })

  it('keeps widening with each year', () => {
    expect(copyrightNotice(new Date(2030, 5, 15))).toBe('© 2026-2030 Mobile, All rights reserved')
  })

  it('changes at the turn of the local year, not at midnight UTC', () => {
    expect(copyrightNotice(new Date(2026, 11, 31, 23, 59, 59))).toBe(
      '© 2026 Mobile, All rights reserved'
    )
    expect(copyrightNotice(new Date(2027, 0, 1, 0, 0, 0))).toBe(
      '© 2026-2027 Mobile, All rights reserved'
    )
  })

  it('reads the clock when it is given no date', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2028, 2, 3))

    expect(copyrightNotice()).toBe('© 2026-2028 Mobile, All rights reserved')
  })

  it('never prints a range that runs backwards, whatever the clock says', () => {
    // A clock set before the first year still gets the notice, not "2026-2024".
    expect(copyrightNotice(new Date(2024, 3, 1))).toBe('© 2026 Mobile, All rights reserved')
  })
})
