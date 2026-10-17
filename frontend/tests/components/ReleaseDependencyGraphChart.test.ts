import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import ReleaseDependencyGraphChart from '@/components/charts/ReleaseDependencyGraphChart.vue'
import type { ReleaseDependencyGraphLink, ReleaseDependencyGraphNode } from '@/utils/releaseDependencyGraph'

// The shape of the option the chart hands to the (stubbed) canvas - only what
// the assertions below read.
interface ChartNode {
  id: string
  name: string
  fixed: boolean
  x?: number
  y?: number
}
interface ReleaseDependencyGraphChartOption {
  series: [{ layout: string; draggable: boolean; data: ChartNode[] }]
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
const { dispatchAction, roamHandlers, dblclickHandlers, chartFake, setZoom } = vi.hoisted(() => {
  const roamHandlers: Array<(action?: { zoom?: number; dx?: number; dy?: number }) => void> = []
  const dblclickHandlers: Array<(params?: unknown) => void> = []
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
    on: (name: string, handler: (payload?: unknown) => void) => {
      if (name === 'graphRoam') {
        roamHandlers.push(handler as (action?: { zoom?: number; dx?: number; dy?: number }) => void)
      }
      if (name === 'dblclick') dblclickHandlers.push(handler)
    },
  }
  return {
    dispatchAction,
    roamHandlers,
    dblclickHandlers,
    chartFake,
    setZoom: (zoom: number) => {
      state.zoom = zoom
    },
  }
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

function mountWith(props: {
  nodes?: ReleaseDependencyGraphNode[]
  links?: ReleaseDependencyGraphLink[]
  viewKey?: string
}) {
  return mount(ReleaseDependencyGraphChart, {
    props: { nodes, links, ...props },
    // The canvas is stubbed above; the toolbar around it is Element Plus.
    global: { plugins: [ElementPlus] },
  })
}

const mountChart = () => mountWith({})

/** A closure large enough that the force layout would never settle into a picture. */
function bigGraph(): { nodes: ReleaseDependencyGraphNode[]; links: ReleaseDependencyGraphLink[] } {
  const many: ReleaseDependencyGraphNode[] = [{ id: 'app', name: 'app', category: 0 }]
  const edges: ReleaseDependencyGraphLink[] = []
  for (let index = 0; index < 160; index++) {
    const id = `pkg-${index}`
    many.push({ id, name: id, category: 1 })
    edges.push({ source: 'app', target: id })
  }
  return { nodes: many, links: edges }
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

  it('lends the graph the window and gives the page it back', async () => {
    const wrapper = mountChart()
    await flushPromises()

    await wrapper.find('[data-test="graph-maximize"]').trigger('click')
    // the frame is the window now, not the card the page had given it
    expect(wrapper.find('.chart').classes()).toContain('maximized')

    await wrapper.find('[data-test="graph-maximize"]').trigger('click')
    expect(wrapper.find('.chart').classes()).not.toContain('maximized')

    wrapper.unmount()
  })

  it('leaves the window-sized frame on Escape as well', async () => {
    const wrapper = mountChart()
    await flushPromises()

    await wrapper.find('[data-test="graph-maximize"]').trigger('click')
    expect(wrapper.find('.chart').classes()).toContain('maximized')

    // a frame that covers the page needs a way out that is not a small button
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await flushPromises()

    expect(wrapper.find('.chart').classes()).not.toContain('maximized')
    wrapper.unmount()
  })

  it('zooms the picture from the toolbar, around the middle of the canvas', async () => {
    dispatchAction.mockClear()
    const wrapper = mountChart()
    await flushPromises()

    await wrapper.find('[data-test="graph-zoom-in"]').trigger('click')
    await wrapper.find('[data-test="graph-zoom-out"]').trigger('click')

    const roams = dispatchAction.mock.calls
      .map((call) => call[0])
      .filter((action) => action?.type === 'graphRoam')
    // One press scales one step from the middle: a press has no pointer to zoom on.
    expect(roams[0]).toEqual({ type: 'graphRoam', zoom: 1.25, originX: 500, originY: 250 })
    expect(roams[1]).toEqual({ type: 'graphRoam', zoom: 0.8, originX: 500, originY: 250 })
    wrapper.unmount()
  })

  it('puts the picture back in frame when the fit is asked for', async () => {
    dispatchAction.mockClear()
    const wrapper = mountChart()
    await flushPromises()

    // the reader takes the view by hand: the fit stops following the picture
    roamHandlers[roamHandlers.length - 1]?.()
    await new Promise((resolve) => setTimeout(resolve, 400))
    dispatchAction.mockClear()

    await wrapper.find('[data-test="graph-fit"]').trigger('click')
    await new Promise((resolve) => setTimeout(resolve, 700))

    const roams = dispatchAction.mock.calls
      .map((call) => call[0])
      .filter((action) => action?.type === 'graphRoam')
    // handing the view back is what the button is for: the picture fits again
    expect(roams.some((action) => action.zoom > 1)).toBe(true)
    wrapper.unmount()
  })

  it('draws a closure too large to settle as rows instead', async () => {
    const wrapper = mountWith(bigGraph())
    await flushPromises()

    const option = chartOption(wrapper)
    // rows rather than a force simulation: the same graph, arranged where it reads
    expect(option.series[0].layout).toBe('none')
    expect(option.series[0].draggable).toBe(false)
    expect(typeof option.series[0].data[0].x).toBe('number')
    expect(typeof option.series[0].data[0].y).toBe('number')
    // and the canvas says why the picture holds still
    expect(wrapper.find('.chart-note').text()).toBe('Layered layout')

    wrapper.unmount()
  })

  it('clears the placements the reader made by hand', async () => {
    const wrapper = mountChart()
    await flushPromises()

    await dropNode(wrapper, 'packageA')
    expect(nodeFixed(chartOption(wrapper), 'packageA')).toBe(true)

    await wrapper.find('[data-test="graph-reset"]').trigger('click')
    await flushPromises()

    // back to the layout's own arrangement
    expect(nodeFixed(chartOption(wrapper), 'packageA')).toBe(false)
    wrapper.unmount()
  })

  it('magnifies the package a double-click names, and centres it', async () => {
    dispatchAction.mockClear()
    const wrapper = mountChart()
    await flushPromises()

    dblclickHandlers[dblclickHandlers.length - 1]?.({
      dataType: 'node',
      data: { id: 'packageA' },
      event: { offsetX: 400, offsetY: 300 },
    })

    const roams = dispatchAction.mock.calls
      .map((call) => call[0])
      .filter((action) => action?.type === 'graphRoam')
    // one step in, where the reader pointed...
    expect(roams[0]).toEqual({ type: 'graphRoam', zoom: 1.8, originX: 400, originY: 300 })
    // ...and then the point under the pointer is the middle of the canvas
    expect(roams[1]).toEqual({ type: 'graphRoam', dx: 100, dy: -50 })
    wrapper.unmount()
  })

  it('answers the toolbar keys from the page', async () => {
    dispatchAction.mockClear()
    const wrapper = mountChart()
    await flushPromises()

    window.dispatchEvent(new KeyboardEvent('keydown', { key: '+' }))
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'f' }))
    await flushPromises()

    const roams = dispatchAction.mock.calls
      .map((call) => call[0])
      .filter((action) => action?.type === 'graphRoam')
    expect(roams[0]).toMatchObject({ zoom: 1.25 })
    expect(wrapper.find('.chart').classes()).toContain('maximized')
    wrapper.unmount()
  })

  it('leaves the keys to a field the reader is typing in', async () => {
    dispatchAction.mockClear()
    const wrapper = mountChart()
    await flushPromises()

    const input = document.createElement('input')
    document.body.appendChild(input)
    input.dispatchEvent(new KeyboardEvent('keydown', { key: '+', bubbles: true }))
    document.body.removeChild(input)
    await flushPromises()

    const roams = dispatchAction.mock.calls
      .map((call) => call[0])
      .filter((action) => action?.type === 'graphRoam')
    expect(roams).toHaveLength(0)
    wrapper.unmount()
  })

  it('opens a repository at the zoom it was left at', async () => {
    window.localStorage.setItem('release-dependency-graph:view:CORE/app', '{"zoom":1.5}')
    dispatchAction.mockClear()
    const wrapper = mountWith({ viewKey: 'CORE/app' })

    await new Promise((resolve) => setTimeout(resolve, UNTIL_SETTLED))

    const roams = dispatchAction.mock.calls
      .map((call) => call[0])
      .filter((action) => action?.type === 'graphRoam')
    // the stored zoom, not the fit's own: the repository was left this way
    expect(roams.some((action) => Math.abs(action.zoom - 1.5) < 1e-6)).toBe(true)

    wrapper.unmount()
    window.localStorage.removeItem('release-dependency-graph:view:CORE/app')
  })

  it('remembers the zoom a repository was left at', async () => {
    window.localStorage.removeItem('release-dependency-graph:view:CORE/web')
    const wrapper = mountWith({ viewKey: 'CORE/web' })
    await flushPromises()

    setZoom(1.7)
    // the reader's own zoom, not the fit's: from here the view is this repository's
    roamHandlers[roamHandlers.length - 1]?.({ zoom: 1.7 })

    expect(window.localStorage.getItem('release-dependency-graph:view:CORE/web')).toBe(
      '{"zoom":1.7}',
    )
    setZoom(1)
    wrapper.unmount()
    window.localStorage.removeItem('release-dependency-graph:view:CORE/web')
  })
})
