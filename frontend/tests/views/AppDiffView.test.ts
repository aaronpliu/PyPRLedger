import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus, { ElRadioButton, ElRadioGroup, ElSelect } from 'element-plus'
import { createI18n } from 'vue-i18n'
import { createMemoryHistory, createRouter } from 'vue-router'
import AppDiffView from '@/views/releases/AppDiffView.vue'
import enMessages from '@/locales/en.json'
import { appVersionDiffApi } from '@/api/appVersionDiff'
import { projectsApi } from '@/api/projects'
import { releaseDiffApi } from '@/api/releaseDiff'
import type { ReleaseRefsResponse } from '@/api/releaseDiff'
import {
  APP_NAME,
  RELEASE_DEFERRED,
  RELEASE_EARLIER,
  RELEASE_LATER,
  RELEASE_MISSING,
} from '../fixtures/appDiff'

// The repository and its refs come from the provider in the running app; the
// stand-ins hand over the one project, the one repository and the refs the
// assertions below read.
vi.mock('@/api/projects', () => ({
  projectsApi: {
    getAllProjects: vi.fn(async () => [
      { project_key: 'CORE', project_name: 'Core' },
      { project_key: 'GHE', project_name: 'GitHub', git_provider: 'github_enterprise' },
    ]),
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
      tags: ['v2.0.0', 'v1.1.0', 'v1.0.0', 'v9.9.9'],
      branches: ['main'],
    })),
  },
}))

