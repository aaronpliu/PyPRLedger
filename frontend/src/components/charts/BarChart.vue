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

onMounted(() => {
  // Ensure DOM is ready before rendering chart
  isMounted.value = true
})

const chartOption = computed(() => ({
  title: {
    text: props.title,
    left: 'center',
    textStyle: {
      color: 'var(--el-text-color-primary)',
    },
  },
  tooltip: {
    trigger: 'axis',
    axisPointer: {
      type: 'shadow',
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
      color: 'var(--el-text-color-secondary)',
      interval: 0,
    },
    axisLine: {
      lineStyle: {
        color: 'var(--el-border-color)',
      },
    },
  },
  yAxis: {
    type: 'value',
    axisLabel: {
      color: 'var(--el-text-color-secondary)',
    },
    axisLine: {
      lineStyle: {
        color: 'var(--el-border-color)',
      },
    },
    splitLine: {
      lineStyle: {
        color: 'var(--el-border-color-lighter)',
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
      label: {
        show: true,
        position: 'top',
        color: 'var(--el-text-color-primary)',
        fontSize: 12,
      },
    },
  ],
}))
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