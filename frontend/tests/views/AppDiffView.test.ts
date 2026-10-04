import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus, { ElSelect } from 'element-plus'
import { createI18n } from 'vue-i18n'
import { createMemoryHistory, createRouter } from 'vue-router'
import AppDiffView from '@/views/releases/AppDiffView.vue'
import enMessages from '@/locales/en.json'
import { appVersionDiffApi } from '@/api/appVersionDiff'

// The repository and its refs come from the provider in the running app; the
// stand-ins hand over the one project, the one repository and the refs the
// assertions below read.
vi.mock('@/api/projects', () => ({
  projectsApi: {
    getAllProjects: async () => [
      { project_key: 'CORE', project_name: 'Core' },
      { project_key: 'GHE', project_name: 'GitHub', git_provider: 'github_enterprise' },
    ],
    getProjectRepositories: async () => [
      { repository_slug: 'app', repository_name: 'Application' },
    ],
    getCloudWorkspaces: async () => [],
  },
}))

vi.mock('@/api/releaseDiff', () => ({
  releaseDiffApi: {
    listRefs: async () => ({
      project_key: 'CORE',
      repository_slug: 'app',
      git_provider: 'bitbucket_server',
      tags: ['v2.0.0', 'v1.1.0', 'v1.0.0', 'v9.9.9'],
      branches: ['main'],
    }),
  },
}))

// The comparison endpoint answers from the fixtures, so every state the page
// has to read can be produced without a running backend.
vi.mock('@/api/appVersionDiff', async () => {
  const { diffOf } = await import('../fixtures/appDiff')
  return {
    appVersionDiffApi: {
      compare: vi.fn(async (payload: { refs: string[] }) => diffOf(payload)),
    },
  }
})

async function mountView(query = '') {
  const i18n = createI18n({
    legacy: false,
    locale: 'en',
    messages: { en: enMessages },
  })
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', component: { template: '<div />' } }],
  })
  // the initial navigation has to be started before the router is ready, and a
  // link's query rides on it
  await router.push(query ? `/${query}` : '/')
  await router.isReady()

  const wrapper = mount(AppDiffView, {
    global: { plugins: [ElementPlus, i18n, router] },
  })
  await flushPromises()
  return wrapper
}

type View = Awaited<ReturnType<typeof mountView>>

async function pick(wrapper: View, index: number, value: unknown) {
  wrapper.findAllComponents(ElSelect)[index].vm.$emit('update:modelValue', value)
  await flushPromises()
  await flushPromises()
}

/** Walk the picker the way a reader does: a project, then a repository. */
async function openOn(wrapper: View) {
  await pick(wrapper, 0, 'CORE')
  await pick(wrapper, 1, 'app')
}

function compare() {
  return vi.mocked(appVersionDiffApi.compare)
}

beforeEach(() => {
  compare().mockClear()
})

