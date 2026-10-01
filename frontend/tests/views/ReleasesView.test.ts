import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import ElementPlus from 'element-plus'
import { createI18n } from 'vue-i18n'
import { createMemoryHistory, createRouter } from 'vue-router'
import type { Router } from 'vue-router'
import ReleasesView from '@/views/releases/ReleasesView.vue'
import { projectsApi } from '@/api/projects'
import type { RepositorySummary } from '@/api/projects'
import { releaseDiffApi } from '@/api/releaseDiff'
import type { ReleaseCompareResponse } from '@/api/releaseDiff'
import {
  buildReleaseReportHtml,
  downloadReleaseReport,
  releaseReportFilename,
} from '@/utils/export/releaseReport'
import {
  canShareImage,
  captureElementToPng,
  copyPngToClipboard,
  downloadDataUrl,
  sharePng,
} from '@/utils/screenshot'
import enMessages from '@/locales/en.json'

vi.mock('@/api/projects', () => ({
  projectsApi: {
    getAllProjects: vi.fn(),
    getProjectRepositories: vi.fn(),
    getCloudWorkspaces: vi.fn(),
  },
}))

vi.mock('@/api/releaseDiff', () => ({
  releaseDiffApi: {
    compare: vi.fn(),
    check: vi.fn(),
    listRefs: vi.fn(),
  },
}))

// JIRA ticket links are driven by these settings (no JIRA configured here)
vi.mock('@/api/rbac', () => ({
  rbacApi: {
    getJiraSettings: vi.fn().mockResolvedValue({ base_url: '', project_keys: [] }),
  },
}))

vi.mock('@/utils/export/releaseReport', () => ({
  buildReleaseReportHtml: vi.fn(() => '<html>report</html>'),
  downloadReleaseReport: vi.fn(),
  releaseReportFilename: vi.fn(() => 'release-report.html'),
}))

vi.mock('@/utils/screenshot', () => ({
  canShareImage: vi.fn(() => false),
  captureElementToPng: vi.fn(async () => 'data:image/png;base64,AAA'),
  copyPngToClipboard: vi.fn(async () => undefined),
  downloadDataUrl: vi.fn(),
  screenshotFilename: vi.fn((prefix: string) => `${prefix}.png`),
  sharePng: vi.fn(async () => true),
}))

const PROJECTS = [
  {
    id: 1,
    project_id: 101,
    project_name: 'Alpha Platform',
    project_key: 'ALPHA',
    project_url: 'http://git.local/projects/ALPHA',
    git_provider: 'bitbucket_server',
    created_date: '2024-01-01T00:00:00',
    updated_date: '2024-01-01T00:00:00',
  },
  {
    id: 2,
    project_id: 102,
    project_name: 'Beta Service',
    project_key: 'BETA',
    project_url: 'http://git.local/projects/BETA',
    git_provider: 'github_enterprise',
    created_date: '2024-01-02T00:00:00',
    updated_date: '2024-01-02T00:00:00',
  },
]

const REPOSITORIES_BY_PROJECT: Record<string, RepositorySummary[]> = {
  ALPHA: [
    {
      id: 11,
      repository_id: 1001,
      repository_name: 'Alpha API',
      repository_slug: 'alpha-api',
      repository_url: 'http://git.local/projects/ALPHA/repos/alpha-api',
      project_id: 101,
      created_date: '2024-01-01T00:00:00',
      updated_date: '2024-01-01T00:00:00',
    },
    {
      id: 12,
      repository_id: 1002,
      repository_name: 'Alpha Web',
      repository_slug: 'alpha-web',
      repository_url: 'http://git.local/projects/ALPHA/repos/alpha-web',
      project_id: 101,
      created_date: '2024-01-01T00:00:00',
      updated_date: '2024-01-01T00:00:00',
    },
  ],
  BETA: [
    {
      id: 21,
      repository_id: 2001,
      repository_name: 'Beta Worker',
      repository_slug: 'beta-worker',
      repository_url: 'http://git.local/projects/BETA/repos/beta-worker',
      project_id: 102,
      created_date: '2024-01-02T00:00:00',
      updated_date: '2024-01-02T00:00:00',
    },
  ],
}

const REFS = {
  project_key: 'ALPHA',
  repository_slug: 'alpha-api',
  git_provider: 'bitbucket_server',
  tags: ['v1.0.0', 'v1.1.0'],
  branches: ['main', 'release/1.0'],
}

const CLOUD_PROJECT = {
  id: 3,
  project_id: 103,
  project_name: 'AI',
  project_key: 'AI',
  project_url: 'https://bitbucket.org/aaronpliu',
  git_provider: 'bitbucket_cloud',
  created_date: '2024-01-03T00:00:00',
  updated_date: '2024-01-03T00:00:00',
}

const BASE_REF_PLACEHOLDER = enMessages.releaseDiff.base_ref_placeholder
const WORKSPACE_PLACEHOLDER = enMessages.releaseDiff.workspace_slug_placeholder

/* eslint-disable @typescript-eslint/no-explicit-any */
type AnyWrapper = any

function inputsByPlaceholder(wrapper: AnyWrapper, placeholder: string) {
  return wrapper
    .findAllComponents({ name: 'ElAutocomplete' })
    .filter((input: AnyWrapper) => input.props('placeholder') === placeholder)
}

/**
 * The comparison card labels its refs as source / target (one vocabulary for the
 * merged tool); the commit check card keeps the generic ref placeholder.
 */
function compareRefInputs(wrapper: AnyWrapper) {
  return [
    ...inputsByPlaceholder(wrapper, enMessages.releaseDiff.missing_source_placeholder),
    ...inputsByPlaceholder(wrapper, enMessages.releaseDiff.missing_target_placeholder),
  ]
}

function workspaceSelect(wrapper: AnyWrapper) {
  return wrapper
    .findAllComponents({ name: 'ElSelect' })
    .find((select: AnyWrapper) => select.props('placeholder') === WORKSPACE_PLACEHOLDER)
}

