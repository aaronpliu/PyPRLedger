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
// stands in for the chart instance the view fit and the tooltip speak to.
const { dispatchAction, roamHandlers, chartFake } = vi.hoisted(() => {
  const roamHandlers: Array<(action?: { zoom?: number; dx?: number; dy?: number }) => void> = []
  const state = { points: [[100, 100], [300, 400], [500, 200]], zoom: 1 }
  const dispatchAction = vi.fn()
  const chartFake = {
    getWidth: () => 1000,
    getHeight: () => 500,
    getModel: () => ({
      getSeriesByIndex: () => ({
        getData: () => ({
          count: () => state.points.length,
          getItemLayout: (index: number) => state.points[index] ?? null,
          getName: (index: number) => ['app', 'packageA', 'packageB'][index] ?? `node-${index}`,
        }),
        coordinateSystem: { getZoom: () => state.zoom },
      }),
    }),
    // The view is the identity in the test: a data point converts to itself.
    convertToPixel: (_finder: unknown, point: number[]) => point,
    dispatchAction,
    on: (name: string, handler: (action?: { zoom?: number; dx?: number; dy?: number }) => void) => {
      if (name === 'graphRoam') roamHandlers.push(handler)
    },
  }
  return { dispatchAction, roamHandlers, chartFake }
})
vi.mock('vue-echarts', async () => {
  const { defineComponent, h } = await import('vue')
  return {
    default: defineComponent({
      name: 'VChartStub',
      props: ['option'],
      emits: ['click', 'mousedown', 'zr:dragend'],
      setup(_props, { expose }) {
        expose({ chart: chartFake, dispatchAction })
        return () => h('div', { class: 'v-chart-stub' })
      },
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
  // The view fit samples the layout on a timer: a mounted chart keeps sampling
  // until its picture holds still, so every test leaves with its chart unmounted.
  const UNTIL_SETTLED = 900

  it('leaves every node free until one is dropped by hand', () => {
    const wrapper = mountChart()

    // a fresh graph is the force layout's own arrangement: nothing held in place
    expect(nodeFixed(chartOption(wrapper), 'app')).toBe(false)
    expect(nodeFixed(chartOption(wrapper), 'packageA')).toBe(false)
    wrapper.unmount()
  })

  it('holds the dropped node where the reader left it', async () => {
    const wrapper = mountChart()
    await flushPromises()

    await dropNode(wrapper, 'packageA')

    // the package stays placed, its neighbour stays under the layout's control
    expect(nodeFixed(chartOption(wrapper), 'packageA')).toBe(true)
    expect(nodeFixed(chartOption(wrapper), 'packageB')).toBe(false)
    wrapper.unmount()
  })

  it('keeps a node placed across later drops', async () => {
    const wrapper = mountChart()
    await flushPromises()

    await dropNode(wrapper, 'packageA')
    await dropNode(wrapper, 'packageB')

    expect(nodeFixed(chartOption(wrapper), 'packageA')).toBe(true)
    expect(nodeFixed(chartOption(wrapper), 'packageB')).toBe(true)
    wrapper.unmount()
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
    wrapper.unmount()
  })

  it('writes the version a pinned edge carries onto its line', async () => {
    const wrapper = mountChart()
    await flushPromises()

    // one pin to place: app -> packageA, whose middle is the midpoint of the
    // two nodes the stub laid out, and the range edge is not a version to shout
    const pills = wrapper.findAll('.edge-label')
    expect(pills).toHaveLength(1)
    expect(pills[0].text()).toBe('@1.4.2')
    expect(pills[0].attributes('style')).toContain('left: 200px')
    expect(pills[0].attributes('style')).toContain('top: 250px')
    // along the edge, not at its feet: the angle runs from app to packageA
    expect(pills[0].attributes('style')).toContain('--angle: 56.309932474020215deg')
    wrapper.unmount()
  })

  it('drops the pills of the edges a picked node dims', async () => {
    const wrapper = mountChart()
    await flushPromises()
    expect(wrapper.findAll('.edge-label')).toHaveLength(1)

    await wrapper.setProps({ selectedId: 'packageB' })

    // packageB lights the edges it touches; app -> packageA dims out of the story
    expect(wrapper.findAll('.edge-label')).toHaveLength(0)
    wrapper.unmount()
  })

  it('drops a tooltip the rescaled view left behind', async () => {
    dispatchAction.mockClear()
    const wrapper = mountChart()
    await flushPromises()

    // the fit zooms the settled picture into frame: a tooltip anchored to where
    // the node used to stand describes a place the node has left
    roamHandlers[roamHandlers.length - 1]?.({ zoom: 1.4 })

    expect(dispatchAction).toHaveBeenCalledWith({ type: 'hideTip' })
    wrapper.unmount()
  })

  it('leaves a tooltip in place while the pan carries it', async () => {
    dispatchAction.mockClear()
    const wrapper = mountChart()
    await flushPromises()

    // a pan slides the whole picture: the tooltip travels with its node
    roamHandlers[roamHandlers.length - 1]?.({ dx: 12, dy: -6 })

    expect(dispatchAction).not.toHaveBeenCalledWith({ type: 'hideTip' })
    wrapper.unmount()
  })

  it('scales the settled graph into the canvas and centres it', async () => {
    dispatchAction.mockClear()
    const wrapper = mountChart()

    // the stub's layout spans a small box on a large canvas: fitting it means
    // zooming in, then panning the picture back to the middle
    await new Promise((resolve) => setTimeout(resolve, UNTIL_SETTLED))

    const roams = dispatchAction.mock.calls.map((call) => call[0]).filter((action) => action?.type === 'graphRoam')
    expect(roams.some((action) => action.zoom > 1)).toBe(true)
    expect(roams.some((action) => action.dx !== undefined)).toBe(true)
    wrapper.unmount()
  })

  it('leaves the view alone once the reader has roamed it', async () => {
    dispatchAction.mockClear()
    const wrapper = mountChart()

    // the reader pans by hand: from here the view is theirs, fit or no fit
    roamHandlers[roamHandlers.length - 1]?.()
    await new Promise((resolve) => setTimeout(resolve, UNTIL_SETTLED))

    const roams = dispatchAction.mock.calls.map((call) => call[0]).filter((action) => action?.type === 'graphRoam')
    expect(roams).toHaveLength(0)
    wrapper.unmount()
  })
})
