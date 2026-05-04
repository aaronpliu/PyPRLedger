<template>
  <div v-if="isMounted" class="chart-container">
    <v-chart class="chart" :option="chartOption" autoresize />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { BarChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([
  BarChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  CanvasRenderer,
])

interface Props {
  title?: string
  data: Array<{ name: string; value: number }>
  color?: string
  height?: string
}

const props = withDefaults(defineProps<Props>(), {
  title: 'Distribution',
  color: '#67c23a',
  height: '350px',
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
        color: dark ? '#e5eaf3' : '#303133',
        fontSize: 14,
        fontWeight: 600,
      },
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow',
      },
      backgroundColor: dark ? 'rgba(30, 30, 30, 0.95)' : 'rgba(50, 50, 50, 0.9)',
      borderColor: dark ? '#444' : '#333',
      borderWidth: 1,
      textStyle: {
        color: '#fff',
      },
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '15%',
      top: '15%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: props.data.map(d => d.name),
      axisLabel: {
        rotate: 45,
        color: dark ? '#a3a6ad' : '#606266',
        interval: 0,
        fontSize: 11,
      },
      axisLine: {
        lineStyle: {
          color: dark ? '#4c4d4f' : '#dcdfe6',
        },
      },
      axisTick: {
        lineStyle: {
          color: dark ? '#4c4d4f' : '#dcdfe6',
        },
      },
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        color: dark ? '#a3a6ad' : '#606266',
        fontSize: 11,
      },
      axisLine: {
        show: false,
      },
      axisTick: {
        show: false,
      },
      splitLine: {
        lineStyle: {
          color: dark ? '#363637' : '#ebeef5',
          type: 'dashed',
        },
      },
    },
    series: [
      {
        name: 'Value',
        type: 'bar',
        data: props.data.map(d => d.value),
        itemStyle: {
          color: props.color,
          borderRadius: [4, 4, 0, 0],
        },
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowColor: 'rgba(0, 0, 0, 0.3)',
          },
        },
        label: {
          show: true,
          position: 'top',
          color: dark ? '#e5eaf3' : '#303133',
          fontSize: 11,
          fontWeight: 500,
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