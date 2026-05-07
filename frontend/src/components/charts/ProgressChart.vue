<template>
  <div class="progress-chart">
    <h3 v-if="title" class="chart-title">{{ title }}</h3>
    <div class="progress-list">
      <div
        v-for="(item, index) in sortedData"
        :key="index"
        class="progress-item"
      >
        <div class="progress-label">
          <span class="label-text">{{ item.label }}</span>
          <span class="label-value">{{ item.completed }}/{{ item.total }}</span>
        </div>
        <el-progress
          :percentage="item.percentage"
          :stroke-width="12"
          :color="getProgressColor(item.percentage)"
          :show-text="false"
        />
        <div class="progress-percentage">{{ item.percentage.toFixed(1) }}%</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface ProgressItem {
  label: string
  total: number
  completed: number
  percentage: number
}

interface Props {
  title?: string
  data: ProgressItem[]
  height?: string
}

const props = withDefaults(defineProps<Props>(), {
  title: '',
  height: 'auto',
})

// Sort by percentage descending
const sortedData = computed(() => {
  return [...props.data].sort((a, b) => b.percentage - a.percentage)
})

const getProgressColor = (percentage: number): string => {
  if (percentage >= 80) return '#67c23a' // Green
  if (percentage >= 50) return '#409eff' // Blue
  if (percentage >= 30) return '#e6a23c' // Orange
  return '#f56c6c' // Red
}
</script>

<style scoped>
.progress-chart {
  width: 100%;
  height: v-bind(height);
  overflow-y: auto;
}

.chart-title {
  margin: 0 0 16px 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  text-align: center;
}

.progress-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.progress-item {
  padding: 12px;
  background: var(--el-fill-color-lighter);
  border-radius: 8px;
  transition: background-color 0.2s;
}

.progress-item:hover {
  background: var(--el-fill-color-light);
}

.progress-label {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.label-text {
  font-weight: 500;
  color: var(--el-text-color-primary);
  font-size: 14px;
}

.label-value {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.progress-percentage {
  margin-top: 4px;
  text-align: right;
  font-size: 12px;
  font-weight: 600;
  color: var(--el-text-color-regular);
}

/* Dark theme adjustments */
[data-theme='dark'] .progress-item {
  background: rgba(255, 255, 255, 0.05);
}

[data-theme='dark'] .progress-item:hover {
  background: rgba(255, 255, 255, 0.08);
}
</style>
