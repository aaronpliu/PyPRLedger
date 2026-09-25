import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createI18n } from 'vue-i18n'
import ReleasesView from '@/views/releases/ReleasesView.vue'
import { projectsApi } from '@/api/projects'
import type { RepositorySummary } from '@/api/projects'
import { releaseDiffApi } from '@/api/releaseDiff'
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
const REF_PLACEHOLDER = enMessages.releaseDiff.ref_placeholder
const WORKSPACE_PLACEHOLDER = enMessages.releaseDiff.workspace_slug_placeholder

/* eslint-disable @typescript-eslint/no-explicit-any */
type AnyWrapper = any

function inputsByPlaceholder(wrapper: AnyWrapper, placeholder: string) {
  return wrapper
    .findAllComponents({ name: 'ElAutocomplete' })
    .filter((input: AnyWrapper) => input.props('placeholder') === placeholder)
}

function workspaceSelect(wrapper: AnyWrapper) {
  return wrapper
    .findAllComponents({ name: 'ElSelect' })
    .find((select: AnyWrapper) => select.props('placeholder') === WORKSPACE_PLACEHOLDER)
}

function mountView() {
  const i18n = createI18n({
    legacy: false,
    locale: 'en',
    messages: { en: enMessages },
  })

  return mount(ReleasesView, {
    global: {
      plugins: [ElementPlus, i18n],
    },
  })
}

