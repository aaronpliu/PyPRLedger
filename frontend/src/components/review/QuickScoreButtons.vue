<template>
  <div class="quick-score-buttons">
    <h4>
      <el-icon><Star /></el-icon>
      Quick Score
    </h4>
    <div class="score-buttons-grid">
      <el-button
        v-for="preset in scorePresets"
        :key="preset.value"
        size="small"
        @click="$emit('select', preset.value)"
        :class="['score-btn', `score-btn-${preset.type}`]"
      >
        <span class="score-value">{{ preset.value }}</span>
        <span class="score-label">{{ preset.label }}</span>
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Star } from '@element-plus/icons-vue'

defineEmits<{
  select: [value: number]
}>()

const scorePresets = [
  { value: 9.5, label: 'Excellent', type: 'excellent' },
  { value: 8.5, label: 'Good', type: 'good' },
  { value: 7.5, label: 'Average', type: 'average' },
  { value: 6.5, label: 'Below Avg', type: 'acceptable' },
  { value: 5.0, label: 'Poor', type: 'poor' },
]
</script>

<style scoped>
.quick-score-buttons {
  background: white;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
  border: 2px solid var(--el-border-color);
}

[data-theme='dark'] .quick-score-buttons {
  background: var(--el-bg-color);
}

.quick-score-buttons h4 {
  margin: 0 0 12px 0;
  font-size: 0.95rem;
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--el-text-color-primary);
  font-weight: 700;
}

.score-buttons-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
  gap: 8px;
}

.score-btn {
  height: auto !important;
  padding: 12px 8px !important;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  border-width: 2px !important;
  transition: all 0.3s ease !important;
}

.score-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.score-value {
  font-size: 1.5rem;
  font-weight: 700;
  line-height: 1;
}

.score-label {
  font-size: 0.7rem;
  opacity: 0.8;
  font-weight: 600;
}

/* Custom button styles matching ScoreRangeGuide colors */
.score-btn-excellent {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%) !important;
  border-color: #10b981 !important;
  color: white !important;
}

.score-btn-good {
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%) !important;
  border-color: #3b82f6 !important;
  color: white !important;
}

.score-btn-average {
  background: linear-gradient(135deg, #f3f4f6 0%, #e5e7eb 100%) !important;
  border-color: #d1d5db !important;
  color: #374151 !important;
}

.score-btn-acceptable {
  background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%) !important;
  border-color: #f59e0b !important;
  color: white !important;
}

.score-btn-poor {
  background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%) !important;
  border-color: #ef4444 !important;
  color: white !important;
}

[data-theme='dark'] .score-btn-average {
  background: linear-gradient(135deg, #374151 0%, #1f2937 100%) !important;
  border-color: #4b5563 !important;
  color: #e5e7eb !important;
}
</style>
