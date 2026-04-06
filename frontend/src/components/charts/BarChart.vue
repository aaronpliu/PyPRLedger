<template>
  <v-chart class="chart" :option="chartOption" autoresize />
</template>

<script setup lang="ts">
import { computed } from 'vue'
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

const chartOption = computed(() => ({
  title: {
    text: props.title,
    left: 'center',
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
    bottom: '3%',
    containLabel: true,
  },
  xAxis: {
    type: 'category',
    data: props.data.map(d => d.name),
    axisLabel: {
      rotate: 45,
    },
  },
  yAxis: {
    type: 'value',
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
