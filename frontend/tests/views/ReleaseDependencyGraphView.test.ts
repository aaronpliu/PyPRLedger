import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus, { ElRadioGroup, ElSelect, ElSwitch } from 'element-plus'
import { createI18n } from 'vue-i18n'
import ReleaseDependencyGraphView from '@/views/releases/ReleaseDependencyGraphView.vue'
import enMessages from '@/locales/en.json'
import { projectsApi } from '@/api/projects'

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
    listRefs: async () => ({
      project_key: 'CORE',
      repository_slug: 'app',
      git_provider: 'bitbucket_server',
      tags: ['v2.0.0', 'v1.1.0', 'v1.0.0', 'v9.9.9'],
      branches: ['main'],
    }),
  },
}))

// The dependency database answers for the refs the fixture holds; one ref has
// no record, the way a repository whose build was never scanned has none.
vi.mock('@/api/releaseDependencyGraph', async () => {
  const { dependencyFileOf } = await import('../fixtures/dependencyFiles')
  return {
    releaseDependencyGraphApi: {
      read: async (payload: { ref: string }) => {
        if (payload.ref === 'v9.9.9') {
          throw new Error('no dependency record')
        }
        return dependencyFileOf(payload.ref)
      },
    },
  }
})

// The shape of the option the chart hands to the (stubbed) canvas - only what
// the assertions below read.
interface ChartOptionNode {
  name: string
  symbolSize?: number
  itemStyle?: { opacity?: number }
}
interface ReleaseDependencyGraphChartOption {
  series: [
    {
      data: ChartOptionNode[]
      categories: Array<{ name: string }>
    },
  ]
}

// The canvas renderer has nothing to draw on in the test DOM; the stub keeps
// the props and the click event, which is all this view's behaviour is about.
vi.mock('vue-echarts', async () => {
  const { defineComponent, h } = await import('vue')
  return {
    default: defineComponent({
      name: 'VChartStub',
      props: ['option'],
      emits: ['click'],
      setup() {
        return () => h('div', { class: 'v-chart-stub' })
      },
    }),
  }
})

function mountView() {
  const i18n = createI18n({
    legacy: false,
    locale: 'en',
    messages: { en: enMessages },
  })

  return mount(ReleaseDependencyGraphView, {
    global: {
      plugins: [ElementPlus, i18n],
    },
  })
}

type View = ReturnType<typeof mountView>

/** Pick one of the form's selects, the way a reader does. */
async function pick(wrapper: View, index: number, value: string) {
  wrapper.findAllComponents(ElSelect)[index].vm.$emit('update:modelValue', value)
  await flushPromises()
  await flushPromises()
}

/** Walk as far as the repository: the ref is still the reader's to pick. */
async function openRepository(wrapper: View) {
  await pick(wrapper, 0, 'CORE')
  await pick(wrapper, 1, 'app')
}

/**
 * Walk the picker the way a reader does: a project, a repository, then a ref.
 * Nothing is read before that last choice is made.
 */
async function openOn(wrapper: View, ref: string = 'v2.0.0') {
  await openRepository(wrapper)
  await pick(wrapper, 3, ref)
}

function chartOption(wrapper: View): ReleaseDependencyGraphChartOption {
  const chart = wrapper.findComponent({ name: 'VChartStub' })
  return chart.props('option') as unknown as ReleaseDependencyGraphChartOption
}

function nodeOpacity(option: ReleaseDependencyGraphChartOption, id: string): number | undefined {
  return option.series[0].data.find((node) => node.name === id)?.itemStyle?.opacity
}

function nodeSize(wrapper: View, id: string): number | undefined {
  return chartOption(wrapper).series[0].data.find((node) => node.name === id)?.symbolSize
}

function clickNode(wrapper: View, id: string) {
  wrapper.findComponent({ name: 'VChartStub' }).vm.$emit('click', {
    dataType: 'node',
    data: { id },
  })
}

