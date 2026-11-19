import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'
import ElementPlus, { ElSelect } from 'element-plus'
import { createI18n } from 'vue-i18n'
import { createMemoryHistory, createRouter } from 'vue-router'
import AggregateReleaseNoteView from '@/views/releases/AggregateReleaseNoteView.vue'
import enMessages from '@/locales/en.json'
import { aggregateReleaseNoteApi } from '@/api/aggregateReleaseNote'
import type { AggregateReleaseNoteResponse } from '@/api/aggregateReleaseNote'
import { projectsApi } from '@/api/projects'
import { releaseDiffApi } from '@/api/releaseDiff'

// The repository and its refs come from the provider in the running app; the
// stand-ins hand over the one project, the one repository and the refs the
// tests below read.
vi.mock('@/api/projects', () => ({
  projectsApi: {
    getAllProjects: vi.fn(async () => [{ project_key: 'CORE', project_name: 'Core' }]),
    getProjectRepositories: vi.fn(async () => [
      { repository_slug: 'app', repository_name: 'Application' },
    ]),
    getCloudWorkspaces: vi.fn(async () => []),
  },
}))

vi.mock('@/api/releaseDiff', () => ({
  releaseDiffApi: {
    listRefs: vi.fn(async () => ({
      project_key: 'CORE',
      repository_slug: 'app',
      git_provider: 'bitbucket_server',
      tags: ['v2.0.0', 'v1.0.0'],
      branches: ['main'],
    })),
  },
}))

// JIRA ticket links are driven by these settings; the commit table reads them.
vi.mock('@/api/rbac', () => ({
  rbacApi: {
    getJiraSettings: vi.fn(async () => ({
      base_url: 'https://jira.example.com',
      project_keys: [],
    })),
  },
}))

/** One compared package, one skipped with the reason, plus the app's own half. */
function noteFixture(): AggregateReleaseNoteResponse {
  return {
    app_name: 'MyApp',
    project_key: 'CORE',
    repository_slug: 'app',
    git_provider: 'bitbucket_server',
    source_ref: 'v1.0.0',
    target_ref: 'v2.0.0',
    application: {
      project_key: 'CORE',
      repository_slug: 'app',
      git_provider: 'bitbucket_server',
      source_ref: 'v1.0.0',
      target_ref: 'v2.0.0',
      narrowed: false,
      verdict: 'contained',
      scan_complete: true,
      scan_limit: 500,
      filtered_by_baseline_count: 0,
      missing_count: 0,
      missing_commits: [],
      added_count: 2,
      added_commits: [
        { id: 'c1', display_id: 'abc1234', message: 'PRL-9: ship the feature', url: 'https://git/commit/c1' },
        { id: 'c2', display_id: 'def5678', message: 'bump pkgA', url: 'https://git/commit/c2' },
      ],
      added_complete: true,
      rendered_truncated: false,
    },
    packages: [
      {
        name: 'pkgA',
        change: 'upgraded',
        from_version: '1.2.0',
        to_version: '1.4.0',
        status: 'compared',
        repository: { project_key: 'PKGA', repository_slug: 'pkgA-repo', git_provider: 'bitbucket_server' },
        comparison: {
          project_key: 'PKGA',
          repository_slug: 'pkgA-repo',
          git_provider: 'bitbucket_server',
          source_ref: '1.2.0',
          target_ref: '1.4.0',
          narrowed: false,
          verdict: 'missing',
          scan_complete: true,
          scan_limit: 500,
          filtered_by_baseline_count: 0,
          missing_count: 1,
          missing_commits: [{ id: 'm1', message: 'hotfix the regression' }],
          added_count: 1,
          added_commits: [{ id: 'a1', display_id: 'aaa1111', message: 'PRL-10: pkgA work', url: 'https://git/commit/a1' }],
          added_complete: true,
          rendered_truncated: false,
        },
      },
      {
        name: 'pkgY',
        change: 'upgraded',
        from_version: '0.9.0',
        to_version: '1.0.0',
        status: 'skipped',
        reason: "no repository is registered as 'pkgY'",
      },
    ],
    unchanged_packages: ['pkgC@3.2.0', 'pkgD@2.0.0'],
    summary: {
      packages_changed: 2,
      packages_compared: 1,
      packages_skipped: 1,
      packages_failed: 0,
      app_commits: 2,
      package_commits: 1,
    },
  }
}

// The build endpoint answers from the fixture, so every state the page reads
// is produced without a running backend.
const { buildMock, createNoteMock } = vi.hoisted(() => ({
  buildMock: vi.fn(),
  createNoteMock: vi.fn(),
}))

vi.mock('@/api/releaseNotes', () => ({
  releaseNotesApi: {
    create: createNoteMock,
  },
}))

vi.mock('@/api/aggregateReleaseNote', () => ({
  aggregateReleaseNoteApi: {
    build: buildMock,
  },
}))

beforeEach(() => {
  buildMock.mockImplementation(async () => noteFixture())
  createNoteMock.mockReset()
})

afterEach(() => {
  vi.clearAllMocks()
})

// The component is mounted through ElementPlus, so the wrapper type stays loose
type AnyWrapper = VueWrapper<any>
let mounted: AnyWrapper | null = null

async function mountView() {
  const i18n = createI18n({ legacy: false, locale: 'en', messages: { en: enMessages } })
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', component: { template: '<div />' } }],
  })
  await router.push('/')
  await router.isReady()

  mounted = mount(AggregateReleaseNoteView, {
    // no teleport stub: stubbing it makes every Element Plus popper render
    // inline, and that races the selects into a recursive-update loop in jsdom.
    // The save dialog lands in document.body, where the save test reads it.
    global: { plugins: [ElementPlus, i18n, router] },
  })
  await flushPromises()
  return mounted
}

