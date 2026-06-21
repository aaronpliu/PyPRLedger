<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Warning, Check, TrendCharts, QuestionFilled } from '@element-plus/icons-vue'
import { reviewsApi, type ReviewValidationSummary, type ReviewRawRecord } from '@/api/reviews'

const { t } = useI18n()

const loading = ref(false)
const retrying = ref<number | null>(null)
const deleting = ref<number | null>(null)
const validationData = ref<ReviewValidationSummary | null>(null)

// Filter parameters
const dateFrom = ref<string>('')
const dateTo = ref<string>('')
const projectKey = ref<string>('')

// Computed properties for metrics
const successRateColor = computed(() => {
  if (!validationData.value) return '#909399'
  const rate = validationData.value.success_rate
  if (rate >= 95) return '#67c23a' // Green
  if (rate >= 80) return '#e6a23c' // Yellow
  return '#f56c6c' // Red
})

const formatDate = (dateStr: string | null) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString()
}

const formatRelativeTime = (dateStr: string) => {
  const now = new Date()
  const date = new Date(dateStr)
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 1) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  return `${diffDays}d ago`
}

const getErrorMessage = (record: ReviewRawRecord) => {
  if (record.error_message) {
    return record.error_message
  }
  if (record.error_details?.error_type) {
    return `${record.error_details.error_type}: ${record.error_message || 'Unknown error'}`
  }
  return 'Unknown error'
}

const loadValidationData = async () => {
  loading.value = true
  try {
    const params: any = {}
    if (dateFrom.value) params.date_from = dateFrom.value
    if (dateTo.value) params.date_to = dateTo.value
    if (projectKey.value) params.project_key = projectKey.value

    validationData.value = await reviewsApi.getValidationSummary(params)
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || 'Failed to load validation data')
  } finally {
    loading.value = false
  }
}

const handleRetry = async (record: ReviewRawRecord) => {
  try {
    await ElMessageBox.confirm(
      `Retry failed review #${record.id}? This will attempt to reprocess the review using the stored raw data.`,
      'Confirm Retry',
      {
        confirmButtonText: 'Retry',
        cancelButtonText: 'Cancel',
        type: 'warning',
      }
    )

    retrying.value = record.id
    const result = await reviewsApi.retryFailedReview(record.id)
    
    ElMessage.success(result.message || 'Review retried successfully')
    
    // Reload data to show updated status
    await loadValidationData()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || 'Failed to retry review')
    }
  } finally {
    retrying.value = null
  }
}

const handleDelete = async (record: ReviewRawRecord) => {
  try {
    await ElMessageBox.confirm(
      `Delete failed review #${record.id}? This will remove the record from the validation table. This action cannot be undone.`,
      'Confirm Delete',
      {
        confirmButtonText: 'Delete',
        cancelButtonText: 'Cancel',
        type: 'error',
        confirmButtonClass: 'el-button--danger',
      }
    )

    deleting.value = record.id
    const result = await reviewsApi.deleteFailedReview(record.id)

    ElMessage.success(result.message || 'Record deleted successfully')

    // Reload data
    await loadValidationData()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || 'Failed to delete record')
    }
  } finally {
    deleting.value = null
  }
}

const resetFilters = () => {
  dateFrom.value = ''
  dateTo.value = ''
  projectKey.value = ''
  loadValidationData()
}

onMounted(() => {
  loadValidationData()
})
</script>

