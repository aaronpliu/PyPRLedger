<template>
  <div v-if="isMounted" class="chart-container">
    <v-chart class="chart" :option="chartOption" autoresize />
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

interface Props {
  title?: string
  data: Array<{ date: string; value: number }>
  color?: string
  height?: string
  axisLabelColor?: string
  axisLineColor?: string
  splitLineColor?: string
}

const props = withDefaults(defineProps<Props>(), {
  title: 'Trend',
  color: '#409eff',
  height: '350px',
  axisLabelColor: '#64748b',
  axisLineColor: '#e2e8f0',
  splitLineColor: '#f1f5f9',
})

const isMounted = ref(false)
const isDarkTheme = ref(false)

onMounted(() => {
  // Ensure DOM is ready before rendering chart
  isMounted.value = true
  checkTheme()

  // Watch for theme changes
  const observer = new MutationObserver(checkTheme)
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['data-theme'],
  })
})

const checkTheme = () => {
  isDarkTheme.value = document.documentElement.getAttribute('data-theme') === 'dark'
}

const chartOption = computed(() => {
  const dark = isDarkTheme.value

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
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      outerBounds: {
        top: '15%',
        right: '4%',
        bottom: '15%',
        left: '3%',
      },
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: props.data.map(d => d.date),
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
    series: [
      {
        name: 'Value',
        type: 'line',
        smooth: true,
        data: props.data.map(d => d.value),
        itemStyle: {
          color: props.color,
        },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: props.color + '40' },
              { offset: 1, color: props.color + '05' },
            ],
          },
        },
      },
    ],
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

/* Dark theme optimizations */
[data-theme='dark'] .chart :deep(.echarts-tooltip) {
  background-color: #1f1f1f !important;
  border-color: #333 !important;
}
</style>
