import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus, { ElMessageBox } from 'element-plus'
import { createI18n } from 'vue-i18n'
import ReleaseNotesView from '@/views/releases/ReleaseNotesView.vue'
import { projectsApi } from '@/api/projects'
import { releaseDiffApi } from '@/api/releaseDiff'
import { releaseNotesApi, type ReleaseNote } from '@/api/releaseNotes'
import { useAuthStore } from '@/stores/auth'
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
    listRefs: vi.fn(),
    compare: vi.fn(),
    check: vi.fn(),
  },
}))

vi.mock('@/api/releaseNotes', () => ({
  releaseNotesApi: {
    list: vi.fn(),
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
    preview: vi.fn(),
    push: vi.fn(),
    importReleases: vi.fn(),
  },
}))

// md-editor-v3 needs a real layout engine - stub it with plain inputs
vi.mock('md-editor-v3', () => ({
  MdEditor: {
    name: 'MdEditor',
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template:
      '<textarea class="md-editor-stub" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
  MdPreview: {
    name: 'MdPreview',
    props: ['modelValue'],
    template: '<div class="md-preview-stub">{{ modelValue }}</div>',
  },
}))

vi.mock('md-editor-v3/lib/style.css', () => ({}))

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
]

const REPOSITORIES = [
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
]

const REFS = {
  project_key: 'ALPHA',
  repository_slug: 'alpha-api',
  git_provider: 'bitbucket_server',
  tags: ['v1.1.0', 'v1.0.0'],
  branches: ['main'],
}

function signIn(roles: string[]) {
  const authStore = useAuthStore()
  authStore.user = { id: 1, username: 'tester', roles } as never
}

const GITHUB_PROJECT = {
  id: 2,
  project_id: 102,
  project_name: 'acme',
  project_key: 'acme',
  project_url: 'https://github.local/acme',
  git_provider: 'github_enterprise',
  created_date: '2024-01-02T00:00:00',
  updated_date: '2024-01-02T00:00:00',
}

function release(overrides: Partial<ReleaseNote> = {}): ReleaseNote {
  return {
    id: 1,
    project_key: 'ALPHA',
    repository_slug: 'alpha-api',
    tag_name: 'v1.1.0',
    name: 'v1.1.0',
    body: '## What\u2019s Changed\n\n- add login page',
    previous_tag: 'v1.0.0',
    status: 'published',
    is_prerelease: false,
    is_latest: true,
    author: 'alice',
    published_date: '2026-09-01T10:00:00',
    created_date: '2026-09-01T09:00:00',
    updated_date: '2026-09-01T10:00:00',
    ...overrides,
  }
}

/* eslint-disable @typescript-eslint/no-explicit-any */
type AnyWrapper = any

const mountedWrappers: AnyWrapper[] = []

afterEach(() => {
  mountedWrappers.splice(0).forEach((wrapper) => wrapper.unmount())
})

function mountView() {
  const i18n = createI18n({ legacy: false, locale: 'en', messages: { en: enMessages } })
  const wrapper = mount(ReleaseNotesView, {
    global: { plugins: [ElementPlus, i18n] },
  })
  mountedWrappers.push(wrapper)
  return wrapper
}

function buttonsByLabel(wrapper: AnyWrapper, label: string) {
  return wrapper.findAll('button').filter((button: AnyWrapper) => button.text() === label)
}

function selectByPlaceholder(wrapper: AnyWrapper, placeholder: string) {
  return wrapper
    .findAllComponents({ name: 'ElSelect' })
    .find((select: AnyWrapper) => select.props('placeholder') === placeholder)
}

async function selectRepository(wrapper: AnyWrapper) {
  const selects = wrapper.findAllComponents({ name: 'ElSelect' })
  await selects[0].vm.$emit('update:modelValue', 'ALPHA')
  await flushPromises()
  await selects[1].vm.$emit('update:modelValue', 'alpha-api')
  await flushPromises()
}

