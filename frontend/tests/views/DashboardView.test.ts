import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createI18n } from 'vue-i18n'
import enMessages from '@/locales/en.json'

const api = vi.hoisted(() => ({
  getReviewerActivityTrends: vi.fn(),
  getScoreTrends: vi.fn(),
  getProjectRepoActivityTrends: vi.fn(),
  getGoodSuggestionsTrends: vi.fn(),
  getReviews: vi.fn(),
  push: vi.fn(),
}))

// Capture the option handed to the activity chart (the first echarts instance).
const charts = vi.hoisted(() => ({ instances: [] as any[] }))

vi.mock('echarts', () => ({
  init: vi.fn(() => {
    const instance = {
      setOption: vi.fn(),
      resize: vi.fn(),
      dispose: vi.fn(),
    }
    charts.instances.push(instance)
    return instance
  }),
}))

vi.mock('@/api/reviews', () => ({
  reviewsApi: {
    getReviewerActivityTrends: api.getReviewerActivityTrends,
    getScoreTrends: api.getScoreTrends,
    getProjectRepoActivityTrends: api.getProjectRepoActivityTrends,
    getGoodSuggestionsTrends: api.getGoodSuggestionsTrends,
    getReviews: api.getReviews,
  },
}))

vi.mock('vue-router', () => ({ useRouter: () => ({ push: api.push }) }))

const mountedWrappers: any[] = []

function trendDay(date: string) {
  return { date, assigned_reviews: 2, self_raised_prs: 1, total: 3 }
}

async function mountView() {
  const { default: DashboardView } = await import('@/views/dashboard/DashboardView.vue')
  const i18n = createI18n({ legacy: false, locale: 'en', messages: { en: enMessages } })
  const wrapper = mount(DashboardView, {
    global: { plugins: [ElementPlus, i18n] },
  })
  mountedWrappers.push(wrapper)
  await flushPromises()
  return wrapper
}

/** The most recent option passed to the activity chart. */
function activityOptions(): any[] {
  const chart = charts.instances[0]
  return chart ? chart.setOption.mock.calls.map((call: any[]) => call[0]) : []
}

beforeEach(() => {
  charts.instances.length = 0
  api.getReviewerActivityTrends.mockResolvedValue({ trends: [trendDay('2026-11-01')] })
  api.getScoreTrends.mockResolvedValue({ trends: [] })
  api.getProjectRepoActivityTrends.mockResolvedValue({ trends: [] })
  api.getGoodSuggestionsTrends.mockResolvedValue({ trends: [] })
  api.getReviews.mockResolvedValue({ items: [], total: 0 })
  api.push.mockReset()
})

afterEach(() => {
  while (mountedWrappers.length) mountedWrappers.pop()?.unmount()
  delete (window as any).__themeObserver
  vi.clearAllMocks()
})

describe('DashboardView — Reviewer Activity Trend chart', () => {
  it('renders without an inside dataZoom, so a wheel over the chart cannot zoom it', async () => {
    await mountView()

    const options = activityOptions()
    expect(options.length).toBeGreaterThan(0)
    for (const option of options) {
      const zooms = option.dataZoom ?? []
      expect(zooms.some((zoom: any) => zoom.type === 'inside')).toBe(false)
    }
  })

  it('keeps the explicit slider for long ranges, hidden by default', async () => {
    await mountView()

    const options = activityOptions()
    const option = options[options.length - 1]
    expect(option.dataZoom).toHaveLength(1)
    expect(option.dataZoom[0].type).toBe('slider')
    expect(option.dataZoom[0].show).toBe(false)
    expect(option.dataZoom[0].start).toBe(0)
    expect(option.dataZoom[0].end).toBe(100)
  })

  it('shows the slider once there are more than 30 data points', async () => {
    api.getReviewerActivityTrends.mockResolvedValue({
      trends: Array.from({ length: 31 }, (_, i) => trendDay(`2026-11-${String(i + 1).padStart(2, '0')}`)),
    })
    await mountView()

    const options = activityOptions()
    const option = options[options.length - 1]
    expect(option.dataZoom[0].type).toBe('slider')
    expect(option.dataZoom[0].show).toBe(true)
  })

  it('replaces the option on re-render so a stale zoom range is not merged back', async () => {
    await mountView()

    const chart = charts.instances[0]
    const calls = chart.setOption.mock.calls
    expect(calls[calls.length - 1][1]).toEqual({ notMerge: true })
  })
})
