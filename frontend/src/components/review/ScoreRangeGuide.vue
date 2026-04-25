<template>
  <div class="score-range-guide">
    <h4>
      <el-icon><InfoFilled /></el-icon>
      AI Review Evaluation Guidelines
    </h4>
    <div class="score-ranges">
      <div
        v-for="range in scoreRanges"
        :key="range.min"
        class="score-range-item"
        :class="range.className"
      >
        <div class="range-header">
          <span class="range-icon">{{ range.icon }}</span>
          <div class="range-badge">{{ range.min }}-{{ range.max }}</div>
        </div>
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
    min: 9,
    max: 10,
    label: 'Excellent',
    description: 'Outstanding insight with zero errors. The review is exceptionally accurate and insightful, identifying critical issues or optimizations without any hallucinations or noise.',
    className: 'excellent',
    icon: '🟢',
  },
  {
    min: 7,
    max: 8.9,
    label: 'Good',
    description: 'Helpful and accurate with minor nitpicks. The review is reliable and valuable, providing correct feedback that may only lack depth in complex areas or include trivial stylistic suggestions.',
    className: 'good',
    icon: '🔵',
  },
  {
    min: 5,
    max: 6.9,
    label: 'Acceptable',
    description: 'Basic validity mixed with generic advice. The review correctly identifies obvious surface-level issues but lacks depth, offering generic suggestions that provide limited value.',
    className: 'acceptable',
    icon: '🟠',
  },
  {
    min: 3,
    max: 4.9,
    label: 'Needs Improvement',
    description: 'Significant noise or missed critical context. The review contains noticeable inaccuracies, misunderstandings of logic, or irrelevant comments that require the developer to filter out significant noise.',
    className: 'needs-improvement',
    icon: '🔴',
  },
  {
    min: 0,
    max: 2.9,
    label: 'Poor',
    description: 'Fundamentally broken or misleading output. The review is completely incorrect, hallucinates issues, or provides dangerous advice that could harm the codebase.',
    className: 'poor',
    icon: '⛔',
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
  grid-template-columns: repeat(5, 1fr);
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

.range-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.range-icon {
  font-size: 1.2rem;
  line-height: 1;
}

.range-badge {
  font-size: 0.85rem;
  font-weight: 700;
  color: var(--el-text-color-primary);
}

.range-label {
  font-size: 0.9rem;
  font-weight: 600;
  margin-bottom: 6px;
}

.range-description {
  font-size: 0.75rem;
  color: var(--el-text-color-secondary);
  line-height: 1.5;
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