<template>
  <div class="review-validation">
    <el-card>
      <template #header>
        <div class="card-header">
          <div class="title-with-help">
            <h2>{{ t('menu.reviewValidation') }}</h2>
            <el-tooltip placement="bottom" effect="light">
              <template #content>
                <div class="validation-help-content">
                  <p>
                    This dashboard monitors the integrity of PR review processing by comparing
                    <strong>total attempted reviews</strong> against <strong>successfully processed reviews</strong>.
                  </p>
                  <p>
                    When a PR review is submitted, the system first stores the raw request data before attempting
                    to process it. If processing fails (e.g., missing project/repository/user information), the
                    failed attempt is recorded here for troubleshooting and retry.
                  </p>
                  <p>
                    <strong>Key Features:</strong> Track success rates, identify failed reviews with error details,
                    and retry failed submissions without requiring users to resubmit from Bitbucket.
                  </p>
                </div>
              </template>
              <el-icon class="help-icon"><QuestionFilled /></el-icon>
            </el-tooltip>
          </div>
          <el-button type="primary" :icon="Refresh" @click="loadValidationData" :loading="loading">
            Refresh
          </el-button>
        </div>
      </template>

      <!-- Filters -->
      <el-form :inline="true" class="filter-form">
        <el-form-item label="Date From">
          <el-date-picker
            v-model="dateFrom"
            type="datetime"
            placeholder="Select start date"
            format="YYYY-MM-DD HH:mm:ss"
            value-format="YYYY-MM-DDTHH:mm:ss"
            style="width: 200px"
          />
        </el-form-item>
        <el-form-item label="Date To">
          <el-date-picker
            v-model="dateTo"
            type="datetime"
            placeholder="Select end date"
            format="YYYY-MM-DD HH:mm:ss"
            value-format="YYYY-MM-DDTHH:mm:ss"
            style="width: 200px"
          />
        </el-form-item>
        <el-form-item label="Project">
          <el-input
            v-model="projectKey"
            placeholder="Enter project key"
            clearable
            style="width: 150px"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadValidationData">Apply</el-button>
          <el-button @click="resetFilters">Reset</el-button>
        </el-form-item>
      </el-form>

      <!-- Metrics Cards -->
      <el-row :gutter="20" class="metrics-row">
      <el-col :xs="24" :sm="12" :md="6">
        <el-card class="metric-card total">
          <div class="metric-content">
            <div class="metric-icon">
              <el-icon :size="32"><TrendCharts /></el-icon>
            </div>
            <div class="metric-info">
              <div class="metric-value">{{ validationData?.total_attempted || 0 }}</div>
              <div class="metric-label">Total Attempted</div>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :sm="12" :md="6">
        <el-card class="metric-card success">
          <div class="metric-content">
            <div class="metric-icon">
              <el-icon :size="32" color="#67c23a"><Check /></el-icon>
            </div>
            <div class="metric-info">
              <div class="metric-value">{{ validationData?.total_successful || 0 }}</div>
              <div class="metric-label">Successful</div>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :sm="12" :md="6">
        <el-card class="metric-card failed">
          <div class="metric-content">
            <div class="metric-icon">
              <el-icon :size="32" color="#f56c6c"><Warning /></el-icon>
            </div>
            <div class="metric-info">
              <div class="metric-value">{{ validationData?.total_failed || 0 }}</div>
              <div class="metric-label">Failed</div>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :sm="12" :md="6">
        <el-card class="metric-card rate">
          <div class="metric-content">
            <div class="metric-icon">
              <el-progress
                type="circle"
                :percentage="validationData?.success_rate || 0"
                :color="successRateColor"
                :width="60"
                :stroke-width="6"
              />
            </div>
            <div class="metric-info">
              <div class="metric-value" :style="{ color: successRateColor }">
                {{ validationData?.success_rate.toFixed(2) || 0 }}%
              </div>
              <div class="metric-label">Success Rate</div>
            </div>
          </div>
        </el-card>
      </el-col>
      </el-row>

      <!-- Failed Reviews Section -->
      <div class="failed-reviews-section">
        <div class="section-header">
          <h3>Failed Reviews</h3>
          <el-tag type="danger" size="large">
            {{ validationData?.failed_reviews.length || 0 }} Failed
          </el-tag>
        </div>

        <el-table
        v-loading="loading"
        :data="validationData?.failed_reviews || []"
        stripe
        style="width: 100%"
        empty-text="No failed reviews"
      >
        <el-table-column prop="id" label="ID" width="80" />
        
        <el-table-column label="Pull Request" min-width="150">
          <template #default="{ row }">
            <div class="pr-info">
              <div class="pr-id">{{ row.request_payload.pull_request_id || '-' }}</div>
              <div class="pr-meta">
                {{ row.request_payload.project_key }}/{{ row.request_payload.repository_slug }}
              </div>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="PR User" width="120">
          <template #default="{ row }">
            {{ row.request_payload.pull_request_user || '-' }}
          </template>
        </el-table-column>

        <el-table-column label="Reviewer" width="120">
          <template #default="{ row }">
            {{ row.request_payload.reviewer || '-' }}
          </template>
        </el-table-column>

        <el-table-column label="Error" min-width="250">
          <template #default="{ row }">
            <el-tooltip
              :content="getErrorMessage(row)"
              placement="top"
              :show-after="500"
            >
              <div class="error-cell">
                <el-icon color="#f56c6c"><Warning /></el-icon>
                <span class="error-message">{{ getErrorMessage(row) }}</span>
              </div>
            </el-tooltip>
          </template>
        </el-table-column>

        <el-table-column label="Created" width="150">
          <template #default="{ row }">
            <div class="time-info">
              <div>{{ formatDate(row.created_date) }}</div>
              <div class="relative-time">{{ formatRelativeTime(row.created_date) }}</div>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="Actions" width="180" fixed="right">
          <template #default="{ row }">
            <div class="actions-cell">
              <el-button
                type="primary"
                size="small"
                :loading="retrying === row.id"
                @click="handleRetry(row)"
              >
                Retry
              </el-button>
              <el-button
                type="danger"
                size="small"
                :loading="deleting === row.id"
                :disabled="retrying === row.id"
                @click="handleDelete(row)"
              >
                Delete
              </el-button>
            </div>
          </template>
        </el-table-column>
        </el-table>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.review-validation {
  padding: 0;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.title-with-help {
  display: flex;
  align-items: center;
  gap: 8px;
}

.card-header h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.help-icon {
  font-size: 18px;
  color: var(--el-text-color-secondary);
  cursor: pointer;
  transition: color 0.2s;
}

.help-icon:hover {
  color: var(--el-color-primary);
}

.validation-help-content {
  max-width: 400px;
  line-height: 1.6;
}

.validation-help-content p {
  margin: 0 0 8px 0;
}

.validation-help-content p:last-child {
  margin-bottom: 0;
}

.filter-form {
  margin-bottom: 20px;
}

.metrics-row {
  margin-bottom: 24px;
}

.metric-card {
  height: 120px;
  transition: transform 0.2s;
}

.metric-card:hover {
  transform: translateY(-2px);
}

.metric-content {
  display: flex;
  align-items: center;
  gap: 16px;
  height: 100%;
}

.metric-icon {
  flex-shrink: 0;
}

.metric-info {
  flex: 1;
}

.metric-value {
  font-size: 28px;
  font-weight: bold;
  color: var(--el-text-color-primary);
  line-height: 1.2;
}

.metric-label {
  font-size: 14px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
}

.failed-reviews-section {
  margin-top: 24px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.section-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.pr-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.pr-id {
  font-weight: 600;
  color: var(--el-color-primary);
}

.pr-meta {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.error-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.error-message {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--el-color-danger);
  font-size: 13px;
}

.time-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.relative-time {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

/* Responsive adjustments */
@media (max-width: 768px) {
  .metric-card {
    height: auto;
    min-height: 100px;
  }

  .metric-value {
    font-size: 24px;
  }
}

/* Dark theme adjustments */
[data-theme='dark'] .metric-card {
  background-color: var(--el-bg-color-overlay);
}

[data-theme='dark'] .metric-value {
  color: var(--el-text-color-primary);
}

[data-theme='dark'] .section-header h3 {
  color: var(--el-text-color-primary);
}

.actions-cell {
  display: flex;
  gap: 6px;
  white-space: nowrap;
}
</style>