// The comparison endpoint answers from the fixtures, so every state the page
// has to read can be produced without a running backend.
vi.mock('@/api/appVersionDiff', async () => {
  const { diffOf, packageAnswers } = await import('../fixtures/appDiff')
  return {
    appVersionDiffApi: {
      compare: vi.fn(async (payload: { refs: string[] }) => diffOf(payload)),
      // the batch the page asks for afterwards answers about the packages it named
      comparePackages: vi.fn(
        async (payload: {
          project_key: string
          repository_slug: string
          source_ref: string
          target_ref: string
          packages: { name: string; source_version: string; target_version: string }[]
        }) => ({
          project_key: payload.project_key,
          repository_slug: payload.repository_slug,
          source_ref: payload.source_ref,
          target_ref: payload.target_ref,
          packages: packageAnswers(payload.packages),
        }),
      ),
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

/** Walk as far as the repository: the releases are still the reader's to pick. */
async function openRepository(wrapper: View) {
  await pick(wrapper, 0, 'CORE')
  await pick(wrapper, 1, 'app')
}

/**
 * Walk the picker the way a reader does: a project, a repository, then the
 * releases. Nothing is compared before those last choices are made.
 */
async function openOn(wrapper: View, refs: string[] = ['v2.0.0', 'v1.1.0']) {
  await openRepository(wrapper)
  await pick(wrapper, 3, refs)
}

function compare() {
  return vi.mocked(appVersionDiffApi.compare)
}

/** The batch that reads the packages the first response deferred. */
function comparePackages() {
  return vi.mocked(appVersionDiffApi.comparePackages)
}

/** The reading-depth picker, found by its hook rather than by position. */
function depthPicker(wrapper: View) {
  return wrapper.find('[data-test="depth-select"]').findComponent(ElSelect)
}

/** Choose a reading depth the way the picker does. */
async function setDepth(wrapper: View, value: string) {
  depthPicker(wrapper).vm.$emit('update:modelValue', value)
  await flushPromises()
  await flushPromises()
}

beforeEach(() => {
  compare().mockClear()
  comparePackages().mockClear()
  // the depth is a preference, so a test that kept one must not hand it to the next
  localStorage.clear()
})

describe('AppDiffView', () => {
  it('waits for a repository before it compares anything', async () => {
    const wrapper = await mountView()

    expect(wrapper.text()).toContain('Pick a project and a repository')
    expect(wrapper.find('[data-test="matrix"]').exists()).toBe(false)
  })

  it('compares nothing until the releases are picked', async () => {
    const wrapper = await mountView()
    await openRepository(wrapper)

    // the releases are suggestions of the provider, not a choice made for the reader
    expect(compare()).not.toHaveBeenCalled()
    expect(wrapper.find('[data-test="need-two"]').exists()).toBe(true)

    await pick(wrapper, 3, ['v2.0.0', 'v1.1.0'])

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
    // four changed: three dependencies and the application's own version
    expect(intervals.text()).toContain('4 changed')
    expect(intervals.text()).toContain('1 added')
    expect(intervals.text()).toContain('1 removed')
    expect(intervals.text()).toContain('1 downgraded')
  })

  it("shows the application's own version as the first row of the matrix", async () => {
    const wrapper = await mountView()
    await openOn(wrapper)

    const matrix = wrapper.find('[data-test="matrix"]')
    const headerRow = matrix.find('thead tr')
    const firstRow = matrix.find('tbody tr')
    expect(firstRow.find('th').text()).toContain('mylang')
    expect(firstRow.find('[data-test="application-row"]').exists()).toBe(true)

    // it is a row of the same table as the dependencies, above them
    expect(matrix.findAll('tbody tr').length).toBe(7)
    expect(firstRow.find('th').text()).not.toBe(headerRow.text())

    // and its move is classified like theirs
    expect(wrapper.find('[data-test="cell-mylang-1"]').classes()).toContain('cell-upgrade')
  })

  it('marks only the application row as the application', async () => {
    const wrapper = await mountView()
    await openOn(wrapper)

    expect(wrapper.findAll('[data-test="application-row"]')).toHaveLength(1)
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

  it('lists which package moved where between two releases', async () => {
    const wrapper = await mountView()
    await openOn(wrapper)

    expect(wrapper.find('[data-test="changes-heading"]').text()).toBe('What moved')
    const changes = wrapper.find('[data-test="changes"]')
    expect(changes.exists()).toBe(true)

    // the two versions the move is about, and what kind of move it was
    const dependency = changes.find('[data-test="change-packageA"]')
    expect(dependency.text()).toContain('1.0.0 → 1.0.1')
    expect(dependency.text()).toContain('Upgrade')

    // the application's own version is one entry among them, marked as not a dependency
    const application = changes.find(`[data-test="change-${APP_NAME}"]`)
    expect(application.find('[data-test="change-application"]').exists()).toBe(true)
    expect(application.text()).toContain('1.0.0_10000 → 1.1.0_10000')

    // an added package has no earlier version, which reads as a dash, not a gap
    expect(changes.find('[data-test="change-packageD"]').text()).toContain('— → 0.9.0')
  })

  it('compares each moved package in the repository the registry names', async () => {
    const wrapper = await mountView()
    await openOn(wrapper)

    // compared in its own repository, and the verdict says what the counts suggest
    const packageA = wrapper.find('[data-test="change-packageA"]')
    expect(packageA.text()).toContain('CORE/pkg-a')
    expect(packageA.find('[data-test="package-packageA-verdict"]').text()).toBe('Contained')
    expect(packageA.find('[data-test="package-packageA-counts"]').text()).toContain(
      '4 commits added',
    )

    // a package the registry does not know says so, instead of reading as compared
    const packageE = wrapper.find('[data-test="change-packageE"]')
    expect(packageE.find('[data-test="package-packageE-unavailable"]').text()).toContain(
      "no repository is registered as 'packageE'",
    )

    // a package with one version has no pair of refs to compare
    const packageC = wrapper.find('[data-test="change-packageC"]')
    expect(packageC.find('[data-test="package-packageC-unavailable"]').text()).toContain(
      'only one version is recorded',
    )
  })

  it("opens a package's own commits on demand", async () => {
    const wrapper = await mountView()
    await openOn(wrapper)

    expect(wrapper.find('[data-test="package-packageA-commits"]').exists()).toBe(false)

    await wrapper.find('[data-test="package-packageA-toggle"]').trigger('click')

    expect(wrapper.find('[data-test="package-packageA-commits"]').text()).toContain('a1b2c3d')
  })

  it('lists nothing for a pair whose releases could not be compared', async () => {
    const wrapper = await mountView()
    await openOn(wrapper)

    await pick(wrapper, 3, ['v2.0.0', 'v1.1.0', 'v9.9.9'])

    // the pair that can be compared carries its list; the one that cannot carries none
    expect(wrapper.findAll('[data-test="changes"]')).toHaveLength(1)
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

    expect(wrapper.find('[data-test="code-commits"]').exists()).toBe(false)

    await wrapper.find('[data-test="code-toggle"]').trigger('click')

    const commits = wrapper.find('[data-test="code-commits"]')
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

  it('compares three releases as two adjacent pairs, in timeline order', async () => {
    const wrapper = await mountView()
    await openOn(wrapper)

    // picked out of order on purpose: the columns, and the pairs, follow the dates
    await pick(wrapper, 3, [RELEASE_LATER, RELEASE_EARLIER, RELEASE_MISSING])

    const headers = wrapper.findAll('[data-test="matrix"] thead th')
    // the first header names the row column; the rest are the releases, by date
    expect(headers[0].text()).toContain('Package')
    expect(headers[1].text()).toContain(RELEASE_EARLIER)
    expect(headers[2].text()).toContain(RELEASE_LATER)
    expect(headers[3].text()).toContain(RELEASE_MISSING)

    // three releases are three columns and two pairs: 1.0.0 -> 1.1.0, 1.1.0 -> 1.2.0
    const intervals = wrapper.findAll('[data-test="intervals"] article')
    expect(intervals).toHaveLength(2)
    expect(intervals[0].text()).toContain(RELEASE_EARLIER)
    expect(intervals[0].text()).toContain(RELEASE_LATER)
    expect(intervals[1].text()).toContain(RELEASE_LATER)
    expect(intervals[1].text()).toContain(RELEASE_MISSING)
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

  it('says a package is not compared yet instead of leaving the row empty', async () => {
    const wrapper = await mountView()
    await openOn(wrapper, [RELEASE_EARLIER, RELEASE_DEFERRED])
    await flushPromises()

    // the response deferred it: there is a pair and a repository, so it is waiting
    // its turn - which is not the same as a package that was checked
    expect(wrapper.find('[data-test="package-packageF-deferred"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="package-packageF-unavailable"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="package-packageF-counts"]').exists()).toBe(false)
  })

  it('reads what the response deferred, up to the allowance it carries', async () => {
    const wrapper = await mountView()
    await openOn(wrapper, [RELEASE_EARLIER, RELEASE_DEFERRED])
    await flushPromises()

    // the deferred packages are asked for without the reader doing anything
    expect(comparePackages()).toHaveBeenCalledWith(
      expect.objectContaining({
        source_ref: RELEASE_EARLIER,
        target_ref: RELEASE_DEFERRED,
        packages: [{ name: 'packageE', source_version: '2.1.0', target_version: '2.0.0' }],
      }),
    )
    // the answer replaced the entry that was waiting
    expect(wrapper.find('[data-test="package-packageE-counts"]').text()).toContain(
      '2 commits added',
    )
    expect(wrapper.find('[data-test="package-packageE-deferred"]').exists()).toBe(false)

    // the allowance was one, so what is left says so rather than reading as checked
    expect(wrapper.find('[data-test="package-packageF-deferred"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="packages-pending"]').text()).toContain('were not read')
  })

  it('reads the rest when the reader asks, past the allowance', async () => {
    const wrapper = await mountView()
    await openOn(wrapper, [RELEASE_EARLIER, RELEASE_DEFERRED])
    await flushPromises()

    expect(comparePackages()).toHaveBeenCalledTimes(1)

    await wrapper.find('[data-test="packages-read-rest"]').trigger('click')
    await flushPromises()

    expect(comparePackages()).toHaveBeenCalledTimes(2)
    expect(wrapper.find('[data-test="package-packageF-counts"]').text()).toContain(
      '2 commits added',
    )
    // nothing is left waiting, so nothing says it is
    expect(wrapper.find('[data-test="packages-pending"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="packages-read-rest"]').exists()).toBe(false)
  })

  it('leaves a package the batch could not read saying so', async () => {
    comparePackages().mockRejectedValueOnce(new Error('git provider unreachable'))
    const wrapper = await mountView()
    await openOn(wrapper, [RELEASE_EARLIER, RELEASE_DEFERRED])
    await flushPromises()

    // a batch that failed must not read as a comparison that found nothing
    expect(wrapper.find('[data-test="package-packageE-deferred"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="package-packageE-counts"]').exists()).toBe(false)
    // and the reader can ask again
    expect(wrapper.find('[data-test="packages-read-rest"]').exists()).toBe(true)
  })

  it('asks for the deferred packages in the batches the answer names', async () => {
    const wrapper = await mountView()
    await openOn(wrapper, [RELEASE_EARLIER, RELEASE_DEFERRED])
    await flushPromises()

    await wrapper.find('[data-test="packages-read-rest"]').trigger('click')
    await flushPromises()

    // one package per request: the reader's own ask is not bounded by the allowance,
    // so a batch of one can only be the batch the answer named
    const manual = comparePackages().mock.calls[1][0]
    expect(manual.packages).toHaveLength(1)
    expect(manual.packages[0].name).toBe('packageF')
  })

  it('asks for nothing at the default depth, leaving the server its own numbers', async () => {
    const wrapper = await mountView()
    await openOn(wrapper)

    const sent = compare().mock.calls[0][0]
    expect(sent.max_package_comparisons).toBeUndefined()
    expect(sent.max_total_package_comparisons).toBeUndefined()
  })

  it('asks the server for the reading depth the reader chose', async () => {
    const wrapper = await mountView()
    await openOn(wrapper)
    compare().mockClear()

    await setDepth(wrapper, 'all')

    // a deeper reading is a different question, so what is on screen is read again
    expect(compare()).toHaveBeenCalledWith(
      expect.objectContaining({
        max_package_comparisons: 50,
        max_total_package_comparisons: 300,
      }),
    )
  })

  it('keeps the reading depth when the reader asks it to', async () => {
    const wrapper = await mountView()
    await openOn(wrapper)

    await wrapper.find('[data-test="depth-remember"] input').setValue(true)
    await setDepth(wrapper, 'deep')

    expect(localStorage.getItem('app_diff_depth')).toBe('deep')
    expect(depthPicker(wrapper).props('modelValue')).toBe('deep')

    // letting it go drops it, so a reader is never stuck with a choice they made once
    await wrapper.find('[data-test="depth-remember"] input').setValue(false)

    expect(localStorage.getItem('app_diff_depth')).toBeNull()
  })

  it('opens on the depth that was kept', async () => {
    localStorage.setItem('app_diff_depth', 'deep')

    const wrapper = await mountView()
    await openOn(wrapper)

    // the choice is read without the reader making it again, and it is asked for
    expect(depthPicker(wrapper).props('modelValue')).toBe('deep')
    expect(compare()).toHaveBeenCalledWith(
      expect.objectContaining({
        max_package_comparisons: 25,
        max_total_package_comparisons: 200,
      }),
    )
  })

  it('puts the matrix above the pair details', async () => {
    const wrapper = await mountView()
    await openOn(wrapper)

    const matrix = wrapper.find('[data-test="matrix"]').element
    const details = wrapper.find('[data-test="intervals"]').element

    // the matrix is the whole comparison at a glance; a page of pair details above it
    // is what used to push it off the screen
    expect(matrix.compareDocumentPosition(details) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('shows one pair at a time when a comparison has several', async () => {
    const wrapper = await mountView()
    await openOn(wrapper)
    await pick(wrapper, 3, [RELEASE_LATER, RELEASE_EARLIER, RELEASE_MISSING])

    const articles = wrapper.findAll('[data-test="intervals"] article')
    expect(articles).toHaveLength(2)
    // two pairs, one on screen: a stack of them is what made the page unreadable
    expect(articles[0].attributes('style') ?? '').not.toContain('display: none')
    expect(articles[1].attributes('style')).toContain('display: none')

    expect(wrapper.findAll('[data-test="pair-tab"]')).toHaveLength(2)

    // choosing the second pair shows it, and takes the first out of the page
    const second = wrapper.findAllComponents(ElRadioButton)[1].props('value')
    wrapper.findComponent(ElRadioGroup).vm.$emit('update:modelValue', second)
    await flushPromises()

    const after = wrapper.findAll('[data-test="intervals"] article')
    expect(after[1].attributes('style') ?? '').not.toContain('display: none')
    expect(after[0].attributes('style')).toContain('display: none')
  })

  it('shows no pair selector for a single pair', async () => {
    const wrapper = await mountView()
    await openOn(wrapper)

    // the common case says nothing about pairs, because there is only one
    expect(wrapper.find('[data-test="pair-tabs"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="intervals"] article').isVisible()).toBe(true)
  })

  it('says the repository is being read while its refs are in flight', async () => {
    let settle: (refs: ReleaseRefsResponse) => void = () => {}
    vi.mocked(releaseDiffApi.listRefs).mockReturnValueOnce(
      new Promise<ReleaseRefsResponse>((resolve) => {
        settle = resolve
      }),
    )

    const wrapper = await mountView('?project_key=CORE&repository_slug=app')

    // reading the tags and branches is a provider call, and nothing else on the page
    // moves while it is in flight: saying so is what keeps the wait from reading as a
    // page that did nothing at all
    expect(wrapper.find('[data-test="refs-loading"]').exists()).toBe(true)

    settle({
      project_key: 'CORE',
      repository_slug: 'app',
      git_provider: 'bitbucket_server',
      tags: ['v2.0.0'],
      branches: ['main'],
    })
    await flushPromises()

    expect(wrapper.find('[data-test="refs-loading"]').exists()).toBe(false)
  })

  it('leaves out only the repositories marked as packages', async () => {
    // a link's coordinates save the walk through the pickers this test is not about
    const wrapper = await mountView('?project_key=CORE&repository_slug=app')
    await flushPromises()

    // a package has no release records to read, so a repository an administrator
    // marked as one is left out - and everything nobody has classified comes back,
    // so a registry nobody has worked through behaves as it always did
    expect(vi.mocked(projectsApi.getProjectRepositories)).toHaveBeenCalledWith('CORE', [
      'application',
      'unclassified',
    ])
    expect(wrapper.find('[data-test="no-applications"]').exists()).toBe(false)
  })
})
