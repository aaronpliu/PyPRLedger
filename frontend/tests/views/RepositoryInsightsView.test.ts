import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createI18n } from 'vue-i18n'
import enMessages from '@/locales/en.json'

const api = vi.hoisted(() => ({
  getRepositoryInsights: vi.fn(),
  getAllProjects: vi.fn(),
  getProjectRepositories: vi.fn(),
}))

// The page watches review events on the shared stream; the tests hand it the
// events directly through the same registry the service would call.
const sse = vi.hoisted(() => ({ listeners: new Set<(event: any) => void>() }))

vi.mock('@/utils/sse', () => ({
  sseService: {
    addReviewListener: (handler: (event: any) => void) => sse.listeners.add(handler),
    removeReviewListener: (handler: (event: any) => void) => sse.listeners.delete(handler),
  },
}))

vi.mock('@/api/insights', () => ({
  insightsApi: { getRepositoryInsights: api.getRepositoryInsights },
}))

vi.mock('@/api/projects', () => ({
  projectsApi: {
    getAllProjects: api.getAllProjects,
    getProjectRepositories: api.getProjectRepositories,
  },
}))

const mountedWrappers: any[] = []

function reading(overrides: Record<string, unknown> = {}) {
  return {
    scope: {
      project_key: 'CORE',
      repository_slug: null,
      days: 30,
      period: 'weekly',
      generated_at: '2026-11-16T10:00:00',
    },
    kpis: {
      reviews_total: 12,
      reviews_open: 3,
      reviews_today: 1,
      avg_score: 7.4,
      good_suggestion_rate: 0.38,
      assigned_pending: 2,
      assigned_in_progress: 1,
      unassigned_count: 4,
      active_reviewers: 5,
    },
    trends: [
      { period_start: '2026-W44', reviews: 4, avg_score: 7.1, high_scores: 1, assigned: 3, completed: 2 },
      { period_start: '2026-W45', reviews: 8, avg_score: 7.6, high_scores: 3, assigned: 5, completed: 4 },
    ],
    breakdown: {
      by_status: [{ key: 'open', count: 3 }],
      by_reviewer: [{ reviewer: 'alice', assigned: 4, completed: 3 }],
      by_project: [],
    },
    recent: [
      {
        project_key: 'CORE',
        repository_slug: 'app',
        pull_request_id: '42',
        pull_request_commit_id: 'c1',
        status: 'open',
        avg_score: 8.2,
        created_date: '2026-11-15T09:00:00',
      },
    ],
    ...overrides,
  }
}

async function mountView() {
  api.getAllProjects.mockResolvedValue([
    { project_key: 'CORE', project_name: 'Core' },
  ])
  api.getProjectRepositories.mockResolvedValue([
    { repository_slug: 'app', repository_name: 'App' },
  ])

  const { default: RepositoryInsightsView } = await import(
    '@/views/insights/RepositoryInsightsView.vue'
  )
  const i18n = createI18n({ legacy: false, locale: 'en', messages: { en: enMessages } })
  const wrapper = mount(RepositoryInsightsView, {
    global: {
      plugins: [ElementPlus, i18n],
      stubs: { MultiLineChart: true, LineChart: true, PieChart: true, BarChart: true },
    },
  })
  mountedWrappers.push(wrapper)
  await flushPromises()
  return wrapper
}

/** Pick a scope the way the picker does. */
async function pick(wrapper: any, projectKey: string, repositorySlug = '') {
  const picker = wrapper.findComponent({ name: 'RepositoryScopePicker' })
  picker.vm.$emit('update:modelValue', { projectKey, repositorySlug })
  await flushPromises()
}

