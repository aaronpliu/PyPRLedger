<template>
  <div class="score-range-guide">
    <h4>
      <el-icon><InfoFilled /></el-icon>
      AI Review Evaluation Guidelines
    </h4>
    <p class="score-guide-intro">
      This score evaluates the <strong>AI code review output</strong> for this PR, not the PR's
      code quality. As a human reviewer, double-check the AI findings — whether it surfaced real
      issues worth fixing with accurate, actionable suggestions and avoided hallucination/noise —
      then pick the grade that best describes the review's value.
    </p>
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
import { SCORE_GRADES } from '@/constants/scoreGuide'

const rangeDescriptions: Record<string, string> = {
  excellent:
    'Outstanding insight with zero errors. The review surfaces genuine issues worth fixing — even critical bugs — with accurate, actionable fix suggestions. Human double-check confirms each finding; no hallucinations or noise.',
  good: 'Helpful and accurate with minor nitpicks. The review reliably finds real issues and practical, worth-applying suggestions; only a slight lack of depth or trivial stylistic noise holds it back.',
  acceptable:
    'Basic validity mixed with generic advice. The review catches obvious, surface-level issues but lacks depth, and much of its advice is generic with limited added value.',
  'needs-improvement':
    'Significant noise or missed critical context. The review contains inaccuracies, misunderstands logic, or adds irrelevant comments, forcing the reviewer to filter significant noise and re-verify important areas.',
  poor: 'Fundamentally broken or misleading output. The review hallucinates issues, misses what matters, or gives advice that could harm the codebase; its output should be discarded or the review redone.',
}

const rangeIcons: Record<string, string> = {
  excellent: '🟢',
  good: '🔵',
  acceptable: '🟠',
  'needs-improvement': '🔴',
  poor: '⛔',
}

const scoreRanges = SCORE_GRADES.map((grade) => ({
  min: grade.min,
  max: grade.max,
  label: grade.label,
  description: rangeDescriptions[grade.className] || '',
  className: grade.className,
  icon: rangeIcons[grade.className] || '•',
}))
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
  margin: 0 0 8px 0;
  font-size: 0.95rem;
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--el-text-color-primary);
  font-weight: 700;
}

.score-guide-intro {
  margin: 0 0 12px 0;
  font-size: 0.8rem;
  color: var(--el-text-color-secondary);
  line-height: 1.6;
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
