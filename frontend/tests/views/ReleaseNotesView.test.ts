import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import ElementPlus, { ElMessageBox } from 'element-plus'
import { createI18n } from 'vue-i18n'
import ReleaseNotesView from '@/views/releases/ReleaseNotesView.vue'
import { projectsApi } from '@/api/projects'
import { rbacApi } from '@/api/rbac'
import { releaseDiffApi } from '@/api/releaseDiff'
import { releaseNotesApi, type ReleaseNote } from '@/api/releaseNotes'
import { resetJiraSettings } from '@/composables/useJira'
import { useAuthStore } from '@/stores/auth'
import enMessages from '@/locales/en.json'

vi.mock('@/api/projects', () => ({
  projectsApi: {
    getAllProjects: vi.fn(),
    getProjectRepositories: vi.fn(),
    getCloudWorkspaces: vi.fn(),
  },
}))

// The commit tables ask for the JIRA link settings (no JIRA configured here)
vi.mock('@/api/rbac', () => ({
  rbacApi: {
    getJiraSettings: vi.fn().mockResolvedValue({ base_url: '', project_keys: [] }),
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
    props: ['modelValue', 'theme'],
    emits: ['update:modelValue'],
    template:
      '<textarea class="md-editor-stub" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
  MdPreview: {
    name: 'MdPreview',
    props: ['modelValue', 'theme'],
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

const PREVIEW_COMMIT = {
  id: 'abc1234567890',
  display_id: 'abc1234',
  author_name: 'Jane Doe',
  message: 'feat: add login page',
  url: 'https://git.local/commits/abc1234',
}

/** Preview payload (the note body is irrelevant for the tag -> commits view). */
function preview(commits: (typeof PREVIEW_COMMIT)[] = []) {
  return {
    version: 'v1.2.0',
    previous_version: 'v1.1.0' as string | null,
    suggested_name: 'v1.2.0',
    body: '## What’s Changed',
    commit_count: commits.length,
    commits,
    truncated: false,
  }
}

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

/** Switch the navigator between the releases and the tags tab. */
async function selectTab(wrapper: AnyWrapper, label: string) {
  const tab = wrapper
    .findAll('.el-tabs__item')
    .find((item: AnyWrapper) => item.text() === label)
  expect(tab).toBeDefined()
  await tab!.trigger('click')
  await flushPromises()
}

/** Label of the navigator tab that is currently active. */
function activeTabLabel(wrapper: AnyWrapper) {
  const active = wrapper
    .findAll('.el-tabs__item')
    .find((item: AnyWrapper) => item.classes().includes('is-active'))
  return active?.text() ?? ''
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
    // JIRA is off unless a test asks for it
    vi.mocked(rbacApi.getJiraSettings).mockResolvedValue({ base_url: '', project_keys: [] })
    resetJiraSettings()
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
      limit: 10,
      offset: 0,
    })
    const text = wrapper.text()
    expect(text).toContain('v1.1.0')
    expect(text).toContain(enMessages.releaseNotes.badge_latest)
    expect(text).toContain(enMessages.releaseNotes.badge_draft)
    expect(text).toContain(enMessages.releaseNotes.released_by.replace('{author}', 'alice'))
  })

  it('shows the profile icon of the author when one is available', async () => {
    vi.mocked(releaseNotesApi.list).mockResolvedValue({
      total: 1,
      items: [
        release({ author: 'alice', author_avatar_url: '/api/v1/users/avatars/1_ab.png' }),
      ],
    })

    const wrapper = mountView()
    await flushPromises()
    await selectRepository(wrapper)

    // one icon in the navigator entry, one next to the author of the notes
    const icons = wrapper.findAll('img.avatar-img')
    expect(icons).toHaveLength(2)
    expect(icons.map((icon: AnyWrapper) => icon.attributes('src'))).toEqual([
      '/api/v1/users/avatars/1_ab.png',
      '/api/v1/users/avatars/1_ab.png',
    ])
    expect(icons.map((icon: AnyWrapper) => icon.attributes('alt'))).toEqual(['alice', 'alice'])
  })

  it('keeps the release without an icon when the author has no picture', async () => {
    const wrapper = mountView()
    await flushPromises()
    await selectRepository(wrapper)

    // the author is still named, only the icon is skipped
    expect(
      wrapper.text().includes(
        enMessages.releaseNotes.released_by.replace('{author}', 'alice'),
      ),
    ).toBe(true)
    expect(wrapper.find('img.avatar-img').exists()).toBe(false)
    expect(wrapper.find('.release-author-avatar').exists()).toBe(false)
  })

  it('refreshes the tag suggestions through the provider', async () => {
    const wrapper = mountView()
    await flushPromises()
    await selectRepository(wrapper)
    await selectTab(wrapper, enMessages.releaseNotes.panel_tags)

    expect(releaseDiffApi.listRefs).toHaveBeenLastCalledWith(
      expect.objectContaining({ refresh: false }),
    )

    // the refresh sits in the tags tab, next to the tags it reloads
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
      body: '## What\u2019s Changed\n\n### ✨ Added\n- add login page',
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
    // the notice is a banner above the two columns
    expect(wrapper.find('.read-only-alert').exists()).toBe(true)
    expect(wrapper.findAll('.notes-row > .el-col')).toHaveLength(2)
    // but no management affordances
    expect(buttonsByLabel(wrapper, enMessages.releaseNotes.draft_new)).toHaveLength(0)
    expect(buttonsByLabel(wrapper, enMessages.releaseNotes.edit_release)).toHaveLength(0)
    expect(buttonsByLabel(wrapper, enMessages.releaseNotes.delete)).toHaveLength(0)
    expect(wrapper.find('.md-editor-stub').exists()).toBe(false)
  })

  it('opens release note links in a new tab', async () => {
    const openSpy = vi.spyOn(window, 'open').mockReturnValue(null)

    try {
      const wrapper = mountView()
      await flushPromises()
      await selectRepository(wrapper)

      // the markdown preview is stubbed, so drop a link into the rendered body
      const body = wrapper.find('.release-body')
      const anchor = document.createElement('a')
      anchor.setAttribute(
        'href',
        'https://bitbucket.org/aaronpliu/pylang/branches/compare/v0.2.0%0Dv0.1.0',
      )
      body.element.appendChild(anchor)
      const click = new MouseEvent('click', { bubbles: true, cancelable: true })
      anchor.dispatchEvent(click)

      expect(openSpy).toHaveBeenCalledWith(anchor.href, '_blank', 'noopener,noreferrer')
      expect(click.defaultPrevented).toBe(true)
    } finally {
      openSpy.mockRestore()
    }
  })

  it('does not intercept clicks that are not links', async () => {
    const openSpy = vi.spyOn(window, 'open').mockReturnValue(null)

    try {
      const wrapper = mountView()
      await flushPromises()
      await selectRepository(wrapper)

      const click = new MouseEvent('click', { bubbles: true, cancelable: true })
      wrapper.find('.release-body').element.dispatchEvent(click)

      expect(openSpy).not.toHaveBeenCalled()
      expect(click.defaultPrevented).toBe(false)
    } finally {
      openSpy.mockRestore()
    }
  })

  it('lays the navigator and the notes out in two columns', async () => {
    const wrapper = mountView()
    await flushPromises()
    await selectRepository(wrapper)

    const columns = wrapper.findAll('.notes-row > .el-col')
    expect(columns).toHaveLength(2)
    // navigator (releases + tags) on the left, notes on the right
    expect(columns[0].classes()).toContain('el-col-lg-8')
    expect(columns[1].classes()).toContain('el-col-lg-16')
    expect(columns[0].text()).toContain('v1.1.0')
    expect(columns[1].find('.md-preview-stub').exists()).toBe(true)
  })

  it('shows the notes of the selected release in the second column', async () => {
    vi.mocked(releaseNotesApi.list).mockResolvedValue({
      total: 2,
      items: [
        release(),
        release({ id: 2, tag_name: 'v1.2.0', name: 'v1.2.0', body: '## Later release' }),
      ],
    })

    const wrapper = mountView()
    await flushPromises()
    await selectRepository(wrapper)

    // the newest release is selected by default
    expect(wrapper.find('.nav-item.active').text()).toContain('v1.1.0')
    expect(wrapper.find('.md-preview-stub').text()).toContain('add login page')

    const items = wrapper.findAll('.nav-item')
    const later = items.find((item) => item.text().includes('v1.2.0'))!
    await later.trigger('click')
    await flushPromises()

    expect(wrapper.find('.nav-item.active').text()).toContain('v1.2.0')
    expect(wrapper.find('.md-preview-stub').text()).toContain('Later release')
    // the released meta of the selection is shown above the notes
    expect(wrapper.text()).toContain(
      enMessages.releaseNotes.released_by.replace('{author}', 'alice'),
    )
  })

  it('links the JIRA tickets of a note body written by hand', async () => {
    vi.mocked(rbacApi.getJiraSettings).mockResolvedValue({
      base_url: 'https://jira.local',
      project_keys: [],
    })
    vi.mocked(releaseNotesApi.list).mockResolvedValue({
      total: 1,
      items: [release({ body: '## Notes\n\n- ship the login fix PRL-123' })],
    })

    const wrapper = mountView()
    await flushPromises()
    await selectRepository(wrapper)

    const preview = wrapper.find('.md-preview-stub').text()
    expect(preview).toContain('- ship the login fix [PRL-123](https://jira.local/browse/PRL-123)')
  })

  it('keeps a hand written note body as typed while JIRA is not configured', async () => {
    vi.mocked(releaseNotesApi.list).mockResolvedValue({
      total: 1,
      items: [release({ body: '## Notes\n\n- ship the login fix PRL-123' })],
    })

    const wrapper = mountView()
    await flushPromises()
    await selectRepository(wrapper)

    const preview = wrapper.find('.md-preview-stub').text()
    expect(preview).toContain('- ship the login fix PRL-123')
    expect(preview).not.toContain('browse/PRL-123')
  })

  it('drafts from the newest tag whatever order the provider returns', async () => {
    // Bitbucket Cloud lists tags oldest first (alphabetically)
    vi.mocked(releaseDiffApi.listRefs).mockResolvedValue({
      ...REFS,
      tags: ['v0.1.0', 'v0.2.0', 'v0.3.0'],
      branches: ['feature/Pylang'],
    } as never)

    const wrapper = mountView()
    await flushPromises()
    await selectRepository(wrapper)

    expect(wrapper.find('.form-card').exists()).toBe(false)
    await buttonsByLabel(wrapper, enMessages.releaseNotes.draft_new)[0].trigger('click')
    await flushPromises()

    const tagSelect = selectByPlaceholder(wrapper, enMessages.releaseNotes.tag_placeholder)
    // the newest tag is preselected, not the first entry of the provider
    expect(tagSelect.props('modelValue')).toBe('v0.3.0')
    expect(
      tagSelect
        .findAllComponents({ name: 'ElOption' })
        .map((option: AnyWrapper) => option.props('label')),
    ).toEqual(['v0.3.0', 'v0.2.0', 'v0.1.0'])
  })

  it('ignores repeated ref names coming from the provider', async () => {
    vi.mocked(releaseDiffApi.listRefs).mockResolvedValue({
      ...REFS,
      tags: ['v0.1.0', 'v0.1.0', 'v0.2.0', 'v0.2.0'],
      branches: ['main', 'main'],
    } as never)
    vi.mocked(releaseNotesApi.preview).mockResolvedValue(preview([]))

    const wrapper = mountView()
    await flushPromises()
    await selectRepository(wrapper)

    await selectTab(wrapper, enMessages.releaseNotes.panel_tags)

    expect(wrapper.findAll('.tag-item').map((item: AnyWrapper) => item.text())).toEqual([
      'v0.2.0',
      'v0.1.0',
    ])
  })

  it('maps a tag of the tags tab to the commits it released', async () => {
    vi.mocked(releaseDiffApi.listRefs).mockResolvedValue({
      ...REFS,
      tags: ['v1.2.0', 'v1.1.0', 'v1.0.0'],
    } as never)
    vi.mocked(releaseNotesApi.preview).mockResolvedValue(preview([PREVIEW_COMMIT]))

    const wrapper = mountView()
    await flushPromises()
    await selectRepository(wrapper)

    await selectTab(wrapper, enMessages.releaseNotes.panel_tags)

    // the newest tag is selected and scoped against the next older one
    expect(releaseNotesApi.preview).toHaveBeenCalledWith(
      expect.objectContaining({
        project_key: 'ALPHA',
        repository_slug: 'alpha-api',
        version: 'v1.2.0',
        previous_version: 'v1.1.0',
      }),
    )
    expect(wrapper.text()).toContain(
      enMessages.releaseNotes.tag_commits_title.replace('{tag}', 'v1.2.0'),
    )
    expect(wrapper.text()).toContain(
      enMessages.releaseNotes.range.replace('{from}', 'v1.1.0').replace('{to}', 'v1.2.0'),
    )
    expect(wrapper.find('.commit-table').text()).toContain('abc1234')

    // the oldest tag has no predecessor: its full history is listed
    const oldest = wrapper
      .findAll('.tag-item')
      .find((item) => item.text() === 'v1.0.0')!
    await oldest.trigger('click')
    await flushPromises()

    expect(releaseNotesApi.preview).toHaveBeenLastCalledWith(
      expect.objectContaining({ version: 'v1.0.0', previous_version: undefined }),
    )
    expect(wrapper.text()).toContain(
      enMessages.releaseNotes.full_history.replace('{tag}', 'v1.0.0'),
    )
  })

  it('shows a note icon only for tags that have a release', async () => {
    vi.mocked(releaseDiffApi.listRefs).mockResolvedValue({
      ...REFS,
      tags: ['v1.2.0', 'v1.1.0'],
    } as never)
    vi.mocked(releaseNotesApi.preview).mockResolvedValue(preview([]))

    const wrapper = mountView()
    await flushPromises()
    await selectRepository(wrapper)
    await selectTab(wrapper, enMessages.releaseNotes.panel_tags)

    const tagItems = wrapper.findAll('.tag-item')
    // v1.2.0 has no release, v1.1.0 does
    expect(tagItems[0].find('.tag-note-link').exists()).toBe(false)
    expect(tagItems[1].find('.tag-note-link').exists()).toBe(true)
  })

  it('opens the release note of a tag from the note icon', async () => {
    vi.mocked(releaseDiffApi.listRefs).mockResolvedValue({
      ...REFS,
      tags: ['v1.2.0', 'v1.1.0'],
    } as never)
    vi.mocked(releaseNotesApi.preview).mockResolvedValue(preview([]))

    const wrapper = mountView()
    await flushPromises()
    await selectRepository(wrapper)
    await selectTab(wrapper, enMessages.releaseNotes.panel_tags)

    // clicking the icon must not fall through to the commits of the tag
    const commitsLoads = vi.mocked(releaseNotesApi.preview).mock.calls.length
    const released = wrapper.findAll('.tag-item')[1]
    await released.find('.tag-note-link').trigger('click')
    await flushPromises()

    // the releases tab is back and the release of that tag is selected
    expect(activeTabLabel(wrapper)).toBe(enMessages.releaseNotes.list_title)
    expect(wrapper.find('.nav-item.active').text()).toContain('v1.1.0')
    expect(wrapper.find('.md-preview-stub').text()).toContain('add login page')
    expect(vi.mocked(releaseNotesApi.preview).mock.calls.length).toBe(commitsLoads)
  })

  it('pages the releases tab to the note of a tag living on another page', async () => {
    const manyNotes = Array.from({ length: 25 }, (_, index) =>
      release({
        id: index + 1,
        tag_name: `v1.${25 - index}.0`,
        name: `v1.${25 - index}.0`,
        body: `## release v1.${25 - index}.0`,
      }),
    )
    const wanted = manyNotes[22] // page 3 with a page size of 10
    vi.mocked(releaseNotesApi.list).mockImplementation(async (params) => {
      const offset = params?.offset ?? 0
      if ((params?.limit ?? 0) > 10) {
        // the lookup from the tags tab asks for the whole list
        return { total: manyNotes.length, items: manyNotes }
      }
      return {
        total: manyNotes.length,
        items: manyNotes.slice(offset, offset + (params?.limit ?? 10)),
      }
    })
    vi.mocked(releaseDiffApi.listRefs).mockResolvedValue({
      ...REFS,
      tags: [wanted.tag_name, 'v1.1.0'],
    } as never)
    vi.mocked(releaseNotesApi.preview).mockResolvedValue(preview([]))

    const wrapper = mountView()
    await flushPromises()
    await selectRepository(wrapper)
    await selectTab(wrapper, enMessages.releaseNotes.panel_tags)

    await wrapper.findAll('.tag-item')[0].find('.tag-note-link').trigger('click')
    await flushPromises()

    expect(releaseNotesApi.list).toHaveBeenLastCalledWith(
      expect.objectContaining({ limit: 10, offset: 20 }),
    )
    expect(wrapper.find('.nav-item.active').text()).toContain(wanted.tag_name)
    expect(wrapper.find('.md-preview-stub').text()).toContain(wanted.body)
  })

  it('walks the capped pages of the release list when indexing the tags', async () => {
    const allNotes = Array.from({ length: 450 }, (_, index) =>
      release({
        id: index + 1,
        tag_name: `v1.${450 - index}.0`,
        name: `v1.${450 - index}.0`,
        body: `## release ${index}`,
      }),
    )
    const wanted = allNotes[320] // page 33 at a page size of 10
    const unreleased = 'v0.9.0' // no release note for this one
    const requested: Array<{ limit: number; offset: number }> = []
    vi.mocked(releaseNotesApi.list).mockImplementation(async (params) => {
      const limit = params?.limit ?? 50
      const offset = params?.offset ?? 0
      requested.push({ limit, offset })
      return { total: allNotes.length, items: allNotes.slice(offset, offset + limit) }
    })
    vi.mocked(releaseDiffApi.listRefs).mockResolvedValue({
      ...REFS,
      tags: [wanted.tag_name, unreleased],
    } as never)
    vi.mocked(releaseNotesApi.preview).mockResolvedValue(preview([]))

    const wrapper = mountView()
    await flushPromises()
    await selectRepository(wrapper)
    await selectTab(wrapper, enMessages.releaseNotes.panel_tags)

    // 200 is the backend cap for GET /release/notes - asking for more answers 422
    const indexRequests = requested.filter((call) => call.limit === 200)
    expect(indexRequests.map((call) => call.offset)).toEqual([0, 200, 400])

    const tagItems = wrapper.findAll('.tag-item')
    expect(tagItems[0].find('.tag-note-link').exists()).toBe(true)
    expect(tagItems[1].find('.tag-note-link').exists()).toBe(false)

    await tagItems[0].find('.tag-note-link').trigger('click')
    await flushPromises()

    expect(releaseNotesApi.list).toHaveBeenLastCalledWith(
      expect.objectContaining({ limit: 10, offset: 320 }),
    )
    expect(wrapper.find('.nav-item.active').text()).toContain(wanted.tag_name)
    expect(wrapper.find('.md-preview-stub').text()).toContain(wanted.body)
  })

  it('offers to draft a release from the selected tag', async () => {
    vi.mocked(releaseDiffApi.listRefs).mockResolvedValue({
      ...REFS,
      tags: ['v1.2.0', 'v1.1.0'],
    } as never)
    vi.mocked(releaseNotesApi.preview).mockResolvedValue(preview([]))

    const wrapper = mountView()
    await flushPromises()
    await selectRepository(wrapper)
    await selectTab(wrapper, enMessages.releaseNotes.panel_tags)

    await buttonsByLabel(wrapper, enMessages.releaseNotes.draft_for_tag)[0].trigger('click')
    await flushPromises()

    const tagSelect = selectByPlaceholder(wrapper, enMessages.releaseNotes.tag_placeholder)
    expect(tagSelect.props('modelValue')).toBe('v1.2.0')
  })

  it('paginates the releases on the server', async () => {
    vi.mocked(releaseNotesApi.list).mockResolvedValue({ total: 30, items: [release()] })

    const wrapper = mountView()
    await flushPromises()
    await selectRepository(wrapper)

    const pager = wrapper.findComponent({ name: 'ElPagination' })
    expect(pager.props('total')).toBe(30)

    // Element Plus emits kebab-case update events
    pager.vm.$emit('update:current-page', 2)
    await flushPromises()

    expect(releaseNotesApi.list).toHaveBeenLastCalledWith(
      expect.objectContaining({ limit: 10, offset: 10 }),
    )

    // a bigger page size asks the backend for more releases at once
    wrapper.findComponent({ name: 'ElPagination' }).vm.$emit('update:page-size', 50)
    await flushPromises()

    expect(releaseNotesApi.list).toHaveBeenLastCalledWith(
      expect.objectContaining({ limit: 50, offset: 0 }),
    )
  })

  it('paginates the tags in the browser', async () => {
    const manyTags = Array.from({ length: 25 }, (_, index) => `v1.${25 - index}.0`)
    vi.mocked(releaseDiffApi.listRefs).mockResolvedValue({ ...REFS, tags: manyTags } as never)
    vi.mocked(releaseNotesApi.preview).mockResolvedValue(preview([]))

    const wrapper = mountView()
    await flushPromises()
    await selectRepository(wrapper)
    await selectTab(wrapper, enMessages.releaseNotes.panel_tags)

    expect(wrapper.findAll('.tag-item')).toHaveLength(20)

    const pager = wrapper.findComponent({ name: 'ElPagination' })
    expect(pager.props('total')).toBe(25)

    pager.vm.$emit('update:current-page', 2)
    await flushPromises()

    expect(wrapper.findAll('.tag-item')).toHaveLength(5)
    // no extra provider round trip: the tags are already in memory
    expect(releaseDiffApi.listRefs).toHaveBeenCalledTimes(1)
  })

  it('keeps the editor closed until it is requested', async () => {
    const wrapper = mountView()
    await flushPromises()
    await selectRepository(wrapper)

    // the notes of the selected release are shown instead of the editor
    expect(wrapper.find('.editor-form').exists()).toBe(false)
    expect(wrapper.find('.md-editor-stub').exists()).toBe(false)
    expect(wrapper.find('.md-preview-stub').exists()).toBe(true)

    await buttonsByLabel(wrapper, enMessages.releaseNotes.draft_new)[0].trigger('click')
    await flushPromises()

    expect(wrapper.find('.editor-form').exists()).toBe(true)
    expect(wrapper.find('.md-editor-stub').exists()).toBe(true)

    // closing it brings the notes of the selection back
    await buttonsByLabel(wrapper, enMessages.releaseNotes.close_editor)[0].trigger('click')
    await flushPromises()

    expect(wrapper.find('.editor-form').exists()).toBe(false)
    expect(wrapper.find('.md-preview-stub').exists()).toBe(true)
  })

  it('closes the editor after a release is saved and selects it', async () => {
    const wrapper = mountView()
    await flushPromises()
    await selectRepository(wrapper)

    await buttonsByLabel(wrapper, enMessages.releaseNotes.draft_new)[0].trigger('click')
    await flushPromises()

    await buttonsByLabel(wrapper, enMessages.releaseNotes.save_draft)[0].trigger('click')
    await flushPromises()

    expect(releaseNotesApi.create).toHaveBeenCalled()
    expect(wrapper.find('.editor-form').exists()).toBe(false)
  })

  it('follows the dark theme in the markdown preview and editor', async () => {
    document.documentElement.setAttribute('data-theme', 'dark')

    try {
      const wrapper = mountView()
      await flushPromises()
      await selectRepository(wrapper)

      expect(wrapper.findComponent({ name: 'MdPreview' }).props('theme')).toBe('dark')

      await buttonsByLabel(wrapper, enMessages.releaseNotes.draft_new)[0].trigger('click')
      await flushPromises()

      expect(wrapper.findComponent({ name: 'MdEditor' }).props('theme')).toBe('dark')
    } finally {
      document.documentElement.setAttribute('data-theme', 'light')
    }
  })

  it('switches the markdown theme when the app theme changes', async () => {
    document.documentElement.setAttribute('data-theme', 'light')

    try {
      const wrapper = mountView()
      await flushPromises()
      await selectRepository(wrapper)

      await buttonsByLabel(wrapper, enMessages.releaseNotes.draft_new)[0].trigger('click')
      await flushPromises()

      expect(wrapper.findComponent({ name: 'MdEditor' }).props('theme')).toBe('light')
      // the notes panel is replaced by the editor, so close it to check the preview
      await buttonsByLabel(wrapper, enMessages.releaseNotes.close_editor)[0].trigger('click')
      await flushPromises()
      expect(wrapper.findComponent({ name: 'MdPreview' }).props('theme')).toBe('light')

      document.documentElement.setAttribute('data-theme', 'dark')
      // MutationObserver callbacks are microtasks - let them run before asserting
      await new Promise((resolve) => setTimeout(resolve, 0))
      await nextTick()

      expect(wrapper.findComponent({ name: 'MdPreview' }).props('theme')).toBe('dark')
    } finally {
      document.documentElement.setAttribute('data-theme', 'light')
    }
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
