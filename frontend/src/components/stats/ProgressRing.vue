<template>
  <div class="progress-ring-container">
    <svg class="progress-ring" :width="size" :height="size">
      <!-- Background circle -->
      <circle
        class="progress-ring__background"
        :stroke-width="strokeWidth"
        fill="transparent"
        :r="radius"
        :cx="size / 2"
        :cy="size / 2"
      />
      <!-- Progress circle -->
      <circle
        class="progress-ring__circle"
        :stroke-width="strokeWidth"
        fill="transparent"
        :r="radius"
        :cx="size / 2"
        :cy="size / 2"
        :style="{
          strokeDasharray: circumference,
          strokeDashoffset: strokeDashoffset,
          transition: 'stroke-dashoffset 0.6s ease-in-out'
        }"
      />
    </svg>
    <div class="progress-ring__content">
      <div class="progress-ring__value">{{ value }}{{ suffix }}</div>
      <div v-if="label" class="progress-ring__label">{{ label }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  percentage: number
  size?: number
  strokeWidth?: number
  color?: string
  backgroundColor?: string
  value?: string | number
  suffix?: string
  label?: string
}

const props = withDefaults(defineProps<Props>(), {
  percentage: 0,
  size: 120,
  strokeWidth: 8,
  color: '#67c23a',
  backgroundColor: '#e5e7eb',
  value: '',
  suffix: '%',
  label: '',
})

const radius = computed(() => (props.size - props.strokeWidth) / 2)
const circumference = computed(() => 2 * Math.PI * radius.value)
const strokeDashoffset = computed(() => {
  const progress = Math.min(100, Math.max(0, props.percentage))
  return circumference.value - (progress / 100) * circumference.value
})
</script>

<style scoped>
.progress-ring-container {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
}

.progress-ring {
  transform: rotate(-90deg);
  transform-origin: 50% 50%;
}

.progress-ring__background {
  stroke: v-bind(backgroundColor);
}

.progress-ring__circle {
  stroke: v-bind(color);
  stroke-linecap: round;
}

.progress-ring__content {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
}

.progress-ring__value {
  font-size: 24px;
  font-weight: 700;
  color: var(--el-text-color-primary);
  line-height: 1;
}

.progress-ring__label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
}

/* Dark theme adjustments */
[data-theme='dark'] .progress-ring__background {
  stroke: rgba(255, 255, 255, 0.1);
}
</style>