describe('ReleasesView', () => {
  beforeEach(() => {
    vi.mocked(projectsApi.getAllProjects).mockReset()
    vi.mocked(projectsApi.getProjectRepositories).mockReset()
    vi.mocked(projectsApi.getCloudWorkspaces).mockReset()
    vi.mocked(releaseDiffApi.listRefs).mockReset()
    vi.mocked(releaseDiffApi.compare).mockReset()
    vi.mocked(projectsApi.getCloudWorkspaces).mockResolvedValue([])
    vi.mocked(releaseDiffApi.listRefs).mockResolvedValue(REFS)
    vi.mocked(projectsApi.getAllProjects).mockResolvedValue(PROJECTS)
    vi.mocked(projectsApi.getProjectRepositories).mockImplementation((projectKey: string) =>
      Promise.resolve(REPOSITORIES_BY_PROJECT[projectKey] ?? []),
    )
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

  it('hides the base ref inputs until the release scope toggle is enabled', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(inputsByPlaceholder(wrapper, BASE_REF_PLACEHOLDER)).toHaveLength(0)

    await wrapper.findAllComponents({ name: 'ElSwitch' })[0].vm.$emit('update:modelValue', true)
    await flushPromises()

    expect(inputsByPlaceholder(wrapper, BASE_REF_PLACEHOLDER)).toHaveLength(2)
  })

  it('renders the effective scope of each release', async () => {
    const wrapper = mountView()
    await flushPromises()

    await wrapper.findAllComponents({ name: 'ElSwitch' })[0].vm.$emit('update:modelValue', true)
    await flushPromises()

    const releaseInputs = inputsByPlaceholder(wrapper, REF_PLACEHOLDER)
    await releaseInputs[0].find('input').setValue('v1.2.0')
    await releaseInputs[1].find('input').setValue('v1.3.0')

    const baseInputs = inputsByPlaceholder(wrapper, BASE_REF_PLACEHOLDER)
    // no base ref yet -> the whole history reachable from the release ref
    expect(wrapper.text()).toContain('full history of v1.2.0')
    expect(wrapper.text()).toContain('full history of v1.3.0')

    await baseInputs[0].find('input').setValue('v1.1.0')
    await baseInputs[1].find('input').setValue('v1.2.0')
    await flushPromises()

    expect(wrapper.text()).toContain('v1.1.0..v1.2.0')
    expect(wrapper.text()).toContain('v1.2.0..v1.3.0')
  })

  it('fills the new release base with the old release ref on demand', async () => {
    const wrapper = mountView()
    await flushPromises()

    await wrapper.findAllComponents({ name: 'ElSwitch' })[0].vm.$emit('update:modelValue', true)
    await flushPromises()

    await inputsByPlaceholder(wrapper, REF_PLACEHOLDER)[0].find('input').setValue('v1.2.0')
    await flushPromises()

    const quickFill = wrapper
      .findAll('button')
      .find((button) => button.text() === enMessages.releaseDiff.scope_use_old_as_new_base)
    expect(quickFill).toBeDefined()

    await quickFill!.trigger('click')
    await flushPromises()

    const baseInputs = inputsByPlaceholder(wrapper, BASE_REF_PLACEHOLDER)
    expect((baseInputs[1].find('input').element as HTMLInputElement).value).toBe('v1.2.0')
  })

  it('only sends base refs when the release scope is enabled', async () => {
    vi.mocked(releaseDiffApi.compare).mockResolvedValue({
      project_key: 'ALPHA',
      repository_slug: 'alpha-api',
      git_provider: 'bitbucket_server',
      old_release_ref: 'v1.2.0',
      new_release_ref: 'v1.3.0',
      old_commits_included: true,
      status: 'included',
      summary: {},
      missing_commits: [],
      added_commits: [],
      old_release_commits: [],
      new_release_commits: [],
      truncated: false,
    })

    const wrapper = mountView()
    await flushPromises()

    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    await selects[0].vm.$emit('update:modelValue', 'ALPHA')
    await flushPromises()
    await selects[1].vm.$emit('update:modelValue', 'alpha-api')
    await flushPromises()

    const releaseInputs = inputsByPlaceholder(wrapper, REF_PLACEHOLDER)
    await releaseInputs[0].find('input').setValue('v1.2.0')
    await releaseInputs[1].find('input').setValue('v1.3.0')

    const compareButton = wrapper
      .findAll('button')
      .find((button) => button.text() === enMessages.releaseDiff.run_compare)
    await compareButton!.trigger('click')
    await flushPromises()

    expect(releaseDiffApi.compare).toHaveBeenCalledWith(
      expect.objectContaining({
        project_key: 'ALPHA',
        repository_slug: 'alpha-api',
        old_release_ref: 'v1.2.0',
        new_release_ref: 'v1.3.0',
        old_release_base_ref: undefined,
        new_release_base_ref: undefined,
      }),
    )

    await wrapper.findAllComponents({ name: 'ElSwitch' })[0].vm.$emit('update:modelValue', true)
    await flushPromises()
    const baseInputs = inputsByPlaceholder(wrapper, BASE_REF_PLACEHOLDER)
    await baseInputs[0].find('input').setValue('v1.1.0')
    await baseInputs[1].find('input').setValue('v1.2.0')

    await compareButton!.trigger('click')
    await flushPromises()

    expect(releaseDiffApi.compare).toHaveBeenLastCalledWith(
      expect.objectContaining({
        old_release_base_ref: 'v1.1.0',
        new_release_base_ref: 'v1.2.0',
      }),
    )
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

  it('lays the compare and check tools out in two columns', async () => {
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
      old_release_ref: 'v1.2.0',
      new_release_ref: 'v1.3.0',
      old_commits_included: false,
      status: 'missing_commits',
      summary: { missing_count: 2 },
      missing_commits: [
        { id: 'aaa1111', display_id: 'aaa111' },
        { id: 'bbb2222', display_id: 'bbb222' },
      ],
      added_commits: [],
      old_release_commits: [],
      new_release_commits: [],
      truncated: false,
    })

    const wrapper = mountView()
    await flushPromises()

    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    await selects[0].vm.$emit('update:modelValue', 'ALPHA')
    await flushPromises()
    await selects[1].vm.$emit('update:modelValue', 'alpha-api')
    await flushPromises()

    const releaseInputs = inputsByPlaceholder(wrapper, REF_PLACEHOLDER)
    await releaseInputs[0].find('input').setValue('v1.2.0')
    await releaseInputs[1].find('input').setValue('v1.3.0')

    const compareButton = wrapper
      .findAll('button')
      .find((button) => button.text() === enMessages.releaseDiff.run_compare)
    await compareButton!.trigger('click')
    await flushPromises()

    const sendButton = wrapper
      .findAll('button')
      .find((button) => button.text() === enMessages.releaseDiff.send_missing_to_check)
    expect(sendButton).toBeDefined()

    await sendButton!.trigger('click')
    await flushPromises()

    expect((wrapper.find('textarea').element as HTMLTextAreaElement).value).toBe(
      'aaa1111\nbbb2222',
    )
  })

  it('resets a tool without touching the shared repository context', async () => {
    const wrapper = mountView()
    await flushPromises()

    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    await selects[0].vm.$emit('update:modelValue', 'ALPHA')
    await flushPromises()
    await selects[1].vm.$emit('update:modelValue', 'alpha-api')
    await flushPromises()

    const releaseInputs = inputsByPlaceholder(wrapper, REF_PLACEHOLDER)
    await releaseInputs[0].find('input').setValue('v1.2.0')
    await releaseInputs[1].find('input').setValue('v1.3.0')

    const resetButtons = wrapper
      .findAll('button')
      .filter((button) => button.text() === enMessages.releaseDiff.reset)
    expect(resetButtons).toHaveLength(2)

    await resetButtons[0].trigger('click')
    await flushPromises()

    expect(
      (inputsByPlaceholder(wrapper, REF_PLACEHOLDER)[0].find('input').element as HTMLInputElement)
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

  it('suggests the loaded refs and still accepts a manually typed ref', async () => {
    vi.mocked(releaseDiffApi.compare).mockResolvedValue({
      project_key: 'ALPHA',
      repository_slug: 'alpha-api',
      git_provider: 'bitbucket_server',
      old_release_ref: 'deadbeef',
      new_release_ref: 'v1.1.0',
      old_commits_included: true,
      status: 'included',
      summary: {},
      missing_commits: [],
      added_commits: [],
      old_release_commits: [],
      new_release_commits: [],
      truncated: false,
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

    const releaseFields = inputsByPlaceholder(wrapper, REF_PLACEHOLDER)
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
      expect.objectContaining({ old_release_ref: 'deadbeef', new_release_ref: 'v1.1.0' }),
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
      old_release_ref: 'v1.0.0',
      new_release_ref: 'v1.1.0',
      old_commits_included: true,
      status: 'included',
      summary: {},
      missing_commits: [],
      added_commits: [],
      old_release_commits: [],
      new_release_commits: [],
      truncated: false,
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

    const releaseInputs = inputsByPlaceholder(wrapper, REF_PLACEHOLDER)
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
      old_release_ref: 'v1.0.0',
      new_release_ref: 'v1.1.0',
      old_commits_included: true,
      status: 'included',
      summary: {},
      missing_commits: [],
      added_commits: [],
      old_release_commits: [],
      new_release_commits: [],
      truncated: false,
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

    const releaseInputs = inputsByPlaceholder(wrapper, REF_PLACEHOLDER)
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
})
