import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { createMemoryHistory, createRouter } from 'vue-router'
import ReviewsBanner from '@/components/common/ReviewsBanner.vue'
import { rbacApi, type BannerItem } from '@/api/rbac'
import enMessages from '@/locales/en.json'

vi.mock('@/api/rbac', () => ({
  rbacApi: { getBanner: vi.fn() },
}))

const DISMISSED_KEY = 'banner_dismissed_ids'
const LEGACY_DISMISSED_KEY = 'banner_dismissed_id'
const ROTATE_MS = 6000

/* eslint-disable @typescript-eslint/no-explicit-any */
type AnyWrapper = any

const mountedWrappers: AnyWrapper[] = []

function banner(patch: Partial<BannerItem> = {}): BannerItem {
  return {
    id: 'b1',
    enabled: true,
    content: 'A notice',
    start_date: '',
    end_date: '',
    level: 'info',
    link_url: '',
    link_label: '',
    priority: 0,
    ...patch,
  }
}

function storedDismissals(): string[] {
  return JSON.parse(localStorage.getItem(DISMISSED_KEY) ?? '[]')
}

async function mountBanner(banners: BannerItem[]) {
  vi.mocked(rbacApi.getBanner).mockResolvedValue({ banners })
  const i18n = createI18n({ legacy: false, locale: 'en', messages: { en: enMessages } })
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/releases/notes', component: { template: '<div />' } },
    ],
  })
  const wrapper = mount(ReviewsBanner, { global: { plugins: [i18n, router] } })
  mountedWrappers.push(wrapper)
  await flushPromises()
  return wrapper
}

/** The one banner in the bar, or null when there is nothing to show. */
function currentText(wrapper: AnyWrapper): string | null {
  const text = wrapper.find('.banner-text')
  return text.exists() ? text.text() : null
}

function dotCount(wrapper: AnyWrapper): number {
  return wrapper.findAll('[data-test="banner-dot"]').length
}

/**
 * The rotation is the only thing on a clock, so only the interval is faked —
 * `flushPromises` keeps working on real timers.
 */
function useRotationClock() {
  vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] })
}

async function rotate(ms = ROTATE_MS) {
  await vi.advanceTimersByTimeAsync(ms)
  await flushPromises()
}

