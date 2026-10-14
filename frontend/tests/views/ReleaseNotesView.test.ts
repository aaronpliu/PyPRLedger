import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import ElementPlus, { ElMessage, ElMessageBox } from 'element-plus'
import { createI18n } from 'vue-i18n'
import ReleaseNotesView from '@/views/releases/ReleaseNotesView.vue'
import { projectsApi } from '@/api/projects'
import { rbacApi } from '@/api/rbac'
import { releaseDiffApi } from '@/api/releaseDiff'
import { releaseNotesApi, type ReleaseNote } from '@/api/releaseNotes'
import { llmApi } from '@/api/llm'
import { resetJiraSettings } from '@/composables/useJira'
import { useAuthStore } from '@/stores/auth'
import { copyTextToClipboard, downloadMarkdown } from '@/utils/export/markdown'
import enMessages from '@/locales/en.json'

// The document comes from the backend: the browser only hands the bytes over
vi.mock('@/utils/export/markdown', () => ({
  downloadMarkdown: vi.fn(),
  copyTextToClipboard: vi.fn().mockResolvedValue(true),
}))

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

// The AI summary switch is only offered when the deployment has an LLM
vi.mock('@/api/llm', () => ({
  llmApi: {
    getConfig: vi.fn(),
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
    exportNotes: vi.fn(),
    confluenceStatus: vi.fn(),
    syncToConfluence: vi.fn(),
  },
}))