describe('ReleaseNotesView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    signIn(['review_admin'])
    vi.mocked(projectsApi.getAllProjects).mockResolvedValue(PROJECTS as any)
    vi.mocked(projectsApi.getProjectRepositories).mockResolvedValue(REPOSITORIES as any)
    vi.mocked(projectsApi.getCloudWorkspaces).mockResolvedValue([])
    vi.mocked(releaseDiffApi.listRefs).mockResolvedValue(REFS as any)
    vi.mocked(releaseNotesApi.list).mockResolvedValue({ total: 1, items: [release()] })
    vi.mocked(releaseNotesApi.create).mockResolvedValue(release({ status: 'draft' }) as any)
    vi.mocked(releaseNotesApi.update).mockResolvedValue(release() as any)
    vi.mocked(releaseNotesApi.remove).mockResolvedValue({ message: 'ok' })
  })

  it('asks for a repository before showing releases', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain(enMessages.releaseNotes.needs_repository)
    expect(releaseNotesApi.list).not.toHaveBeenCalled()
  })

  it('lists the releases of the selected repository and flags the latest one', async () => {
    vi.mocked(releaseNotesApi.list).mockResolvedValue({
      total: 2,
      items: [
        release(),
        release({ id: 2, tag_name: 'v1.2.0', name: 'v1.2.0', status: 'draft', is_latest: false, published_date: null }),
      ],
    })

    const wrapper = mountView()
    await flushPromises()
    await selectRepository(wrapper)

    expect(releaseNotesApi.list).toHaveBeenCalledWith({
      project_key: 'ALPHA',
      repository_slug: 'alpha-api',
      limit: 100,
    })
    const text = wrapper.text()
    expect(text).toContain('v1.1.0')
    expect(text).toContain(enMessages.releaseNotes.badge_latest)
    expect(text).toContain(enMessages.releaseNotes.badge_draft)
    expect(text).toContain(enMessages.releaseNotes.released_by.replace('{author}', 'alice'))
  })

  it('refreshes the tag suggestions through the provider', async () => {
    const wrapper = mountView()
    await flushPromises()
    await selectRepository(wrapper)

    expect(releaseDiffApi.listRefs).toHaveBeenLastCalledWith(
      expect.objectContaining({ refresh: false }),
    )

    const refreshButton = buttonsByLabel(wrapper, enMessages.releaseNotes.refresh_tags)
    expect(refreshButton).toHaveLength(1)

    await refreshButton[0].trigger('click')
    await flushPromises()

    expect(releaseDiffApi.listRefs).toHaveBeenLastCalledWith(
      expect.objectContaining({ project_key: 'ALPHA', refresh: true }),
    )
  })

  it('drafts a new version release', async () => {
    const wrapper = mountView()
    await flushPromises()
    await selectRepository(wrapper)

    await buttonsByLabel(wrapper, enMessages.releaseNotes.draft_new)[0].trigger('click')
    await flushPromises()

    // the newest tag is preselected, the title falls back to the tag name
    const tagSelect = selectByPlaceholder(wrapper, enMessages.releaseNotes.tag_placeholder)
    expect(tagSelect.props('modelValue')).toBe('v1.1.0')

    await buttonsByLabel(wrapper, enMessages.releaseNotes.save_draft)[0].trigger('click')
    await flushPromises()

    expect(releaseNotesApi.create).toHaveBeenCalledWith(
      expect.objectContaining({
        project_key: 'ALPHA',
        repository_slug: 'alpha-api',
        tag_name: 'v1.1.0',
        name: 'v1.1.0',
        status: 'draft',
        is_prerelease: false,
      }),
    )
  })

  it('publishes a draft from the list', async () => {
    vi.mocked(releaseNotesApi.list).mockResolvedValue({
      total: 1,
      items: [release({ status: 'draft', published_date: null, is_latest: false })],
    })

    const wrapper = mountView()
    await flushPromises()
    await selectRepository(wrapper)

    await buttonsByLabel(wrapper, enMessages.releaseNotes.publish)[0].trigger('click')
    await flushPromises()

    expect(releaseNotesApi.update).toHaveBeenCalledWith(1, { status: 'published' })
  })

  it('generates the release notes from the commits of the release scope', async () => {
    vi.mocked(releaseNotesApi.preview).mockResolvedValue({
      version: 'v1.1.0',
      previous_version: 'v1.0.0',
      suggested_name: 'v1.1.0',
      body: '## What\u2019s Changed\n\n### 🚀 Features\n- add login page',
      commit_count: 3,
      commits: [],
      truncated: false,
    })

    const wrapper = mountView()
    await flushPromises()
    await selectRepository(wrapper)

    await buttonsByLabel(wrapper, enMessages.releaseNotes.draft_new)[0].trigger('click')
    await flushPromises()

    const previousTagSelect = selectByPlaceholder(
      wrapper,
      enMessages.releaseNotes.previous_tag_placeholder,
    )
    await previousTagSelect.vm.$emit('update:modelValue', 'v1.0.0')
    await flushPromises()

    await buttonsByLabel(wrapper, enMessages.releaseNotes.generate_notes)[0].trigger('click')
    await flushPromises()

    expect(releaseNotesApi.preview).toHaveBeenCalledWith(
      expect.objectContaining({
        project_key: 'ALPHA',
        repository_slug: 'alpha-api',
        version: 'v1.1.0',
        previous_version: 'v1.0.0',
      }),
    )
    expect(wrapper.text()).toContain(
      enMessages.releaseNotes.generated.replace('{count}', '3'),
    )
  })

  it('deletes a release after confirmation', async () => {
    const confirmSpy = vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm' as any)

    const wrapper = mountView()
    await flushPromises()
    await selectRepository(wrapper)

    await buttonsByLabel(wrapper, enMessages.releaseNotes.delete)[0].trigger('click')
    await flushPromises()

    expect(confirmSpy).toHaveBeenCalled()
    expect(releaseNotesApi.remove).toHaveBeenCalledWith(1)
    expect(releaseNotesApi.list).toHaveBeenCalledTimes(2)
  })

  it('keeps the release when the deletion is cancelled', async () => {
    const confirmSpy = vi
      .spyOn(ElMessageBox, 'confirm')
      .mockRejectedValue(new Error('cancel'))

    const wrapper = mountView()
    await flushPromises()
    await selectRepository(wrapper)

    await buttonsByLabel(wrapper, enMessages.releaseNotes.delete)[0].trigger('click')
    await flushPromises()

    expect(confirmSpy).toHaveBeenCalled()
    expect(releaseNotesApi.remove).not.toHaveBeenCalled()
  })

  it('is read-only for users without a release administrator role', async () => {
    signIn(['viewer'])

    const wrapper = mountView()
    await flushPromises()
    await selectRepository(wrapper)

    // the list is still visible
    expect(wrapper.text()).toContain('v1.1.0')
    expect(wrapper.text()).toContain(enMessages.releaseNotes.read_only_title)
    // but no management affordances
    expect(buttonsByLabel(wrapper, enMessages.releaseNotes.draft_new)).toHaveLength(0)
    expect(buttonsByLabel(wrapper, enMessages.releaseNotes.edit_release)).toHaveLength(0)
    expect(buttonsByLabel(wrapper, enMessages.releaseNotes.delete)).toHaveLength(0)
    expect(wrapper.find('.md-editor-stub').exists()).toBe(false)
  })

  it('imports the releases of a GitHub repository', async () => {
    vi.mocked(projectsApi.getAllProjects).mockResolvedValue([GITHUB_PROJECT] as any)
    vi.mocked(projectsApi.getProjectRepositories).mockResolvedValue([
      { ...REPOSITORIES[0], repository_slug: 'pyledger', project_id: 102 },
    ] as any)
    vi.mocked(releaseDiffApi.listRefs).mockResolvedValue({
      ...REFS,
      project_key: 'acme',
      repository_slug: 'pyledger',
      git_provider: 'github_enterprise',
    } as any)
    vi.mocked(releaseNotesApi.importReleases).mockResolvedValue({
      imported: 2,
      updated: 1,
      skipped: 0,
      items: [],
    })

    const wrapper = mountView()
    await flushPromises()

    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    await selects[0].vm.$emit('update:modelValue', 'acme')
    await flushPromises()
    await selects[1].vm.$emit('update:modelValue', 'pyledger')
    await flushPromises()

    const importButton = buttonsByLabel(wrapper, enMessages.releaseNotes.import_from_provider)
    expect(importButton).toHaveLength(1)

    await importButton[0].trigger('click')
    await flushPromises()

    expect(releaseNotesApi.importReleases).toHaveBeenCalledWith(
      expect.objectContaining({
        project_key: 'acme',
        repository_slug: 'pyledger',
        git_provider: 'github_enterprise',
      }),
    )
    // the list is refreshed after the import
    expect(releaseNotesApi.list).toHaveBeenCalledTimes(2)
  })

  it('hides the GitHub integration for providers without a release API', async () => {
    const wrapper = mountView()
    await flushPromises()
    await selectRepository(wrapper)

    expect(buttonsByLabel(wrapper, enMessages.releaseNotes.import_from_provider)).toHaveLength(0)
    expect(buttonsByLabel(wrapper, enMessages.releaseNotes.push_to_provider)).toHaveLength(0)
  })

  it('pushes an existing release to GitHub from the list', async () => {
    vi.mocked(projectsApi.getAllProjects).mockResolvedValue([GITHUB_PROJECT] as any)
    vi.mocked(projectsApi.getProjectRepositories).mockResolvedValue([
      { ...REPOSITORIES[0], repository_slug: 'pyledger', project_id: 102 },
    ] as any)
    vi.mocked(releaseNotesApi.push).mockResolvedValue(
      release({ external_provider: 'github_enterprise', external_url: 'https://github.local/x' }),
    )

    const wrapper = mountView()
    await flushPromises()
    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    await selects[0].vm.$emit('update:modelValue', 'acme')
    await flushPromises()
    await selects[1].vm.$emit('update:modelValue', 'pyledger')
    await flushPromises()

    const pushButton = buttonsByLabel(wrapper, enMessages.releaseNotes.push_to_provider)
    expect(pushButton).toHaveLength(1)

    await pushButton[0].trigger('click')
    await flushPromises()

    expect(releaseNotesApi.push).toHaveBeenCalledWith(
      1,
      expect.objectContaining({
        project_key: 'acme',
        repository_slug: 'pyledger',
        git_provider: 'github_enterprise',
        update_existing: true,
      }),
    )
  })

  it('publishes and pushes in one go when asked', async () => {
    vi.mocked(projectsApi.getAllProjects).mockResolvedValue([GITHUB_PROJECT] as any)
    vi.mocked(projectsApi.getProjectRepositories).mockResolvedValue([
      { ...REPOSITORIES[0], repository_slug: 'pyledger', project_id: 102 },
    ] as any)
    vi.mocked(releaseDiffApi.listRefs).mockResolvedValue({
      ...REFS,
      project_key: 'acme',
      repository_slug: 'pyledger',
      git_provider: 'github_enterprise',
    } as any)
    vi.mocked(releaseNotesApi.push).mockResolvedValue(release())

    const wrapper = mountView()
    await flushPromises()
    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    await selects[0].vm.$emit('update:modelValue', 'acme')
    await flushPromises()
    await selects[1].vm.$emit('update:modelValue', 'pyledger')
    await flushPromises()

    await buttonsByLabel(wrapper, enMessages.releaseNotes.draft_new)[0].trigger('click')
    await flushPromises()

    // opt in to the provider push
    const pushCheckbox = wrapper
      .findAllComponents({ name: 'ElCheckbox' })
      .find((box: AnyWrapper) => box.text() === enMessages.releaseNotes.push_to_provider)
    expect(pushCheckbox).toBeDefined()
    await pushCheckbox!.vm.$emit('update:modelValue', true)
    await flushPromises()

    await buttonsByLabel(wrapper, enMessages.releaseNotes.publish)[0].trigger('click')
    await flushPromises()

    expect(releaseNotesApi.create).toHaveBeenCalledWith(
      expect.objectContaining({ tag_name: 'v1.1.0', status: 'published' }),
    )
    expect(releaseNotesApi.push).toHaveBeenCalledWith(
      1,
      expect.objectContaining({
        project_key: 'acme',
        repository_slug: 'pyledger',
        update_existing: true,
      }),
    )
  })

  it('loads an existing release into the form for editing', async () => {
    const wrapper = mountView()
    await flushPromises()
    await selectRepository(wrapper)

    await buttonsByLabel(wrapper, enMessages.releaseNotes.edit_release)[0].trigger('click')
    await flushPromises()

    const editor = wrapper.find('.md-editor-stub')
    expect((editor.element as HTMLTextAreaElement).value).toContain('add login page')
    // the tag of an existing release cannot be changed
    const tagSelect = selectByPlaceholder(wrapper, enMessages.releaseNotes.tag_placeholder)
    expect(tagSelect.props('disabled')).toBe(true)

    await buttonsByLabel(wrapper, enMessages.releaseNotes.save)[0].trigger('click')
    await flushPromises()

    expect(releaseNotesApi.update).toHaveBeenCalledWith(
      1,
      expect.objectContaining({ status: 'published', previous_tag: 'v1.0.0' }),
    )
  })
})