describe('ReviewsBanner', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.mocked(rbacApi.getBanner).mockReset()
  })

  afterEach(() => {
    mountedWrappers.splice(0).forEach((wrapper) => wrapper.unmount())
    vi.useRealTimers()
  })

  it('starts on the highest priority banner', async () => {
    const wrapper = await mountBanner([
      banner({ id: 'low', content: 'Low', priority: 0 }),
      banner({ id: 'high', content: 'High', priority: 9 }),
      banner({ id: 'mid', content: 'Mid', priority: 5 }),
    ])

    expect(currentText(wrapper)).toBe('High')
    // One dot per banner, so it is clear there are more to read.
    expect(dotCount(wrapper)).toBe(3)
  })

  it('takes turns through the banners and comes back round', async () => {
    useRotationClock()
    const wrapper = await mountBanner([
      banner({ id: 'high', content: 'High', priority: 9 }),
      banner({ id: 'mid', content: 'Mid', priority: 5 }),
      banner({ id: 'low', content: 'Low', priority: 0 }),
    ])

    expect(currentText(wrapper)).toBe('High')
    await rotate()
    expect(currentText(wrapper)).toBe('Mid')
    await rotate()
    expect(currentText(wrapper)).toBe('Low')
    await rotate()
    expect(currentText(wrapper)).toBe('High')
  })

  it('keeps equal priorities in the order the server returned', async () => {
    useRotationClock()
    const wrapper = await mountBanner([
      banner({ id: 'first', content: 'First' }),
      banner({ id: 'second', content: 'Second' }),
    ])

    expect(currentText(wrapper)).toBe('First')
    await rotate()
    expect(currentText(wrapper)).toBe('Second')
  })

  it('never turns away from the only banner there is', async () => {
    useRotationClock()
    const wrapper = await mountBanner([banner({ id: 'only', content: 'Only one' })])

    await rotate(ROTATE_MS * 3)

    expect(currentText(wrapper)).toBe('Only one')
    // Nothing to choose between, so no dots either.
    expect(dotCount(wrapper)).toBe(0)
  })

  it('leaves out what should not be shown', async () => {
    const wrapper = await mountBanner([
      banner({ id: 'shown', content: 'Shown' }),
      banner({ id: 'disabled', content: 'Disabled', enabled: false }),
      banner({ id: 'wordless', content: '   ' }),
      banner({ id: 'future', content: 'Future', start_date: '2099-01-01T00:00:00+00:00' }),
      banner({ id: 'past', content: 'Past', end_date: '2000-01-01T00:00:00+00:00' }),
    ])

    expect(currentText(wrapper)).toBe('Shown')
    expect(dotCount(wrapper)).toBe(0)
  })

  it('carries the level as a class, so the bar is coloured by the banner on show', async () => {
    useRotationClock()
    const wrapper = await mountBanner([
      banner({ id: 'warning', content: 'Careful', level: 'warning' }),
      banner({ id: 'success', content: 'Done', level: 'success' }),
    ])

    expect(wrapper.find('.reviews-banner').classes()).toContain('reviews-banner--warning')
    await rotate()
    expect(wrapper.find('.reviews-banner').classes()).toContain('reviews-banner--success')
  })

  it('holds the banner while the pointer is over it', async () => {
    useRotationClock()
    const wrapper = await mountBanner([
      banner({ id: 'one', content: 'First' }),
      banner({ id: 'two', content: 'Second' }),
    ])

    await wrapper.find('.reviews-banner').trigger('mouseenter')
    await rotate(ROTATE_MS * 3)
    expect(currentText(wrapper)).toBe('First')

    await wrapper.find('.reviews-banner').trigger('mouseleave')
    await rotate()
    expect(currentText(wrapper)).toBe('Second')
  })

  it('lets a dot pick a banner, and gives it a full turn', async () => {
    useRotationClock()
    const wrapper = await mountBanner([
      banner({ id: 'a', content: 'A' }),
      banner({ id: 'b', content: 'B' }),
      banner({ id: 'c', content: 'C' }),
    ])

    await wrapper.findAll('[data-test="banner-dot"]')[2].trigger('click')
    expect(currentText(wrapper)).toBe('C')

    // The picked banner stays for a whole interval rather than for what was left of one.
    await rotate(ROTATE_MS - 100)
    expect(currentText(wrapper)).toBe('C')
    await rotate(100)
    expect(currentText(wrapper)).toBe('A')
  })

  it('dismisses the banner on show and keeps turning through the rest', async () => {
    useRotationClock()
    const wrapper = await mountBanner([
      banner({ id: 'one', content: 'First' }),
      banner({ id: 'two', content: 'Second' }),
    ])

    await wrapper.find('.banner-close').trigger('click')

    // The one after it slides in, without a jump back to the top.
    expect(currentText(wrapper)).toBe('Second')
    expect(dotCount(wrapper)).toBe(0)
    expect(storedDismissals()).toHaveLength(1)
  })

  it('shows a banner again once its wording is edited', async () => {
    const first = await mountBanner([banner({ id: 'b1', content: 'Original' })])
    await first.find('.banner-close').trigger('click')
    expect(currentText(first)).toBeNull()
    first.unmount()

    // Same banner, new words: it is a different announcement now.
    const second = await mountBanner([banner({ id: 'b1', content: 'Rewritten' })])

    expect(currentText(second)).toBe('Rewritten')
  })

  it('forgets the keys of banners that no longer exist', async () => {
    const first = await mountBanner([banner({ id: 'retired', content: 'Retired' })])
    await first.find('.banner-close').trigger('click')
    expect(storedDismissals()).toHaveLength(1)
    first.unmount()

    await mountBanner([banner({ id: 'other', content: 'Something else' })])

    expect(storedDismissals()).toEqual([])
  })

  it('clears the single dismissal slot it used before', async () => {
    localStorage.setItem(LEGACY_DISMISSED_KEY, 'anything')

    await mountBanner([banner()])

    expect(localStorage.getItem(LEGACY_DISMISSED_KEY)).toBeNull()
  })

  it('stops the clock when it goes away', async () => {
    useRotationClock()
    const wrapper = await mountBanner([
      banner({ id: 'one', content: 'First' }),
      banner({ id: 'two', content: 'Second' }),
    ])
    expect(vi.getTimerCount()).toBe(1)

    wrapper.unmount()

    expect(vi.getTimerCount()).toBe(0)
  })

  it('routes an in-app link and opens an outside one in a new tab', async () => {
    useRotationClock()
    const wrapper = await mountBanner([
      banner({ id: 'inside', content: 'Inside', link_url: '/releases/notes', link_label: 'Notes' }),
      banner({ id: 'outside', content: 'Outside', link_url: 'https://git.local/x' }),
    ])

    const inside = wrapper.find('.banner-link')
    expect(inside.text()).toBe('Notes')
    expect(inside.attributes('href')).toBe('/releases/notes')

    await rotate()
    const outside = wrapper.find('.banner-link')
    // No label given, so the shared word is used.
    expect(outside.text()).toBe(enMessages.common.more)
    expect(outside.attributes('href')).toBe('https://git.local/x')
    expect(outside.attributes('target')).toBe('_blank')
  })
})