describe('AppDiffView', () => {
  it('waits for a repository before it compares anything', async () => {
    const wrapper = await mountView()

    expect(wrapper.text()).toContain('Pick a project and a repository')
    expect(wrapper.find('[data-test="matrix"]').exists()).toBe(false)
  })

  it('opens on the two most recent releases', async () => {
    const wrapper = await mountView()
    await openOn(wrapper)

    expect(compare()).toHaveBeenCalledWith(
      expect.objectContaining({ refs: ['v2.0.0', 'v1.1.0'], refresh: false }),
    )
    expect(wrapper.find('[data-test="matrix"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="verdict"]').text()).toBe('Dependencies changed')
  })

  it('states that only the declared dependencies are compared', async () => {
    const wrapper = await mountView()
    await openOn(wrapper)

    expect(wrapper.find('[data-test="scope"]').text()).toBe(
      'Only the dependencies the application declares are compared.',
    )
  })

  it('marks what each column moved by', async () => {
    const wrapper = await mountView()
    await openOn(wrapper)

    // the later release is the second column; every cell carries the move into it
    expect(wrapper.find('[data-test="cell-packageA-1"]').classes()).toContain('cell-upgrade')
    expect(wrapper.find('[data-test="cell-packageB-1"]').classes()).toContain('cell-none')
    expect(wrapper.find('[data-test="cell-packageC-1"]').classes()).toContain('cell-removed')
    expect(wrapper.find('[data-test="cell-packageD-1"]').classes()).toContain('cell-added')
    // nothing moved into the first column
    expect(wrapper.find('[data-test="cell-packageA-0"]').find('[data-test="move"]').exists()).toBe(
      false,
    )
  })

  it('calls a downgrade out as a risk', async () => {
    const wrapper = await mountView()
    await openOn(wrapper)

    const cell = wrapper.find('[data-test="cell-packageE-1"]')
    expect(cell.classes()).toContain('cell-downgrade')
    expect(cell.find('[data-test="risk"]').exists()).toBe(true)
  })

  it('never reads a change with no direction as an upgrade', async () => {
    const wrapper = await mountView()
    await openOn(wrapper)

    const cell = wrapper.find('[data-test="cell-packageF-1"]')
    expect(cell.classes()).toContain('cell-changed')
    expect(cell.classes()).not.toContain('cell-upgrade')
    expect(cell.find('[data-test="move"]').attributes('title')).toBe(
      'Changed, direction unknown',
    )
    expect(cell.find('[data-test="risk"]').exists()).toBe(false)
  })

  it('summarizes each adjacent pair', async () => {
    const wrapper = await mountView()
    await openOn(wrapper)

    const intervals = wrapper.find('[data-test="intervals"]')
    expect(intervals.text()).toContain('3 changed')
    expect(intervals.text()).toContain('1 added')
    expect(intervals.text()).toContain('1 removed')
    expect(intervals.text()).toContain('1 downgraded')
  })

  it('asks for two releases before it compares', async () => {
    const wrapper = await mountView()
    await openOn(wrapper)
    compare().mockClear()

    await pick(wrapper, 3, ['v2.0.0'])

    expect(wrapper.find('[data-test="need-two"]').exists()).toBe(true)
    expect(compare()).not.toHaveBeenCalled()
  })

  it('marks a release with no record and leaves the pairs that touch it open', async () => {
    const wrapper = await mountView()
    await openOn(wrapper)

    await pick(wrapper, 3, ['v2.0.0', 'v1.1.0', 'v9.9.9'])

    expect(wrapper.find('[data-test="column-missing"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="verdict"]').text()).toBe('Incomplete')
    expect(wrapper.find('[data-test="incomplete"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="interval-incomplete"]').exists()).toBe(true)

    // the column with no record reads as unknown, never as unchanged
    const unknown = wrapper.find('[data-test="cell-packageA-2"]')
    expect(unknown.classes()).toContain('cell-unknown')
    expect(unknown.text()).toContain('?')
  })

  it('refreshes past the cache on demand', async () => {
    const wrapper = await mountView()
    await openOn(wrapper)
    compare().mockClear()

    await wrapper.find('[data-test="refresh"]').trigger('click')
    await flushPromises()

    expect(compare()).toHaveBeenCalledWith(expect.objectContaining({ refresh: true }))
  })

  it('reports a source it could not read instead of an empty comparison', async () => {
    compare().mockRejectedValueOnce(new Error('dependency database is down'))
    const wrapper = await mountView()
    await openOn(wrapper)

    expect(wrapper.find('[data-test="failed"]').exists()).toBe(true)
    // an empty matrix would read as a comparison in which nothing moved
    expect(wrapper.find('[data-test="matrix"]').exists()).toBe(false)
  })

  it('reports the commits between a pair', async () => {
    const wrapper = await mountView()
    await openOn(wrapper)

    expect(wrapper.find('[data-test="code-counts"]').text()).toContain('5 commits added')
    expect(wrapper.find('[data-test="code-unavailable"]').exists()).toBe(false)
  })

  it('opens the commit list on demand', async () => {
    const wrapper = await mountView()
    await openOn(wrapper)

    expect(wrapper.find('[data-test="commits"]').exists()).toBe(false)

    await wrapper.find('[data-test="code-toggle"]').trigger('click')

    const commits = wrapper.find('[data-test="commits"]')
    expect(commits.text()).toContain('a1b2c3d')
    expect(commits.text()).toContain('Add the new module')
  })

  it('says a release was rebuilt when only its commits moved', async () => {
    const wrapper = await mountView()
    await openOn(wrapper)

    await pick(wrapper, 3, ['v1.1.0', 'v3.0.0'])

    // the dependency axis has nothing to report ...
    expect(wrapper.find('[data-test="interval-unchanged"]').exists()).toBe(true)
    // ... and the page does not leave it at that
    expect(wrapper.find('[data-test="rebuilt"]').exists()).toBe(true)
  })

  it('says the commits could not be read instead of showing none', async () => {
    const wrapper = await mountView()
    await openOn(wrapper)

    await pick(wrapper, 3, ['v1.1.0', 'v4.0.0'])

    expect(wrapper.find('[data-test="code-unavailable"]').text()).toContain(
      'provider unreachable',
    )
    // no counts and no toggle, so nothing reads as a pair without commits
    expect(wrapper.find('[data-test="code-counts"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="code-toggle"]').exists()).toBe(false)
  })

  it('shows no code axis for a pair it could not compare', async () => {
    const wrapper = await mountView()
    await openOn(wrapper)

    await pick(wrapper, 3, ['v2.0.0', 'v1.1.0', 'v9.9.9'])

    // the incomplete pair carries no code axis at all
    expect(wrapper.findAll('[data-test="code-axis"]')).toHaveLength(1)
  })

  it('restores the comparison a link carries', async () => {
    const wrapper = await mountView(
      '?project_key=CORE&repository_slug=app&refs=v1.0.0,v1.1.0,v2.0.0',
    )
    await flushPromises()

    expect(compare()).toHaveBeenCalledWith(
      expect.objectContaining({ refs: ['v1.0.0', 'v1.1.0', 'v2.0.0'] }),
    )
    expect(wrapper.find('[data-test="need-two"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="matrix"]').exists()).toBe(true)
  })
})
