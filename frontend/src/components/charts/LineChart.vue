<template>
  <v-chart class="chart" :option="chartOption" autoresize />
</template>

<script setup lang="ts">
import { computed } from 'vue'
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
}

const props = withDefaults(defineProps<Props>(), {
  title: 'Trend',
  color: '#409eff',
  height: '350px',
})

const chartOption = computed(() => ({
  title: {
    text: props.title,
    left: 'center',
  },
  tooltip: {
    trigger: 'axis',
  },
  grid: {
    left: '3%',
    right: '4%',
    bottom: '3%',
    containLabel: true,
  },
  xAxis: {
    type: 'category',
    boundaryGap: false,
    data: props.data.map(d => d.date),
  },
  yAxis: {
    type: 'value',
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
}))
</script>

<style scoped>
.chart {
  width: 100%;
  height: v-bind(height);
}
</style>
