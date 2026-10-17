<template>
  <!-- Force layout: a dependency closure is a graph with cycles, not a dag, and
       the reader pans and pins nodes by hand until it reads the way they think -->
  <div ref="rootRef" class="chart" :class="{ maximized }">
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
    <!-- A closure too large for the force layout is drawn as rows, and saying so
         is what keeps the still picture from reading as a graph still settling. -->
    <span v-if="layered" class="chart-note">{{ toolbarLabels.layered }}</span>
    <!-- The canvas only reads as well as the frame it is given, so the frame is
         the reader's: zoom it, put it back in frame, or lend it the window. -->
    <div class="chart-toolbar">
      <el-tooltip :content="toolbarLabels.zoomOut" placement="bottom">
        <el-button
          size="small"
          circle
          :icon="ZoomOut"
          :aria-label="toolbarLabels.zoomOut"
          data-test="graph-zoom-out"
          @click="zoomBy(1 / ZOOM_STEP)"
        />
      </el-tooltip>
      <el-tooltip :content="toolbarLabels.zoomIn" placement="bottom">
        <el-button
          size="small"
          circle
          :icon="ZoomIn"
          :aria-label="toolbarLabels.zoomIn"
          data-test="graph-zoom-in"
          @click="zoomBy(ZOOM_STEP)"
        />
      </el-tooltip>
      <el-tooltip :content="toolbarLabels.fit" placement="bottom">
        <el-button
          size="small"
          circle
          :icon="Aim"
          :aria-label="toolbarLabels.fit"
          data-test="graph-fit"
          @click="fitToView"
        />
      </el-tooltip>
      <!-- Only a force layout has placements of the reader's to clear; a layered
           drawing already says where every package stands. -->
      <el-tooltip v-if="!layered" :content="toolbarLabels.resetLayout" placement="bottom">
        <el-button
          size="small"
          circle
          :icon="RefreshLeft"
          :aria-label="toolbarLabels.resetLayout"
          data-test="graph-reset"
          @click="resetLayout"
        />
      </el-tooltip>
      <el-tooltip
        :content="maximized ? toolbarLabels.restore : toolbarLabels.maximize"
        placement="bottom-end"
      >
        <el-button
          size="small"
          circle
          :icon="maximized ? Close : FullScreen"
          :aria-label="maximized ? toolbarLabels.restore : toolbarLabels.maximize"
          data-test="graph-maximize"
          @click="toggleMaximize"
        />
      </el-tooltip>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, unref, watch } from 'vue'
import { Aim, Close, FullScreen, RefreshLeft, ZoomIn, ZoomOut } from '@element-plus/icons-vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import type { ECharts } from 'echarts/core'
import { GraphChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { layeredPositions, pinnedEdgeLabels, relatedHighlight } from '@/utils/releaseDependencyGraph'
import { useTheme } from '@/composables/useTheme'
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
  /** The toolbar's wordings - localised by the page, like the category names. */
  toolbarLabels?: {
    zoomIn: string
    zoomOut: string
    fit: string
    maximize: string
    restore: string
    resetLayout: string
    layered: string
  }
  /**
   * What the reader's view is remembered under (the repository): the zoom this
   * chart was left at is the one it opens at. Empty remembers nothing.
   */
  viewKey?: string
  height?: string
}

const props = withDefaults(defineProps<Props>(), {
  selectedId: null,
  transitive: false,
  // Indexed by category as the file numbers them: 0 project, 1 dependency,
  // 2 the packages the application ships.
  categoryNames: () => ['Project', 'Dependency', 'Workspace package'],
  toolbarLabels: () => ({
    zoomIn: 'Zoom in',
    zoomOut: 'Zoom out',
    fit: 'Fit to view',
    maximize: 'Maximize',
    restore: 'Restore',
    resetLayout: 'Reset layout',
    layered: 'Layered layout',
  }),
  viewKey: '',
  height: '600px',
})

const emit = defineEmits<{
  (e: 'node-click', id: string): void
}>()