// Mounting this view is heavy: unmount every wrapper so the DOM of previous
// tests does not pile up and slow the whole file down.
const mountedWrappers: AnyWrapper[] = []

afterEach(() => {
  mountedWrappers.splice(0).forEach((wrapper) => wrapper.unmount())
})

// The merge check keeps its selection in the URL, so the view needs a router
let testRouter: Router | null = null

function mountView() {
  const i18n = createI18n({
    legacy: false,
    locale: 'en',
    messages: { en: enMessages },
  })
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', component: { template: '<div />' } }],
  })
  testRouter = router

  const wrapper = mount(ReleasesView, {
    global: {
      plugins: [ElementPlus, i18n, router],
    },
  })
  mountedWrappers.push(wrapper)
  return wrapper
}

describe('ReleasesView', () => {
  beforeEach(() => {
    vi.mocked(projectsApi.getAllProjects).mockReset()
    vi.mocked(projectsApi.getProjectRepositories).mockReset()
    vi.mocked(projectsApi.getCloudWorkspaces).mockReset()
    vi.mocked(releaseDiffApi.listRefs).mockReset()
    vi.mocked(releaseDiffApi.compare).mockReset()
    vi.mocked(releaseDiffApi.check).mockReset()
    vi.mocked(buildReleaseReportHtml).mockClear()
    vi.mocked(downloadReleaseReport).mockClear()
    vi.mocked(releaseReportFilename).mockClear()
    vi.mocked(releaseReportFilename).mockReturnValue('release-report.html')
    vi.mocked(canShareImage).mockReset()
    vi.mocked(canShareImage).mockReturnValue(false)
    vi.mocked(captureElementToPng).mockClear()
    vi.mocked(captureElementToPng).mockResolvedValue('data:image/png;base64,AAA')
    vi.mocked(copyPngToClipboard).mockClear()
    vi.mocked(copyPngToClipboard).mockResolvedValue(undefined)
    vi.mocked(downloadDataUrl).mockClear()
    vi.mocked(sharePng).mockClear()
    vi.mocked(sharePng).mockResolvedValue(true)
    vi.mocked(projectsApi.getCloudWorkspaces).mockResolvedValue([])
    vi.mocked(releaseDiffApi.listRefs).mockResolvedValue(REFS)
    vi.mocked(projectsApi.getAllProjects).mockResolvedValue(PROJECTS)
    vi.mocked(projectsApi.getProjectRepositories).mockImplementation((projectKey: string) =>
      Promise.resolve(REPOSITORIES_BY_PROJECT[projectKey] ?? []),
    )
  })

  it('opens with the coordinate panel shown and folds it away on demand', async () => {
    const wrapper = mountView()
    await flushPromises()

    const toggle = wrapper.find('[data-test="coordinates-toggle"]')
    const panel = wrapper.find('.context-card .panel-body')

    // the panel a first visit fills in is open on arrival
    expect(toggle.attributes('aria-expanded')).toBe('true')
    expect(panel.classes()).not.toContain('is-collapsed')

    await toggle.trigger('click')

    expect(toggle.attributes('aria-expanded')).toBe('false')
    expect(toggle.classes()).toContain('is-collapsed')
    // folded away rather than unmounted, so what was picked is still there
    expect(panel.classes()).toContain('is-collapsed')
    expect(panel.find('.repo-form').exists()).toBe(true)

    await toggle.trigger('click')

    expect(toggle.attributes('aria-expanded')).toBe('true')
    expect(panel.classes()).not.toContain('is-collapsed')
  })

  it('populates the project key dropdown from the projects API', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(projectsApi.getAllProjects).toHaveBeenCalledTimes(1)

    const projectOptions = wrapper
      .findAllComponents({ name: 'ElSelect' })[0]
      .findAllComponents({ name: 'ElOption' })
    expect(projectOptions).toHaveLength(2)
    expect(projectOptions[0].props('value')).toBe('ALPHA')
    expect(projectOptions[1].props('value')).toBe('BETA')
  })

  it('shows the project key only once when the project name equals the key', async () => {
    vi.mocked(projectsApi.getAllProjects).mockResolvedValue([
      {
        ...PROJECTS[0],
        project_key: 'FOO',
        project_name: 'FOO',
      },
    ])

    const wrapper = mountView()
    await flushPromises()

    const option = wrapper
      .findAllComponents({ name: 'ElSelect' })[0]
      .findAllComponents({ name: 'ElOption' })[0]

    expect(option.props('label')).toBe('FOO')
    expect(option.text()).toBe('FOO')
  })

  it('does not repeat the project key as name when they only differ in case', async () => {
    vi.mocked(projectsApi.getAllProjects).mockResolvedValue([
      {
        ...PROJECTS[0],
        project_key: 'ai',
        project_name: 'AI',
      },
    ])

    const wrapper = mountView()
    await flushPromises()

    const option = wrapper
      .findAllComponents({ name: 'ElSelect' })[0]
      .findAllComponents({ name: 'ElOption' })[0]

    expect(option.props('label')).toBe('ai')
    expect(option.text()).toBe('ai')
  })

  it('shows the project name as secondary text when it differs from the key', async () => {
    const wrapper = mountView()
    await flushPromises()

    const option = wrapper
      .findAllComponents({ name: 'ElSelect' })[0]
      .findAllComponents({ name: 'ElOption' })[0]

    expect(option.props('label')).toBe('ALPHA')
    expect(option.text()).toContain('ALPHA')
    expect(option.text()).toContain('Alpha Platform')
  })

  it('keeps the repository dropdown disabled until a project is selected', async () => {
    const wrapper = mountView()
    await flushPromises()

    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    expect(selects[1].props('disabled')).toBe(true)

    await selects[0].vm.$emit('update:modelValue', 'ALPHA')
    await flushPromises()

    expect(selects[1].props('disabled')).toBe(false)
  })

  it('loads repositories of the selected project and fills them into the dropdown', async () => {
    const wrapper = mountView()
    await flushPromises()

    await wrapper.findAllComponents({ name: 'ElSelect' })[0].vm.$emit('update:modelValue', 'BETA')
    await flushPromises()

    expect(projectsApi.getProjectRepositories).toHaveBeenCalledWith('BETA')

    const repositoryOptions = wrapper
      .findAllComponents({ name: 'ElSelect' })[1]
      .findAllComponents({ name: 'ElOption' })
    expect(repositoryOptions).toHaveLength(1)
    expect(repositoryOptions[0].props('value')).toBe('beta-worker')
  })

  it('resets the repository and reloads when the project changes', async () => {
    const wrapper = mountView()
    await flushPromises()

    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    await selects[0].vm.$emit('update:modelValue', 'ALPHA')
    await flushPromises()
    await selects[1].vm.$emit('update:modelValue', 'alpha-api')
    await flushPromises()

    expect(selects[1].props('modelValue')).toBe('alpha-api')

    await selects[0].vm.$emit('update:modelValue', 'BETA')
    await flushPromises()

    expect(projectsApi.getProjectRepositories).toHaveBeenLastCalledWith('BETA')
    expect(selects[1].props('modelValue')).toBe('')
  })

  it('auto selects the git provider of the chosen project', async () => {
    const wrapper = mountView()
    await flushPromises()

    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    await selects[0].vm.$emit('update:modelValue', 'BETA')
    await flushPromises()

    expect(selects[2].props('modelValue')).toBe('github_enterprise')
  })





  it('shows both tools at once instead of hiding them behind tabs', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.findAllComponents({ name: 'ElTabs' })).toHaveLength(0)

    const text = wrapper.text()
    expect(text).toContain(enMessages.releaseDiff.tab_compare)
    expect(text).toContain(enMessages.releaseDiff.tab_check)
    expect(text).toContain(enMessages.releaseDiff.compare_help)
    expect(text).toContain(enMessages.releaseDiff.check_help)
  })

  it('lays the release diff and the commit check out in two columns', async () => {
    const wrapper = mountView()
    await flushPromises()

    const columns = wrapper.findAll('.tool-sections > .el-col')
    expect(columns).toHaveLength(2)
    expect(columns[0].text()).toContain(enMessages.releaseDiff.tab_compare)
    expect(columns[1].text()).toContain(enMessages.releaseDiff.tab_check)
    // half width on large screens, stacked on small ones
    expect(columns[0].classes()).toContain('el-col-lg-12')
    expect(columns[0].classes()).toContain('el-col-24')
    expect(columns[1].classes()).toContain('el-col-lg-12')
  })

  it('sends the missing SHAs of a comparison to the commit check', async () => {
    vi.mocked(releaseDiffApi.compare).mockResolvedValue({
      project_key: 'ALPHA',
      repository_slug: 'alpha-api',
      git_provider: 'bitbucket_server',
      source_ref: 'v1.2.0',
      target_ref: 'v1.3.0',
      verdict: 'missing',
      scan_complete: true,
      scan_limit: 2000,
      filtered_by_baseline_count: 0,
      narrowed: false,
      missing_count: 2,
      missing_commits: [
        { id: 'aaa1111', display_id: 'aaa111' },
        { id: 'bbb2222', display_id: 'bbb222' },
      ],
      added_count: 0,
      added_commits: [],
      added_complete: true,
      rendered_truncated: false,
    })

    const wrapper = mountView()
    await flushPromises()

    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    await selects[0].vm.$emit('update:modelValue', 'ALPHA')
    await flushPromises()
    await selects[1].vm.$emit('update:modelValue', 'alpha-api')
    await flushPromises()

    const releaseInputs = compareRefInputs(wrapper)
    await releaseInputs[0].find('input').setValue('v1.2.0')
    await releaseInputs[1].find('input').setValue('v1.3.0')

    const compareButton = wrapper
      .findAll('button')
      .find((button) => button.text() === enMessages.releaseDiff.run_compare)
    await compareButton!.trigger('click')
    await flushPromises()

    const handoff = wrapper
      .findAll('button')
      .find((button) => button.text().includes(enMessages.releaseDiff.handoff_to_check))
    expect(handoff).toBeDefined()
    // the strip leads with the number of missing shas
    expect(handoff!.text()).toContain('2')

    // the delivery must never move the page: the token and the tint on the strip
    // are the whole story
    const textarea = wrapper.find('textarea').element as HTMLTextAreaElement
    vi.spyOn(textarea, 'getBoundingClientRect').mockReturnValue({
      top: 400,
      left: 700,
      bottom: 580,
      right: 1200,
      width: 500,
      height: 180,
      x: 700,
      y: 400,
      toJSON: () => ({}),
    } as DOMRect)
    const scrollIntoView = vi.fn()
    Object.defineProperty(textarea, 'scrollIntoView', { value: scrollIntoView })

    await handoff!.trigger('click')
    await flushPromises()

    expect(textarea.value).toBe('aaa1111\nbbb2222')
    // the strip answers where it was clicked instead of lighting up a distant card
    expect(wrapper.find('.result-handoff.is-delivered').exists()).toBe(true)
    expect(scrollIntoView).not.toHaveBeenCalled()
  })

  it('resets a tool without touching the shared repository context', async () => {
    const wrapper = mountView()
    await flushPromises()

    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    await selects[0].vm.$emit('update:modelValue', 'ALPHA')
    await flushPromises()
    await selects[1].vm.$emit('update:modelValue', 'alpha-api')
    await flushPromises()

    const releaseInputs = compareRefInputs(wrapper)
    await releaseInputs[0].find('input').setValue('v1.2.0')
    await releaseInputs[1].find('input').setValue('v1.3.0')

    const resetButtons = wrapper
      .findAll('button')
      .filter((button) => button.text() === enMessages.releaseDiff.reset)
    expect(resetButtons).toHaveLength(2)

    await resetButtons[0].trigger('click')
    await flushPromises()

    expect(
      (compareRefInputs(wrapper)[0].find('input').element as HTMLInputElement)
        .value,
    ).toBe('')
    expect(selects[1].props('modelValue')).toBe('alpha-api')
  })

  it('loads tag and branch suggestions of the selected repository', async () => {
    const wrapper = mountView()
    await flushPromises()

    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    await selects[0].vm.$emit('update:modelValue', 'ALPHA')
    await flushPromises()
    await selects[1].vm.$emit('update:modelValue', 'alpha-api')
    await flushPromises()

    const refreshButton = wrapper
      .findAll('button')
      .find((button) => button.text() === enMessages.releaseDiff.refresh_refs)
    await refreshButton!.trigger('click')
    await flushPromises()

    expect(releaseDiffApi.listRefs).toHaveBeenCalledWith(
      expect.objectContaining({ project_key: 'ALPHA', repository_slug: 'alpha-api' }),
    )
    expect(wrapper.text()).toContain('2 tag(s) / 2 branch(es) loaded')
  })

  it('refreshes the ref suggestions through the provider, bypassing the cache', async () => {
    const wrapper = mountView()
    await flushPromises()

    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    await selects[0].vm.$emit('update:modelValue', 'ALPHA')
    await flushPromises()
    await selects[1].vm.$emit('update:modelValue', 'alpha-api')
    await flushPromises()
    // the coordinate watcher loads the ref suggestions on the next tick
    await nextTick()

    // the automatic load may use the backend cache
    expect(releaseDiffApi.listRefs).toHaveBeenLastCalledWith(
      expect.objectContaining({ refresh: false }),
    )

    const refreshButton = wrapper
      .findAll('button')
      .find((button) => button.text() === enMessages.releaseDiff.refresh_refs)
    await refreshButton!.trigger('click')
    await flushPromises()

    // the Refresh action asks the backend to read through to Bitbucket (a debounced
    // automatic load may follow it, so match any cache-bypassing call)
    expect(releaseDiffApi.listRefs).toHaveBeenCalledWith(
      expect.objectContaining({ refresh: true }),
    )
    expect(wrapper.text()).toContain(
      enMessages.releaseDiff.refs_fetched_at.replace('{time}', ''),
    )
  })

  it('suggests the loaded refs and still accepts a manually typed ref', async () => {
    vi.mocked(releaseDiffApi.compare).mockResolvedValue({
      project_key: 'ALPHA',
      repository_slug: 'alpha-api',
      git_provider: 'bitbucket_server',
      source_ref: 'deadbeef',
      target_ref: 'v1.1.0',
      verdict: 'contained',
      scan_complete: true,
      scan_limit: 2000,
      filtered_by_baseline_count: 0,
      narrowed: false,
      missing_count: 0,
      missing_commits: [],
      added_count: 0,
      added_commits: [],
      added_complete: true,
      rendered_truncated: false,
    })

    const wrapper = mountView()
    await flushPromises()

    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    await selects[0].vm.$emit('update:modelValue', 'ALPHA')
    await flushPromises()
    await selects[1].vm.$emit('update:modelValue', 'alpha-api')
    await flushPromises()

    const refreshButton = wrapper
      .findAll('button')
      .find((button) => button.text() === enMessages.releaseDiff.refresh_refs)
    await refreshButton!.trigger('click')
    await flushPromises()

    const releaseFields = compareRefInputs(wrapper)
    const fetchSuggestions = releaseFields[0].props('fetchSuggestions') as (
      query: string,
      cb: (items: { value: string }[]) => void,
    ) => void
    const suggestions: { value: string }[] = []
    fetchSuggestions('v1.1', (items) => suggestions.push(...items))
    expect(suggestions.map((item) => item.value)).toEqual(['v1.1.0'])

    await releaseFields[0].find('input').setValue('deadbeef')
    await releaseFields[1].find('input').setValue('v1.1.0')

    const compareButton = wrapper
      .findAll('button')
      .find((button) => button.text() === enMessages.releaseDiff.run_compare)
    await compareButton!.trigger('click')
    await flushPromises()

    expect(releaseDiffApi.compare).toHaveBeenCalledWith(
      expect.objectContaining({ source_ref: 'deadbeef', target_ref: 'v1.1.0' }),
    )
  })

  it('hides the Cloud workspace field for non-Cloud providers', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(workspaceSelect(wrapper)).toBeUndefined()

    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    await selects[0].vm.$emit('update:modelValue', 'ALPHA')
    await flushPromises()

    expect(workspaceSelect(wrapper)).toBeUndefined()
  })

  it('offers the Cloud workspaces and pre-selects a single suggestion', async () => {
    vi.mocked(projectsApi.getAllProjects).mockResolvedValue([CLOUD_PROJECT])
    vi.mocked(projectsApi.getCloudWorkspaces).mockResolvedValue([
      { slug: 'aaronpliu', name: 'Aaron Liu', source: 'database' },
    ])
    vi.mocked(releaseDiffApi.compare).mockResolvedValue({
      project_key: 'AI',
      repository_slug: 'pylang',
      git_provider: 'bitbucket_cloud',
      source_ref: 'v1.0.0',
      target_ref: 'v1.1.0',
      verdict: 'contained',
      scan_complete: true,
      scan_limit: 2000,
      filtered_by_baseline_count: 0,
      narrowed: false,
      missing_count: 0,
      missing_commits: [],
      added_count: 0,
      added_commits: [],
      added_complete: true,
      rendered_truncated: false,
    })

    const wrapper = mountView()
    await flushPromises()

    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    await selects[0].vm.$emit('update:modelValue', 'AI')
    await flushPromises()
    await selects[1].vm.$emit('update:modelValue', 'pylang')
    await flushPromises()

    expect(projectsApi.getCloudWorkspaces).toHaveBeenCalledTimes(1)

    const select = workspaceSelect(wrapper)
    expect(select).toBeDefined()
    // the only known workspace is offered and applied automatically
    expect(select.props('modelValue')).toBe('aaronpliu')
    expect(
      select.findAllComponents({ name: 'ElOption' }).map((option: AnyWrapper) => option.props('value')),
    ).toEqual(['aaronpliu'])

    const releaseInputs = compareRefInputs(wrapper)
    await releaseInputs[0].find('input').setValue('v1.0.0')
    await releaseInputs[1].find('input').setValue('v1.1.0')

    const compareButton = wrapper
      .findAll('button')
      .find((button) => button.text() === enMessages.releaseDiff.run_compare)
    await compareButton!.trigger('click')
    await flushPromises()

    expect(releaseDiffApi.compare).toHaveBeenCalledWith(
      expect.objectContaining({
        project_key: 'AI',
        repository_slug: 'pylang',
        git_provider: 'bitbucket_cloud',
        workspace_slug: 'aaronpliu',
      }),
    )
  })

  it('keeps an arbitrary Cloud workspace typeable when nothing matches', async () => {
    vi.mocked(projectsApi.getAllProjects).mockResolvedValue([CLOUD_PROJECT])
    vi.mocked(releaseDiffApi.listRefs).mockResolvedValue({
      ...REFS,
      project_key: 'AI',
      repository_slug: 'pylang',
      git_provider: 'bitbucket_cloud',
    })

    const wrapper = mountView()
    await flushPromises()

    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    await selects[0].vm.$emit('update:modelValue', 'AI')
    await flushPromises()
    await selects[1].vm.$emit('update:modelValue', 'pylang')
    await flushPromises()

    const select = workspaceSelect(wrapper)
    expect(select.props('allowCreate')).toBe(true)
    expect(select.props('filterable')).toBe(true)
    // no suggestion available -> nothing is forced into the field
    expect(select.props('modelValue')).toBe('')

    await select.vm.$emit('update:modelValue', 'typo-workspace')
    await flushPromises()

    const refreshButton = wrapper
      .findAll('button')
      .find((button) => button.text() === enMessages.releaseDiff.refresh_refs)
    await refreshButton!.trigger('click')
    await flushPromises()

    expect(releaseDiffApi.listRefs).toHaveBeenCalledWith(
      expect.objectContaining({ workspace_slug: 'typo-workspace' }),
    )
  })

  it('loads the Cloud workspaces when the provider is picked by hand', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(projectsApi.getCloudWorkspaces).not.toHaveBeenCalled()

    const providerSelect = wrapper
      .findAllComponents({ name: 'ElSelect' })
      .find((select: AnyWrapper) => select.props('placeholder') === enMessages.releaseDiff.git_provider_placeholder)
    await providerSelect!.vm.$emit('update:modelValue', 'bitbucket_cloud')
    await flushPromises()

    expect(projectsApi.getCloudWorkspaces).toHaveBeenCalledTimes(1)
    expect(workspaceSelect(wrapper)).toBeDefined()
  })

  it('sends the Cloud workspace along with the business project key', async () => {
    vi.mocked(projectsApi.getAllProjects).mockResolvedValue([CLOUD_PROJECT])
    vi.mocked(releaseDiffApi.compare).mockResolvedValue({
      project_key: 'AI',
      repository_slug: 'pylang',
      git_provider: 'bitbucket_cloud',
      source_ref: 'v1.0.0',
      target_ref: 'v1.1.0',
      verdict: 'contained',
      scan_complete: true,
      scan_limit: 2000,
      filtered_by_baseline_count: 0,
      narrowed: false,
      missing_count: 0,
      missing_commits: [],
      added_count: 0,
      added_commits: [],
      added_complete: true,
      rendered_truncated: false,
    })

    const wrapper = mountView()
    await flushPromises()

    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    await selects[0].vm.$emit('update:modelValue', 'AI')
    await flushPromises()
    await selects[1].vm.$emit('update:modelValue', 'pylang')
    await flushPromises()

    expect(selects[2].props('modelValue')).toBe('bitbucket_cloud')

    const cloudWorkspaceSelect = workspaceSelect(wrapper)
    expect(cloudWorkspaceSelect).toBeDefined()
    await cloudWorkspaceSelect.vm.$emit('update:modelValue', 'aaronpliu')
    await flushPromises()

    const releaseInputs = compareRefInputs(wrapper)
    await releaseInputs[0].find('input').setValue('v1.0.0')
    await releaseInputs[1].find('input').setValue('v1.1.0')

    const compareButton = wrapper
      .findAll('button')
      .find((button) => button.text() === enMessages.releaseDiff.run_compare)
    await compareButton!.trigger('click')
    await flushPromises()

    expect(releaseDiffApi.compare).toHaveBeenCalledWith(
      expect.objectContaining({
        project_key: 'AI',
        repository_slug: 'pylang',
        git_provider: 'bitbucket_cloud',
        workspace_slug: 'aaronpliu',
      }),
    )
  }, 30000)
})

