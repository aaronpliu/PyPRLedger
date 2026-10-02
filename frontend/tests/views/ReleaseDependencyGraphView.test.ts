import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus, { ElRadioGroup, ElSelect, ElSwitch } from 'element-plus'
import { createI18n } from 'vue-i18n'
import ReleaseDependencyGraphView from '@/views/releases/ReleaseDependencyGraphView.vue'
import enMessages from '@/locales/en.json'

// The shape of the option the chart hands to the (stubbed) canvas - only what
// the assertions below read.
interface ChartOptionNode {
  name: string
  itemStyle?: { opacity?: number }
}
interface ReleaseDependencyGraphChartOption {
  series: [
    {
      data: ChartOptionNode[]
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

function chartOption(wrapper: ReturnType<typeof mountView>): ReleaseDependencyGraphChartOption {
  const chart = wrapper.findComponent({ name: 'VChartStub' })
  return chart.props('option') as unknown as ReleaseDependencyGraphChartOption
}

function nodeOpacity(option: ReleaseDependencyGraphChartOption, id: string): number | undefined {
  return option.series[0].data.find((node) => node.name === id)?.itemStyle?.opacity
}

function clickNode(wrapper: ReturnType<typeof mountView>, id: string) {
  wrapper.findComponent({ name: 'VChartStub' }).vm.$emit('click', {
    dataType: 'node',
    data: { id },
  })
}

describe('ReleaseDependencyGraphView', () => {
  it('opens on the complete graph of the latest release, nothing picked', async () => {
    const wrapper = mountView()
    await flushPromises()

    // v2.0.0, the whole closure: eight packages, seventeen edges - the cycle
    // among them, not only the app's own six edges
    expect(wrapper.text()).toContain('Packages: 8')
    expect(wrapper.text()).toContain('Dependencies: 17')
    expect(wrapper.text()).toContain('Pick a node in the graph')
    expect(wrapper.text()).toContain('2026-09-30')
    expect(wrapper.text()).toContain('2.0.0')
    // nothing is dimmed before a pick is spent
    expect(nodeOpacity(chartOption(wrapper), 'packageE')).toBe(1)
  })

  it('shows the picked package with the constraints its edges declare', async () => {
    const wrapper = mountView()
    await flushPromises()

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

  it('draws the graph of another release when the version is picked', async () => {
    const wrapper = mountView()
    await flushPromises()

    wrapper.findComponent(ElSelect).vm.$emit('update:modelValue', '1.0.0')
    await flushPromises()

    // v1.0.0 in full: seven packages, ten edges - a smaller graph, no cycle
    expect(wrapper.text()).toContain('Packages: 7')
    expect(wrapper.text()).toContain('Dependencies: 10')
    expect(wrapper.text()).toContain('2026-06-15')
    // packageG arrived in a later release: not drawn, not countenanced
    expect(nodeOpacity(chartOption(wrapper), 'packageG')).toBeUndefined()
  })

  it('clears a pick the picked release does not name', async () => {
    const wrapper = mountView()
    await flushPromises()

    clickNode(wrapper, 'packageG')
    await flushPromises()

    wrapper.findComponent(ElSelect).vm.$emit('update:modelValue', '1.0.0')
    await flushPromises()

    expect(wrapper.text()).toContain('Pick a node in the graph')
  })
})
