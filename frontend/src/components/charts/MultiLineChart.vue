<template>
  <div v-if="isMounted" class="chart-container">
    <v-chart ref="chartRef" class="chart" :option="chartOption" autoresize />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([
  LineChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  CanvasRenderer,
])

interface SeriesDataPoint {
  date: string
  value: number
}

interface SeriesItem {
  name: string
  data: SeriesDataPoint[]
  color: string
}

interface Props {
  title?: string
  series: SeriesItem[]
  height?: string
  axisLabelColor?: string
  axisLineColor?: string
  splitLineColor?: string
}

const props = withDefaults(defineProps<Props>(), {
  title: '',
  height: '350px',
  axisLabelColor: '#64748b',
  axisLineColor: '#e2e8f0',
  splitLineColor: '#f1f5f9',
})

// Chart instance ref for manual resize (used by parent in fullscreen)
const chartRef = ref()

const isMounted = ref(false)
const isDarkTheme = ref(false)

defineExpose({
  resize: () => {
    if (chartRef.value) {
      chartRef.value.resize()
    }
  },
})

onMounted(() => {
  isMounted.value = true
  checkTheme()
  const observer = new MutationObserver(checkTheme)
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['data-theme'],
  })
})

const checkTheme = () => {
  isDarkTheme.value = document.documentElement.getAttribute('data-theme') === 'dark'
}

// Collect all unique dates across all series
const allDates = computed(() => {
  const dateSet = new Set<string>()
  for (const s of props.series) {
    for (const d of s.data) {
      dateSet.add(d.date)
    }
  }
  return Array.from(dateSet).sort()
})

const chartOption = computed(() => {
  const dark = isDarkTheme.value

  const echartSeries = props.series.map((s) => ({
    name: s.name,
    type: 'line' as const,
    smooth: true,
    data: allDates.value.map(
      (date) => s.data.find((d) => d.date === date)?.value ?? 0
    ),
    itemStyle: { color: s.color },
    lineStyle: { width: 2 },
    // Area fill with gradient
    areaStyle: {
      color: {
        type: 'linear' as const,
        x: 0,
        y: 0,
        x2: 0,
        y2: 1,
        colorStops: [
          { offset: 0, color: s.color + '30' },
          { offset: 1, color: s.color + '05' },
        ],
      },
    },
    symbol: 'circle',
    symbolSize: 6,
  }))

  return {
    title: {
      text: props.title,
      left: 'center',
      textStyle: {
        color: props.axisLabelColor,
      },
    },
    tooltip: {
      trigger: 'axis',
    },
    legend: {
      bottom: 0,
      textStyle: {
        color: dark ? '#cbd5e1' : props.axisLabelColor,
      },
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '18%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: allDates.value,
      axisLabel: {
        color: dark ? '#cbd5e1' : props.axisLabelColor,
      },
      axisLine: {
        lineStyle: {
          color: dark ? '#475569' : props.axisLineColor,
        },
      },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      axisLabel: {
        color: dark ? '#cbd5e1' : props.axisLabelColor,
      },
      axisLine: {
        lineStyle: {
          color: dark ? '#475569' : props.axisLineColor,
        },
      },
      splitLine: {
        lineStyle: {
          color: dark ? '#334155' : props.splitLineColor,
        },
      },
    },
    series: echartSeries,
  }
})
</script>

<style scoped>
.chart-container {
  width: 100%;
  height: v-bind(height);
}

.chart {
  width: 100%;
  height: 100%;
}

[data-theme='dark'] .chart :deep(.echarts-tooltip) {
  background-color: #1f1f1f !important;
  border-color: #333 !important;
}
</style>