describe('ReleasesView reports and screenshots', () => {
  const COMPARE_RESULT: ReleaseCompareResponse = {
    project_key: 'ALPHA',
    repository_slug: 'alpha-api',
    git_provider: 'bitbucket_server',
    source_ref: 'v1.2.0',
    target_ref: 'v1.3.0',
    baseline_ref: null,
    narrowed: false,
    verdict: 'missing',
    scan_complete: true,
    scan_limit: 2000,
    filtered_by_baseline_count: 0,
    missing_count: 1,
    missing_commits: [{ id: 'aaa1111', display_id: 'aaa111' }],
    added_count: 0,
    added_commits: [],
    added_complete: true,
    rendered_truncated: false,
  }

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(projectsApi.getAllProjects).mockResolvedValue(PROJECTS)
    vi.mocked(projectsApi.getProjectRepositories).mockImplementation((projectKey: string) =>
      Promise.resolve(REPOSITORIES_BY_PROJECT[projectKey] ?? []),
    )
    vi.mocked(releaseDiffApi.listRefs).mockResolvedValue(REFS)
    vi.mocked(canShareImage).mockReturnValue(false)
    vi.mocked(captureElementToPng).mockResolvedValue('data:image/png;base64,AAA')
    vi.mocked(copyPngToClipboard).mockResolvedValue(undefined)
    vi.mocked(sharePng).mockResolvedValue(true)
    vi.mocked(buildReleaseReportHtml).mockReturnValue('<html>report</html>')
    vi.mocked(releaseReportFilename).mockReturnValue('release-report.html')
  })

  async function mountWithCompareResult(
    response: ReleaseCompareResponse = COMPARE_RESULT as ReleaseCompareResponse,
  ) {
    vi.mocked(releaseDiffApi.compare).mockResolvedValue(response)

    const wrapper = mountView()
    await flushPromises()

    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    await selects[0].vm.$emit('update:modelValue', 'ALPHA')
    await flushPromises()
    await selects[1].vm.$emit('update:modelValue', 'alpha-api')
    await flushPromises()

    const releaseInputs = compareRefInputs(wrapper)
    await releaseInputs[0].find('input').setValue('v1.2.0')
    await releaseInputs[1].find('input').setValue('v1.3.0')

    const compareButton = wrapper
      .findAll('button')
      .find((button) => button.text() === enMessages.releaseDiff.run_compare)
    await compareButton!.trigger('click')
    await flushPromises()

    return wrapper
  }

  function buttonsByLabel(wrapper: AnyWrapper, label: string) {
    return wrapper.findAll('button').filter((button: AnyWrapper) => button.text() === label)
  }

  it('offers report actions for the comparison result', async () => {
    const wrapper = await mountWithCompareResult()

    // one per tool that has a result, plus the shared pair in the context card header
    expect(buttonsByLabel(wrapper, enMessages.releaseDiff.report_export_html)).toHaveLength(1)
    expect(buttonsByLabel(wrapper, enMessages.releaseDiff.screenshot)).toHaveLength(1)
    expect(buttonsByLabel(wrapper, enMessages.releaseDiff.report_export_both)).toHaveLength(1)
    expect(buttonsByLabel(wrapper, enMessages.releaseDiff.screenshot_both)).toHaveLength(1)
    // the shared pair rides in the context card header, beside the fold toggle
    const headerActions = wrapper.find('.card-header-actions')
    expect(headerActions.exists()).toBe(true)
    expect(
      headerActions.findAll('button').map((button: AnyWrapper) => button.text()),
    ).toEqual(
      expect.arrayContaining([
        enMessages.releaseDiff.report_export_both,
        enMessages.releaseDiff.screenshot_both,
      ]),
    )
  }, 30000)

  it('highlights missing release commits in red', async () => {
    const wrapper = await mountWithCompareResult()

    // status banner turns red instead of amber
    expect(wrapper.findComponent({ name: 'ElAlert' }).props('type')).toBe('error')
    // missing commits counter is red and visible even when the section is collapsed
    expect(wrapper.find('.collapse-title-missing').text()).toContain(
      enMessages.releaseDiff.missing_commits_title,
    )
    expect(wrapper.findAll('.el-tag--danger').length).toBeGreaterThan(0)
    // the handoff that forwards the missing shas leads with their number
    const handoff = wrapper.find('.result-handoff')
    expect(handoff.exists()).toBe(true)
    expect(handoff.text()).toContain(String(COMPARE_RESULT.missing_count))
    expect(handoff.text()).toContain(enMessages.releaseDiff.handoff_to_check)
  })

  it('keeps the handoff out when nothing is missing', async () => {
    const wrapper = await mountWithCompareResult({
      ...COMPARE_RESULT,
      verdict: 'contained',
      missing_count: 0,
      missing_commits: [],
    } as ReleaseCompareResponse)

    expect(wrapper.find('.result-handoff').exists()).toBe(false)
  })

  it('highlights missing commits in the check result', async () => {
    vi.mocked(releaseDiffApi.check).mockResolvedValue({
      project_key: 'ALPHA',
      repository_slug: 'alpha-api',
      git_provider: 'bitbucket_server',
      target_release_ref: 'v1.3.0',
      target_release_base_ref: null,
      all_included: false,
      summary: { requested: 2, included_count: 1, missing_count: 1, release_commit_count: 5 },
      results: [
        { commit: 'aaa1111', included: true, matched_id: 'aaa1111' },
        { commit: 'bbb2222', included: false },
      ],
      truncated: false,
    })

    const wrapper = await mountWithCompareResult()

    await wrapper.find('textarea').setValue('aaa1111\nbbb2222')
    // the check card keeps the generic ref placeholder
    const checkRef = inputsByPlaceholder(wrapper, enMessages.releaseDiff.ref_placeholder)[0]
    await checkRef.find('input').setValue('v1.3.0')

    const checkButton = wrapper
      .findAll('button')
      .find((button) => button.text() === enMessages.releaseDiff.run_check)
    await checkButton!.trigger('click')
    await flushPromises()

    // the check banner is red and missing rows get a red tint
    const errorAlert = wrapper
      .findAllComponents({ name: 'ElAlert' })
      .find(
        (alert: AnyWrapper) =>
          alert.props('type') === 'error' &&
          alert.text().includes(enMessages.releaseDiff.status_missing_in_release),
      )
    expect(errorAlert).toBeDefined()

    const resultsTable = wrapper
      .findAllComponents({ name: 'ElTable' })
      .find((table: AnyWrapper) =>
        (table.props('data') ?? []).some((row: AnyWrapper) => 'included' in row),
      )
    const rowClassName = resultsTable!.props('rowClassName')
    expect(rowClassName({ row: { included: false }, rowIndex: 0 })).toBe('row-missing')
    expect(rowClassName({ row: { included: true }, rowIndex: 1 })).toBe('')
  })

  it('marks rounded counts and a capped detail list, keeping the counts complete', async () => {
    const wrapper = await mountWithCompareResult({
      ...COMPARE_RESULT,
      missing_count: 250,
      missing_commits: [{ id: 'aaa1111', display_id: 'aaa111' }],
      rendered_truncated: true,
    })

    // the scan completed, so the count is exact; only the rendered list is capped
    expect(wrapper.text()).toContain('250')
    expect(wrapper.text()).toContain(
      enMessages.releaseDiff.missing_render_truncated
        .replace('{rendered}', '1')
        .replace('{count}', '250'),
    )
  })

  it('flags a lower bound when the missing direction could not be enumerated', async () => {
    const wrapper = await mountWithCompareResult({
      ...COMPARE_RESULT,
      verdict: 'inconclusive',
      scan_complete: false,
      scan_limit: 1,
      missing_count: 1,
    })

    expect(wrapper.text()).toContain('≥1')
    expect(wrapper.text()).toContain(
      enMessages.releaseDiff.inconclusive_help
        .replace('{limit}', '1')
        .replace('{count}', '1'),
    )
  })

  it('exports the comparison result as an HTML report', async () => {
    const wrapper = await mountWithCompareResult()

    await buttonsByLabel(wrapper, enMessages.releaseDiff.report_export_html)[0].trigger('click')
    await flushPromises()

    expect(buildReleaseReportHtml).toHaveBeenCalledWith(
      expect.objectContaining({
        context: expect.objectContaining({
          project_key: 'ALPHA',
          repository_slug: 'alpha-api',
          // urls of the selected coordinates are forwarded to the report
          project_url: 'http://git.local/projects/ALPHA',
          repository_url: 'http://git.local/projects/ALPHA/repos/alpha-api',
        }),
        compare: expect.objectContaining({ source_ref: 'v1.2.0' }),
        check: null,
      }),
    )
    expect(downloadReleaseReport).toHaveBeenCalledWith(
      '<html>report</html>',
      'release-report.html',
    )
  }, 30000)

  it('exports both tools into one report from the context card header', async () => {
    const wrapper = await mountWithCompareResult()

    await buttonsByLabel(wrapper, enMessages.releaseDiff.report_export_both)[0].trigger('click')
    await flushPromises()

    expect(buildReleaseReportHtml).toHaveBeenCalledWith(
      expect.objectContaining({
        compare: expect.objectContaining({ verdict: 'missing' }),
        check: null,
      }),
    )
    expect(downloadReleaseReport).toHaveBeenCalledTimes(1)
  }, 30000)

  it('does not export before a result exists', async () => {
    const wrapper = mountView()
    await flushPromises()

    const toolbarButtons = buttonsByLabel(wrapper, enMessages.releaseDiff.report_export_both)
    expect(toolbarButtons[0].attributes('disabled')).toBeDefined()
    expect(downloadReleaseReport).not.toHaveBeenCalled()
  })

  it('downloads a PNG screenshot of both columns', async () => {
    const wrapper = await mountWithCompareResult()

    // dropdown order: context card header, compare card, check card
    const dropdowns = wrapper.findAllComponents({ name: 'ElDropdown' })
    dropdowns[0].vm.$emit('command', 'download')
    await flushPromises()

    expect(captureElementToPng).toHaveBeenCalledTimes(1)
    expect(downloadDataUrl).toHaveBeenCalledWith('data:image/png;base64,AAA', 'release-report.png')
  }, 30000)

  it('copies the screenshot of a single tool to the clipboard', async () => {
    const wrapper = await mountWithCompareResult()

    const dropdowns = wrapper.findAllComponents({ name: 'ElDropdown' })
    dropdowns[1].vm.$emit('command', 'copy')
    await flushPromises()

    expect(copyPngToClipboard).toHaveBeenCalledWith('data:image/png;base64,AAA')
    expect(downloadDataUrl).not.toHaveBeenCalled()
  }, 30000)

  it('shares the screenshot through the OS share sheet when available', async () => {
    vi.mocked(canShareImage).mockReturnValue(true)
    vi.mocked(sharePng).mockResolvedValue(true)

    const wrapper = await mountWithCompareResult()

    const dropdowns = wrapper.findAllComponents({ name: 'ElDropdown' })
    dropdowns[0].vm.$emit('command', 'share')
    await flushPromises()

    expect(sharePng).toHaveBeenCalledWith('data:image/png;base64,AAA', 'release-report.png', 'Releases')
    expect(downloadDataUrl).not.toHaveBeenCalled()
  }, 30000)

  it('falls back to the clipboard when sharing is unavailable', async () => {
    vi.mocked(sharePng).mockResolvedValue(false)

    const wrapper = await mountWithCompareResult()

    const dropdowns = wrapper.findAllComponents({ name: 'ElDropdown' })
    dropdowns[0].vm.$emit('command', 'share')
    await flushPromises()

    expect(copyPngToClipboard).toHaveBeenCalledWith('data:image/png;base64,AAA')
  }, 30000)
})

