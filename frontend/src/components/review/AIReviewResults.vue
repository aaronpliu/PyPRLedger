<template>
  <div class="ai-review-results">
    <!-- Disclaimer -->
    <el-alert
      type="warning"
      :closable="false"
      show-icon
      style="margin-bottom: 15px"
    >
      <template #title>
        ⚠️ AI-Generated Review - Please verify independently
      </template>
    </el-alert>

    <!-- Summary Stats -->
    <div class="ai-summary-stats">
      <div class="ai-stat-card">
        <div class="ai-stat-value ai-stat-files">{{ suggestions.Reviewed_files || 0 }}</div>
        <div class="ai-stat-label">Files Reviewed</div>
      </div>
      <div class="ai-stat-card">
        <div class="ai-stat-value ai-stat-critical">{{ suggestions.Critical_issues || 0 }}</div>
        <div class="ai-stat-label">Critical Issues</div>
      </div>
      <div class="ai-stat-card">
        <div class="ai-stat-value ai-stat-total">{{ suggestions.Total_issues || 0 }}</div>
        <div class="ai-stat-label">Total Issues</div>
      </div>
    </div>

    <!-- Issues List -->
    <div v-if="issues.length > 0" class="ai-issues-list">
      <div
        v-for="(issue, index) in issues"
        :key="index"
        class="ai-issue-item"
        :class="`severity-${issue.severity}`"
      >
        <div class="ai-issue-header">
          <span class="ai-issue-number">#Issue {{ index + 1 }}</span>
          <span class="ai-issue-file">📄 {{ issue.file_name }}</span>
          <span v-if="issue.line_number" class="ai-issue-line">
            Line {{ issue.line_number }}
          </span>
        </div>
        
        <div class="issue-badges">
          <el-tag :type="getIssueTypeColor(issue.issue_type)" size="small">
            {{ issue.issue_type }}
          </el-tag>
          <el-tag :type="getSeverityColor(issue.severity)" size="small">
            {{ issue.severity.toUpperCase() }}
          </el-tag>
        </div>

        <div v-if="issue.description" class="ai-issue-description">
          <strong>📝 Description:</strong>
          <p>{{ issue.description }}</p>
        </div>

        <div v-if="issue.suggestion" class="ai-issue-suggestion">
          <strong>💡 Suggestion:</strong>
          <p>{{ issue.suggestion }}</p>
        </div>

        <div v-if="issue.code_snippet" class="ai-issue-code">
          <strong>💻 Code Snippet:</strong>
          <pre><code>{{ issue.code_snippet }}</code></pre>
        </div>
      </div>
    </div>

    <el-empty v-else description="✅ No issues found! Great code!" />

    <!-- Overall Assessment -->
    <div v-if="suggestions.overall_assessment" class="ai-overall-assessment">
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
  padding: 15px;
}

.ai-summary-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-bottom: 15px;
}

.ai-stat-card {
  background: white;
  padding: 12px;
  border-radius: 6px;
  text-align: center;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  border: 2px solid var(--el-border-color);
}

[data-theme='dark'] .ai-stat-card {
  background: #1e293b;
  border-color: #334155;
}

.ai-stat-value {
  font-size: 1.5rem;
  font-weight: 800;
  margin-bottom: 4px;
}

.ai-stat-critical { color: #ef4444; }
.ai-stat-total { color: #f59e0b; }
.ai-stat-files { color: #3b82f6; }

[data-theme='dark'] .ai-stat-critical { color: #fca5a5; }
[data-theme='dark'] .ai-stat-total { color: #fbbf24; }
[data-theme='dark'] .ai-stat-files { color: #60a5fa; }

.ai-stat-label {
  font-size: 0.75rem;
  color: var(--el-text-color-secondary);
  font-weight: 600;
  text-transform: uppercase;
}

.ai-issues-list {
  margin-top: 15px;
}

.ai-issue-item {
  background: white;
  border: 2px solid var(--el-border-color);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 10px;
  transition: all 0.3s;
}

[data-theme='dark'] .ai-issue-item {
  background: #1e293b;
  border-color: #334155;
}

.ai-issue-item:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  transform: translateX(3px);
}

/* Severity-based border colors */
.ai-issue-item.severity-critical {
  border-left: 4px solid #ef4444;
}

.ai-issue-item.severity-high {
  border-left: 4px solid #f97316;
}

.ai-issue-item.severity-medium {
  border-left: 4px solid #eab308;
}

.ai-issue-item.severity-low {
  border-left: 4px solid #3b82f6;
}

.ai-issue-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  flex-wrap: wrap;
  gap: 8px;
}

.ai-issue-number {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 0.85rem;
  font-weight: 700;
  box-shadow: 0 2px 4px rgba(102, 126, 234, 0.3);
}

[data-theme='dark'] .ai-issue-number {
  background: linear-gradient(135deg, #8b5cf6 0%, #a78bfa 100%);
}

.ai-issue-file {
  font-weight: 700;
  color: var(--el-text-color-primary);
  font-size: 0.9rem;
}

.ai-issue-line {
  background: #f1f5f9;
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--el-text-color-secondary);
}

[data-theme='dark'] .ai-issue-line {
  background: #334155;
  color: #cbd5e1;
}

.issue-badges {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.ai-issue-description,
.ai-issue-suggestion {
  margin-bottom: 12px;
  padding: 10px;
  border-radius: 6px;
  font-size: 0.9rem;
  line-height: 1.6;
}

.ai-issue-description {
  background: #f8fafc;
  border-left: 3px solid #3b82f6;
  color: var(--text-secondary);
}

[data-theme='dark'] .ai-issue-description {
  background: #0f172a;
  border-left-color: #60a5fa;
  color: #cbd5e1;
}

.ai-issue-suggestion {
  background: #f0fdf4;
  border-left: 3px solid #22c55e;
  color: #166534;
}

[data-theme='dark'] .ai-issue-suggestion {
  background: #064e3b;
  border-left-color: #6ee7b7;
  color: #6ee7b7;
}

.ai-issue-description strong,
.ai-issue-suggestion strong {
  display: block;
  margin-bottom: 4px;
  font-size: 0.85rem;
  color: var(--el-text-color-primary);
}

.ai-issue-description p,
.ai-issue-suggestion p {
  margin: 0;
  color: inherit;
}

.ai-issue-code {
  margin-top: 12px;
}

.ai-issue-code strong {
  display: block;
  margin-bottom: 8px;
  font-size: 0.85rem;
  color: var(--el-text-color-primary);
}

.ai-issue-code pre {
  background: #1e293b;
  color: #e2e8f0;
  padding: 10px;
  border-radius: 6px;
  overflow-x: auto;
  margin: 0;
  font-size: 0.85rem;
  line-height: 1.5;
}

.ai-issue-code code {
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', monospace;
}

.ai-overall-assessment {
  background: #eff6ff;
  padding: 12px;
  border-radius: 6px;
  border-left: 4px solid #2563eb;
  margin-top: 15px;
  font-size: 0.9rem;
  line-height: 1.6;
  color: var(--el-text-color-primary);
}

[data-theme='dark'] .ai-overall-assessment {
  background: #1e3a8a;
  border-left-color: #3b82f6;
  color: #bfdbfe;
}

.ai-overall-assessment h4 {
  margin: 0 0 8px 0;
  font-size: 1rem;
  color: var(--el-text-color-primary);
}

.ai-overall-assessment p {
  margin: 0;
  color: inherit;
}
</style>
