<template>
  <!-- Force layout: a dependency closure is a graph with cycles, not a dag, and
       the reader pans and pins nodes by hand until it reads the way they think -->
  <div class="chart">
    <v-chart
      class="canvas"
      ref="chartRef"
      :option="chartOption"
      autoresize
      @click="onNodeClick"
      @mousedown="onNodePress"
      @zr:dragend="onNodeDragEnd"
    />
    <!-- The version a pinned edge carries, written on its own line. The canvas
         draws its edge labels in whatever zoom the view hands the label layout
         and only cleans them up when the view roams, so they drift off their
         lines and scale with the zoom: these sit over the canvas and follow the
         layout frame by frame. -->
    <div class="edge-labels" aria-hidden="true">
      <span
        v-for="label in edgeLabels"
        :key="label.id"
        class="edge-label"
        :style="{ left: `${label.x}px`, top: `${label.y}px`, '--angle': `${label.angle}deg` }"
        >@{{ label.text }}</span
      >
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, unref, watch } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import type { ECharts } from 'echarts/core'
import { GraphChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { pinnedEdgeLabels, relatedHighlight } from '@/utils/releaseDependencyGraph'
import type {
  ReleaseDependencyGraphData,
  ReleaseDependencyGraphLink,
  ReleaseDependencyGraphNode,
} from '@/utils/releaseDependencyGraph'

use([GraphChart, TooltipComponent, LegendComponent, CanvasRenderer])

interface Props {
  nodes: ReleaseDependencyGraphNode[]
  links: ReleaseDependencyGraphLink[]
  /** The picked node; its relationships stay in full colour, the rest dims. */
  selectedId?: string | null
  /** Highlight the whole closure of the picked node, not just its neighbours. */
  transitive?: boolean
  /** Legend names for categories 0, 1 and 2 - the page localises them. */
  categoryNames?: string[]
  height?: string
}

const props = withDefaults(defineProps<Props>(), {
  selectedId: null,
  transitive: false,
  categoryNames: () => ['Project', 'Workspace package', 'Dependency'],
  height: '600px',
})

const emit = defineEmits<{
  (e: 'node-click', id: string): void
}>()

const chartRef = ref<InstanceType<typeof VChart> | null>(null)

/** The ECharts instance behind the canvas, once vue-echarts has mounted it. */
function chartInstance(): ECharts | null {
  return unref(chartRef.value?.chart) ?? null
}

// The force layout settles slowly, and settles at a size of its own choosing:
// the view then scales and centres on what actually landed, so the graph reads
// as large as the canvas allows whatever the closure's shape. A view the reader
// panned or zoomed by hand is left exactly where they put it.
const FIT_FILL = 0.9
const FIT_ZOOM_MAX = 2
// A node carries its name above it: the label clears the symbol by its height.
const LABEL_MARGIN = 50
let roamedByHand = false
let fittingView = false
// One fit loop at a time: the newest trigger wins, the older one stands down.
let fitGeneration = 0
// Which node the pointer is down on: zrender drags speak only of elements, the
// mouse event is what names the package under it.
let pressedNodeId: string | null = null

interface ContentBox {
  minX: number
  maxX: number
  minY: number
  maxY: number
}

/** The roam view of the graph series, where pan and zoom live. */
interface GraphView {
  getZoom(): number
}

interface GraphSeries {
  getData(): {
    count(): number
    getItemLayout(index: number): number[] | null
    getName(index: number): string
  }
  coordinateSystem?: GraphView
}

/** Layout positions live on the model, which the public API keeps private. */
interface ChartInternals {
  getModel?(): { getSeriesByIndex(index: number): GraphSeries | undefined } | undefined
}

function graphSeries(chart: ECharts): GraphSeries | undefined {
  // The model is absent on the first frames of a render - ECharts keeps it
  // private and hands it over only once the graph is built - and reaching for
  // it there throws out of the render handler on every frame of the animation.
  const model = (chart as unknown as ChartInternals).getModel?.()
  return model?.getSeriesByIndex(0)
}

/** One version pin, placed where its edge sits as the canvas draws it now. */
interface EdgeLabelPosition {
  /** Names the edge, so the pill keeps its place between placements. */
  id: string
  /** The middle of the edge, in the pixels the chart paints in. */
  x: number
  y: number
  /** The edge's direction: the pill lies along its own line. */
  angle: number
  text: string
}

const edgeLabels = ref<EdgeLabelPosition[]>([])

/** Whether two placements read the same picture on screen. */
function samePlacement(one: EdgeLabelPosition[], other: EdgeLabelPosition[]): boolean {
  if (one.length !== other.length) return false
  return one.every((item, idx) => {
    const was = other[idx]
    return (
      was.id === item.id &&
      Math.abs(was.x - item.x) < 0.5 &&
      Math.abs(was.y - item.y) < 0.5 &&
      Math.abs(was.angle - item.angle) < 0.5
    )
  })
}

/**
 * Place a pill on every pinned edge the picture still lights. The force layout
 * moves the picture for seconds after the graph appears, the view carries it
 * under every pan and zoom, and the canvas only re-renders: each rendered frame
 * places the pills again from where the edges now run, and a picture that has
 * not moved leaves the pills where they already are.
 */
function syncEdgeLabels() {
  const chart = chartInstance()
  if (!chart) return
  const data = graphSeries(chart)?.getData()
  if (!data) return
  const layout = new Map<string, number[]>()
  for (let idx = 0; idx < data.count(); idx++) {
    const point = data.getItemLayout(idx)
    if (point) layout.set(data.getName(idx), point)
  }
  const placed: EdgeLabelPosition[] = []
  for (const link of pinnedEdgeLabels(props.links)) {
    // A dimmed edge takes its label with it.
    if (dimming.value && !highlight.value.links.has(link)) continue
    const constraint = link.constraint
    if (!constraint) continue
    const from = layout.get(link.source)
    const to = layout.get(link.target)
    if (!from || !to) continue
    const start = chart.convertToPixel({ seriesIndex: 0 }, from)
    const end = chart.convertToPixel({ seriesIndex: 0 }, to)
    let angle = (Math.atan2(end[1] - start[1], end[0] - start[0]) * 180) / Math.PI
    // A pill reads left to right: an edge heading left hands its text over.
    if (angle > 90 || angle < -90) angle += 180
    placed.push({
      id: `${link.source}->${link.target}->${constraint}`,
      x: (start[0] + end[0]) / 2,
      y: (start[1] + end[1]) / 2,
      angle,
      text: constraint,
    })
  }
  placed.sort((one, other) => one.id.localeCompare(other.id))
  if (samePlacement(placed, edgeLabels.value)) return
  edgeLabels.value = placed
}

/** Where the nodes ended up, in the canvas pixels the force layout worked in. */
function measureContent(chart: ECharts): ContentBox | null {
  const data = graphSeries(chart)?.getData()
  if (!data) return null
  let minX = Infinity
  let maxX = -Infinity
  let minY = Infinity
  let maxY = -Infinity
  for (let idx = 0; idx < data.count(); idx++) {
    const point = data.getItemLayout(idx)
    if (!point) continue
    minX = Math.min(minX, point[0])
    maxX = Math.max(maxX, point[0])
    minY = Math.min(minY, point[1])
    maxY = Math.max(maxY, point[1])
  }
  if (!Number.isFinite(minX) || !Number.isFinite(maxX) || !Number.isFinite(minY) || !Number.isFinite(maxY)) {
    return null
  }
  return { minX, maxX, minY, maxY }
}

/**
 * Scale and centre the view on the settled layout. Roaming moves the view
 * without a setOption: the force layout runs again on every option change, and
 * a view fitted over a moving layout refits itself forever otherwise.
 */
function applyFit(chart: ECharts, measured: ContentBox) {
  const width = chart.getWidth()
  const height = chart.getHeight()
  const view = graphSeries(chart)?.coordinateSystem
  if (!width || !height || !view) return
  // A label sits above the node it names, outside it: the margin keeps the
  // outermost labels on the canvas and not under its edge.
  const box: ContentBox = {
    minX: measured.minX - LABEL_MARGIN,
    maxX: measured.maxX + LABEL_MARGIN,
    minY: measured.minY - LABEL_MARGIN,
    maxY: measured.maxY + LABEL_MARGIN,
  }
  const spanX = Math.max(box.maxX - box.minX, 1)
  const spanY = Math.max(box.maxY - box.minY, 1)
  const zoom = Math.min(FIT_ZOOM_MAX, (FIT_FILL * Math.min(width / spanX, height / spanY)))
  // A roam is a roam, action or pointer: without this flag the fit would read
  // as the reader's own hand and refuse to touch the view again.
  fittingView = true
  try {
    chart.dispatchAction({
      type: 'graphRoam',
      zoom: zoom / view.getZoom(),
      originX: width / 2,
      originY: height / 2,
    })
    // The zoom grows the picture around the middle: two passes of nudging the
    // picture home land its centre on the centre of the canvas.
    for (let pass = 0; pass < 2; pass++) {
      const lower = chart.convertToPixel({ seriesIndex: 0 }, [box.minX, box.minY])
      const upper = chart.convertToPixel({ seriesIndex: 0 }, [box.maxX, box.maxY])
      const dx = width / 2 - (lower[0] + upper[0]) / 2
      const dy = height / 2 - (lower[1] + upper[1]) / 2
      if (Math.abs(dx) < 1 && Math.abs(dy) < 1) break
      chart.dispatchAction({ type: 'graphRoam', dx, dy })
    }
  } finally {
    fittingView = false
  }
}

/** Whether the layout has slowed to the point where fitting it is worthwhile. */
function settlingEnough(previous: ContentBox | null, box: ContentBox): boolean {
  if (!previous) return false
  // The force steps run a fixed, long count and their tail is slow creep: once
  // the picture barely moves between samples, fitting it close is good enough -
  // the loop below keeps correcting while the last of the drift unwinds.
  const spanX = Math.max(box.maxX - box.minX, 1)
  const spanY = Math.max(box.maxY - box.minY, 1)
  const moveX = Math.max(Math.abs(box.minX - previous.minX), Math.abs(box.maxX - previous.maxX))
  const moveY = Math.max(Math.abs(box.minY - previous.minY), Math.abs(box.maxY - previous.maxY))
  return moveX / spanX < 0.06 && moveY / spanY < 0.06
}

/** Whether the picture moved far enough from the fitted one to fit it again. */
function driftedFrom(fitted: ContentBox, box: ContentBox, width: number, height: number): boolean {
  const widthThan = Math.max(box.maxX - box.minX, 1)
  const heightThan = Math.max(box.maxY - box.minY, 1)
  const widthWas = Math.max(fitted.maxX - fitted.minX, 1)
  const heightWas = Math.max(fitted.maxY - fitted.minY, 1)
  const centreX = (box.minX + box.maxX) / 2
  const centreY = (box.minY + box.maxY) / 2
  const centreWasX = (fitted.minX + fitted.maxX) / 2
  const centreWasY = (fitted.minY + fitted.maxY) / 2
  return (
    Math.abs(widthThan - widthWas) > 0.03 * widthWas ||
    Math.abs(heightThan - heightWas) > 0.03 * heightWas ||
    Math.abs(centreX - centreWasX) > 0.02 * width ||
    Math.abs(centreY - centreWasY) > 0.02 * height
  )
}

/**
 * The layout settles out of random start positions and every option change runs
 * it again: the view fits once it holds still, then keeps it fitted while the
 * picture wanders, and leaves the view alone the moment the reader moves it.
 * One loop runs at a time: a newer trigger supersedes the loop still watching.
 */
function refitView(newPictures: boolean) {
  const chart = chartInstance()
  if (!chart) return
  // A new closure is a new picture: what the reader did to the last one does
  // not carry over. An option recompute of the same closure keeps their hand.
  if (newPictures) {
    roamedByHand = false
  }
  const generation = ++fitGeneration
  let previous: ContentBox | null = null
  let fitted: ContentBox | null = null
  let steadyRuns = 0
  let attempts = 0
  const step = () => {
    if (roamedByHand || generation !== fitGeneration) return
    if (pressedNodeId !== null) {
      // A node in hand is the picture mid move: fitting under the reader's
      // pointer would scale the view out from under it.
      previous = null
      window.setTimeout(step, 250)
      return
    }
    const box = measureContent(chart)
    attempts += 1
    if (!box) {
      previous = null
      if (attempts > 48) return
      window.setTimeout(step, 250)
      return
    }
    const width = chart.getWidth()
    const height = chart.getHeight()
    if (fitted && driftedFrom(fitted, box, width, height)) {
      applyFit(chart, box)
      fitted = box
      steadyRuns = 0
    } else if (!fitted && settlingEnough(previous, box)) {
      applyFit(chart, box)
      fitted = box
      steadyRuns = 0
    } else if (fitted) {
      steadyRuns += 1
      // The layout's tail creeps for seconds after it looks done: stay on watch
      // through it, or the outermost nodes wander off the canvas afterwards.
      if (steadyRuns >= 12) return
    } else if (attempts > 48) {
      applyFit(chart, box)
      return
    }
    previous = box
    window.setTimeout(step, 250)
  }
  window.setTimeout(step, 250)
}

// A taller window asks for a taller picture, unless the reader moved it.
const onWindowResize = () => refitView(false)

onMounted(() => {
  const chart = chartInstance()
  if (!chart) return
  chart.on('graphRoam', (...args: unknown[]) => {
    // A roam reports the move it made: a zoom scales the picture, a pan slides it.
    const action = args[0] as { zoom?: number } | undefined
    if (!fittingView) {
      roamedByHand = true
    }
    // A pan carries a shown tooltip along with the picture; a zoom rescales the
    // picture under it and leaves the tooltip pointing where the node used to be.
    if (action?.zoom !== undefined) {
      hideTooltip()
    }
  })
  // Every frame the canvas draws is a frame the picture can have moved.
  chart.on('rendered', syncEdgeLabels)
  syncEdgeLabels()
  refitView(false)
  window.addEventListener('resize', onWindowResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onWindowResize)
})

// A node the reader dropped by hand stays where it was left: the force layout
// springs every node back to its own equilibrium on the next update, so a
// placed node is pinned and held from then on.
const pinnedNodeIds = ref<string[]>([])

const CATEGORY_COLORS = ['#409eff', '#67c23a', '#909399']
// Projects carry the page, workspace packages the middle, dependencies the mass.
const CATEGORY_SYMBOL_SIZES = [52, 38, 26]
// A dimmed node keeps a readable but retreating label: graph labels carry no
// opacity of their own, grey is how one reads as switched off.
const DIM_LABEL_COLOR = '#c0c4cc'
const DIM_OPACITY = 0.12

const categoryNames = computed(() => props.categoryNames)

const data = computed<ReleaseDependencyGraphData>(() => ({
  nodes: props.nodes,
  links: props.links,
}))

const highlight = computed(() =>
  relatedHighlight(data.value, props.selectedId, props.transitive),
)

/** Whether anything is dimmed at all - an empty selection lights the whole graph. */
const dimming = computed(() => props.selectedId !== null)

function isLitNode(node: ReleaseDependencyGraphNode): boolean {
  return !dimming.value || highlight.value.nodes.has(node.id)
}

function linkStyle(link: ReleaseDependencyGraphLink) {
  const lit = !dimming.value || highlight.value.links.has(link)
  if (link.circular) {
    // A cycle stays visible even dimmed: it is the one edge a reader hunts for.
    return { color: '#f56c6c', type: 'dashed', opacity: lit ? 0.85 : 0.25, curveness: 0.12 }
  }
  return { color: lit ? '#a6c8ff' : '#dcdfe6', opacity: lit ? 0.65 : DIM_OPACITY, curveness: 0.08 }
}

const chartOption = computed(() => ({
  tooltip: {
    trigger: 'item' as const,
    formatter: (params: { dataType?: string; data?: unknown }) => {
      // An edge is hovered as often as a node: what the one package declares for
      // the other is the question the line answers.
      if (params.dataType === 'edge') {
        const link = params.data as ReleaseDependencyGraphLink | undefined
        if (!link) return ''
        const constraint = link.constraint ? `  ${link.constraint}` : ''
        return `${link.source} &rarr; ${link.target}${constraint}`
      }
      const node = params.data as ReleaseDependencyGraphNode | undefined
      if (!node) return ''
      const kind = categoryNames.value[node.category] ?? 'Package'
      const version = node.version ? `@${node.version}` : ''
      return `${node.name ?? node.id}${version}<br/>${kind}`
    },
  },
  legend: [
    {
      data: categoryNames.value.map((name) => ({ name, icon: 'circle' })),
      bottom: 0,
      textStyle: { color: '#606266' },
    },
  ],
  series: [
    {
      type: 'graph' as const,
      layout: 'force' as const,
      roam: true,
      draggable: true,
      scaleLimit: { min: 0.3, max: 3 },
      edgeSymbol: ['none', 'arrow'],
      edgeSymbolSize: [0, 6],
      cursor: 'pointer',
      categories: categoryNames.value.map((name) => ({ name })),
      // Spread to the size of the canvas it is given: a closure drawn small in
      // the middle reads as a thumbnail of itself, whatever fits the view.
      force: {
        repulsion: 800,
        edgeLength: [220, 380],
        gravity: 0.02,
        friction: 0.6,
      },
      // Hovering a node lights its neighbourhood before any click is spent.
      emphasis: {
        focus: 'adjacency' as const,
        scale: 1.15,
        lineStyle: { width: 3 },
      },
      label: { show: true, color: '#303133', fontSize: 11 },
      labelLayout: { hideOverlap: true },
      data: props.nodes.map((node) => ({
        ...node,
        name: node.name ?? node.id,
        fixed: pinnedNodeIds.value.includes(node.id),
        symbolSize: CATEGORY_SYMBOL_SIZES[node.category] ?? 26,
        itemStyle: {
          color: CATEGORY_COLORS[node.category] ?? '#909399',
          borderColor: '#ffffff',
          borderWidth: 1.5,
          opacity: isLitNode(node) ? 1 : DIM_OPACITY,
        },
        label: { color: isLitNode(node) ? '#303133' : DIM_LABEL_COLOR },
      })),
      links: props.links.map((link) => ({
        ...link,
        lineStyle: linkStyle(link),
      })),
    },
  ],
}))

function onNodeClick(params: { dataType?: string; data?: unknown }) {
  if (params.dataType === 'node') {
    const node = params.data as ReleaseDependencyGraphNode | undefined
    if (node?.id) {
      emit('node-click', node.id)
    }
  }
}

// A tooltip is anchored to the spot its item held when the pointer arrived: a
// view rescaled or a picture moved since leaves it describing the wrong place,
// so it goes and the next hover anchors it where the item now stands.
function hideTooltip() {
  chartInstance()?.dispatchAction({ type: 'hideTip' })
}

function onNodePress(params: { dataType?: string; data?: unknown }) {
  if (params.dataType === 'node') {
    const node = params.data as ReleaseDependencyGraphNode | undefined
    pressedNodeId = node?.id ?? null
    return
  }
  pressedNodeId = null
}

function onNodeDragEnd() {
  const id = pressedNodeId
  pressedNodeId = null
  if (id && !pinnedNodeIds.value.includes(id)) {
    pinnedNodeIds.value = [...pinnedNodeIds.value, id]
  }
}

// A new closure is a new picture: its view fits from scratch, hand and all.
watch([() => props.nodes, () => props.links], () => refitView(true))

// Every option change restarts the force layout, and the picture wanders again:
// the loop follows it, unless the reader owns the view by now.
watch(chartOption, () => {
  // The restart moves every node out from under a shown tooltip: it goes with
  // them, and the next hover puts it back where its node settled.
  hideTooltip()
  refitView(false)
  syncEdgeLabels()
})
</script>

<style scoped>
.chart {
  position: relative;
  width: 100%;
  height: v-bind(height);
}
.canvas {
  width: 100%;
  height: 100%;
}
/* The pins ride over the canvas and let the pointer through to it. */
.edge-labels {
  position: absolute;
  inset: 0;
  overflow: hidden;
  pointer-events: none;
}
.edge-label {
  position: absolute;
  padding: 1px 6px;
  border-radius: 3px;
  background: var(--graph-pin-bg, rgba(255, 255, 255, 0.85));
  color: var(--graph-pin-color, #606266);
  font-size: 10px;
  line-height: 1.3;
  white-space: nowrap;
  transform: translate(-50%, -50%) rotate(var(--angle, 0deg));
}
:global([data-theme='dark']) .edge-label {
  --graph-pin-bg: rgba(52, 60, 93, 0.92);
  --graph-pin-color: #c7cfe4;
}
</style>
