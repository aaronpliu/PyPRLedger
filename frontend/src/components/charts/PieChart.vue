<template>
  <div v-if="isMounted" class="chart-container">
    <v-chart class="chart" :option="chartOption" autoresize />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
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
    trigger: 'item',
    formatter: '{b}: {c} ({d}%)',
  },
  legend: {
    orient: 'vertical',
    left: 'left',
    top: 'middle',
    textStyle: {
      color: 'var(--el-text-color-secondary)',
    },
  },
  series: [
    {
      name: props.title,
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['60%', '50%'],
      avoidLabelOverlap: true,
      itemStyle: {
        borderRadius: 10,
        borderColor: 'var(--el-bg-color)',
        borderWidth: 2,
      },
      label: {
        show: true,
        formatter: '{b}: {d}%',
        color: 'var(--el-text-color-primary)',
        fontSize: 12,
      },
      emphasis: {
        label: {
          show: true,
          fontSize: 14,
          fontWeight: 'bold',
        },
      },
      labelLine: {
        show: true,
        lineStyle: {
          color: 'var(--el-border-color)',
        },
      },
      data: props.data,
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