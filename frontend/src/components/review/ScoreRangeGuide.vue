<template>
  <div class="score-range-guide">
    <h4>
      <el-icon><InfoFilled /></el-icon>
      Scoring Guidelines
    </h4>
    <div class="score-ranges">
      <div
        v-for="range in scoreRanges"
        :key="range.min"
        class="score-range-item"
        :class="range.className"
      >
        <div class="range-badge">{{ range.min }}-{{ range.max }}</div>
        <div class="range-label">{{ range.label }}</div>
        <div class="range-description">{{ range.description }}</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { InfoFilled } from '@element-plus/icons-vue'

const scoreRanges = [
  {
    min: 90,
    max: 100,
    label: 'Excellent',
    description: 'Outstanding code quality with minimal issues',
    className: 'excellent',
  },
  {
    min: 80,
    max: 89,
    label: 'Good',
    description: 'Good quality with minor improvements needed',
    className: 'good',
  },
  {
    min: 70,
    max: 79,
    label: 'Acceptable',
    description: 'Meets basic requirements but needs some work',
    className: 'acceptable',
  },
  {
    min: 60,
    max: 69,
    label: 'Needs Improvement',
    description: 'Significant issues that should be addressed',
    className: 'needs-improvement',
  },
  {
    min: 0,
    max: 59,
    label: 'Poor',
    description: 'Major problems requiring substantial rework',
    className: 'poor',
  },
]
</script>

<style scoped>
.score-range-guide {
  background: linear-gradient(135deg, #f5f7fa 0%, #e8ecf1 100%);
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 20px;
}

[data-theme='dark'] .score-range-guide {
  background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
}

.score-range-guide h4 {
  margin: 0 0 12px 0;
  font-size: 0.95rem;
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--el-text-color-primary);
  font-weight: 700;
}

.score-ranges {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
}

.score-range-item {
  background: white;
  border-radius: 6px;
  padding: 12px;
  border-left: 4px solid;
  transition: all 0.3s ease;
}

[data-theme='dark'] .score-range-item {
  background: rgba(255, 255, 255, 0.05);
}

.score-range-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.range-badge {
  font-size: 0.85rem;
  font-weight: 700;
  margin-bottom: 4px;
  color: var(--el-text-color-primary);
}

.range-label {
  font-size: 0.9rem;
  font-weight: 600;
  margin-bottom: 4px;
}

.range-description {
  font-size: 0.75rem;
  color: var(--el-text-color-secondary);
  line-height: 1.4;
}

/* Score range colors */
.excellent {
  border-left-color: #10b981;
}

.excellent .range-label {
  color: #10b981;
}

.good {
  border-left-color: #3b82f6;
}

.good .range-label {
  color: #3b82f6;
}

.acceptable {
  border-left-color: #f59e0b;
}

.acceptable .range-label {
  color: #f59e0b;
}

.needs-improvement {
  border-left-color: #f97316;
}

.needs-improvement .range-label {
  color: #f97316;
}

.poor {
  border-left-color: #ef4444;
}

.poor .range-label {
  color: #ef4444;
}
</style>