// md-editor-v3 needs a real layout engine - stub it with plain inputs
vi.mock('md-editor-v3', () => ({
  MdEditor: {
    name: 'MdEditor',
    props: ['modelValue', 'theme', 'toolbars', 'previewTheme', 'language'],
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

/** The scope of a tag whose predecessor the server resolved and verified. */
const RESOLVED_SCOPE = {
  previous_version: 'v1.1.0' as string | null,
  previous_sha: null as string | null,
  version_sha: null as string | null,
  previous_source: 'ancestor' as const,
  previous_verified: true,
  scope_reason: 'resolved' as const,
}

/** Preview payload (the note body is irrelevant for the tag -> commits view). */
function preview(
  commits: (typeof PREVIEW_COMMIT)[] = [],
  overrides: Record<string, unknown> = {},
) {
  return {
    version: 'v1.2.0',
    ...RESOLVED_SCOPE,
    suggested_name: 'v1.2.0',
    body: '## What’s Changed',
    commit_count: commits.length,
    commits,
    truncated: false,
    ...overrides,
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

/**
 * Open the overflow menu of one release entry.
 *
 * The control sits on the entry; the menu itself is teleported to the document,
 * and only the menu that was opened is rendered - which is what makes reading it
 * from there unambiguous.
 */
async function openNoteMenu(wrapper: AnyWrapper, index = 0) {
  const menus = wrapper.findAll('[data-test="note-menu"]')
  expect(menus.length, 'no release entry offers a menu').toBeGreaterThan(index)
  await menus[index].trigger('click')
  await flushPromises()
  await nextTick()
}

/** One item of an open release menu, by the command it carries. */
function noteMenuItem(command: string): HTMLElement | undefined {
  const items = document.querySelectorAll<HTMLElement>(`[data-test="note-menu-${command}"]`)
  return items.length ? items[items.length - 1] : undefined
}

/** Ask one release's menu to do something, the way a reader would. */
async function useNoteMenu(wrapper: AnyWrapper, command: string, index = 0) {
  await openNoteMenu(wrapper, index)
  const item = noteMenuItem(command)
  expect(item, `the menu offers no '${command}' item`).toBeTruthy()
  item!.dispatchEvent(new MouseEvent('click', { bubbles: true }))
  await flushPromises()
  await nextTick()
}

function selectByPlaceholder(wrapper: AnyWrapper, placeholder: string) {
  return wrapper
    .findAllComponents({ name: 'ElSelect' })
    .find((select: AnyWrapper) => select.props('placeholder') === placeholder)
}

/** The pager of the reading column (the navigator carries one of its own). */
function detailPager(wrapper: AnyWrapper) {
  return wrapper
    .findAllComponents({ name: 'ElPagination' })
    .find((pager: AnyWrapper) => pager.classes().includes('detail-pagination'))
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
  // let the coordinate watcher load the refs / notes of the new repository
  await nextTick()
}

/** Names of the tags on the visible page of the tag navigator. */
function tagNames(wrapper: AnyWrapper) {
  return wrapper
    .findAll('.nav-item.tag-item .nav-item-name')
    .map((name: AnyWrapper) => name.text())
}

/** Type into the search box of the tag navigator. */
async function setTagSearch(wrapper: AnyWrapper, value: string) {
  const input = wrapper.find(
    `input[placeholder="${enMessages.releaseNotes.tags_search_placeholder}"]`,
  )
  expect(input.exists()).toBe(true)
  await input.setValue(value)
  await flushPromises()
}

// The page under test is the heaviest of the application: three columns, two paginated
// lists, a markdown editor, and a tag index that walks the whole release list. The
// tests that walk its pagination take two to three seconds where the rest take a
// fraction of one, and the five seconds every test is given by default is what made
// them flake on a loaded machine - so the file says what its own tests may take.
describe('ReleaseNotesView', { timeout: 20_000 }, () => {
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
    // Confluence is absent unless a test asks for it
    vi.mocked(releaseNotesApi.confluenceStatus).mockResolvedValue({
      configured: false,
      auto_sync: false,
    })
    // no LLM configured unless a test asks for one
    vi.mocked(llmApi.getConfig).mockResolvedValue({ enabled: false, model: '', base_url: '' })
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

    // a draft is the one state that offers publishing, and it is in the menu
    await openNoteMenu(wrapper)
    expect(noteMenuItem('publish')?.textContent?.trim()).toBe(enMessages.releaseNotes.publish)

    await useNoteMenu(wrapper, 'publish')

    expect(releaseNotesApi.update).toHaveBeenCalledWith(1, { status: 'published' })
  })

  it('leaves publishing out of the menu of a release that is already out', async () => {
    const wrapper = mountView()
    await flushPromises()
    await selectRepository(wrapper)

    await openNoteMenu(wrapper)

    expect(noteMenuItem('publish')).toBeUndefined()
    expect(noteMenuItem('edit')).toBeDefined()
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
    // no LLM configured: the AI summary is not offered and is not asked for
    expect(wrapper.text()).toContain(enMessages.releaseNotes.ai_summary_unavailable)
    expect(releaseNotesApi.preview).toHaveBeenCalledWith(
      expect.objectContaining({ summarize: false, language: 'en' }),
    )
  })

  it('asks for an AI summary when the deployment has an LLM', async () => {
    vi.mocked(llmApi.getConfig).mockResolvedValue({
      enabled: true,
      model: 'test-model',
      base_url: 'https://llm.local/v1',
    })
    vi.mocked(releaseNotesApi.preview).mockResolvedValue({
      ...preview([], { version: 'v1.1.0', commit_count: 3 }),
      summary: 'Adds single sign-on.',
      summary_source: 'llm',
    })

    const wrapper = mountView()
    await flushPromises()
    await selectRepository(wrapper)

    await buttonsByLabel(wrapper, enMessages.releaseNotes.draft_new)[0].trigger('click')
    await flushPromises()

    const aiSummary = wrapper
      .findAllComponents({ name: 'ElCheckbox' })
      .find((box: AnyWrapper) => box.text() === enMessages.releaseNotes.ai_summary)
    expect(aiSummary).toBeDefined()
    await aiSummary!.vm.$emit('update:modelValue', true)
    await flushPromises()

    await buttonsByLabel(wrapper, enMessages.releaseNotes.generate_notes)[0].trigger('click')
    await flushPromises()

    expect(releaseNotesApi.preview).toHaveBeenCalledWith(
      expect.objectContaining({ summarize: true }),
    )
    expect(wrapper.text()).toContain(enMessages.releaseNotes.generated_with_ai)
  })

  it('says so when the AI summary it asked for could not be made', async () => {
    vi.mocked(llmApi.getConfig).mockResolvedValue({
      enabled: true,
      model: 'test-model',
      base_url: 'https://llm.local/v1',
    })
    vi.mocked(releaseNotesApi.preview).mockResolvedValue({
      ...preview([], { version: 'v1.1.0', commit_count: 3 }),
      summary: null,
      summary_source: 'deterministic',
      summary_notice: 'not_configured',
    })

    const wrapper = mountView()
    await flushPromises()
    await selectRepository(wrapper)

    await buttonsByLabel(wrapper, enMessages.releaseNotes.draft_new)[0].trigger('click')
    await flushPromises()

    const aiSummary = wrapper
      .findAllComponents({ name: 'ElCheckbox' })
      .find((box: AnyWrapper) => box.text() === enMessages.releaseNotes.ai_summary)
    await aiSummary!.vm.$emit('update:modelValue', true)
    await flushPromises()

    // nothing has been asked of the server yet, so the switch explains itself
    expect(wrapper.text()).toContain(enMessages.releaseNotes.ai_summary_help)
    expect(wrapper.text()).not.toContain(
      enMessages.releaseNotes.ai_summary_fallback_not_configured,
    )

    await buttonsByLabel(wrapper, enMessages.releaseNotes.generate_notes)[0].trigger('click')
    await flushPromises()

    // the notes on screen came from the commit subjects, and the form says why
    expect(wrapper.text()).toContain(
      enMessages.releaseNotes.ai_summary_fallback_not_configured,
    )
    expect(wrapper.text()).not.toContain(enMessages.releaseNotes.generated_with_ai)
  })

  it('shows what the LLM answered when it refused the call', async () => {
    vi.mocked(llmApi.getConfig).mockResolvedValue({
      enabled: true,
      model: 'test-model',
      base_url: 'https://llm.local/v1',
    })
    vi.mocked(releaseNotesApi.preview).mockResolvedValue({
      ...preview([], { version: 'v1.1.0', commit_count: 3 }),
      summary: null,
      summary_source: 'deterministic',
      summary_notice: 'provider_error',
      summary_error: 'HTTP 404: model `test-model` not found',
    })

    const wrapper = mountView()
    await flushPromises()
    await selectRepository(wrapper)

    await buttonsByLabel(wrapper, enMessages.releaseNotes.draft_new)[0].trigger('click')
    await flushPromises()

    const aiSummary = wrapper
      .findAllComponents({ name: 'ElCheckbox' })
      .find((box: AnyWrapper) => box.text() === enMessages.releaseNotes.ai_summary)
    await aiSummary!.vm.$emit('update:modelValue', true)
    await flushPromises()

    await buttonsByLabel(wrapper, enMessages.releaseNotes.generate_notes)[0].trigger('click')
    await flushPromises()

    // the reason, and the answer that names what to change
    expect(wrapper.text()).toContain(enMessages.releaseNotes.ai_summary_fallback_provider_error)
    expect(wrapper.text()).toContain('HTTP 404: model `test-model` not found')
  })

  it('edits the notes with the rendered markdown beside them', async () => {
    const wrapper = mountView()
    await flushPromises()
    await selectRepository(wrapper)

    await buttonsByLabel(wrapper, enMessages.releaseNotes.draft_new)[0].trigger('click')
    await flushPromises()

    const editor = wrapper.findComponent({ name: 'MdEditor' })
    // the toolbar offers the preview: what is being typed can be read as it will
    // be published, and the markdown can be put aside for a moment
    expect(editor.props('toolbars')).toEqual(
      expect.arrayContaining(['preview', 'previewOnly', 'catalog']),
    )
    // the preview is the one a reader gets, not a second rendering of its own
    expect(editor.props('previewTheme')).toBe('github')
    expect(editor.props('language')).toBe('en-US')
  })

  it('deletes a release after confirmation', async () => {
    const confirmSpy = vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm' as any)

    const wrapper = mountView()
    await flushPromises()
    await selectRepository(wrapper)

    // the destructive one is set apart and marked, so it is not hit by accident,
    // and the way in is a labelled control rather than a bare glyph
    await openNoteMenu(wrapper)
    const remove = noteMenuItem('delete')
    expect(remove?.className).toContain('note-menu-danger')
    // Element Plus draws `divided` as a rule before the item rather than a class
    expect(remove?.previousElementSibling?.className).toContain(
      'el-dropdown-menu__item--divided',
    )
    expect(wrapper.findAll('[data-test="note-menu"]')[0].attributes('aria-label')).toBe(
      enMessages.releaseNotes.more_actions,
    )

    await useNoteMenu(wrapper, 'delete')

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

    await useNoteMenu(wrapper, 'delete')

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
    // the restriction is a label only: no banner above the page
    expect(wrapper.find('.el-alert').exists()).toBe(false)
    const readOnlyTag = wrapper.find('.read-only-tag')
    expect(readOnlyTag.exists()).toBe(true)
    expect(readOnlyTag.text()).toContain(enMessages.releaseNotes.read_only_title)
    // the explanation is kept in the tooltip of the label
    const readOnlyTooltip = wrapper
      .findAllComponents({ name: 'ElTooltip' })
      .find((tooltip: AnyWrapper) => tooltip.find('.read-only-tag').exists())
    expect(readOnlyTooltip!.props('content')).toBe(enMessages.releaseNotes.read_only_help)
    // but no management affordances
    expect(buttonsByLabel(wrapper, enMessages.releaseNotes.draft_new)).toHaveLength(0)
    // nothing to manage and nowhere to go: the entry offers no menu at all
    expect(wrapper.findAll('[data-test="note-menu"]')).toHaveLength(0)
    expect(noteMenuItem('edit')).toBeUndefined()
    expect(noteMenuItem('delete')).toBeUndefined()
    expect(wrapper.find('.md-editor-stub').exists()).toBe(false)
  })

  it('offers a reader the release page and nothing to manage', async () => {
    signIn(['viewer'])
    const openSpy = vi.spyOn(window, 'open').mockReturnValue(null)
    vi.mocked(releaseNotesApi.list).mockResolvedValue({
      total: 1,
      items: [release({ external_url: 'https://git.local/ALPHA/alpha-api/releases/v1.1.0' })],
    })

    const wrapper = mountView()
    await flushPromises()
    await selectRepository(wrapper)

    // The menu stays where it is, even holding a single item: a reader finds the
    // release page in the same place whoever they are.
    await openNoteMenu(wrapper)
    expect(noteMenuItem('provider')?.textContent?.trim()).toBe(
      enMessages.releaseNotes.view_on_provider,
    )
    expect(noteMenuItem('edit')).toBeUndefined()
    expect(noteMenuItem('delete')).toBeUndefined()

    await useNoteMenu(wrapper, 'provider')
    expect(openSpy).toHaveBeenCalledWith(
      'https://git.local/ALPHA/alpha-api/releases/v1.1.0',
      '_blank',
      'noopener',
    )
    openSpy.mockRestore()
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

  it('shows every release of the page and marks the one in focus', async () => {
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

    // the newest release is in focus, and both releases of the page are rendered
    expect(wrapper.find('.nav-item.active').text()).toContain('v1.1.0')
    const entries = wrapper.findAll('.note-entry')
    expect(entries).toHaveLength(2)
    expect(entries[0].find('.md-preview-stub').text()).toContain('add login page')
    expect(entries[1].find('.md-preview-stub').text()).toContain('Later release')

    const items = wrapper.findAll('.nav-item')
    const later = items.find((item) => item.text().includes('v1.2.0'))!
    await later.trigger('click')
    await flushPromises()

    expect(wrapper.find('.nav-item.active').text()).toContain('v1.2.0')
    // the navigator brings the entry into focus instead of replacing the others
    expect(wrapper.findAll('.note-entry')).toHaveLength(2)
    expect(wrapper.findAll('.note-entry.focused')).toHaveLength(1)
    expect(wrapper.find('.note-entry.focused').attributes('data-note-id')).toBe('2')
    // the released meta of a release is shown above its notes
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
    expect(panel.find('form').exists()).toBe(true)

    await toggle.trigger('click')

    expect(toggle.attributes('aria-expanded')).toBe('true')
    expect(panel.classes()).not.toContain('is-collapsed')
  })

  it('lists the tags in the order the provider lists them, and searches them by name', async () => {
    // the provider answers newest first, which is the order Bitbucket defines: a
    // patch cut for an older line is newer than the release that follows it in
    // version order, and a version sort is what used to bury the tag just cut
    vi.mocked(releaseDiffApi.listRefs).mockResolvedValue({
      ...REFS,
      tags: ['v1.1.1', 'v2.0.0-rc1', 'v1.1.0', 'v1.0.0'],
    } as never)

    const wrapper = mountView()
    await flushPromises()
    await selectRepository(wrapper)
    await selectTab(wrapper, enMessages.releaseNotes.panel_tags)

    // The box a reader types a tag into is a full-sized field: 40px with 14px text,
    // where the small size it had been left at is 24px with 12px text. Its height is
    // written on the input itself, which is what the test environment can see - the
    // stylesheet beside it is not applied by jsdom, a style on the element is - and
    // the field it belongs to is the input's wrapper, the hook riding on the inner one.
    const searchInput = wrapper.find('[data-test="tags-search"]')
    expect(searchInput.attributes('style')).toContain('height: 38px')
    expect(searchInput.attributes('style')).toContain('font-size: 14px')

    const searchField = searchInput.element.closest('.el-input')
    expect(searchField?.classList.contains('el-input--small')).toBe(false)
    expect(searchField?.classList.contains('el-input--large')).toBe(true)

    // the listing is shown as it arrived, tag for tag
    expect(tagNames(wrapper)).toEqual(['v1.1.1', 'v2.0.0-rc1', 'v1.1.0', 'v1.0.0'])

    await setTagSearch(wrapper, '1.1')

    expect(tagNames(wrapper)).toEqual(['v1.1.1', 'v1.1.0'])

    await setTagSearch(wrapper, 'rc')

    expect(tagNames(wrapper)).toEqual(['v2.0.0-rc1'])

    // a search that matches nothing says so instead of looking like an empty repo
    await setTagSearch(wrapper, 'nope')
    expect(tagNames(wrapper)).toEqual([])
    expect(wrapper.text()).toContain(enMessages.releaseNotes.tags_no_match)
    expect(wrapper.text()).not.toContain(enMessages.releaseNotes.tags_empty)

    // and clearing it brings the whole list back
    await setTagSearch(wrapper, '')
    expect(tagNames(wrapper)).toEqual(['v1.1.1', 'v2.0.0-rc1', 'v1.1.0', 'v1.0.0'])
  })

  it('badges the selected tag instead of the release of the other tab', async () => {
    vi.mocked(releaseDiffApi.listRefs).mockResolvedValue({
      ...REFS,
      tags: ['v0.1.0', 'v0.2.0', 'v0.3.0'],
    } as never)
    vi.mocked(releaseNotesApi.list).mockResolvedValue({
      total: 2,
      items: [
        release(),
        release({ id: 2, tag_name: 'v0.2.0', name: 'v0.2.0', is_latest: false }),
      ],
    })
    vi.mocked(releaseNotesApi.preview).mockResolvedValue(preview([]))

    const wrapper = mountView()
    await flushPromises()
    await selectRepository(wrapper)
    await selectTab(wrapper, enMessages.releaseNotes.panel_tags)

    const row = wrapper
      .findAll('.tag-item')
      .find((item: AnyWrapper) => item.text() === 'v0.2.0')
    await row!.trigger('click')
    await flushPromises()

    const header = wrapper.find('.detail-card .section-title').text()
    expect(header).toContain(
      enMessages.releaseNotes.tag_commits_title.replace('{tag}', 'v0.2.0'),
    )
    // the release badges of the releases tab (tag v1.1.0, "Latest") stay there
    expect(header).not.toContain('v1.1.0')
    expect(header).not.toContain(enMessages.releaseNotes.badge_latest)
  })

  it('drafts for the tag selected in the tags navigator', async () => {
    vi.mocked(releaseDiffApi.listRefs).mockResolvedValue({
      ...REFS,
      tags: ['v0.1.0', 'v0.2.0', 'v0.3.0'],
    } as never)
    vi.mocked(releaseNotesApi.preview).mockResolvedValue(preview([]))

    const wrapper = mountView()
    await flushPromises()
    await selectRepository(wrapper)
    await selectTab(wrapper, enMessages.releaseNotes.panel_tags)

    // pick an older tag in the navigator
    const row = wrapper
      .findAll('.tag-item')
      .find((item: AnyWrapper) => item.text() === 'v0.2.0')
    await row!.trigger('click')
    await flushPromises()

    // the list header button must draft for that tag, not for the newest one
    await buttonsByLabel(wrapper, enMessages.releaseNotes.draft_new)[0].trigger('click')
    await flushPromises()

    const tagSelect = selectByPlaceholder(wrapper, enMessages.releaseNotes.tag_placeholder)
    expect(tagSelect.props('modelValue')).toBe('v0.2.0')
  })

  it('drafts from the newest tag, which is where the listing starts', async () => {
    // the provider answers newest first, and that is the order every tag picker of
    // this page offers them in
    vi.mocked(releaseDiffApi.listRefs).mockResolvedValue({
      ...REFS,
      tags: ['v0.3.0', 'v0.2.0', 'v0.1.0'],
      branches: ['feature/Pylang'],
    } as never)

    const wrapper = mountView()
    await flushPromises()
    await selectRepository(wrapper)

    expect(wrapper.find('.form-card').exists()).toBe(false)
    await buttonsByLabel(wrapper, enMessages.releaseNotes.draft_new)[0].trigger('click')
    await flushPromises()

    const tagSelect = selectByPlaceholder(wrapper, enMessages.releaseNotes.tag_placeholder)
    // the newest tag - the first entry of the listing - is what a draft opens on
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
      tags: ['v0.2.0', 'v0.2.0', 'v0.1.0', 'v0.1.0'],
      branches: ['main', 'main'],
    } as never)
    vi.mocked(releaseNotesApi.preview).mockResolvedValue(preview([]))

    const wrapper = mountView()
    await flushPromises()
    await selectRepository(wrapper)

    await selectTab(wrapper, enMessages.releaseNotes.panel_tags)

    // de-duplicated, and still in the order the provider answered in
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

    // The tag is scoped by the server: the browser only holds a page of tags, so
    // it must not decide the predecessor itself.
    expect(releaseNotesApi.preview).toHaveBeenCalledWith(
      expect.objectContaining({
        project_key: 'ALPHA',
        repository_slug: 'alpha-api',
        version: 'v1.2.0',
      }),
    )
    expect(vi.mocked(releaseNotesApi.preview).mock.calls[0][0]).not.toHaveProperty(
      'previous_version',
    )
    expect(wrapper.text()).toContain(
      enMessages.releaseNotes.tag_commits_title.replace('{tag}', 'v1.2.0'),
    )
    expect(wrapper.text()).toContain(
      enMessages.releaseNotes.range.replace('{from}', 'v1.1.0').replace('{to}', 'v1.2.0'),
    )
    expect(wrapper.find('.commit-table').text()).toContain('abc1234')

    // the oldest tag has no predecessor: the scope says so instead of reporting a
    // repository limit
    vi.mocked(releaseNotesApi.preview).mockResolvedValue(
      preview([], {
        previous_version: null,
        previous_source: 'none',
        previous_verified: false,
        scope_reason: 'first_release',
      }),
    )
    const oldest = wrapper
      .findAll('.tag-item')
      .find((item) => item.text() === 'v1.0.0')!
    await oldest.trigger('click')
    await flushPromises()

    expect(releaseNotesApi.preview).toHaveBeenLastCalledWith(
      expect.objectContaining({ version: 'v1.0.0' }),
    )
    expect(vi.mocked(releaseNotesApi.preview).mock.calls[1][0]).not.toHaveProperty(
      'previous_version',
    )
    expect(wrapper.text()).toContain(
      enMessages.releaseNotes.scope_first_release.replace('{tag}', 'v1.0.0'),
    )
  })

  it('shows the revisions the scope was pinned to next to the refs', async () => {
    vi.mocked(releaseDiffApi.listRefs).mockResolvedValue({
      ...REFS,
      tags: ['v1.2.0', 'v1.1.0'],
    } as never)
    vi.mocked(releaseNotesApi.preview).mockResolvedValue(
      preview([], {
        previous_sha: '1111111aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
        version_sha: '2222222bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
      }),
    )

    const wrapper = mountView()
    await flushPromises()
    await selectRepository(wrapper)
    await selectTab(wrapper, enMessages.releaseNotes.panel_tags)

    expect(wrapper.text()).toContain('v1.1.0 (1111111)...v1.2.0 (2222222)')
  })

  it('warns when the predecessor was inferred from the tag order', async () => {
    vi.mocked(releaseDiffApi.listRefs).mockResolvedValue({
      ...REFS,
      tags: ['v1.2.0', 'v1.1.0'],
    } as never)
    vi.mocked(releaseNotesApi.preview).mockResolvedValue(
      preview([], { previous_source: 'name_order', previous_verified: false }),
    )

    const wrapper = mountView()
    await flushPromises()
    await selectRepository(wrapper)
    await selectTab(wrapper, enMessages.releaseNotes.panel_tags)

    // the scope is still used, but the panel says it was not proven
    expect(wrapper.text()).toContain('v1.1.0...v1.2.0')
    expect(wrapper.find('.el-alert').text()).toContain(
      enMessages.releaseNotes.scope_inferred.replace('{from}', 'v1.1.0'),
    )
  })

  it('reports an unresolved scope instead of the repository history', async () => {
    vi.mocked(releaseDiffApi.listRefs).mockResolvedValue({
      ...REFS,
      tags: ['v1.2.0'],
    } as never)
    vi.mocked(releaseNotesApi.preview).mockResolvedValue(
      preview([PREVIEW_COMMIT], {
        previous_version: null,
        previous_source: 'none',
        previous_verified: false,
        scope_reason: 'unresolved',
      }),
    )

    const wrapper = mountView()
    await flushPromises()
    await selectRepository(wrapper)
    await selectTab(wrapper, enMessages.releaseNotes.panel_tags)

    expect(wrapper.text()).toContain(
      enMessages.releaseNotes.scope_unresolved.replace('{tag}', 'v1.2.0'),
    )
    expect(wrapper.find('.el-alert').exists()).toBe(false)
  })

  it('reports a trimmed listing as a display limit of the scope', async () => {
    vi.mocked(releaseDiffApi.listRefs).mockResolvedValue({
      ...REFS,
      tags: ['v1.2.0', 'v1.1.0'],
    } as never)
    vi.mocked(releaseNotesApi.preview).mockResolvedValue(
      preview([PREVIEW_COMMIT], { commit_count: 12, truncated: true }),
    )

    const wrapper = mountView()
    await flushPromises()
    await selectRepository(wrapper)
    await selectTab(wrapper, enMessages.releaseNotes.panel_tags)

    expect(wrapper.find('.el-alert').text()).toContain(
      enMessages.releaseNotes.commits_trimmed
        .replace('{shown}', '1')
        .replace('{count}', '12'),
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
    // the release is rendered as one entry of that page, with its notes
    const entry = wrapper.find(`[data-note-id="${wanted.id}"]`)
    expect(entry.exists()).toBe(true)
    expect(entry.find('.md-preview-stub').text()).toContain(wanted.body)
  })

  it('links the version title of a release back to its tag', async () => {
    vi.mocked(releaseNotesApi.list).mockResolvedValue({
      total: 2,
      items: [
        release(),
        release({ id: 2, tag_name: 'v1.0.0', name: 'v1.0.0', is_latest: false }),
      ],
    })
    vi.mocked(releaseNotesApi.preview).mockResolvedValue(preview([]))

    const wrapper = mountView()
    await flushPromises()
    await selectRepository(wrapper)

    const link = wrapper.findAll('.note-entry')[1].find('.note-entry-tag-link')
    expect(link.text()).toBe('v1.0.0')

    await link.trigger('click')
    await flushPromises()

    // the title is the mirror of the note icon: it opens the tags tab on that tag
    expect(activeTabLabel(wrapper)).toBe(enMessages.releaseNotes.panel_tags)
    const active = wrapper.find('.nav-item.active')
    expect(active.classes()).toContain('tag-item')
    expect(active.text()).toContain('v1.0.0')
    // selecting it loads the commits the tag released
    expect(releaseNotesApi.preview).toHaveBeenCalledWith(
      expect.objectContaining({ version: 'v1.0.0' }),
    )
  })

  /**
   * The index walks the whole release list to place every tag, so this test needs a
   * list longer than two pages: the walk is asserted to ask for offsets 0, 200 and
   * 400, and the tag it then jumps to sits at position 320 - inside the third page.
   * 401 releases is the least that proves both, and the size of this fixture is not
   * what costs - 450 of them take the same time - so shrinking it further would only
   * weaken what is being proved.
   */
  it('walks the capped pages of the release list when indexing the tags', async () => {
    const allNotes = Array.from({ length: 401 }, (_, index) =>
      release({
        id: index + 1,
        tag_name: `v1.${401 - index}.0`,
        name: `v1.${401 - index}.0`,
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
  }, 20_000)

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

    // the draft inherits the scope the server resolved for the selected tag
    const previousSelect = selectByPlaceholder(
      wrapper,
      enMessages.releaseNotes.previous_tag_placeholder,
    )
    expect(previousSelect.props('modelValue')).toBe('v1.1.0')
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
    // the entry still has a menu (it can be edited), just not that item
    await openNoteMenu(wrapper)
    expect(noteMenuItem('push')).toBeUndefined()
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

    await openNoteMenu(wrapper)
    expect(noteMenuItem('push')?.textContent?.trim()).toBe(
      enMessages.releaseNotes.push_to_provider,
    )

    await useNoteMenu(wrapper, 'push')

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

    await useNoteMenu(wrapper, 'edit')

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

  it('carries the badges of each release on its own entry', async () => {
    vi.mocked(releaseNotesApi.list).mockResolvedValue({
      total: 3,
      items: [
        release({
          id: 1,
          tag_name: 'v3.0.0-rc.1',
          name: 'Candidate',
          is_latest: false,
          is_prerelease: true,
        }),
        release({
          id: 2,
          tag_name: 'v2.0.0',
          name: 'DraftTwo',
          is_latest: false,
          status: 'draft',
        }),
        release({ id: 3, tag_name: 'v1.0.0', name: 'LatestOne', is_latest: true }),
      ],
    })

    const wrapper = mountView()
    await flushPromises()
    await selectRepository(wrapper)

    const entries = wrapper.findAll('.note-entry')
    expect(entries[0].text()).toContain(enMessages.releaseNotes.badge_prerelease)
    expect(entries[0].text()).not.toContain(enMessages.releaseNotes.badge_draft)
    expect(entries[1].text()).toContain(enMessages.releaseNotes.badge_draft)
    expect(entries[2].text()).toContain(enMessages.releaseNotes.badge_latest)
  })

  it('acts on the release of the entry that was clicked', async () => {
    vi.mocked(releaseNotesApi.list).mockResolvedValue({
      total: 2,
      items: [
        release({ id: 11, tag_name: 'v1.1.0', name: 'Newer' }),
        release({ id: 10, tag_name: 'v1.0.0', name: 'Older', is_latest: false }),
      ],
    })

    const wrapper = mountView()
    await flushPromises()
    await selectRepository(wrapper)

    // the menu of the second entry: the command carries the release it belongs to
    await useNoteMenu(wrapper, 'edit', 1)

    // the entry's own release is edited, not the one in focus
    const tagSelect = selectByPlaceholder(wrapper, enMessages.releaseNotes.tag_placeholder)
    expect(tagSelect.props('modelValue')).toBe('v1.0.0')
  })

  it('pages the releases from the reading column too', async () => {
    const many = Array.from({ length: 25 }, (_, index) =>
      release({ id: index + 1, tag_name: `v1.${25 - index}.0`, name: `v1.${25 - index}.0` }),
    )
    vi.mocked(releaseNotesApi.list).mockImplementation(async (params) => {
      const offset = params?.offset ?? 0
      const limit = params?.limit ?? 10
      return { total: many.length, items: many.slice(offset, offset + limit) }
    })

    const wrapper = mountView()
    await flushPromises()
    await selectRepository(wrapper)

    const pager = detailPager(wrapper)
    expect(pager).toBeDefined()
    pager!.vm.$emit('update:current-page', 2)
    await flushPromises()

    expect(releaseNotesApi.list).toHaveBeenLastCalledWith(
      expect.objectContaining({ offset: 10, limit: 10 }),
    )
    expect(wrapper.findAll('.note-entry')).toHaveLength(10)
  })

  it('collapses a long note and expands it on demand', async () => {
    const longBody = Array.from({ length: 30 }, (_, index) => `- line ${index}`).join('\n')
    vi.mocked(releaseNotesApi.list).mockResolvedValue({
      total: 2,
      items: [
        release({ id: 1, tag_name: 'v2.0.0', name: 'Long', body: longBody }),
        release({
          id: 2,
          tag_name: 'v1.0.0',
          name: 'Short',
          body: '- one line',
          is_latest: false,
        }),
      ],
    })

    const wrapper = mountView()
    await flushPromises()
    await selectRepository(wrapper)

    const longEntry = wrapper.findAll('.note-entry')[0]
    const shortEntry = wrapper.findAll('.note-entry')[1]

    expect(longEntry.find('.release-body').classes()).toContain('collapsed')
    expect(longEntry.find('.note-expand').text()).toBe(enMessages.releaseNotes.show_more)
    // a note that fits needs no control
    expect(shortEntry.find('.note-expand').exists()).toBe(false)
    expect(shortEntry.find('.release-body').classes()).not.toContain('collapsed')

    await longEntry.find('.note-expand').trigger('click')
    await flushPromises()

    expect(longEntry.find('.release-body').classes()).not.toContain('collapsed')
    expect(longEntry.find('.note-expand').text()).toBe(enMessages.releaseNotes.show_less)
  })

  it('invites the reader to draft the first release of an empty repository', async () => {
    vi.mocked(releaseNotesApi.list).mockResolvedValue({ total: 0, items: [] })

    const wrapper = mountView()
    await flushPromises()
    await selectRepository(wrapper)

    expect(wrapper.find('.detail-card .el-empty').text()).toContain(
      enMessages.releaseNotes.empty,
    )
  })

  it('steps back a page when the last release of a page is deleted', async () => {
    const many = Array.from({ length: 11 }, (_, index) =>
      release({ id: index + 1, tag_name: `v1.${11 - index}.0`, name: `v1.${11 - index}.0` }),
    )
    vi.mocked(releaseNotesApi.list).mockImplementation(async (params) => {
      const offset = params?.offset ?? 0
      const limit = params?.limit ?? 10
      return { total: many.length, items: many.slice(offset, offset + limit) }
    })
    const confirmSpy = vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm' as any)

    try {
      const wrapper = mountView()
      await flushPromises()
      await selectRepository(wrapper)

      detailPager(wrapper)!.vm.$emit('update:current-page', 2)
      await flushPromises()
      expect(wrapper.findAll('.note-entry')).toHaveLength(1)

      await useNoteMenu(wrapper, 'delete')

      // page 2 held nothing else: the reader steps back instead of facing an empty list
      expect(releaseNotesApi.list).toHaveBeenLastCalledWith(
        expect.objectContaining({ offset: 0 }),
      )
      expect(wrapper.findAll('.note-entry').length).toBeGreaterThan(0)
    } finally {
      confirmSpy.mockRestore()
    }
  })
})

// --------------------------------------------------------------------------- #
// Export
// --------------------------------------------------------------------------- #

function exported(overrides: Record<string, unknown> = {}) {
  return {
    filename: 'releasenotes-ALPHA-alpha-api-v1.1.0.md',
    content: '# Release notes - ALPHA/alpha-api',
    count: 1,
    skipped_ids: [] as number[],
    truncated: false,
    ...overrides,
  }
}

describe('ReleaseNotesView export', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    signIn(['review_admin'])
    vi.mocked(projectsApi.getAllProjects).mockResolvedValue(PROJECTS as any)
    vi.mocked(projectsApi.getProjectRepositories).mockResolvedValue(REPOSITORIES as any)
    vi.mocked(projectsApi.getCloudWorkspaces).mockResolvedValue([])
    vi.mocked(releaseDiffApi.listRefs).mockResolvedValue(REFS as any)
    vi.mocked(releaseNotesApi.list).mockResolvedValue({
      total: 2,
      items: [
        release({ id: 11, tag_name: 'v1.1.0', name: 'Newer' }),
        release({ id: 10, tag_name: 'v1.0.0', name: 'Older', is_latest: false }),
      ],
    })
    vi.mocked(releaseNotesApi.exportNotes).mockResolvedValue(exported())
    vi.mocked(copyTextToClipboard).mockResolvedValue(true)
  })

  /** Mount the page and pick the repository (loads the releases). */
  async function mountAndSelect() {
    const wrapper = mountView()
    await flushPromises()
    await selectRepository(wrapper)
    return wrapper
  }

  /** The header checkbox first, then one per release row. */
  function exportCheckboxes(wrapper: AnyWrapper) {
    return wrapper.findAllComponents({ name: 'ElCheckbox' })
  }

  it('exports the releases ticked in the list', async () => {
    const wrapper = await mountAndSelect()

    exportCheckboxes(wrapper)[1].vm.$emit('change', true)
    await flushPromises()

    await wrapper.find('[data-test="export-selected"]').trigger('click')
    await flushPromises()

    expect(releaseNotesApi.exportNotes).toHaveBeenCalledWith(
      expect.objectContaining({ ids: [11] }),
    )
    expect(downloadMarkdown).toHaveBeenCalledWith(
      '# Release notes - ALPHA/alpha-api',
      'releasenotes-ALPHA-alpha-api-v1.1.0.md',
    )
  })

  it('exports every release of the repository', async () => {
    const wrapper = await mountAndSelect()

    exportCheckboxes(wrapper)[0].vm.$emit('change', true)
    await flushPromises()

    await wrapper.find('[data-test="export-selected"]').trigger('click')
    await flushPromises()

    const payload = vi.mocked(releaseNotesApi.exportNotes).mock.calls[0][0]
    expect(payload.select_all).toBe(true)
    expect(payload).not.toHaveProperty('ids')
  })

  it('does not offer the export while nothing is selected', async () => {
    const wrapper = await mountAndSelect()

    const button = () => wrapper.find('[data-test="export-selected"]').element as HTMLButtonElement
    expect(button().disabled).toBe(true)

    exportCheckboxes(wrapper)[1].vm.$emit('change', true)
    await flushPromises()

    expect(button().disabled).toBe(false)
  })

  it('exports one release through the selection the list already carries', async () => {
    const wrapper = await mountAndSelect()

    // The entry no longer carries an export of its own: selecting it and using
    // the export above is how one release is written out.
    exportCheckboxes(wrapper)[1].vm.$emit('change', true)
    await flushPromises()
    await wrapper.find('[data-test="export-selected"]').trigger('click')
    await flushPromises()

    expect(releaseNotesApi.exportNotes).toHaveBeenCalledWith(
      expect.objectContaining({ ids: [11] }),
    )
  })

  it('reports the releases that were skipped or cut', async () => {
    vi.mocked(releaseNotesApi.exportNotes).mockResolvedValue(
      exported({ count: 12, truncated: true, skipped_ids: [7] }),
    )
    const warning = vi.spyOn(ElMessage, 'warning').mockImplementation(() => ({}) as any)

    const wrapper = await mountAndSelect()
    exportCheckboxes(wrapper)[1].vm.$emit('change', true)
    await flushPromises()

    await wrapper.find('[data-test="export-selected"]').trigger('click')
    await flushPromises()

    const messages = warning.mock.calls.map((call) => String(call[0]))
    expect(messages.some((text) => text.includes('only the newest 12'))).toBe(true)
    expect(messages.some((text) => text.includes('no longer exist'))).toBe(true)
  })

  it('copies the open release to the clipboard', async () => {
    const success = vi.spyOn(ElMessage, 'success').mockImplementation(() => ({}) as any)
    const wrapper = await mountAndSelect()

    // an icon now: it says what it copies to a screen reader, and to a pointer
    const copy = wrapper.find('[data-test="note-copy"]')
    expect(copy.attributes('aria-label')).toBe(enMessages.releaseNotes.copy_one)

    await copy.trigger('click')
    await flushPromises()

    // the same document the download would use, and nothing downloaded
    expect(copyTextToClipboard).toHaveBeenCalledWith('# Release notes - ALPHA/alpha-api')
    expect(downloadMarkdown).not.toHaveBeenCalled()
    expect(success).toHaveBeenCalled()
  })

  it('reports a clipboard the platform refused', async () => {
    vi.mocked(copyTextToClipboard).mockResolvedValue(false)
    const warning = vi.spyOn(ElMessage, 'warning').mockImplementation(() => ({}) as any)
    const wrapper = await mountAndSelect()

    await wrapper.find('[data-test="note-copy"]').trigger('click')
    await flushPromises()

    expect(
      warning.mock.calls.some((call) => String(call[0]).includes('clipboard')),
    ).toBe(true)
  })

  // ---------------------------------------------------------------- #
  // Confluence (an optional integration: absent unless configured)

  it('offers to write a release to Confluence where it is set up', async () => {
    vi.mocked(releaseNotesApi.confluenceStatus).mockResolvedValue({
      configured: true,
      auto_sync: true,
    })
    const wrapper = await mountAndSelect()

    await buttonsByLabel(wrapper, enMessages.releaseNotes.draft_new)[0].trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain(enMessages.releaseNotes.sync_confluence_label)
  })

  it('does not offer a sync the instance switched off for every repository', async () => {
    vi.mocked(releaseNotesApi.confluenceStatus).mockResolvedValue({
      configured: true,
      auto_sync: false,
    })
    const wrapper = mountView()
    await flushPromises()
    await selectRepository(wrapper)

    await buttonsByLabel(wrapper, enMessages.releaseNotes.draft_new)[0].trigger('click')
    await flushPromises()

    // Set up, but with the automatic path switched off: there is nothing to tick,
    // because a release is written by hand from the release itself instead.
    expect(wrapper.text()).not.toContain(enMessages.releaseNotes.sync_confluence_label)

    await buttonsByLabel(wrapper, enMessages.releaseNotes.save_draft)[0].trigger('click')
    await flushPromises()

    // And the write that is made does not ask for the sync that would not happen.
    expect(releaseNotesApi.create).toHaveBeenCalledWith(
      expect.objectContaining({ sync_to_confluence: false }),
    )
  })

  it('says nothing about Confluence where it is not set up', async () => {
    vi.mocked(releaseNotesApi.confluenceStatus).mockResolvedValue({
      configured: false,
      auto_sync: false,
    })
    // A page made while it was set up is still linked, but nothing anywhere offers
    // to write to Confluence again.
    vi.mocked(releaseNotesApi.list).mockResolvedValue({
      total: 1,
      items: [release({ confluence_url: 'https://confluence.local/spaces/DOC/pages/100' })],
    })
    const wrapper = await mountAndSelect()

    await openNoteMenu(wrapper)
    expect(noteMenuItem('sync')).toBeUndefined()

    await buttonsByLabel(wrapper, enMessages.releaseNotes.draft_new)[0].trigger('click')
    await flushPromises()

    expect(wrapper.text()).not.toContain(enMessages.releaseNotes.sync_confluence_label)
    expect(buttonsByLabel(wrapper, enMessages.releaseNotes.sync_to_confluence)).toHaveLength(0)
  })

  it('links to the Confluence page a release is already on', async () => {
    vi.mocked(releaseNotesApi.confluenceStatus).mockResolvedValue({
      configured: true,
      auto_sync: true,
    })
    vi.mocked(releaseNotesApi.list).mockResolvedValue({
      total: 1,
      items: [release({ confluence_url: 'https://confluence.local/spaces/DOC/pages/100' })],
    })

    const wrapper = await mountAndSelect()

    const link = wrapper
      .findAll('a')
      .find((anchor: AnyWrapper) => anchor.text() === enMessages.releaseNotes.view_on_confluence)
    expect(link?.attributes('href')).toBe('https://confluence.local/spaces/DOC/pages/100')
    // The control beside the release gives way to the link - and writing it again
    // moves into the menu rather than going away with it
    expect(buttonsByLabel(wrapper, enMessages.releaseNotes.sync_to_confluence)).toHaveLength(0)
    await openNoteMenu(wrapper)
    expect(noteMenuItem('sync')?.textContent?.trim()).toBe(
      enMessages.releaseNotes.sync_to_confluence,
    )
  })

  it('syncs a release to Confluence on request', async () => {
    vi.mocked(releaseNotesApi.confluenceStatus).mockResolvedValue({
      configured: true,
      auto_sync: true,
    })
    vi.mocked(releaseNotesApi.syncToConfluence).mockResolvedValue({
      synced: true,
      page_url: 'https://confluence.local/spaces/DOC/pages/100',
      message: 'Synced to Confluence',
    })
    const success = vi.spyOn(ElMessage, 'success').mockImplementation(() => ({}) as any)

    const wrapper = await mountAndSelect()
    await buttonsByLabel(wrapper, enMessages.releaseNotes.sync_to_confluence)[0].trigger('click')
    await flushPromises()

    // The first release of the fixture list, which is the one clicked
    expect(releaseNotesApi.syncToConfluence).toHaveBeenCalledWith(11)
    expect(success).toHaveBeenCalled()
    // The page url is on the release, so the list is read back for it
    expect(releaseNotesApi.list).toHaveBeenCalledTimes(2)
  })

  it('reports a sync that failed without hiding the release', async () => {
    vi.mocked(releaseNotesApi.confluenceStatus).mockResolvedValue({
      configured: true,
      auto_sync: true,
    })
    vi.mocked(releaseNotesApi.syncToConfluence).mockResolvedValue({
      synced: false,
      message: 'Confluence returned 500',
    })
    const warning = vi.spyOn(ElMessage, 'warning').mockImplementation(() => ({}) as any)

    const wrapper = await mountAndSelect()
    await buttonsByLabel(wrapper, enMessages.releaseNotes.sync_to_confluence)[0].trigger('click')
    await flushPromises()

    expect(warning).toHaveBeenCalled()
    expect(wrapper.text()).toContain('v1.1.0')
  })

  it('writes a release that is already on a page again, from the menu', async () => {
    // The automatic path is off: the menu is the only way back in.
    vi.mocked(releaseNotesApi.confluenceStatus).mockResolvedValue({
      configured: true,
      auto_sync: false,
    })
    vi.mocked(releaseNotesApi.list).mockResolvedValue({
      total: 1,
      items: [
        release({ id: 11, confluence_url: 'https://confluence.local/spaces/DOC/pages/100' }),
      ],
    })
    vi.mocked(releaseNotesApi.syncToConfluence).mockResolvedValue({
      synced: true,
      page_url: 'https://confluence.local/spaces/DOC/pages/100',
      message: 'Synced to Confluence',
    })
    const success = vi.spyOn(ElMessage, 'success').mockImplementation(() => ({}) as any)

    const wrapper = await mountAndSelect()
    await useNoteMenu(wrapper, 'sync')

    expect(releaseNotesApi.syncToConfluence).toHaveBeenCalledWith(11)
    expect(success).toHaveBeenCalled()
  })

  it('offers a retry when the last sync failed on a page that exists', async () => {
    vi.mocked(releaseNotesApi.confluenceStatus).mockResolvedValue({
      configured: true,
      auto_sync: true,
    })
    vi.mocked(releaseNotesApi.list).mockResolvedValue({
      total: 1,
      items: [
        release({
          confluence_url: 'https://confluence.local/spaces/DOC/pages/100',
          confluence_sync_error: 'Confluence returned 500: boom',
        }),
      ],
    })

    const wrapper = await mountAndSelect()

    // The badge reports the failure, and the menu says what to do about it -
    // which the badge on its own used to leave a reader guessing at.
    expect(wrapper.text()).toContain(enMessages.releaseNotes.badge_confluence_failed)
    await openNoteMenu(wrapper)
    expect(noteMenuItem('sync')?.textContent?.trim()).toBe(
      enMessages.releaseNotes.sync_confluence_retry,
    )
  })
})