type View = AnyWrapper

async function pick(wrapper: View, index: number, value: unknown) {
  wrapper.findAllComponents(ElSelect)[index].vm.$emit('update:modelValue', value)
  await flushPromises()
  await flushPromises()
}

/** Walk as far as the repository: the refs are still the reader's to pick. */
async function openRepository(wrapper: View) {
  await pick(wrapper, 0, 'CORE')
  await pick(wrapper, 1, 'app')
}

describe('AggregateReleaseNoteView', () => {
  it('sends the application coordinates and the two refs of the span', async () => {
    const wrapper = await mountView()
    await openRepository(wrapper)
    await pick(wrapper, 2, 'v1.0.0') // source
    await pick(wrapper, 3, 'v2.0.0') // target

    await wrapper.find('[data-test=build-button]').trigger('click')
    await flushPromises()

    expect(aggregateReleaseNoteApi.build).toHaveBeenCalledWith(
      expect.objectContaining({
        project_key: 'CORE',
        repository_slug: 'app',
        source_ref: 'v1.0.0',
        target_ref: 'v2.0.0',
      }),
    )
  })

  it('renders the application section, the package entries and the unchanged line', async () => {
    const wrapper = await mountView()
    await openRepository(wrapper)
    await pick(wrapper, 2, 'v1.0.0')
    await pick(wrapper, 3, 'v2.0.0')
    await wrapper.find('[data-test=build-button]').trigger('click')
    await flushPromises()

    const note = wrapper.find('[data-test=note]')
    expect(note.exists()).toBe(true)
    // the application's own verdict opens the note
    expect(note.text()).toContain('Application: MyApp')
    // the compared package answers with its own verdict, the skipped one with its reason
    expect(note.text()).toContain('pkgA')
    expect(note.text()).toContain('1.2.0 → 1.4.0')
    expect(note.text()).toContain("no repository is registered as 'pkgY'")
    // what stayed put reads as one line, not a list of comparisons
    expect(note.find('[data-test=unchanged]').text()).toContain('pkgC@3.2.0')
    expect(note.find('[data-test=unchanged]').text()).toContain('pkgD@2.0.0')
  })

  it('shows the summary counts the reader can trust without scrolling', async () => {
    const wrapper = await mountView()
    await openRepository(wrapper)
    await pick(wrapper, 2, 'v1.0.0')
    await pick(wrapper, 3, 'v2.0.0')
    await wrapper.find('[data-test=build-button]').trigger('click')
    await flushPromises()

    const summary = wrapper.find('[data-test=summary]').text()
    expect(summary).toContain('2')
    expect(summary).toContain('Packages moved')
  })

  it('offers the HTML export of the built note', async () => {
    const wrapper = await mountView()
    await openRepository(wrapper)
    await pick(wrapper, 2, 'v1.0.0')
    await pick(wrapper, 3, 'v2.0.0')
    await wrapper.find('[data-test=build-button]').trigger('click')
    await flushPromises()

    const createObjectURL = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:report')
    const revokeObjectURL = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})

    await wrapper.find('[data-test=export-button]').trigger('click')
    await flushPromises()

    // the report is assembled from the built note and handed to a download
    expect(createObjectURL).toHaveBeenCalledTimes(1)
    expect(revokeObjectURL).toHaveBeenCalledTimes(1)

    vi.restoreAllMocks()
  })

  it('files the note under the target release with its source as the previous tag', async () => {
    const wrapper = await mountView()
    await openRepository(wrapper)
    await pick(wrapper, 2, 'v1.0.0')
    await pick(wrapper, 3, 'v2.0.0')
    await wrapper.find('[data-test=build-button]').trigger('click')
    await flushPromises()

    await wrapper.find('[data-test=save-button]').trigger('click')
    // the dialog body renders on first open, a few ticks behind the flag,
    // teleported to <body> where the wrapper's finders cannot reach it
    await flushPromises()
    await flushPromises()
    await flushPromises()

    // the dialog renders through whatever teleport Element Plus chooses; read
    // it from the wrapper when it stays inline, from the body when it does not
    const findInDialog = (selector: string) => {
      const scoped = wrapper.find(`[data-test=save-dialog] ${selector}`)
      if (scoped.exists()) return scoped
      const global = document.body.querySelector(selector)
      expect(global).not.toBeNull()
      return { element: global! }
    }

    expect(
      wrapper.find('[data-test=save-dialog]').exists() ||
        document.body.querySelector('[data-test=save-dialog]'),
    ).toBeTruthy()
    // the tag and the span are the target's, prefilled for the reader; the
    // data-test attribute lands on the inner input (el-input fallthrough)
    const tagInput = findInDialog('input[data-test=save-tag]')
    expect((tagInput.element as HTMLInputElement).value).toBe('v2.0.0')

    const confirm = findInDialog('[data-test=save-confirm]')
    ;(confirm.element as HTMLElement).click()
    await flushPromises()

    expect(createNoteMock).toHaveBeenCalledTimes(1)
    const payload = createNoteMock.mock.calls[0][0]
    expect(payload).toMatchObject({
      project_key: 'CORE',
      repository_slug: 'app',
      tag_name: 'v2.0.0',
      previous_tag: 'v1.0.0',
      status: 'draft',
    })
    // the body is the markdown note: app section, packages, unchanged line
    expect(payload.body).toContain('## Application')
    expect(payload.body).toContain('### pkgA')
    expect(payload.body).toContain('pkgC@3.2.0')
  })
})
