import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ReleaseDependencyGraphChart from '@/components/charts/ReleaseDependencyGraphChart.vue'
import type { ReleaseDependencyGraphLink, ReleaseDependencyGraphNode } from '@/utils/releaseDependencyGraph'

// The shape of the option the chart hands to the (stubbed) canvas - only what
// the assertions below read.
interface ChartNode {
  id: string
  name: string
  fixed: boolean
}
interface ReleaseDependencyGraphChartOption {
  series: [{ data: ChartNode[] }]
}

const nodes: ReleaseDependencyGraphNode[] = [
  { id: 'app', name: 'app', category: 0, version: '2.0.0' },
  { id: 'packageA', name: 'packageA', category: 2, version: '1.0.0' },
  { id: 'packageB', name: 'packageB', category: 2, version: '2.0.0' },
]

const links: ReleaseDependencyGraphLink[] = [
  { source: 'app', target: 'packageA', constraint: '1.4.2', pinned: true },
  { source: 'packageA', target: 'packageB', constraint: '>=1.0.0 <2.0.0', pinned: false },
]

// The canvas renderer has nothing to draw on in the test DOM: the stub keeps the
// option, forwards the events the component listens for on zrender's side, and
// exposes the dispatchAction the wheel handler hides the tooltip with.
const { dispatchAction } = vi.hoisted(() => ({ dispatchAction: vi.fn() }))
vi.mock('vue-echarts', async () => {
  const { defineComponent, h } = await import('vue')
  return {
    default: defineComponent({
      name: 'VChartStub',
      props: ['option'],
      emits: ['click', 'mousedown', 'zr:dragend', 'zr:mousewheel'],
      setup() {
        return () => h('div', { class: 'v-chart-stub' })
      },
      methods: { dispatchAction },
    }),
  }
})

function mountChart() {
  return mount(ReleaseDependencyGraphChart, {
    props: { nodes, links },
  })
}

function chartOption(wrapper: ReturnType<typeof mountChart>): ReleaseDependencyGraphChartOption {
  const chart = wrapper.findComponent({ name: 'VChartStub' })
  return chart.props('option') as unknown as ReleaseDependencyGraphChartOption
}

function nodeFixed(option: ReleaseDependencyGraphChartOption, id: string): boolean | undefined {
  return option.series[0].data.find((node) => node.id === id)?.fixed
}

/** A pointer press on the node, then the release of the drag zrender reports. */
async function dropNode(wrapper: ReturnType<typeof mountChart>, id: string) {
  const chart = wrapper.findComponent({ name: 'VChartStub' })
  chart.vm.$emit('mousedown', { dataType: 'node', data: { id } })
  chart.vm.$emit('zr:dragend', { target: {} })
  await flushPromises()
}

describe('ReleaseDependencyGraphChart', () => {
  it('leaves every node free until one is dropped by hand', () => {
    const wrapper = mountChart()

    // a fresh graph is the force layout's own arrangement: nothing held in place
    expect(nodeFixed(chartOption(wrapper), 'app')).toBe(false)
    expect(nodeFixed(chartOption(wrapper), 'packageA')).toBe(false)
  })

  it('holds the dropped node where the reader left it', async () => {
    const wrapper = mountChart()
    await flushPromises()

    await dropNode(wrapper, 'packageA')

    // the package stays placed, its neighbour stays under the layout's control
    expect(nodeFixed(chartOption(wrapper), 'packageA')).toBe(true)
    expect(nodeFixed(chartOption(wrapper), 'packageB')).toBe(false)
  })

  it('keeps a node placed across later drops', async () => {
    const wrapper = mountChart()
    await flushPromises()

    await dropNode(wrapper, 'packageA')
    await dropNode(wrapper, 'packageB')

    expect(nodeFixed(chartOption(wrapper), 'packageA')).toBe(true)
    expect(nodeFixed(chartOption(wrapper), 'packageB')).toBe(true)
  })

  it('places nothing when the press was not on a node', async () => {
    const wrapper = mountChart()
    await flushPromises()

    // an edge answers the hover question, it is not a thing to be moved
    const chart = wrapper.findComponent({ name: 'VChartStub' })
    chart.vm.$emit('mousedown', { dataType: 'edge', data: links[0] })
    chart.vm.$emit('zr:dragend', { target: {} })
    await flushPromises()

    expect(nodeFixed(chartOption(wrapper), 'app')).toBe(false)
    expect(nodeFixed(chartOption(wrapper), 'packageA')).toBe(false)
  })

  it('drops a stale tooltip as the wheel moves the graph', async () => {
    dispatchAction.mockClear()
    const wrapper = mountChart()
    await flushPromises()

    wrapper.findComponent({ name: 'VChartStub' }).vm.$emit('zr:mousewheel', {})

    // the box was anchored to the canvas as it was: zooming out leaves it there
    expect(dispatchAction).toHaveBeenCalledWith({ type: 'hideTip' })
  })
})