const chartRef = ref<InstanceType<typeof VChart> | null>(null)
/** The frame the canvas lives in: what a resize is measured on, and what grows. */
const rootRef = ref<HTMLElement | null>(null)
/** Whether the graph has taken the window instead of the card it was given. */
const maximized = ref(false)

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
// Past this many packages the force layout is a hairball that takes seconds to
// settle: the same relationships are drawn as rows, which reads better than a
// few hundred nodes piled on each other and costs nothing to compute.
const LAYERED_NODE_THRESHOLD = 150
// Double-clicking a package magnifies it to about this: close enough to read the
// edges meeting there, wide enough to keep its neighbours in sight.
const FOCUS_ZOOM = 1.8
// A node carries its name above it: the label clears the symbol by its height.
const LABEL_MARGIN = 50
let roamedByHand = false
let fittingView = false
// One fit loop at a time: the newest trigger wins, the older one stands down.
let fitGeneration = 0
// Which node the pointer is down on: zrender drags speak only of elements, the
// mouse event is what names the package under it.
let pressedNodeId: string | null = null
// The canvas follows its container; this is what tells the fit that it moved.
let resizeObserver: ResizeObserver | null = null
// The view a repository was left at, so the same chart opens the same way.
const VIEW_STORAGE_PREFIX = 'release-dependency-graph:view:'
let preferredZoom: number | null = null
let rememberedZoom: number | null = null

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
  // The reader's own zoom where they left one for this repository: the fit is what
  // a view starts at, not what it is held to.
  const fitted = Math.min(FIT_ZOOM_MAX, FIT_FILL * Math.min(width / spanX, height / spanY))
  const zoom = preferredZoom ?? fitted
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

// ---------------------------------------------------------------------------
// The frame is the reader's
// ---------------------------------------------------------------------------

/** How much one press of the zoom buttons scales the picture. */
const ZOOM_STEP = 1.25
/** autoresize hands the canvas its new size a beat after the class lands. */
const MAXIMIZE_SETTLE_MS = 100
/** What the view may be scaled to, by wheel, button or a remembered zoom. */
const SCALE_MIN = 0.3
const SCALE_MAX = 6

/** Scale the picture around the middle: a press has no pointer to zoom on. */
function zoomBy(factor: number) {
  const chart = chartInstance()
  if (!chart) return
  const width = chart.getWidth()
  const height = chart.getHeight()
  if (!width || !height) return
  chart.dispatchAction({
    type: 'graphRoam',
    zoom: factor,
    originX: width / 2,
    originY: height / 2,
  })
}

/** Put the picture back in frame, handing the view back to the layout. */
function fitToView() {
  roamedByHand = false
  // Fitting is asking for the default view: the zoom remembered for this
  // repository is what the fit replaces, so it goes with it.
  preferredZoom = null
  rememberZoom(null)
  refitView(true)
}

/**
 * Magnify the package under the pointer and bring it to the middle: a double-click
 * is the reader saying "this one", and the neighbourhood it lights is what they
 * came to read.
 */
function focusOn(x: number, y: number) {
  const chart = chartInstance()
  if (!chart) return
  const width = chart.getWidth()
  const height = chart.getHeight()
  if (!width || !height) return
  chart.dispatchAction({ type: 'graphRoam', zoom: FOCUS_ZOOM, originX: x, originY: y })
  const dx = width / 2 - x
  const dy = height / 2 - y
  if (Math.abs(dx) > 1 || Math.abs(dy) > 1) {
    chart.dispatchAction({ type: 'graphRoam', dx, dy })
  }
}

/** Clear the nodes the reader placed by hand and let the layout arrange them again. */
function resetLayout() {
  pinnedNodeIds.value = []
  roamedByHand = false
  refitView(true)
}

/** The zoom a repository was last left at, read when its graph opens. */
function readPreferredZoom() {
  preferredZoom = null
  if (!props.viewKey) return
  try {
    const raw = window.localStorage.getItem(VIEW_STORAGE_PREFIX + props.viewKey)
    const saved = raw ? (JSON.parse(raw) as { zoom?: unknown }) : null
    const zoom = Number(saved?.zoom)
    if (Number.isFinite(zoom) && zoom > 0) {
      // A remembered zoom is clamped like any other: the value outlives the canvas
      // it was written for.
      preferredZoom = Math.min(SCALE_MAX, Math.max(SCALE_MIN, zoom))
    }
  } catch {
    // A remembered view is a convenience: unreadable storage is simply no view.
  }
}

