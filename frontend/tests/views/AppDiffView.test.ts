import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus, { ElSelect } from 'element-plus'
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
  RELEASE_REBUILT,
  RELEASE_UNAVAILABLE,
} from '../fixtures/appDiff'

// The repository and its refs come from the provider in the running app; the
// stand-ins hand over the one project, the one repository and the refs the tests
// below read.
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
  mounted = wrapper
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
  await pick(wrapper, 2, refs)
}

/**
 * Mount the page on a link that already carries the releases to compare.
 *
 * A test about what a comparison shows should not be a test of the picker as well,
 * and walking up to a state only to re-pick it is the same page rendered twice. The
 * link is how a reader arrives at a comparison someone sent them, and it is what
 * makes each test below one render.
 */
async function mountOn(...refs: string[]) {
  const wrapper = await mountView(`?project_key=CORE&repository_slug=app&refs=${refs.join(',')}`)
  await flushPromises()
  return wrapper
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

/** The page the test at hand mounted, so it can be taken down again. */
let mounted: View | null = null

beforeEach(() => {
  compare().mockClear()
  comparePackages().mockClear()
  // the depth is a preference, so a test that kept one must not hand it to the next
  localStorage.clear()
})

afterEach(() => {
  // Every test mounts a whole page. Leaving them alive piles up in jsdom, and the
  // tests that follow pay for it in time.
  mounted?.unmount()
  mounted = null
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
  })

  it('compares the two releases once they are picked', async () => {
    const wrapper = await mountOn(RELEASE_LATER, RELEASE_EARLIER)

    expect(compare()).toHaveBeenCalledWith(
      expect.objectContaining({ refs: [RELEASE_LATER, RELEASE_EARLIER], refresh: false }),
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

  it("shows the application's own version as the first row of the matrix", async () => {
    const wrapper = await mountOn(RELEASE_LATER, RELEASE_EARLIER)

    const matrix = wrapper.find('[data-test="matrix"]')
    const headerRow = matrix.find('thead tr')
    const firstRow = matrix.find('tbody tr')
    expect(firstRow.find('th').text()).toContain(APP_NAME)
    expect(firstRow.find('[data-test="application-row"]').exists()).toBe(true)

    // it is a row of the same table as the dependencies, above them
    expect(matrix.findAll('tbody tr').length).toBe(7)
    expect(firstRow.find('th').text()).not.toBe(headerRow.text())
  })

  it("classifies the application's own move like a dependency's", async () => {
    const wrapper = await mountOn(RELEASE_LATER, RELEASE_EARLIER)

    expect(wrapper.find(`[data-test="cell-${APP_NAME}-1"]`).classes()).toContain('cell-upgrade')
  })

  it('marks only the application row as the application', async () => {
    const wrapper = await mountView()
    await openOn(wrapper)

    expect(wrapper.findAll('[data-test="application-row"]')).toHaveLength(1)
  })

  it('asks for two releases before it compares', async () => {
    const wrapper = await mountView()
    await openRepository(wrapper)

    // one release is not a comparison, and the page says as much instead of comparing
    await pick(wrapper, 2, [RELEASE_LATER])

    expect(wrapper.find('[data-test="need-two"]').exists()).toBe(true)
    expect(compare()).not.toHaveBeenCalled()
  })

  it('marks a release the source holds no record for', async () => {
    const wrapper = await mountOn(RELEASE_LATER, RELEASE_EARLIER, RELEASE_MISSING)

    expect(wrapper.find('[data-test="column-missing"]').exists()).toBe(true)
    // the column with no record reads as unknown, never as unchanged
    const unknown = wrapper.find('[data-test="cell-packageA-2"]')
    expect(unknown.classes()).toContain('cell-unknown')
    expect(unknown.text()).toContain('?')
  })

  it('leaves a release with no record as incomplete', async () => {
    const wrapper = await mountOn(RELEASE_LATER, RELEASE_EARLIER, RELEASE_MISSING)

    expect(wrapper.find('[data-test="verdict"]').text()).toBe('Incomplete')
    expect(wrapper.find('[data-test="incomplete"]').exists()).toBe(true)
  })

  it("shows the application's own commits when its row is opened", async () => {
    const wrapper = await mountOn(RELEASE_LATER, RELEASE_EARLIER)

    // tucked into the row: nothing is shown until the row is opened
    expect(wrapper.find('[data-test="matrix-mylang-counts"]').exists()).toBe(false)

    await wrapper.find(`[data-test="matrix-row-${APP_NAME}"]`).trigger('click')

    expect(wrapper.find('[data-test="matrix-mylang-counts"]').text()).toContain('5 commits added')
    expect(wrapper.find('[data-test="matrix-mylang-axis"]').exists()).toBe(true)
  })

  it('reads a version a package did not have as a dash', async () => {
    const wrapper = await mountOn(RELEASE_LATER, RELEASE_EARLIER)

    // an added package has no earlier version, which reads as a dash, not a gap
    expect(wrapper.find('[data-test="cell-packageD-0"]').text()).toContain('—')
    expect(wrapper.find('[data-test="cell-packageD-1"]').text()).toContain('0.9.0')
  })

  it("reads a moved package's comparison in its row", async () => {
    const wrapper = await mountOn(RELEASE_LATER, RELEASE_EARLIER)

    await wrapper.find('[data-test="matrix-row-packageA"]').trigger('click')

    // the verdict says what the counts suggest
    expect(wrapper.find('[data-test="matrix-packageA-verdict"]').text()).toBe('Contained')
    expect(wrapper.find('[data-test="matrix-packageA-counts"]').text()).toContain(
      '4 commits added',
    )
  })

  it("titles a package's comparison by its own versions, not the app's releases", async () => {
    const wrapper = await mountOn(RELEASE_LATER, RELEASE_EARLIER)

    await wrapper.find('[data-test="matrix-row-packageA"]').trigger('click')

    // the commits are between the package's two versions in its own repository
    expect(wrapper.find('[data-test="matrix-packageA-pair-0"]').text()).toBe('1.0.0 → 1.0.1')
  })

  it("titles the application's comparison by the releases it ran between", async () => {
    const wrapper = await mountOn(RELEASE_LATER, RELEASE_EARLIER)

    await wrapper.find(`[data-test="matrix-row-${APP_NAME}"]`).trigger('click')

    expect(wrapper.find(`[data-test="matrix-${APP_NAME}-pair-0"]`).text()).toBe(
      `${RELEASE_EARLIER} → ${RELEASE_LATER}`,
    )
  })

  it('draws the version a package no longer has as a dash in its title', async () => {
    const wrapper = await mountOn(RELEASE_LATER, RELEASE_EARLIER)

    await wrapper.find('[data-test="matrix-row-packageC"]').trigger('click')

    // a removed package reads as a change of state rather than a blank side
    expect(wrapper.find('[data-test="matrix-packageC-pair-0"]').text()).toBe('1.0.0 → —')
  })

  it('says so when no repository is registered for a package', async () => {
    const wrapper = await mountOn(RELEASE_LATER, RELEASE_EARLIER)

    await wrapper.find('[data-test="matrix-row-packageE"]').trigger('click')

    // a package the registry does not know says so, instead of reading as compared
    expect(wrapper.find('[data-test="matrix-packageE-unavailable"]').text()).toContain(
      "no repository is registered as 'packageE'",
    )
  })

  it('says so when a package has only one version to compare', async () => {
    const wrapper = await mountOn(RELEASE_LATER, RELEASE_EARLIER)

    await wrapper.find('[data-test="matrix-row-packageC"]').trigger('click')

    // a package with one version has no pair of refs to compare
    expect(wrapper.find('[data-test="matrix-packageC-unavailable"]').text()).toContain(
      'only one version is recorded',
    )
  })

  it("opens a package's commits on demand", async () => {
    const wrapper = await mountView()
    await openOn(wrapper)

    expect(wrapper.find('[data-test="matrix-packageA-commits"]').exists()).toBe(false)

    await wrapper.find('[data-test="matrix-row-packageA"]').trigger('click')
    await wrapper.find('[data-test="matrix-packageA-toggle"]').trigger('click')

    expect(wrapper.find('[data-test="matrix-packageA-commits"]').text()).toContain('a1b2c3d')
  })

  it("opens a package's diff by clicking its row", async () => {
    const wrapper = await mountOn(RELEASE_EARLIER, RELEASE_LATER)

    expect(wrapper.find('[data-test="matrix-packageA-axis"]').exists()).toBe(false)

    await wrapper.find('[data-test="matrix-row-packageA"]').trigger('click')

    expect(wrapper.find('[data-test="matrix-packageA-axis"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="matrix-packageA-counts"]').text()).toContain('4 commits added')
  })

  it('tints each row by what its commits say', async () => {
    const wrapper = await mountOn(RELEASE_EARLIER, RELEASE_LATER)

    // green: commits were added with the move, for the application and packageA
    expect(wrapper.find(`[data-test="matrix-row-${APP_NAME}"]`).classes()).toContain('rag-green')
    expect(wrapper.find('[data-test="matrix-row-packageA"]').classes()).toContain('rag-green')
    // red: packageF is missing one of the earlier commits
    expect(wrapper.find('[data-test="matrix-row-packageF"]').classes()).toContain('rag-red')
    // amber: packageE and packageC could not be compared
    expect(wrapper.find('[data-test="matrix-row-packageE"]').classes()).toContain('rag-amber')
    expect(wrapper.find('[data-test="matrix-row-packageC"]').classes()).toContain('rag-amber')
    // a moved package nobody compared is not tinted at all
    const packageD = wrapper.find('[data-test="matrix-row-packageD"]')
    expect(packageD.classes().some((name) => name.startsWith('rag-'))).toBe(false)
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

    await wrapper.find(`[data-test="matrix-row-${APP_NAME}"]`).trigger('click')

    expect(wrapper.find('[data-test="matrix-mylang-counts"]').text()).toContain('5 commits added')
    expect(wrapper.find('[data-test="matrix-mylang-unavailable"]').exists()).toBe(false)
  })

  it('opens the commit list on demand', async () => {
    const wrapper = await mountView()
    await openOn(wrapper)

    await wrapper.find(`[data-test="matrix-row-${APP_NAME}"]`).trigger('click')
    expect(wrapper.find('[data-test="matrix-mylang-commits"]').exists()).toBe(false)

    await wrapper.find('[data-test="matrix-mylang-toggle"]').trigger('click')

    const commits = wrapper.find('[data-test="matrix-mylang-commits"]')
    expect(commits.text()).toContain('a1b2c3d')
    expect(commits.text()).toContain('Add the new module')
  })

  it('reads the commits of a release whose own version did not move', async () => {
    const wrapper = await mountOn(RELEASE_EARLIER, RELEASE_REBUILT)

    await wrapper.find(`[data-test="matrix-row-${APP_NAME}"]`).trigger('click')

    // nothing moved, so nothing is marked as having moved - but the release still
    // has commits, and they are read under its name
    expect(wrapper.find('[data-test="matrix-mylang-counts"]').text()).toContain('3 commits added')
  })

  it('says the commits could not be read instead of showing none', async () => {
    const wrapper = await mountOn(RELEASE_EARLIER, RELEASE_UNAVAILABLE)

    await wrapper.find(`[data-test="matrix-row-${APP_NAME}"]`).trigger('click')

    expect(wrapper.find('[data-test="matrix-mylang-unavailable"]').text()).toContain(
      'provider unreachable',
    )
  })

  it('shows no counts or toggle for commits it could not read', async () => {
    const wrapper = await mountOn(RELEASE_EARLIER, RELEASE_UNAVAILABLE)

    await wrapper.find(`[data-test="matrix-row-${APP_NAME}"]`).trigger('click')

    // nothing reads as a pair without commits
    expect(wrapper.find('[data-test="matrix-mylang-counts"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="matrix-mylang-toggle"]').exists()).toBe(false)
  })

  it('shows the releases as columns in timeline order, not the order they were asked for', async () => {
    // asked for out of order on purpose
    const wrapper = await mountOn(RELEASE_LATER, RELEASE_EARLIER, RELEASE_MISSING)

    const headers = wrapper.findAll('[data-test="matrix"] thead th')
    // the first header names the row column; the rest are the releases, by date
    expect(headers[0].text()).toContain('Package')
    expect(headers[1].text()).toContain(RELEASE_EARLIER)
    expect(headers[2].text()).toContain(RELEASE_LATER)
    expect(headers[3].text()).toContain(RELEASE_MISSING)
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

  it("reads a shared link's comparison once", async () => {
    await mountOn(RELEASE_LATER, RELEASE_EARLIER)

    // the link's releases are where the comparison starts; applying them a second
    // time when the repository's listing arrives would read the same two releases
    // again, and start a second round of the package comparisons that follow one
    expect(compare()).toHaveBeenCalledTimes(1)
  })

  it('says a package is not compared yet instead of leaving the row empty', async () => {
    const wrapper = await mountOn(RELEASE_EARLIER, RELEASE_DEFERRED)
    await flushPromises()

    await wrapper.find('[data-test="matrix-row-packageF"]').trigger('click')

    // the response deferred it: there is a pair and a repository, so it is waiting
    // its turn - which is not the same as a package that was checked
    expect(wrapper.find('[data-test="matrix-packageF-deferred"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="matrix-packageF-unavailable"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="matrix-packageF-counts"]').exists()).toBe(false)
  })

  it('reads the packages the response deferred, without being asked', async () => {
    const wrapper = await mountOn(RELEASE_EARLIER, RELEASE_DEFERRED)
    await flushPromises()

    // asked for without the reader doing anything, in the pair they were deferred from
    expect(comparePackages()).toHaveBeenCalledWith(
      expect.objectContaining({
        source_ref: RELEASE_EARLIER,
        target_ref: RELEASE_DEFERRED,
        packages: [{ name: 'packageE', source_version: '2.1.0', target_version: '2.0.0' }],
      }),
    )
  })

  it('puts the answer where the entry that was waiting was', async () => {
    const wrapper = await mountOn(RELEASE_EARLIER, RELEASE_DEFERRED)
    await flushPromises()

    await wrapper.find('[data-test="matrix-row-packageE"]').trigger('click')

    expect(wrapper.find('[data-test="matrix-packageE-counts"]').text()).toContain(
      '2 commits added',
    )
    expect(wrapper.find('[data-test="matrix-packageE-deferred"]').exists()).toBe(false)
  })

  it('stops at the allowance the response carries and says what is left', async () => {
    const wrapper = await mountOn(RELEASE_EARLIER, RELEASE_DEFERRED)
    await flushPromises()

    // the allowance was one, so what is left says so rather than reading as checked
    expect(wrapper.find('[data-test="packages-pending"]').text()).toContain('were not read')
    // and the reader has a way to ask for it
    expect(wrapper.find('[data-test="packages-read-rest"]').exists()).toBe(true)

    await wrapper.find('[data-test="matrix-row-packageF"]').trigger('click')
    expect(wrapper.find('[data-test="matrix-packageF-deferred"]').exists()).toBe(true)
  })

  it('reads the rest when the reader asks, past the allowance', async () => {
    const wrapper = await mountOn(RELEASE_EARLIER, RELEASE_DEFERRED)
    await flushPromises()

    expect(comparePackages()).toHaveBeenCalledTimes(1)

    await wrapper.find('[data-test="packages-read-rest"]').trigger('click')
    await flushPromises()

    expect(comparePackages()).toHaveBeenCalledTimes(2)

    await wrapper.find('[data-test="matrix-row-packageF"]').trigger('click')
    expect(wrapper.find('[data-test="matrix-packageF-counts"]').text()).toContain(
      '2 commits added',
    )
  })

  it('says nothing is left waiting once everything is read', async () => {
    const wrapper = await mountOn(RELEASE_EARLIER, RELEASE_DEFERRED)
    await flushPromises()

    await wrapper.find('[data-test="packages-read-rest"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-test="packages-pending"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="packages-read-rest"]').exists()).toBe(false)
  })

  it('leaves a package the batch could not read saying so', async () => {
    comparePackages().mockRejectedValueOnce(new Error('git provider unreachable'))
    const wrapper = await mountView()
    await openOn(wrapper, [RELEASE_EARLIER, RELEASE_DEFERRED])
    await flushPromises()

    // a batch that failed must not read as a comparison that found nothing
    expect(wrapper.find('[data-test="packages-read-rest"]').exists()).toBe(true)

    await wrapper.find('[data-test="matrix-row-packageE"]').trigger('click')
    expect(wrapper.find('[data-test="matrix-packageE-deferred"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="matrix-packageE-counts"]').exists()).toBe(false)
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
    const wrapper = await mountOn(RELEASE_LATER, RELEASE_EARLIER)

    await wrapper.find('[data-test="depth-remember"] input').setValue(true)
    await setDepth(wrapper, 'deep')

    expect(localStorage.getItem('app_diff_depth')).toBe('deep')
    expect(depthPicker(wrapper).props('modelValue')).toBe('deep')
  })

  it('lets a kept reading depth go when the reader takes it back', async () => {
    localStorage.setItem('app_diff_depth', 'deep')
    const wrapper = await mountOn(RELEASE_LATER, RELEASE_EARLIER)

    // a reader is never stuck with a choice they made once
    await wrapper.find('[data-test="depth-remember"] input').setValue(false)

    expect(localStorage.getItem('app_diff_depth')).toBeNull()
  })

  it('opens on the depth that was kept', async () => {
    localStorage.setItem('app_diff_depth', 'deep')

    const wrapper = await mountOn(RELEASE_LATER, RELEASE_EARLIER)

    // the choice is read without the reader making it again, and it is asked for
    expect(depthPicker(wrapper).props('modelValue')).toBe('deep')
    expect(compare()).toHaveBeenCalledWith(
      expect.objectContaining({
        max_package_comparisons: 25,
        max_total_package_comparisons: 200,
      }),
    )
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

  it('offers the applications the registry names', async () => {
    // a link's coordinates save the walk through the pickers this test is not about
    const wrapper = await mountView('?project_key=CORE&repository_slug=app')
    await flushPromises()

    // the picker is decided by what an administrator named: a repository marked as a
    // package has no release records to read, and a project nobody has classified
    // falls back to every repository it has
    expect(vi.mocked(projectsApi.getProjectRepositories)).toHaveBeenCalledWith('CORE', {
      preferApplications: true,
    })
    expect(wrapper.find('[data-test="no-applications"]').exists()).toBe(false)
  })
})