describe('ReleaseDependencyGraphView', () => {
  it('waits for a repository before it draws anything', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('Pick a project and a repository')
    expect(wrapper.find('[data-test="release-dependency-graph-chart"]').exists()).toBe(false)
  })

  it('auto selects the git provider of the chosen project', async () => {
    const wrapper = mountView()
    await flushPromises()

    const selects = wrapper.findAllComponents(ElSelect)
    await selects[0].vm.$emit('update:modelValue', 'GHE')
    await flushPromises()

    expect(selects[2].props('modelValue')).toBe('github_enterprise')
  })

  it('waits for a ref to be picked before it reads anything', async () => {
    const wrapper = mountView()
    await flushPromises()
    await openRepository(wrapper)

    // the refs are suggestions of the provider, not a choice made for the reader
    expect(wrapper.find('[data-test="pick-ref"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="release-dependency-graph-chart"]').exists()).toBe(false)

    await pick(wrapper, 3, 'v2.0.0')

    // v2.0.0, the whole closure: eight packages, seventeen edges - the cycle
    // among them, not only the app's own six edges
    expect(wrapper.text()).toContain('Packages: 8')
    expect(wrapper.text()).toContain('Dependencies: 17')
    expect(wrapper.text()).toContain('Pick a node in the graph')
    expect(wrapper.text()).toContain('2026-09-30')
    expect(wrapper.text()).toContain('v2.0.0')
    // nothing is dimmed before a pick is spent
    expect(nodeOpacity(chartOption(wrapper), 'packageE')).toBe(1)
  })

  it('names and sizes each category the way the file numbers them', async () => {
    const wrapper = mountView()
    await flushPromises()
    await openOn(wrapper)

    // 0 = the project, 1 = a dependency, 2 = a package the application ships
    expect(chartOption(wrapper).series[0].categories.map((entry) => entry.name)).toEqual([
      'Project',
      'Dependency',
      'Workspace package',
    ])

    // the application is the largest, the packages it ships the middle, what it
    // pulls in the smallest - never the other way round
    expect(nodeSize(wrapper, 'app')).toBe(52)
    expect(nodeSize(wrapper, 'packageA')).toBe(38)
    expect(nodeSize(wrapper, 'packageE')).toBe(26)
  })

  it('names the role of a picked package the way the file numbers it', async () => {
    const wrapper = mountView()
    await flushPromises()
    await openOn(wrapper)

    // packageA (category 2) is a package the application ships...
    clickNode(wrapper, 'packageA')
    await flushPromises()
    expect(wrapper.find('[data-test="detail-panel"]').text()).toContain('Workspace package')

    // ...and packageE (category 1) is a dependency it pulls in
    clickNode(wrapper, 'packageE')
    await flushPromises()
    const panel = wrapper.find('[data-test="detail-panel"]')
    expect(panel.text()).toContain('Dependency')
    expect(panel.text()).not.toContain('Workspace package')
  })

  it('shows the picked package with the constraints its edges declare', async () => {
    const wrapper = mountView()
    await flushPromises()
    await openOn(wrapper)

    clickNode(wrapper, 'packageE')
    await flushPromises()

    const panel = wrapper.find('[data-test="detail-panel"]')
    expect(panel.text()).toContain('packageE')
    expect(panel.text()).toContain('@3.1.0')
    // an external package declares nothing of its own
    expect(panel.text()).toContain('Dependencies (0)')
    // the app pins it, the three packages take it by range
    expect(panel.text()).toContain('Dependents (4)')
    expect(panel.text()).toContain('>=3.0.0 <4.0.0')
    expect(panel.text()).toContain('3.1.0')
  })

  it('reads a range differently from an exact version', async () => {
    const wrapper = mountView()
    await flushPromises()
    await openOn(wrapper)

    clickNode(wrapper, 'packageE')
    await flushPromises()

    const panel = wrapper.find('[data-test="detail-panel"]')
    const ranges = panel.findAll('.detail-constraint.is-range')
    const pinned = panel.findAll('.detail-constraint:not(.is-range)')
    // packageA, packageC and packageD declare ranges for packageE
    expect(ranges.map((span) => span.text())).toEqual([
      '>=3.0.0 <4.0.0',
      '>=3.0.0 <4.0.0',
      '>=3.0.0 <4.0.0',
    ])
    // the app names it by the exact version
    expect(pinned.map((span) => span.text())).toEqual(['3.1.0'])
  })

  it('dims everything the picked package does not touch', async () => {
    const wrapper = mountView()
    await flushPromises()
    await openOn(wrapper)

    clickNode(wrapper, 'packageA')
    await flushPromises()

    const option = chartOption(wrapper)
    // the complete graph is on the canvas: the pick, the packages it names,
    // and the packages that name it
    expect(nodeOpacity(option, 'packageA')).toBe(1)
    expect(nodeOpacity(option, 'app')).toBe(1)
    // packageB and packageD both name packageA - the latter closes the cycle
    expect(nodeOpacity(option, 'packageB')).toBe(1)
    expect(nodeOpacity(option, 'packageD')).toBe(1)
    expect(nodeOpacity(option, 'packageC')).toBe(1)
    expect(nodeOpacity(option, 'packageE')).toBe(1)
    // what the pick neither pulls in nor is pulled in by is context now
    expect(nodeOpacity(option, 'packageF')).toBe(0.12)
    expect(nodeOpacity(option, 'packageG')).toBe(0.12)
  })

  it('walks the full closure when the transitive switch is on', async () => {
    const wrapper = mountView()
    await flushPromises()
    await openOn(wrapper)

    clickNode(wrapper, 'app')
    await flushPromises()

    const option = chartOption(wrapper)
    // packageD is named only by packageA, so the app's direct view leaves it
    expect(nodeOpacity(option, 'packageD')).toBe(0.12)

    wrapper.findComponent(ElSwitch).vm.$emit('update:modelValue', true)
    await flushPromises()

    // the closure reaches packageD once the switch is spent
    expect(nodeOpacity(chartOption(wrapper), 'packageD')).toBe(1)
  })

  it('clears the pick when the same package is clicked again', async () => {
    const wrapper = mountView()
    await flushPromises()
    await openOn(wrapper)

    clickNode(wrapper, 'packageE')
    await flushPromises()
    clickNode(wrapper, 'packageE')
    await flushPromises()

    expect(wrapper.text()).toContain('Pick a node in the graph')
    expect(nodeOpacity(chartOption(wrapper), 'packageF')).toBe(1)
  })

  it('deepens the view when a panel dependency is off the canvas', async () => {
    const wrapper = mountView()
    await flushPromises()
    await openOn(wrapper)

    // trim to what the app names: packageD is named by packageA, so it waits
    // off the canvas until the view is deepened
    wrapper.findComponent(ElRadioGroup).vm.$emit('update:modelValue', '1')
    await flushPromises()
    clickNode(wrapper, 'packageA')
    await flushPromises()

    const panel = wrapper.find('[data-test="detail-panel"]')
    await panel
      .findAll('button.detail-link')
      .find((button) => button.text() === 'packageD')!
      .trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Packages: 8')
    const detail = wrapper.find('[data-test="detail-panel"]')
    expect(detail.text()).toContain('packageD')
    // packageD reaches back to packageA: the cycle warning is on
    expect(detail.text()).toContain('circular dependency')
    expect(nodeOpacity(chartOption(wrapper), 'packageD')).toBe(1)
  })

  it('trims the closure to the picked depth', async () => {
    const wrapper = mountView()
    await flushPromises()
    await openOn(wrapper)

    wrapper.findComponent(ElRadioGroup).vm.$emit('update:modelValue', '1')
    await flushPromises()

    // what the app names on its own
    expect(wrapper.text()).toContain('Packages: 7')
    expect(wrapper.text()).toContain('Dependencies: 6')

    wrapper.findComponent(ElRadioGroup).vm.$emit('update:modelValue', '2')
    await flushPromises()

    // everything two hops out: all eight packages, fifteen edges
    expect(wrapper.text()).toContain('Packages: 8')
    expect(wrapper.text()).toContain('Dependencies: 15')
  })

  it('draws the graph of another ref when the tag is picked', async () => {
    const wrapper = mountView()
    await flushPromises()
    await openOn(wrapper, 'v1.0.0')

    // v1.0.0 in full: seven packages, ten edges - a smaller graph, no cycle
    expect(wrapper.text()).toContain('Packages: 7')
    expect(wrapper.text()).toContain('Dependencies: 10')
    expect(wrapper.text()).toContain('2026-06-15')
    // packageG arrived in a later release: not drawn, not countenanced
    expect(nodeOpacity(chartOption(wrapper), 'packageG')).toBeUndefined()
  })

  it('draws the walk of a branch, not only of a tag', async () => {
    const wrapper = mountView()
    await flushPromises()
    await openOn(wrapper, 'main')

    // main carries what the walk produced at its tip: packageH is on it
    expect(wrapper.text()).toContain('Packages: 9')
    expect(wrapper.text()).toContain('2026-10-01')
    expect(nodeOpacity(chartOption(wrapper), 'packageH')).toBe(1)
  })

  it('clears a pick the picked ref does not name', async () => {
    const wrapper = mountView()
    await flushPromises()
    await openOn(wrapper)

    clickNode(wrapper, 'packageG')
    await flushPromises()

    await openOn(wrapper, 'v1.0.0')

    expect(wrapper.text()).toContain('Pick a node in the graph')
  })

  it('says so when the dependency database holds nothing for the ref', async () => {
    const wrapper = mountView()
    await flushPromises()
    await openOn(wrapper, 'v9.9.9')

    expect(wrapper.text()).toContain('No dependency data for this ref')
    expect(wrapper.find('[data-test="release-dependency-graph-chart"]').exists()).toBe(false)
  })

  it('picks only a ref the repository reports', async () => {
    const wrapper = mountView()
    await flushPromises()
    await openRepository(wrapper)

    // The picker searches the repository's listing rather than accepting a typed
    // name: a tag that does not exist cannot be read, so it cannot be picked.
    const refSelect = wrapper.findAllComponents(ElSelect)[3]
    expect(refSelect.props('allowCreate')).toBe(false)
    expect(refSelect.props('remote')).toBe(true)
    expect(refSelect.findAllComponents({ name: 'ElOption' }).map((option) => option.props('value')))
      .toContain('v2.0.0')
  })

  it('leaves out only the repositories marked as packages', async () => {
    const wrapper = mountView()
    await flushPromises()
    await openRepository(wrapper)

    // this page reads the releases the dependency database holds, so a repository an
    // administrator marked as a package is not offered - and everything nobody has
    // classified is, which is what keeps the classification an opt-in
    expect(vi.mocked(projectsApi.getProjectRepositories)).toHaveBeenCalledWith('CORE', [
      'application',
      'unclassified',
    ])
  })
})