describe('RepositoryInsightsView', () => {
  beforeEach(() => {
    api.getRepositoryInsights.mockReset()
    api.getAllProjects.mockReset()
    api.getProjectRepositories.mockReset()
    api.getRepositoryInsights.mockResolvedValue(reading())
  })

  afterEach(() => {
    mountedWrappers.splice(0).forEach((wrapper) => wrapper.unmount())
    vi.useRealTimers()
  })

  it('asks for a project before reading anything', async () => {
    const wrapper = await mountView()

    expect(wrapper.find('[data-test="insights-no-scope"]').exists()).toBe(true)
    expect(api.getRepositoryInsights).not.toHaveBeenCalled()
  })

  it('reads the project as a whole when no repository is picked', async () => {
    const wrapper = await mountView()
    await pick(wrapper, 'CORE')

    expect(api.getRepositoryInsights).toHaveBeenCalledWith({
      project_key: 'CORE',
      repository_slug: undefined,
      days: 30,
      period: 'weekly',
    })
    expect(wrapper.find('[data-test="insights-kpi-reviews_total"]').text()).toBe('12')
    expect(wrapper.find('[data-test="insights-kpi-unassigned"]').text()).toBe('4')
    expect(wrapper.find('[data-test="insights-recent"]').text()).toContain('#42')
  })

  it('drills into one repository when one is picked', async () => {
    const wrapper = await mountView()
    await pick(wrapper, 'CORE', 'app')

    expect(api.getRepositoryInsights).toHaveBeenCalledWith({
      project_key: 'CORE',
      repository_slug: 'app',
      days: 30,
      period: 'weekly',
    })
  })

  it('polls while the page is on screen', async () => {
    vi.useFakeTimers()
    const wrapper = await mountView()
    await pick(wrapper, 'CORE')
    expect(api.getRepositoryInsights).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(30_000)

    expect(api.getRepositoryInsights).toHaveBeenCalledTimes(2)
    wrapper.unmount()
  })

  it('refreshes at once when a review lands in the scope on screen', async () => {
    vi.useFakeTimers()
    const wrapper = await mountView()
    await pick(wrapper, 'CORE')
    expect(api.getRepositoryInsights).toHaveBeenCalledTimes(1)

    sse.listeners.forEach((listener) =>
      listener({
        review_id: 1,
        project_key: 'CORE',
        repository_slug: 'app',
        pull_request_id: '9',
        created_date: '2026-11-16T10:00:00',
      }),
    )
    await vi.advanceTimersByTimeAsync(300)

    expect(api.getRepositoryInsights).toHaveBeenCalledTimes(2)
    wrapper.unmount()
  })

  it('ignores a review from outside the scope, and a burst collapses into one read', async () => {
    vi.useFakeTimers()
    const wrapper = await mountView()
    await pick(wrapper, 'CORE', 'app')
    expect(api.getRepositoryInsights).toHaveBeenCalledTimes(1)

    const send = (project: string, repository: string) =>
      sse.listeners.forEach((listener) =>
        listener({
          review_id: 1,
          project_key: project,
          repository_slug: repository,
          pull_request_id: '9',
          created_date: '2026-11-16T10:00:00',
        }),
      )

    send('CORE', 'api') // another repository of the same project
    send('PAY', 'app') // another project entirely
    await vi.advanceTimersByTimeAsync(300)
    expect(api.getRepositoryInsights).toHaveBeenCalledTimes(1)

    send('CORE', 'app')
    send('CORE', 'app')
    send('CORE', 'app')
    await vi.advanceTimersByTimeAsync(300)

    expect(api.getRepositoryInsights).toHaveBeenCalledTimes(2)
    wrapper.unmount()
  })

  it('says a scope with nothing in it is empty rather than silently zero', async () => {
    api.getRepositoryInsights.mockResolvedValue(
      reading({
        kpis: {
          reviews_total: 0,
          reviews_open: 0,
          reviews_today: 0,
          avg_score: 0,
          good_suggestion_rate: 0,
          assigned_pending: 0,
          assigned_in_progress: 0,
          unassigned_count: 0,
          active_reviewers: 0,
        },
        trends: [],
        breakdown: { by_status: [], by_reviewer: [], by_project: [] },
        recent: [],
      }),
    )
    const wrapper = await mountView()
    await pick(wrapper, 'CORE')

    const hint = wrapper.find('[data-test="insights-scope-empty"]')
    expect(hint.exists()).toBe(true)
    expect(hint.text()).toContain('no grant')
  })

  it('stops watching the stream once the page is gone', async () => {
    const wrapper = await mountView()
    await pick(wrapper, 'CORE')
    expect(sse.listeners.size).toBe(1)

    wrapper.unmount()

    expect(sse.listeners.size).toBe(0)
  })

  it('keeps the last reading when a poll fails', async () => {
    const wrapper = await mountView()
    await pick(wrapper, 'CORE')
    expect(wrapper.find('[data-test="insights-kpi-reviews_total"]').text()).toBe('12')

    api.getRepositoryInsights.mockRejectedValueOnce(new Error('offline'))
    await wrapper.find('[data-test="insights-refresh"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-test="insights-kpi-reviews_total"]').text()).toBe('12')
  })
})
