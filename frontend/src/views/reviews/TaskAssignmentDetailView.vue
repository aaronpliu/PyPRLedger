<template>
  <div class="task-detail-container">
    <el-page-header @back="goBack" :title="t('task_assignment.detail.back')">
      <template #content>
        <span class="header-content-title">{{ t('task_assignment.detail.title') }}</span>
      </template>
      <template #extra>
        <div class="detail-navigation-actions">
          <span v-if="currentReviewIndex >= 0" class="detail-navigation-position">
            {{ t('common.page') }} {{ taskAssignmentNavStore.currentPage }} · {{ currentReviewIndex + 1 }}/{{ taskAssignmentNavStore.items.length }}
          </span>
          <el-button
            class="detail-navigation-button"
            :disabled="!canGoToPreviousPage || navigatingPage"
            @click="goToPreviousReview"
          >
            <el-icon><ArrowLeft /></el-icon>
            {{ t('reviews.detail.previous') }}
          </el-button>

          <el-button
            class="detail-navigation-button"
            :disabled="!canGoToNextPage || navigatingPage"
            @click="goToNextReview"
          >
            {{ t('reviews.detail.next') }}
            <el-icon><ArrowRight /></el-icon>
          </el-button>
        </div>
      </template>
    </el-page-header>

    <el-card v-loading="loading" class="detail-card">

      <div v-if="review" class="detail-content">
        <!-- PR Information -->
        <el-descriptions :title="t('task_assignment.detail.pr_information')" :column="3" border>
          <el-descriptions-item :label="t('task_assignment.detail.pr_id')">
            <a 
              v-if="review && getPrUrl(review)" 
              :href="getPrUrl(review) || undefined" 
              target="_blank" 
              rel="noopener noreferrer"
              class="pr-link"
            >
              {{ review.pull_request_id }}
              <el-icon style="margin-left: 4px;"><Link /></el-icon>
            </a>
            <span v-else>{{ review?.pull_request_id }}</span>
          </el-descriptions-item>
          <el-descriptions-item :label="t('task_assignment.detail.commit_id')">{{ review.pull_request_commit_id || t('reviews.detail.na') }}</el-descriptions-item>
          <el-descriptions-item :label="t('task_assignment.detail.project')">{{ review.project_key }}</el-descriptions-item>
          <el-descriptions-item :label="t('task_assignment.detail.repository')">{{ review.repository_slug }}</el-descriptions-item>
          <el-descriptions-item :label="t('task_assignment.detail.source_branch')">
            <el-tag>{{ review.source_branch }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item :label="t('task_assignment.detail.target_branch')">
            <el-tag type="success">{{ review.target_branch }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item :label="t('task_assignment.detail.pr_status')">
            <el-tag :type="getStatusType(review.pull_request_status)">
              {{ review.pull_request_status }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item :label="t('task_assignment.detail.created')">
            {{ formatDate(review.created_date) }}
          </el-descriptions-item>
        </el-descriptions>

        <!-- Reviewers + AI Suggestions: two-column row -->
        <el-divider />
        <div class="reviewers-ai-row">
          <!-- LEFT: Reviewers Management -->
          <div class="reviewers-column">
            <div class="section-header">
              <h3>{{ t('task_assignment.detail.reviewers') }} ({{ review.total_reviewers }})</h3>
              <el-button type="primary" size="small" @click="handleAssignReviewer">
                {{ t('task_assignment.detail.assign_reviewer') }}
              </el-button>
            </div>

            <el-table :data="review.reviewers" stripe border header-align="center">
              <el-table-column prop="id" :label="t('task_assignment.detail.id')" width="80" align="center" />
              
              <el-table-column :label="t('task_assignment.detail.reviewer')" min-width="150" align="center">
                <template #default="{ row }">
                  <div class="reviewer-info">
                    <strong>{{ row.reviewer }}</strong>
                    <div v-if="row.reviewer_info" class="display-name">
                      {{ row.reviewer_info.display_name }}
                    </div>
                  </div>
                </template>
              </el-table-column>

              <el-table-column :label="t('task_assignment.detail.assigned_by')" width="150" align="center">
                <template #default="{ row }">
                  {{ row.assigned_by || t('reviews.detail.na') }}
                </template>
              </el-table-column>

              <el-table-column :label="t('task_assignment.detail.assigned_date')" width="180" align="center">
                <template #default="{ row }">
                  {{ row.assigned_date ? formatDate(row.assigned_date) : t('reviews.detail.na') }}
                </template>
              </el-table-column>

              <el-table-column :label="t('task_assignment.detail.status')" width="120" align="center">
                <template #default="{ row }">
                  <el-dropdown @command="(cmd: string) => handleUpdateStatus(row.id, cmd)">
                    <el-tag :type="getAssignmentStatusType(row.assignment_status)" class="clickable">
                      {{ formatAssignmentStatusLabel(row.assignment_status) }}
                      <el-icon class="el-icon--right"><ArrowDown /></el-icon>
                    </el-tag>
                    <template #dropdown>
                      <el-dropdown-menu>
                        <el-dropdown-item command="pending">{{ t('reviews.pending') }}</el-dropdown-item>
                        <el-dropdown-item command="assigned">{{ t('reviews.assigned') }}</el-dropdown-item>
                        <el-dropdown-item command="in_progress">{{ t('reviews.in_progress') }}</el-dropdown-item>
                        <el-dropdown-item command="completed">{{ t('reviews.completed') }}</el-dropdown-item>
                      </el-dropdown-menu>
                    </template>
                  </el-dropdown>
                </template>
              </el-table-column>

              <el-table-column :label="t('task_assignment.detail.comments')" min-width="200" align="left">
                <template #default="{ row }">
                  <span v-if="row.reviewer_comments">{{ row.reviewer_comments }}</span>
                  <span v-else class="status-description">
                    {{ getAssignmentStatusDescription(row.assignment_status) }}
                  </span>
                </template>
              </el-table-column>

              <el-table-column :label="t('task_assignment.detail.actions')" width="100" fixed="right" align="center">
                <template #default="{ row }">
                  <el-button
                    size="small"
                    type="danger"
                    link
                    @click="handleRemoveReviewer(row.reviewer)"
                  >
                    {{ t('task_assignment.detail.remove') }}
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>

          <!-- RIGHT: AI Suggestions -->
          <div v-if="review.ai_suggestions" class="ai-column">
            <div class="ai-section">
              <div class="ai-header">
                <h3>
                  {{ t('task_assignment.detail.ai_review_result') }}
                  <el-tag v-if="review.ai_review_id" size="small" type="info" style="margin-left: 8px">
                    {{ review.ai_review_id }}
                  </el-tag>
                </h3>
                <el-button
                  v-if="review.ai_review_id"
                  size="small"
                  text
                  @click="copyToClipboard(review.ai_review_id)"
                >
                  <el-icon><CopyDocument /></el-icon>
                  {{ t('task_assignment.detail.copy_id') }}
                </el-button>
              </div>
              <el-alert
                v-if="review.ai_suggestions.overall_assessment"
                :title="review.ai_suggestions.overall_assessment"
                type="info"
                :closable="false"
                style="margin-bottom: 16px"
              />
              
              <div v-if="review.ai_suggestions.issues && review.ai_suggestions.issues.length > 0">
                <h4>{{ t('task_assignment.detail.issues_found') }} ({{ review.ai_suggestions.issues.length }})</h4>
                <el-collapse>
                  <el-collapse-item
                    v-for="(issue, index) in review.ai_suggestions.issues"
                    :key="index"
                    :title="`${issue.category} - ${issue.severity} (${issue.file}:${issue.line})`"
                  >
                    <p><strong>{{ t('task_assignment.detail.description') }}:</strong> {{ issue.description }}</p>
                    <p v-if="issue.suggestion"><strong>{{ t('task_assignment.detail.suggestion') }}:</strong> {{ issue.suggestion }}</p>
                    <pre v-if="issue.code_snippet" class="code-snippet">{{ issue.code_snippet }}</pre>
                  </el-collapse-item>
                </el-collapse>
              </div>
            </div>
          </div>
        </div>

        <!-- Code Diff -->
        <el-divider />
        <div v-if="review.git_code_diff" class="diff-section">
          <div class="diff-header">
            <h3>{{ t('task_assignment.detail.code_diff') }}</h3>
            <div class="view-toggle-buttons">
              <el-button
                :type="outputFormat === 'line-by-line' ? 'primary' : 'default'"
                size="small"
                @click="outputFormat = 'line-by-line'"
              >
                {{ t('task_assignment.detail.line_by_line') }}
              </el-button>
              <el-button
                :type="outputFormat === 'side-by-side' ? 'primary' : 'default'"
                size="small"
                @click="outputFormat = 'side-by-side'"
              >
                {{ t('task_assignment.detail.side_by_side') }}
              </el-button>
            </div>
          </div>
          <CodeDiffViewer
            :diff="review.git_code_diff"
            :output-format="outputFormat"
            @update:output-format="outputFormat = $event"
          />
        </div>
      </div>
    </el-card>

    <!-- Floating Navigation Buttons -->
    <div
      v-if="taskAssignmentNavStore.items.length > 1"
      class="floating-navigation"
    >
      <transition name="fade-slide">
        <div
          v-if="canGoToPreviousPage && !navigatingPage"
          class="floating-nav-btn floating-nav-prev"
          @click="goToPreviousReview"
        >
          <el-icon :size="20"><ArrowLeft /></el-icon>
        </div>
      </transition>

      <transition name="fade-slide">
        <div
          v-if="canGoToNextPage && !navigatingPage"
          class="floating-nav-btn floating-nav-next"
          @click="goToNextReview"
        >
          <el-icon :size="20"><ArrowRight /></el-icon>
        </div>
      </transition>
    </div>

    <!-- Assign Reviewer Dialog -->
    <el-dialog v-model="assignDialogVisible" :title="t('task_assignment.detail.assign_reviewer_dialog.title')" width="640px">
      <el-form :model="assignForm" label-width="120px">
        <el-form-item :label="t('task_assignment.detail.assign_reviewer_dialog.pr_id')">
          <el-input :value="review?.pull_request_id" disabled />
        </el-form-item>
        <el-form-item :label="t('task_assignment.detail.assign_reviewer_dialog.project_repo')">
          <el-input :value="review ? `${review.project_key} / ${review.repository_slug}` : ''" disabled />
        </el-form-item>
        <el-form-item :label="t('task_assignment.detail.assign_reviewer_dialog.pr_user')">
          <el-input :value="getPullRequestAuthor()" disabled />
        </el-form-item>
        <el-form-item :label="t('task_assignment.detail.assign_reviewer_dialog.branches')">
          <el-input :value="review ? `${review.source_branch} -> ${review.target_branch}` : ''" disabled />
        </el-form-item>
        <el-form-item :label="t('task_assignment.detail.assign_reviewer_dialog.pr_status')">
          <el-tag v-if="review" :type="getStatusType(review.pull_request_status)">
            {{ review.pull_request_status }}
          </el-tag>
        </el-form-item>
        <el-form-item :label="t('task_assignment.detail.assign_reviewer_dialog.reviewers_label')">
          <div class="current-reviewers">
            <el-tag
              v-for="assignedReviewer in review?.reviewers || []"
              :key="assignedReviewer.id"
              :type="getAssignmentStatusType(assignedReviewer.assignment_status)"
              size="small"
            >
              {{ assignedReviewer.reviewer_info?.display_name || assignedReviewer.reviewer }}
            </el-tag>
            <span v-if="!review?.reviewers?.length" class="empty-reviewers">{{ t('task_assignment.detail.assign_reviewer_dialog.no_reviewers_assigned') }}</span>
          </div>
        </el-form-item>
        <el-form-item :label="t('task_assignment.detail.assign_reviewer_dialog.reviewer_select')" required>
          <el-select
            v-model="assignForm.reviewer"
            :placeholder="t('task_assignment.detail.assign_reviewer_dialog.select_reviewer_placeholder')"
            style="width: 100%"
            filterable
            :loading="loadingReviewers"
            :disabled="loadingReviewers || availableReviewers.length === 0"
          >
            <el-option
              v-for="user in availableReviewers"
              :key="user.username"
              :label="formatReviewerOption(user)"
              :value="user.username"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-if="!loadingReviewers && availableReviewers.length === 0" label="">
          <span class="empty-reviewers">{{ t('task_assignment.detail.assign_reviewer_dialog.no_available_reviewers') }}</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="assignDialogVisible = false">{{ t('task_assignment.detail.assign_reviewer_dialog.cancel') }}</el-button>
        <el-button type="primary" @click="submitAssignment" :loading="assigning">
          {{ t('task_assignment.detail.assign_reviewer_dialog.assign') }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowDown, ArrowLeft, ArrowRight, CopyDocument, Link } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'
import { taskAssignmentApi, type ReviewV2 } from '@/api/taskAssignment'
import { usersApi, type ReviewerUser } from '@/api/users'
import CodeDiffViewer from '@/components/review/CodeDiffViewer.vue'
import { usePrUrl } from '@/composables/usePrUrl'
import { useTaskAssignmentNavigationStore } from '@/stores/taskAssignmentNavigation'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const { getPrUrl } = usePrUrl()
const taskAssignmentNavStore = useTaskAssignmentNavigationStore()

// State
const loading = ref(false)
const navigatingPage = ref(false)
const review = ref<ReviewV2 | null>(null)
const outputFormat = ref<'line-by-line' | 'side-by-side'>('line-by-line')

// Assign dialog
const assignDialogVisible = ref(false)
const assigning = ref(false)
const loadingReviewers = ref(false)
const assignForm = ref({
  reviewer: '',
})
const availableReviewers = ref<ReviewerUser[]>([])

// Load review details
const loadReview = async () => {
  const id = Number(route.params.id)
  if (!id) return

  loading.value = true
  try {
    review.value = await taskAssignmentApi.getReviewById(id)
  } catch (error) {
    console.error('Failed to load review:', error)
    ElMessage.error('Failed to load review details')
  } finally {
    loading.value = false
  }
}

// Format date
const formatDate = (dateStr: string) => {
  return new Date(dateStr).toLocaleString()
}

const getPullRequestAuthor = () => {
  if (!review.value) return ''
  return review.value.pull_request_user_info?.display_name || review.value.pull_request_user || 'Unknown'
}

const formatReviewerOption = (user: ReviewerUser) => {
  return `${user.display_name} (${user.username})`
}

const loadAvailableReviewers = async () => {
  if (!review.value) return

  loadingReviewers.value = true
  try {
    const response = await usersApi.getReviewers(500)
    const assignedReviewers = new Set(review.value.reviewers.map(item => item.reviewer))
    availableReviewers.value = response.items.filter(user => !assignedReviewers.has(user.username))
  } catch (error) {
    console.error('Failed to load reviewers:', error)
    availableReviewers.value = []
    ElMessage.error('Failed to load reviewers')
  } finally {
    loadingReviewers.value = false
  }
}

// Get status type
const getStatusType = (status: string) => {
  switch (status) {
    case 'open':
      return 'success'
    case 'merged':
      return 'info'
    case 'closed':
      return 'danger'
    default:
      return ''
  }
}

// Get assignment status type
const getAssignmentStatusType = (status: string) => {
  switch (status) {
    case 'completed':
      return 'success'
    case 'in_progress':
      return 'warning'
    case 'assigned':
      return 'primary'
    default:
      return 'info'
  }
}

const formatAssignmentStatusLabel = (status: string) => {
  switch (status) {
    case 'in_progress':
      return 'In Progress'
    case 'assigned':
      return 'Assigned'
    case 'pending':
      return 'Pending'
    case 'completed':
      return 'Completed'
    default:
      return status
  }
}

const getAssignmentStatusDescription = (status: string | undefined | null) => {
  if (!status) {
    return t('reviews.assignment_status_descriptions.pending', 'Pending')
  }
  return t(`reviews.assignment_status_descriptions.${status}`, status)
}

// Navigation computed properties
const currentReviewIndex = computed(() => {
  const routeId = Number(route.params.id)
  return taskAssignmentNavStore.items.findIndex(item => item.id === routeId)
})

const nextReview = computed(() => {
  if (currentReviewIndex.value < 0) return null
  return taskAssignmentNavStore.items[currentReviewIndex.value + 1] || null
})

const previousReview = computed(() => {
  if (currentReviewIndex.value <= 0) return null
  return taskAssignmentNavStore.items[currentReviewIndex.value - 1] || null
})

const canGoToNextPage = computed(() => {
  return taskAssignmentNavStore.hasMorePages || (currentReviewIndex.value < taskAssignmentNavStore.items.length - 1)
})

const canGoToPreviousPage = computed(() => {
  return taskAssignmentNavStore.currentPage > 1 || currentReviewIndex.value > 0
})

// Navigation functions
const goToNextReview = async () => {
  if (nextReview.value) {
    router.replace(`/task-assignment/${nextReview.value.id}`)
    return
  }

  if (taskAssignmentNavStore.hasMorePages && currentReviewIndex.value === taskAssignmentNavStore.items.length - 1) {
    await loadNextPage()
  }
}

const goToPreviousReview = async () => {
  if (previousReview.value) {
    router.replace(`/task-assignment/${previousReview.value.id}`)
    return
  }

  if (taskAssignmentNavStore.currentPage > 1 && currentReviewIndex.value === 0) {
    await loadPreviousPage()
  }
}

const loadNextPage = async () => {
  if (!review.value || navigatingPage.value) return

  navigatingPage.value = true
  try {
    const nextPage = taskAssignmentNavStore.currentPage + 1
    const params: Record<string, any> = {
      page: nextPage,
      page_size: taskAssignmentNavStore.pageSize,
    }

    const storedFilters = taskAssignmentNavStore.filters || {}
    if (storedFilters.project_key) params.project_key = storedFilters.project_key
    if (storedFilters.reviewer) params.reviewer = storedFilters.reviewer
    if (storedFilters.status) params.status = storedFilters.status
    if (storedFilters.app_names) params.app_names = storedFilters.app_names
    if (storedFilters.pull_request_user) params.pull_request_user = storedFilters.pull_request_user
    if (storedFilters.severity) params.severity = storedFilters.severity
    if (storedFilters.date_from) params.date_from = storedFilters.date_from
    if (storedFilters.date_to) params.date_to = storedFilters.date_to
    if (storedFilters.hide_archived !== undefined) params.hide_archived = storedFilters.hide_archived

    const response = await taskAssignmentApi.getReviews(params)

    if (response.items.length === 0) {
      ElMessage.warning('No more reviews available')
      return
    }

    const totalPages = Math.ceil(response.total / taskAssignmentNavStore.pageSize)
    taskAssignmentNavStore.setContext({
      items: response.items.map(item => ({
        id: item.id,
        projectKey: item.project_key,
        repositorySlug: item.repository_slug,
        pullRequestId: item.pull_request_id,
      })),
      currentPage: nextPage,
      pageSize: taskAssignmentNavStore.pageSize,
      totalItems: response.total,
      hasMorePages: nextPage < totalPages,
      filters: storedFilters,
    })

    const firstReview = response.items[0]
    if (firstReview) {
      router.replace(`/task-assignment/${firstReview.id}`)
    }
  } catch (error) {
    console.error('Failed to load next page:', error)
    ElMessage.error('Failed to load next page')
  } finally {
    navigatingPage.value = false
  }
}

const loadPreviousPage = async () => {
  if (!review.value || navigatingPage.value) return

  navigatingPage.value = true
  try {
    const prevPage = taskAssignmentNavStore.currentPage - 1
    const params: Record<string, any> = {
      page: prevPage,
      page_size: taskAssignmentNavStore.pageSize,
    }

    const storedFilters = taskAssignmentNavStore.filters || {}
    if (storedFilters.project_key) params.project_key = storedFilters.project_key
    if (storedFilters.reviewer) params.reviewer = storedFilters.reviewer
    if (storedFilters.status) params.status = storedFilters.status
    if (storedFilters.app_names) params.app_names = storedFilters.app_names
    if (storedFilters.pull_request_user) params.pull_request_user = storedFilters.pull_request_user
    if (storedFilters.severity) params.severity = storedFilters.severity
    if (storedFilters.date_from) params.date_from = storedFilters.date_from
    if (storedFilters.date_to) params.date_to = storedFilters.date_to
    if (storedFilters.hide_archived !== undefined) params.hide_archived = storedFilters.hide_archived

    const response = await taskAssignmentApi.getReviews(params)

    if (response.items.length === 0) {
      ElMessage.warning('No more reviews available')
      return
    }

    const totalPages = Math.ceil(response.total / taskAssignmentNavStore.pageSize)
    taskAssignmentNavStore.setContext({
      items: response.items.map(item => ({
        id: item.id,
        projectKey: item.project_key,
        repositorySlug: item.repository_slug,
        pullRequestId: item.pull_request_id,
      })),
      currentPage: prevPage,
      pageSize: taskAssignmentNavStore.pageSize,
      totalItems: response.total,
      hasMorePages: prevPage < totalPages,
      filters: storedFilters,
    })

    const lastReview = response.items[response.items.length - 1]
    if (lastReview) {
      router.replace(`/task-assignment/${lastReview.id}`)
    }
  } catch (error) {
    console.error('Failed to load previous page:', error)
    ElMessage.error('Failed to load previous page')
  } finally {
    navigatingPage.value = false
  }
}

// Go back
const goBack = () => {
  router.push('/task-assignment')
}

// Handle assign reviewer
const handleAssignReviewer = async () => {
  assignForm.value.reviewer = ''
  assignDialogVisible.value = true
  await loadAvailableReviewers()
}

// Submit assignment
const submitAssignment = async () => {
  if (!assignForm.value.reviewer || !review.value) return

  assigning.value = true
  try {
    await taskAssignmentApi.assignReviewer(review.value.id, {
      reviewer: assignForm.value.reviewer,
    })
    ElMessage.success('Reviewer assigned successfully')
    assignDialogVisible.value = false
    await loadReview()
  } catch (error) {
    console.error('Failed to assign reviewer:', error)
    ElMessage.error('Failed to assign reviewer')
  } finally {
    assigning.value = false
  }
}

// Update assignment status
const handleUpdateStatus = async (assignmentId: number, status: string) => {
  try {
    await taskAssignmentApi.updateAssignmentStatus(assignmentId, {
      assignment_status: status as any,
    })
    ElMessage.success('Status updated successfully')
    loadReview()
  } catch (error) {
    console.error('Failed to update status:', error)
    ElMessage.error('Failed to update status')
  }
}

// Remove reviewer
const handleRemoveReviewer = async (reviewer: string) => {
  try {
    await ElMessageBox.confirm(
      `Are you sure you want to remove reviewer "${reviewer}"?`,
      'Confirm Removal',
      {
        confirmButtonText: 'Remove',
        cancelButtonText: 'Cancel',
        type: 'warning',
      }
    )

    if (!review.value) return

    await taskAssignmentApi.removeReviewer(review.value.id, reviewer)
    ElMessage.success('Reviewer removed successfully')
    loadReview()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('Failed to remove reviewer:', error)
      ElMessage.error('Failed to remove reviewer')
    }
  }
}

const copyToClipboard = (text: string) => {
  navigator.clipboard.writeText(text).then(() => {
    ElMessage.success('Copied to clipboard')
  }).catch(() => {
    ElMessage.error('Failed to copy to clipboard')
  })
}

watch(
  () => route.fullPath,
  () => {
    loadReview()
  }
)

onMounted(() => {
  loadReview()
})
</script>

<style scoped>
.task-detail-container {
  padding: 20px;
}

.header-content-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.detail-card {
  margin-top: 20px;
}

.detail-content {
  width: 100%;
}

/* Navigation Styles */
.detail-navigation-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.detail-navigation-button {
  width: 104px;
}

.detail-navigation-position {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--el-text-color-secondary);
  font-size: 13px;
  min-width: 104px;
  height: 32px;
  padding: 0 16px;
  text-align: center;
  box-sizing: border-box;
  border-radius: 999px;
  background: var(--el-fill-color-light);
  border: 1px solid var(--el-border-color-lighter);
  font-weight: 500;
  white-space: nowrap;
}

/* Two-column row: Reviewers (left) + AI Suggestions (right) */
.reviewers-ai-row {
  display: flex;
  gap: 24px;
  align-items: flex-start;
}

.reviewers-column {
  flex: 3;
  min-width: 0;
}

.ai-column {
  flex: 2;
  min-width: 0;
  max-height: 600px;
  overflow-y: auto;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  padding: 20px;
  background: var(--el-fill-color-lighter);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.reviewer-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.display-name {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.clickable {
  cursor: pointer;
}

/* PR Link Styles */
.pr-link {
  text-decoration: none;
  color: var(--el-color-primary);
  font-weight: 500;
  transition: all 0.2s ease;
  display: inline-flex;
  align-items: center;
}

.pr-link:hover {
  opacity: 0.7;
  text-decoration: underline;
}

.current-reviewers {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  min-height: 32px;
  align-items: center;
}

.empty-reviewers {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.status-description {
  color: var(--el-text-color-secondary);
  font-style: italic;
  font-size: 12px;
}

.ai-section {
  margin-top: 0;
}

.ai-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.ai-header h3 {
  display: flex;
  align-items: center;
  margin: 0;
}

.ai-review-id-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  justify-content: center;
}

.empty-value {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.code-snippet {
  background: var(--el-fill-color-light);
  padding: 12px;
  border-radius: 4px;
  overflow-x: auto;
  font-size: 12px;
}

.diff-section {
  margin-top: 20px;
}

.diff-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.view-toggle-buttons {
  display: flex;
  gap: 8px;
}

/* Floating Navigation Styles */
.floating-navigation {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
  z-index: 100;
}

.floating-nav-btn {
  position: fixed;
  top: 50%;
  transform: translateY(-50%);
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  background: var(--el-color-primary);
  color: white;
  border-radius: 50%;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  transition: all 0.3s ease;
  pointer-events: auto;
  opacity: 0;
  visibility: hidden;
}

.floating-nav-btn:hover {
  background: var(--el-color-primary-light-3);
  transform: translateY(-50%) scale(1.15);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
}

.floating-nav-prev {
  left: 5px;
}

.floating-nav-next {
  right: 5px;
}

.task-detail-container:hover .floating-nav-prev,
.floating-navigation:hover .floating-nav-prev {
  opacity: 1;
  visibility: visible;
}

.task-detail-container:hover .floating-nav-next,
.floating-navigation:hover .floating-nav-next {
  opacity: 1;
  visibility: visible;
}

/* Transitions */
.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: all 0.3s ease;
}

.fade-slide-enter-from {
  opacity: 0;
  transform: translateY(-50%) translateX(-10px);
}

.fade-slide-leave-to {
  opacity: 0;
  transform: translateY(-50%) translateX(-10px);
}

.floating-nav-next.fade-slide-enter-from,
.floating-nav-next.fade-slide-leave-to {
  transform: translateY(-50%) translateX(10px);
}

/* Dark theme adjustments */
[data-theme='dark'] .floating-nav-btn {
  background: var(--el-color-primary-dark-2);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}

[data-theme='dark'] .floating-nav-btn:hover {
  background: var(--el-color-primary-light-5);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
}

/* Responsive adjustments */
@media (max-width: 768px) {
  .floating-nav-btn {
    width: 32px;
    height: 32px;
  }

  .floating-nav-prev {
    left: 8px;
  }

  .floating-nav-next {
    right: 8px;
  }
}
</style>