/** Remember this repository's zoom, or forget it - `null` is the fitted view. */
function rememberZoom(zoom: number | null) {
  if (!props.viewKey) return
  try {
    if (zoom === null) {
      window.localStorage.removeItem(VIEW_STORAGE_PREFIX + props.viewKey)
      rememberedZoom = null
      return
    }
    if (!Number.isFinite(zoom) || zoom <= 0) return
    // A wheel fires a roam per frame: write only when the picture actually moved.
    if (rememberedZoom !== null && Math.abs(rememberedZoom - zoom) < 0.01) return
    rememberedZoom = zoom
    window.localStorage.setItem(VIEW_STORAGE_PREFIX + props.viewKey, JSON.stringify({ zoom }))
  } catch {
    // Private mode, or a full quota: the chart works without a memory.
  }
}

/**
 * Give the graph the window, or the window back. A window-sized canvas is a new
 * frame to fit into, and asking for it is not the reader's own roam: the picture
 * is fitted to the size they asked for, once the canvas has taken that size.
 */
function setMaximized(next: boolean) {
  if (maximized.value === next) return
  maximized.value = next
  roamedByHand = false
  window.setTimeout(() => refitView(true), MAXIMIZE_SETTLE_MS)
}

const toggleMaximize = () => setMaximized(!maximized.value)

/**
 * The toolbar's own keys: Escape leaves the window-sized frame, and the rest do
 * what their buttons do. A shortcut is not a modifier combination, and it does not
 * belong to a field the reader is typing in.
 */
function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && maximized.value) {
    setMaximized(false)
    return
  }
  if (event.ctrlKey || event.metaKey || event.altKey) return
  const target = event.target as HTMLElement | null
  if (
    target &&
    (target.isContentEditable ||
      target.tagName === 'INPUT' ||
      target.tagName === 'TEXTAREA' ||
      target.tagName === 'SELECT')
  ) {
    return
  }

  if (event.key === '+' || event.key === '=') zoomBy(ZOOM_STEP)
  else if (event.key === '-' || event.key === '_') zoomBy(1 / ZOOM_STEP)
  else if (event.key === '0') fitToView()
  else if (event.key === 'f' || event.key === 'F') toggleMaximize()
  else return
  event.preventDefault()
}

onMounted(() => {
  const chart = chartInstance()
  if (!chart) return
  chart.on('graphRoam', (...args: unknown[]) => {
    // A roam reports the move it made: a zoom scales the picture, a pan slides it.
    const action = args[0] as { zoom?: number } | undefined
    if (!fittingView) {
      roamedByHand = true
      // The reader's own view is what this repository is remembered by; the fit's
      // zoom is not theirs to remember.
      const zoom = graphSeries(chart)?.coordinateSystem?.getZoom()
      if (typeof zoom === 'number') rememberZoom(zoom)
    }
    // A pan carries a shown tooltip along with the picture; a zoom rescales the
    // picture under it and leaves the tooltip pointing where the node used to be.
    if (action?.zoom !== undefined) {
      hideTooltip()
    }
  })
  // A double-click says "this one": magnify what was pointed at, and bring it to
  // the middle of the canvas.
  chart.on('dblclick', (...args: unknown[]) => {
    const params = args[0] as
      | { dataType?: string; event?: { offsetX?: number; offsetY?: number } }
      | undefined
    if (params?.dataType !== 'node') return
    const width = chart.getWidth()
    const height = chart.getHeight()
    focusOn(params.event?.offsetX ?? width / 2, params.event?.offsetY ?? height / 2)
  })
  // Every frame the canvas draws is a frame the picture can have moved.
  chart.on('rendered', syncEdgeLabels)
  syncEdgeLabels()
  readPreferredZoom()
  refitView(false)
  // A taller frame asks for a taller picture, unless the reader moved it. The
  // canvas follows its container (autoresize), and the container is what changes:
  // on a window resize, but also when the graph takes the window, which the
  // window's own resize event never sees.
  if (typeof ResizeObserver !== 'undefined' && rootRef.value) {
    resizeObserver = new ResizeObserver(() => refitView(false))
    resizeObserver.observe(rootRef.value)
  }
  window.addEventListener('keydown', onKeydown)
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  resizeObserver = null
  window.removeEventListener('keydown', onKeydown)
})