describe('ReleasesView merged release diff', () => {
  const SOURCE_PLACEHOLDER = enMessages.releaseDiff.missing_source_placeholder
  const TARGET_PLACEHOLDER = enMessages.releaseDiff.missing_target_placeholder

  const COMPARISON: ReleaseCompareResponse = {
    project_key: 'ALPHA',
    repository_slug: 'alpha-api',
    git_provider: 'bitbucket_server',
    source_ref: 'v1.1.5',
    target_ref: 'v2.3.0',
    baseline_ref: 'v1.0.0',
    narrowed: true,
    verdict: 'missing',
    scan_complete: true,
    scan_limit: 2000,
    filtered_by_baseline_count: 2,
    missing_count: 2,
    missing_commits: [
      { id: 'aaa1111', display_id: 'aaa111', message: 'fix: crash on logout' },
      { id: 'bbb2222', display_id: 'bbb222', message: 'feat: new dashboard' },
    ],
    added_count: 1,
    added_commits: [{ id: 'ccc3333', display_id: 'ccc333', message: 'chore: bump deps' }],
    added_complete: true,
    rendered_truncated: false,
  }

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(projectsApi.getCloudWorkspaces).mockResolvedValue([])
    vi.mocked(projectsApi.getAllProjects).mockResolvedValue(PROJECTS)
    vi.mocked(projectsApi.getProjectRepositories).mockImplementation((projectKey: string) =>
      Promise.resolve(REPOSITORIES_BY_PROJECT[projectKey] ?? []),
    )
    vi.mocked(releaseDiffApi.listRefs).mockResolvedValue(REFS)
  })

  async function mountWithRepository() {
    const wrapper = mountView()
    await flushPromises()

    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    await selects[0].vm.$emit('update:modelValue', 'ALPHA')
    await flushPromises()
    await selects[1].vm.$emit('update:modelValue', 'alpha-api')
    await flushPromises()

    return wrapper
  }

  function refInput(wrapper: AnyWrapper, placeholder: string) {
    return inputsByPlaceholder(wrapper, placeholder)[0].find('input')
  }

  async function runComparison(
    wrapper: AnyWrapper,
    source = 'v1.1.5',
    target = 'v2.3.0',
  ) {
    await refInput(wrapper, SOURCE_PLACEHOLDER).setValue(source)
    await refInput(wrapper, TARGET_PLACEHOLDER).setValue(target)
    await flushPromises()

    const button = wrapper
      .findAll('button')
      .find((item: AnyWrapper) => item.text() === enMessages.releaseDiff.run_compare)
    await button!.trigger('click')
    await flushPromises()
  }

  it('sends one request carrying source, target and the baseline of the field', async () => {
    vi.mocked(releaseDiffApi.compare).mockResolvedValue(COMPARISON)

    const wrapper = await mountWithRepository()
    await runComparison(wrapper)

    expect(releaseDiffApi.compare).toHaveBeenCalledWith(
      expect.objectContaining({
        project_key: 'ALPHA',
        repository_slug: 'alpha-api',
        source_ref: 'v1.1.5',
        target_ref: 'v2.3.0',
        baseline_ref: undefined,
      }),
    )
  })

  it('explains an empty baseline next to its input instead of under it', async () => {
    const wrapper = await mountWithRepository()

    // the explanation belongs to the field, so it shares the line with its input
    // (it used to sit under the input in a half column and wrapped over two lines)
    const field = wrapper.find('.baseline-field')
    expect(field.find('input').attributes('placeholder')).toBe(
      enMessages.releaseDiff.missing_baseline_placeholder,
    )
    expect(field.find('.baseline-hint').text()).toBe(enMessages.releaseDiff.baseline_field_help)
  })

  it('clears both tools when another repository is picked', async () => {
    vi.mocked(releaseDiffApi.compare).mockResolvedValue(COMPARISON)

    const wrapper = await mountWithRepository()
    await runComparison(wrapper)
    await refInput(wrapper, enMessages.releaseDiff.missing_baseline_placeholder).setValue('v1.0.0')
    await flushPromises()

    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    await selects[1].vm.$emit('update:modelValue', 'alpha-web')
    await flushPromises()

    // a ref of the repository that was just left means nothing in the new one
    expect((refInput(wrapper, SOURCE_PLACEHOLDER).element as HTMLInputElement).value).toBe('')
    expect((refInput(wrapper, TARGET_PLACEHOLDER).element as HTMLInputElement).value).toBe('')
    expect(
      (refInput(wrapper, enMessages.releaseDiff.missing_baseline_placeholder).element as
        HTMLInputElement).value,
    ).toBe('')
    // and the verdict of the old repository is not left on screen
    expect(wrapper.find('.scope-used').exists()).toBe(false)
  })

  it('renders the verdict with the missing and the added commits', async () => {
    vi.mocked(releaseDiffApi.compare).mockResolvedValue(COMPARISON)

    const wrapper = await mountWithRepository()
    await runComparison(wrapper)

    expect(wrapper.text()).toContain(
      enMessages.releaseDiff.missing_found
        .replace('{count}', '2')
        .replace('{source}', 'v1.1.5')
        .replace('{target}', 'v2.3.0'),
    )
    expect(wrapper.text()).toContain('aaa111')
    expect(wrapper.text()).toContain('ccc333')
    expect(wrapper.text()).toContain(
      enMessages.releaseDiff.missing_baseline_used
        .replace('{ref}', 'v1.0.0')
        .replace('{filtered}', '2'),
    )
  })

  it('never renders an inconclusive verdict as a pass', async () => {
    vi.mocked(releaseDiffApi.compare).mockResolvedValue({
      ...COMPARISON,
      verdict: 'inconclusive',
      scan_complete: false,
      scan_limit: 1,
      missing_count: 1,
      added_count: 0,
      added_commits: [],
      narrowed: false,
      baseline_ref: null,
    })

    const wrapper = await mountWithRepository()
    await runComparison(wrapper)

    const verdict = wrapper
      .findAllComponents({ name: 'ElAlert' })
      .find((alert: AnyWrapper) =>
        alert.text().includes(enMessages.releaseDiff.status_inconclusive),
      )

    expect(verdict).toBeDefined()
    expect(verdict!.props('type')).toBe('warning')
    expect(verdict!.props('type')).not.toBe('success')
  })

  it('keeps the comparison selection in the URL', async () => {
    vi.mocked(releaseDiffApi.compare).mockResolvedValue(COMPARISON)

    const wrapper = await mountWithRepository()
    await runComparison(wrapper)

    const query = testRouter!.currentRoute.value.query
    expect(query.project_key).toBe('ALPHA')
    expect(query.repository_slug).toBe('alpha-api')
    expect(query.source).toBe('v1.1.5')
    expect(query.target).toBe('v2.3.0')
  })
})
