<template>
  <div class="sparkline-container" :style="{ height: height }">
    <svg ref="svgRef" :width="width" :height="height" class="sparkline-svg">
      <!-- Gradient definition -->
      <defs>
        <linearGradient id="sparkline-gradient" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" :stop-color="gradientColor" stop-opacity="0.3" />
          <stop offset="100%" :stop-color="gradientColor" stop-opacity="0" />
        </linearGradient>
      </defs>
      
      <!-- Area under the line -->
      <path
        v-if="areaPath"
        :d="areaPath"
        fill="url(#sparkline-gradient)"
        class="sparkline-area"
      />
      
      <!-- Line path -->
      <path
        v-if="linePath"
        :d="linePath"
        :stroke="color"
        :stroke-width="strokeWidth"
        fill="none"
        stroke-linecap="round"
        stroke-linejoin="round"
        class="sparkline-path"
      />
      
      <!-- Data points (optional) -->
      <circle
        v-for="(point, index) in dataPoints"
        :key="index"
        :cx="point.x"
        :cy="point.y"
        :r="dotRadius"
        :fill="color"
        class="sparkline-dot"
        :class="{ 'sparkline-dot--last': index === data.length - 1 }"
      />
    </svg>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

interface Props {
  data: number[]
  width?: number
  height?: string
  color?: string
  strokeWidth?: number
  showDots?: boolean
  dotRadius?: number
  showArea?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  data: () => [],
  width: 200,
  height: '60px',
  color: '#409eff',
  strokeWidth: 2,
  showDots: false,
  dotRadius: 3,
  showArea: true,
})

const svgRef = ref<SVGSVGElement>()

// Parse height to number for calculations
const heightNum = computed(() => {
  const match = props.height.match(/(\d+)/)
  return match ? parseInt(match[1]) : 60
})

// Calculate gradient color (slightly lighter version of main color)
const gradientColor = computed(() => props.color)

// Generate line path
const linePath = computed(() => {
  if (props.data.length < 2) return ''
  
  const padding = 4
  const chartWidth = props.width - padding * 2
  const chartHeight = heightNum.value - padding * 2
  
  const min = Math.min(...props.data)
  const max = Math.max(...props.data)
  const range = max - min || 1
  
  const points = props.data.map((value, index) => {
    const x = padding + (index / (props.data.length - 1)) * chartWidth
    const y = padding + chartHeight - ((value - min) / range) * chartHeight
    return { x, y }
  })
  
  return points.reduce((path, point, index) => {
    return index === 0 ? `M ${point.x} ${point.y}` : `${path} L ${point.x} ${point.y}`
  }, '')
})

// Generate area path (closed shape for gradient fill)
const areaPath = computed(() => {
  if (!props.showArea || props.data.length < 2) return ''
  
  const padding = 4
  const chartWidth = props.width - padding * 2
  const chartHeight = heightNum.value - padding * 2
  
  const min = Math.min(...props.data)
  const max = Math.max(...props.data)
  const range = max - min || 1
  
  const points = props.data.map((value, index) => {
    const x = padding + (index / (props.data.length - 1)) * chartWidth
    const y = padding + chartHeight - ((value - min) / range) * chartHeight
    return { x, y }
  })
  
  const linePathStr = points.reduce((path, point, index) => {
    return index === 0 ? `M ${point.x} ${point.y}` : `${path} L ${point.x} ${point.y}`
  }, '')
  
  // Close the path for area fill
  const lastPoint = points[points.length - 1]
  const firstPoint = points[0]
  return `${linePathStr} L ${lastPoint.x} ${heightNum.value - padding} L ${firstPoint.x} ${heightNum.value - padding} Z`
})

// Calculate data points for dots
const dataPoints = computed(() => {
  if (!props.showDots || props.data.length < 2) return []
  
  const padding = 4
  const chartWidth = props.width - padding * 2
  const chartHeight = heightNum.value - padding * 2
  
  const min = Math.min(...props.data)
  const max = Math.max(...props.data)
  const range = max - min || 1
  
  return props.data.map((value, index) => {
    const x = padding + (index / (props.data.length - 1)) * chartWidth
    const y = padding + chartHeight - ((value - min) / range) * chartHeight
    return { x, y }
  })
})
</script>

<style scoped>
.sparkline-container {
  display: flex;
  align-items: center;
  justify-content: center;
}

.sparkline-svg {
  overflow: visible;
}

.sparkline-path {
  transition: d 0.3s ease;
}

.sparkline-area {
  transition: d 0.3s ease;
}

.sparkline-dot {
  opacity: 0;
  transition: opacity 0.2s ease;
}

.sparkline-dot--last {
  opacity: 1;
}

.sparkline-container:hover .sparkline-dot {
  opacity: 1;
}
</style>
