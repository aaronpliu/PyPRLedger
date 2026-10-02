<template>
  <!-- Force layout: a dependency closure is a graph with cycles, not a dag, and
       the reader pans and pins nodes by hand until it reads the way they think -->
  <v-chart
    class="chart"
    ref="chartRef"
    :option="chartOption"
    autoresize
    @click="onNodeClick"
    @mousedown="onNodePress"
    @zr:dragend="onNodeDragEnd"
    @zr:mousewheel="hideTooltip"
  />
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { GraphChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { relatedHighlight } from '@/utils/releaseDependencyGraph'
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

// A node the reader dropped by hand stays where it was left: the force layout
// springs every node back to its own equilibrium on the next update, so a
// placed node is pinned and held from then on.
const pinnedNodeIds = ref<string[]>([])
// Which node the pointer is down on: zrender drags speak only of elements, the
// mouse event is what names the package under it.
let pressedNodeId: string | null = null

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
      edgeSymbol: ['none', 'arrow'],
      edgeSymbolSize: [0, 6],
      cursor: 'pointer',
      categories: categoryNames.value.map((name) => ({ name })),
      force: {
        repulsion: 140,
        edgeLength: [70, 140],
        gravity: 0.08,
        friction: 0.15,
      },
      // Hovering a node lights its neighbourhood before any click is spent.
      emphasis: {
        focus: 'adjacency' as const,
        scale: 1.15,
        lineStyle: { width: 3 },
      },
      label: { show: true, color: '#303133', fontSize: 11 },
      labelLayout: { hideOverlap: true },
      // An edge answer to "at which version" only when one was asked for: the
      // app pins its direct dependencies, the packages among themselves declare
      // ranges, and a range on the line reads as noise rather than information.
      edgeLabel: {
        show: true,
        position: 'middle' as const,
        color: '#606266',
        fontSize: 10,
        backgroundColor: 'rgba(255, 255, 255, 0.8)',
        padding: [2, 4],
        borderRadius: 2,
        formatter: (params: { dataType?: string; data?: ReleaseDependencyGraphLink }) => {
          const link = params.data
          if (!link?.pinned || !link.constraint) return ''
          // A dimmed edge takes its label with it.
          if (dimming.value && !highlight.value.links.has(link)) return ''
          return `@${link.constraint}`
        },
      },
      edgeLabelLayout: { hideOverlap: true },
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

// The wheel zooms the canvas under the pointer, and a tooltip anchored to the
// last hovered item is left holding stale coordinates: it goes as the graph moves.
function hideTooltip() {
  chartRef.value?.dispatchAction({ type: 'hideTip' })
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
</script>

<style scoped>
.chart {
  width: 100%;
  height: v-bind(height);
}
</style>