// A node the reader dropped by hand stays where it was left: the force layout
// springs every node back to its own equilibrium on the next update, so a
// placed node is pinned and held from then on.
const pinnedNodeIds = ref<string[]>([])

const { primaryColor } = useTheme()

// The application carries the accent. Green is what the application ships - the
// reading the detail panel gives the same node - and grey is what it pulls in, so
// a node's role stays readable whatever the accent is.
const CATEGORY_COLORS: Record<number, string> = { 1: '#909399', 2: '#67c23a' }

const categoryColor = (category: number): string =>
  category === 0 ? primaryColor.value : (CATEGORY_COLORS[category] ?? '#909399')
// Indexed by category as the file numbers them: the projects carry the page, the
// packages the application ships sit in the middle, and the dependencies it pulls
// in are the mass behind them.
const CATEGORY_SYMBOL_SIZES = [52, 26, 38]
// A dimmed node keeps a readable but retreating label: graph labels carry no
// opacity of their own, grey is how one reads as switched off.
const DIM_LABEL_COLOR = '#c0c4cc'
const DIM_OPACITY = 0.12

const categoryNames = computed(() => props.categoryNames)

const data = computed<ReleaseDependencyGraphData>(() => ({
  nodes: props.nodes,
  links: props.links,
}))

// Which drawing the graph gets: rows once the closure is too large for the force
// layout to settle into anything a reader can follow.
const layered = computed(() => props.nodes.length > LAYERED_NODE_THRESHOLD)
const positions = computed(() => (layered.value ? layeredPositions(data.value) : null))

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
      layout: (layered.value ? 'none' : 'force') as 'none' | 'force',
      roam: true,
      // A placed node belongs to the reader while the layout is a force one; a
      // layered drawing has already said where everything goes.
      draggable: !layered.value,
      // A maximized canvas asks for more than the card ever did: the ceiling has
      // to leave room to magnify a corner of the picture, not just to read it.
      scaleLimit: { min: SCALE_MIN, max: SCALE_MAX },
      edgeSymbol: ['none', 'arrow'],
      edgeSymbolSize: [0, 6],
      cursor: 'pointer',
      categories: categoryNames.value.map((name) => ({ name })),
      // Spread to the size of the canvas it is given: a closure drawn small in
      // the middle reads as a thumbnail of itself, whatever fits the view.
      force: layered.value
        ? undefined
        : {
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
        // `layout: 'none'` reads the position off the item: the layered drawing
        // says where each package stands, the force layout picks its own.
        ...(positions.value?.get(node.id) ?? {}),
        name: node.name ?? node.id,
        fixed: layered.value ? false : pinnedNodeIds.value.includes(node.id),
        symbolSize: CATEGORY_SYMBOL_SIZES[node.category] ?? 26,
        itemStyle: {
          color: categoryColor(node.category),
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

// Another repository is another view to remember: its own zoom where it has one,
// and the fitted view where it does not.
watch(
  () => props.viewKey,
  () => {
    rememberedZoom = null
    readPreferredZoom()
    roamedByHand = false
    refitView(true)
  },
)

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
/* The graph given the window: its own frame above the page, at the size the
   canvas would never get inside a card. */
.chart.maximized {
  position: fixed;
  inset: 0;
  /* Above the page, below Element Plus poppers (2000+): the toolbar's tooltips
     are poppers too, and would open behind a frame that outranked them. */
  z-index: 1990;
  height: auto;
  background: var(--el-bg-color);
}
/* The buttons sit on the picture: the surface under them keeps them legible
   whatever the nodes behind them happen to be. */
.chart-toolbar {
  position: absolute;
  top: 8px;
  right: 8px;
  z-index: 2;
  display: flex;
  gap: 6px;
}
.chart-toolbar :deep(.el-button) {
  background: var(--el-bg-color);
  box-shadow: 0 1px 4px rgb(0 0 0 / 12%);
}
.chart-toolbar :deep(.el-button + .el-button) {
  margin-left: 0;
}
/* Why the picture holds still: a closure this large is drawn as rows. */
.chart-note {
  position: absolute;
  top: 10px;
  left: 12px;
  z-index: 2;
  padding: 2px 8px;
  border-radius: 10px;
  background: var(--el-fill-color-light);
  color: var(--el-text-color-secondary);
  font-size: 11px;
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
