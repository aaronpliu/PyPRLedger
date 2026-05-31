<template>
  <div v-if="isMounted" class="chart-container">
    <v-chart ref="chartRef" class="chart" :option="chartOption" autoresize />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { PieChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([
  PieChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  CanvasRenderer,
])

interface Props {
  title?: string
  data: Array<{ name: string; value: number }>
  height?: string
}

const props = withDefaults(defineProps<Props>(), {
  title: 'Distribution',
  height: '350px',
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
      trigger: 'item',
      formatter: '{b}: {c} ({d}%)',
      backgroundColor: dark ? 'rgba(30, 30, 30, 0.95)' : 'rgba(50, 50, 50, 0.9)',
      borderColor: dark ? '#444' : '#333',
      borderWidth: 1,
      textStyle: {
        color: '#fff',
      },
    },
    legend: {
      orient: 'vertical',
      left: 'left',
      top: 'middle',
      textStyle: {
        color: dark ? '#a3a6ad' : '#606266',
        fontSize: 11,
      },
      itemWidth: 10,
      itemHeight: 10,
    },
    series: [
      {
        name: props.title,
        type: 'pie',
        radius: ['35%', '65%'],
        center: ['60%', '55%'],
        avoidLabelOverlap: true,
        itemStyle: {
          borderRadius: 10,
          borderColor: dark ? '#1a1a1a' : '#fff',
          borderWidth: 2,
        },
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.3)',
          },
          label: {
            show: true,
            fontSize: 13,
            fontWeight: 'bold',
          },
        },
        label: {
          show: true,
          formatter: '{b}: {d}%',
          color: dark ? '#e5eaf3' : '#303133',
          fontSize: 11,
          fontWeight: 500,
        },
        labelLine: {
          show: true,
          length: 15,
          length2: 10,
          lineStyle: {
            color: dark ? '#4c4d4f' : '#dcdfe6',
            width: 1,
          },
        },
        data: props.data,
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
</style>