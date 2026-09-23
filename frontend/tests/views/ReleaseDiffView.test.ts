import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createI18n } from 'vue-i18n'
import ReleaseDiffView from '@/views/releases/ReleaseDiffView.vue'
import { projectsApi } from '@/api/projects'
import enMessages from '@/locales/en.json'

vi.mock('@/api/projects', () => ({
  projectsApi: {
    getAllProjects: vi.fn(),
    getProjectRepositories: vi.fn(),
  },
}))

vi.mock('@/api/releaseDiff', () => ({
  releaseDiffApi: {
    compare: vi.fn(),
    check: vi.fn(),
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

const REPOSITORIES_BY_PROJECT: Record<string, Array<Record<string, unknown>>> = {
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

function mountView() {
  const i18n = createI18n({
    legacy: false,
    locale: 'en',
    messages: { en: enMessages },
  })

  return mount(ReleaseDiffView, {
    global: {
      plugins: [ElementPlus, i18n],
    },
  })
}

describe('ReleaseDiffView', () => {
  beforeEach(() => {
    vi.mocked(projectsApi.getAllProjects).mockReset()
    vi.mocked(projectsApi.getProjectRepositories).mockReset()
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
})
