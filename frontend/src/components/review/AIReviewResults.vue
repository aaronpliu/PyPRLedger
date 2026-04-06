<template>
  <div class="ai-review-results">
    <!-- Disclaimer -->
    <el-alert
      type="warning"
      :closable="false"
      show-icon
      style="margin-bottom: 16px"
    >
      <template #title>
        ⚠️ AI-Generated Review - Please verify independently
      </template>
    </el-alert>

    <!-- Summary Stats -->
    <div class="stats-grid">
      <el-card class="stat-card files">
        <div class="stat-value">{{ suggestions.Reviewed_files || 0 }}</div>
        <div class="stat-label">Files Reviewed</div>
      </el-card>
      <el-card class="stat-card critical">
        <div class="stat-value">{{ suggestions.Critical_issues || 0 }}</div>
        <div class="stat-label">Critical Issues</div>
      </el-card>
      <el-card class="stat-card total">
        <div class="stat-value">{{ suggestions.Total_issues || 0 }}</div>
        <div class="stat-label">Total Issues</div>
      </el-card>
    </div>

    <!-- Issues List -->
    <div v-if="issues.length > 0" class="issues-section">
      <h4>🔍 Detailed Issues ({{ issues.length }})</h4>
      <el-card
        v-for="(issue, index) in issues"
        :key="index"
        class="issue-card"
        :class="`severity-${issue.severity}`"
      >
        <div class="issue-header">
          <span class="issue-number">#Issue {{ index + 1 }}</span>
          <el-tag size="small">📄 {{ issue.file_name }}</el-tag>
          <el-tag v-if="issue.line_number" size="small" type="info">
            Line {{ issue.line_number }}
          </el-tag>
        </div>
        
        <div class="issue-badges">
          <el-tag :type="getIssueTypeColor(issue.issue_type)" size="small">
            {{ issue.issue_type }}
          </el-tag>
          <el-tag :type="getSeverityColor(issue.severity)" size="small">
            {{ issue.severity.toUpperCase() }}
          </el-tag>
        </div>

        <div v-if="issue.description" class="issue-description">
          <strong>📝 Description:</strong>
          <p>{{ issue.description }}</p>
        </div>

        <div v-if="issue.suggestion" class="issue-suggestion">
          <strong>💡 Suggestion:</strong>
          <p>{{ issue.suggestion }}</p>
        </div>

        <div v-if="issue.code_snippet" class="issue-code">
          <strong>💻 Code Snippet:</strong>
          <pre><code>{{ issue.code_snippet }}</code></pre>
        </div>
      </el-card>
    </div>

    <el-empty v-else description="✅ No issues found! Great code!" />

    <!-- Overall Assessment -->
    <div v-if="suggestions.overall_assessment" class="overall-assessment">
      <h4>📊 Overall Assessment</h4>
      <p>{{ suggestions.overall_assessment }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { AIReviewSuggestions, AIReviewIssue } from '@/api/reviews'

const props = defineProps<{
  suggestions: AIReviewSuggestions
}>()

const issues = computed(() => props.suggestions.issues || [])

const getSeverityColor = (severity: string) => {
  const colors: Record<string, any> = {
    critical: 'danger',
    high: 'warning',
    medium: '',
    low: 'success',
  }
  return colors[severity] || ''
}

const getIssueTypeColor = (type: string) => {
  const colors: Record<string, any> = {
    bug: 'danger',
    security: 'danger',
    performance: 'warning',
    style: 'info',
    maintainability: '',
  }
  return colors[type.toLowerCase()] || ''
}
</script>

<style scoped>
.ai-review-results {
  padding: 16px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 20px;
}

.stat-card {
  text-align: center;
  padding: 16px;
  border-left: 4px solid;
}

.stat-card.files {
  border-left-color: #3b82f6;
}

.stat-card.critical {
  border-left-color: #ef4444;
}

.stat-card.total {
  border-left-color: #f59e0b;
}

.stat-value {
  font-size: 2rem;
  font-weight: 700;
  line-height: 1;
  margin-bottom: 8px;
}

.stat-card.files .stat-value {
  color: #3b82f6;
}

.stat-card.critical .stat-value {
  color: #ef4444;
}

.stat-card.total .stat-value {
  color: #f59e0b;
}

.stat-label {
  font-size: 0.85rem;
  color: var(--el-text-color-secondary);
  font-weight: 600;
}

.issues-section h4 {
  margin: 0 0 16px 0;
  font-size: 1rem;
  color: var(--el-text-color-primary);
}

.issue-card {
  margin-bottom: 12px;
  border-left: 4px solid;
  transition: all 0.3s ease;
}

.issue-card:hover {
  transform: translateX(4px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.issue-card.severity-critical {
  border-left-color: #ef4444;
}

.issue-card.severity-high {
  border-left-color: #f97316;
}

.issue-card.severity-medium {
  border-left-color: #f59e0b;
}

.issue-card.severity-low {
  border-left-color: #22c55e;
}

.issue-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.issue-number {
  font-weight: 700;
  color: var(--el-text-color-primary);
  font-size: 0.9rem;
}

.issue-badges {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.issue-description,
.issue-suggestion {
  margin-bottom: 12px;
  padding: 10px;
  background: #f8fafc;
  border-radius: 6px;
}

[data-theme='dark'] .issue-description,
[data-theme='dark'] .issue-suggestion {
  background: #1e293b;
}

.issue-description strong,
.issue-suggestion strong {
  display: block;
  margin-bottom: 4px;
  font-size: 0.85rem;
  color: var(--el-text-color-primary);
}

.issue-description p,
.issue-suggestion p {
  margin: 0;
  color: var(--el-text-color-secondary);
  line-height: 1.6;
  font-size: 0.9rem;
}

.issue-code {
  margin-top: 12px;
}

.issue-code strong {
  display: block;
  margin-bottom: 8px;
  font-size: 0.85rem;
  color: var(--el-text-color-primary);
}

.issue-code pre {
  background: #1e293b;
  color: #e2e8f0;
  padding: 12px;
  border-radius: 6px;
  overflow-x: auto;
  margin: 0;
}

.issue-code code {
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', monospace;
  font-size: 0.85rem;
  line-height: 1.5;
}

.overall-assessment {
  margin-top: 20px;
  padding: 16px;
  background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
  border-radius: 8px;
  border-left: 4px solid #0ea5e9;
}

[data-theme='dark'] .overall-assessment {
  background: linear-gradient(135deg, #0c4a6e 0%, #075985 100%);
}

.overall-assessment h4 {
  margin: 0 0 8px 0;
  font-size: 1rem;
  color: var(--el-text-color-primary);
}

.overall-assessment p {
  margin: 0;
  color: var(--el-text-color-secondary);
  line-height: 1.7;
}
</style>
