<template>
  <v-chart class="chart" :option="chartOption" autoresize />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { RadarChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([
  RadarChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  CanvasRenderer,
])

interface Props {
  title?: string
  indicators: Array<{ name: string; max: number }>
  data: Array<{ name: string; value: number[] }>
  height?: string
}

const props = withDefaults(defineProps<Props>(), {
  title: 'Radar Analysis',
  height: '350px',
})

const chartOption = computed(() => ({
  title: {
    text: props.title,
    left: 'center',
  },
  tooltip: {
    trigger: 'item',
  },
  legend: {
    bottom: 'bottom',
  },
  radar: {
    indicator: props.indicators,
    shape: 'polygon',
    splitNumber: 5,
    axisName: {
      color: '#333',
    },
    splitLine: {
      lineStyle: {
        color: ['#ddd'],
      },
    },
    splitArea: {
      show: true,
      areaStyle: {
        color: ['rgba(64, 158, 255, 0.05)', 'rgba(64, 158, 255, 0.1)'],
      },
    },
  },
  series: [
    {
      name: props.title,
      type: 'radar',
      data: props.data.map(item => ({
        value: item.value,
        name: item.name,
        areaStyle: {
          opacity: 0.3,
        },
      })),
    },
  ],
}))
</script>

<style scoped>
.chart {
  width: 100%;
  height: v-bind(height);
}
</style>
