<template>
  <div class="task-assignment-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <div class="header-title-group">
            <h2>{{ t('task_assignment.management_title') }}</h2>
            <el-tag type="info">{{ t('task_assignment.review_admin_only') }}</el-tag>
          </div>
          <div class="header-actions">
            <div class="live-toggle-wrapper">
              <span class="live-dot" :class="{ active: sseEnabled }" />
              <span class="live-label">{{ t('common.live_update') }}</span>
              <el-switch
                :model-value="sseEnabled"
                size="small"
                class="live-switch"
                @change="toggleSse"
              />
            </div>
            <el-button @click="loadReviews">
              <el-icon><Refresh /></el-icon>
              {{ t('task_assignment.refresh') }}
            </el-button>
          </div>
        </div>
      </template>

      <!-- Filters -->
      <FilterPopover
        v-model:search-query="searchQuery"
        v-model:app-filter="appFilter"
        v-model:project-filter="projectFilter"
        v-model:pr-user-filter="prUserFilter"
        v-model:reviewer-filter="reviewerFilter"
        v-model:scored-filter="scoredFilter"
        v-model:severity-filter="severityFilter"
        v-model:status-filter="statusFilter"
        v-model:date-from="dateFrom"
        v-model:date-to="dateTo"
        :app-options="availableApps"
        :project-options="projects"
        :pr-user-options="availablePRUsers"
        :reviewer-options="availableReviewers"
        :pr-users-loading="prUsersLoading"
        :reviewers-loading="reviewersLoading"
        show-project-filter
        @apply="loadReviews"
        @reset="handleResetFilters"
      />
        
      <!-- Bulk Actions Toolbar -->
      <div v-if="selectedReviews.length > 0" class="bulk-actions-toolbar">
        <div class="selection-info">
          <el-icon><CircleCheck /></el-icon>
          <span>{{ selectedReviews.length }} item{{ selectedReviews.length > 1 ? 's' : '' }} selected</span>
        </div>
        <div class="bulk-actions">
          <el-button size="small" type="primary" @click="showBulkAssignDialog">
            <el-icon><Edit /></el-icon>
            Assign Reviewer
          </el-button>
          <el-button size="small" @click="clearSelection">
            <el-icon><Close /></el-icon>
            Clear Selection
          </el-button>
        </div>
      </div>
      
      <!-- Reviews Table -->
      <el-table
        :data="reviews"
        v-loading="loading"
        stripe
        border
        table-layout="auto"
        class="task-assignment-table"
        :header-cell-style="{ textAlign: 'center' }"
        :cell-style="getCellStyle"
        :row-class-name="getRowClassName"
        @selection-change="handleSelectionChange"
      >
        <!-- Selection column for bulk operations -->
        <el-table-column type="selection" width="55" fixed="left" />
        <el-table-column :label="t('task_assignment.seq_number')" width="80">
          <template #default="{ $index }">
            {{ (currentPage - 1) * pageSize + $index + 1 }}
          </template>
        </el-table-column>
        
        <!-- App Name -->
        <el-table-column :label="t('task_assignment.app_name')" width="150">
          <template #default="{ row }">
            <el-tag v-if="row.app_name && row.app_name !== 'Unknown'" type="primary" size="small">
              {{ row.app_name }}
            </el-tag>
            <span v-else class="text-secondary">{{ t('task_assignment.unknown') }}</span>
          </template>
        </el-table-column>
        
        <el-table-column :label="t('task_assignment.pr_info')" min-width="220">
          <template #default="{ row }">
            <div class="pr-info" :title="`${row.pull_request_id} | ${row.project_key}/${row.repository_slug}`">
              <div class="pr-id">
                <a 
                  v-if="getPrUrl(row)" 
                  :href="getPrUrl(row) || undefined" 
                  target="_blank" 
                  rel="noopener noreferrer"
                  class="pr-link"
                >
                  {{ row.pull_request_id }}
                  <el-icon style="margin-left: 4px; font-size: 0.85em;"><Link /></el-icon>
                </a>
                <span v-else>{{ row.pull_request_id }}</span>
              </div>
              <div class="pr-project">{{ row.project_key }}/{{ row.repository_slug }}</div>
            </div>
          </template>
        </el-table-column>

        <el-table-column :label="t('task_assignment.branches')" min-width="220">
          <template #default="{ row }">
            <div class="branches" :title="`${row.source_branch} -> ${row.target_branch}`">
              <el-tag size="small">{{ row.source_branch }}</el-tag>
              <span class="arrow">→</span>
              <el-tag size="small" type="success">{{ row.target_branch }}</el-tag>
            </div>
          </template>
        </el-table-column>

        <el-table-column :label="t('task_assignment.pr_user')" min-width="180">
          <template #default="{ row }">
            <div class="pr-user" :title="row.pull_request_user_info?.display_name || row.pull_request_user || '-'">
              <div class="pr-user-name">{{ row.pull_request_user_info?.display_name || row.pull_request_user || '-' }}</div>
              <div v-if="row.pull_request_user_info?.username && row.pull_request_user_info?.display_name !== row.pull_request_user_info?.username" class="pr-user-username">
                {{ row.pull_request_user_info.username }}
              </div>
            </div>
          </template>
        </el-table-column>

        <el-table-column :label="t('task_assignment.reviewers')" min-width="280">
          <template #default="{ row }">
            <div class="reviewers-list">
              <el-tooltip
                v-for="reviewer in row.reviewers"
                :key="reviewer.id"
                :content="getAssignmentStatusDescription(reviewer.assignment_status)"
                placement="top"
              >
                <el-tag
                  :type="getReviewerTagType(reviewer.assignment_status)"
                  size="small"
                  class="reviewer-tag"
                >
                  {{ reviewer.reviewer_info?.display_name || reviewer.reviewer }}
                  <span v-if="reviewer.assignment_status === 'completed'" class="status-icon">✓</span>
                </el-tag>
              </el-tooltip>
              <el-button
                v-if="row.reviewers.length === 0"
                type="primary"
                size="small"
                link
                @click="handleAssignReviewer(row)"
              >
                {{ t('task_assignment.assign_reviewer') }}
              </el-button>
            </div>
          </template>
        </el-table-column>

        <el-table-column :label="t('task_assignment.progress')" min-width="120">
          <template #default="{ row }">
            <div class="progress-info">
              <el-progress
                :percentage="getProgressPercentage(row)"
                :stroke-width="6"
                :show-text="false"
              />
              <div class="progress-text">
                {{ row.completed_reviewers }}/{{ row.total_reviewers }}
              </div>
            </div>
          </template>
        </el-table-column>

        <el-table-column :label="t('task_assignment.status')" min-width="120">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.pull_request_status)">
              {{ row.pull_request_status }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="created_date" min-width="170">
          <template #header>
            <button
              type="button"
              class="sort-header-button"
              :class="{ active: sortState.prop === 'created_date' }"
              @click="toggleSort('created_date')"
            >
              <span class="sort-header-label">{{ t('task_assignment.created') }}</span>
              <div class="sort-header-icons">
                <el-icon
                  class="sort-header-icon"
                  :class="{ active: isActiveSort('created_date', 'ascending') }"
                >
                  <ArrowUp />
                </el-icon>
                <el-icon
                  class="sort-header-icon"
                  :class="{ active: isActiveSort('created_date', 'descending') }"
                >
                  <ArrowDown />
                </el-icon>
              </div>
            </button>
          </template>
          <template #default="{ row }">
            {{ formatDate(row.created_date) }}
          </template>
        </el-table-column>

        <el-table-column prop="updated_date" min-width="170">
          <template #header>
            <button
              type="button"
              class="sort-header-button"
              :class="{ active: sortState.prop === 'updated_date' }"
              @click="toggleSort('updated_date')"
            >
              <span class="sort-header-label">Updated</span>
              <div class="sort-header-icons">
                <el-icon
                  class="sort-header-icon"
                  :class="{ active: isActiveSort('updated_date', 'ascending') }"
                >
                  <ArrowUp />
                </el-icon>
                <el-icon
                  class="sort-header-icon"
                  :class="{ active: isActiveSort('updated_date', 'descending') }"
                >
                  <ArrowDown />
                </el-icon>
              </div>
            </button>
          </template>
          <template #default="{ row }">
            {{ formatDate(row.updated_date) }}
          </template>
        </el-table-column>

        <el-table-column :label="t('task_assignment.actions')" min-width="150" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" link @click="viewDetail(row.id)">
              {{ t('task_assignment.view_details') }}
            </el-button>
            <el-button size="small" type="success" link @click="handleAssignReviewer(row)">
              {{ t('task_assignment.assign_reviewer') }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- Pagination -->
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="loadReviews"
        @current-change="loadReviews"
        style="margin-top: 20px; justify-content: flex-end"
      />
    </el-card>

    <!-- Assign Reviewer Dialog -->
    <el-dialog v-model="assignDialogVisible" title="Assign Reviewer" width="640px">
      <el-form :model="assignForm" label-width="120px">
        <el-form-item label="PR ID">
          <el-input :value="selectedReview?.pull_request_id" disabled />
        </el-form-item>
        <el-form-item label="Project / Repo">
          <el-input :value="selectedReview ? `${selectedReview.project_key} / ${selectedReview.repository_slug}` : ''" disabled />
        </el-form-item>
        <el-form-item label="PR User">
          <el-input :value="getPullRequestAuthor(selectedReview)" disabled />
        </el-form-item>
        <el-form-item label="Branches">
          <el-input :value="selectedReview ? `${selectedReview.source_branch} -> ${selectedReview.target_branch}` : ''" disabled />
        </el-form-item>
        <el-form-item label="PR Status">
          <el-tag v-if="selectedReview" :type="getStatusType(selectedReview.pull_request_status)">
            {{ selectedReview.pull_request_status }}
          </el-tag>
        </el-form-item>
        <el-form-item label="Reviewers">
          <div class="current-reviewers">
            <el-tag
              v-for="reviewer in selectedReview?.reviewers || []"
              :key="reviewer.id"
              :type="getReviewerTagType(reviewer.assignment_status)"
              size="small"
            >
              {{ reviewer.reviewer_info?.display_name || reviewer.reviewer }}
            </el-tag>
            <span v-if="!selectedReview?.reviewers?.length" class="empty-reviewers">No reviewers assigned</span>
          </div>
        </el-form-item>
        <el-form-item label="Reviewer" required>
          <el-select
            v-model="assignForm.reviewer"
            placeholder="Select reviewer"
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
          <span class="empty-reviewers">No available reviewers to assign</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="assignDialogVisible = false">Cancel</el-button>
        <el-button type="primary" @click="submitAssignment" :loading="assigning">
          Assign
        </el-button>
      </template>
    </el-dialog>

    <!-- Bulk Assign Dialog -->
    <el-dialog
      v-model="showBulkAssignDialogVisible"
      title="Bulk Assign Reviewer"
      width="500px"
    >
      <p>Assign {{ selectedReviews.length }} review(s) to a reviewer:</p>
      <el-form :model="bulkAssignForm" label-width="120px" style="margin-top: 20px">
        <el-form-item label="Reviewer" required>
          <el-select
            v-model="bulkAssignForm.reviewer"
            placeholder="Select reviewer"
            filterable
            style="width: 100%"
          >
            <el-option
              v-for="user in availableReviewers"
              :key="user.username"
              :label="formatReviewerOption(user)"
              :value="user.username"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showBulkAssignDialogVisible = false">Cancel</el-button>
        <el-button type="primary" :loading="bulkAssigning" @click="executeBulkAssign">
          Assign {{ selectedReviews.length }} Items
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowDown, ArrowUp, Refresh, Search, Link, CircleCheck, Edit, Close } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'
import { taskAssignmentApi, type ReviewV2 } from '@/api/taskAssignment'
import { usersApi, type ReviewerUser } from '@/api/users'
import { projectsApi, type ProjectSummary } from '@/api/projects'
import { projectRegistryApi } from '@/api/projectRegistry'
import type { AppInfo } from '@/api/projectRegistry'
import FilterPopover from '@/components/common/FilterPopover.vue'
import { usePrUrl } from '@/composables/usePrUrl'
import { useAuthStore } from '@/stores/auth'
import { useSse } from '@/composables/useSse'
import { type SSEReviewCreatedEvent } from '@/utils/sse'

const router = useRouter()
const authStore = useAuthStore()
const { t } = useI18n()
const { getPrUrl } = usePrUrl()
const { sseEnabled, toggleSse, connectSse, disconnectSse } = useSse()

// Responsive page size calculation
const calculatePageSize = () => {
  const windowHeight = window.innerHeight
  // Reserve space for header, filters, pagination, and margins (~400px)
  const availableHeight = windowHeight - 400
  const rowHeight = 52 // Average row height in pixels
  return Math.max(10, Math.min(100, Math.floor(availableHeight / rowHeight)))
}

const pageSize = ref(calculatePageSize())

// Update page size on window resize
const handleResize = () => {
  pageSize.value = calculatePageSize()
}

// State
const loading = ref(false)
const allReviews = ref<ReviewV2[]>([]) // Store reviews from API (current page)
const reviews = ref<ReviewV2[]>([]) // Filtered reviews for display
const total = ref(0) // Total count from API
const currentPage = ref(1)
const tableRef = ref()

// Filters
const searchQuery = ref('')
const projectFilter = ref('')
const appFilter = ref<string[]>([])
const availableApps = ref<AppInfo[]>([])
const prUserFilter = ref('')
const availablePRUsers = ref<ReviewerUser[]>([])
const allPRUsers = ref<ReviewerUser[]>([]) // Cache for client-side filtering
const prUsersLoading = ref(false)
const reviewerFilter = ref('')
const availableReviewers = ref<ReviewerUser[]>([])
const allReviewers = ref<ReviewerUser[]>([]) // Cache for client-side filtering
const reviewersLoading = ref(false)
const scoredFilter = ref('')
const severityFilter = ref('')
const statusFilter = ref('')
const dateFrom = ref('')
const dateTo = ref('')
const projects = ref<ProjectSummary[]>([])
const sortState = ref<{
  prop: 'created_date' | 'updated_date'
  order: 'ascending' | 'descending'
}>({
  prop: 'created_date',
  order: 'descending',
})

// Assign dialog
const assignDialogVisible = ref(false)
const selectedReview = ref<ReviewV2 | null>(null)
const assigning = ref(false)
const loadingReviewers = ref(false)
const assignForm = ref({
  reviewer: '',
})

// Bulk assignment state
const selectedReviews = ref<ReviewV2[]>([])
const showBulkAssignDialogVisible = ref(false)
const bulkAssigning = ref(false)
const bulkAssignForm = ref({
  reviewer: '',
})

// Load reviews
const loadReviews = async (showLoading = true) => {
  if (showLoading) {
    loading.value = true
  }
  try {
    const params: any = {
      page: currentPage.value,
      page_size: pageSize.value,
    }
    
    // Add filter parameters supported by task-assignment API
    if (projectFilter.value) params.project_key = projectFilter.value
    if (reviewerFilter.value) {
      // Send reviewer parameter including __unassigned__ special value
      params.reviewer = reviewerFilter.value
    }
    if (statusFilter.value) params.status = statusFilter.value
    
    // Add new filter parameters (now supported by backend)
    if (appFilter.value && appFilter.value.length > 0) {
      params.app_names = appFilter.value.join(',')
    }
    if (prUserFilter.value) {
      params.pull_request_user = prUserFilter.value
    }
    if (severityFilter.value) {
      params.severity = severityFilter.value
    }
    if (dateFrom.value) {
      params.date_from = dateFrom.value
    }
    if (dateTo.value) {
      params.date_to = dateTo.value
    }

    const response = await taskAssignmentApi.getReviews(params)
    allReviews.value = response.items
    total.value = response.total
    
    // Apply client-side filters for unsupported fields (search, scored, unassigned)
    applyFilters()

  } catch (error) {
    console.error('Failed to load reviews:', error)
    ElMessage.error('Failed to load reviews')
  } finally {
    loading.value = false
  }
}

const loadProjects = async () => {
  try {
    const response = await projectsApi.listProjects({
      page: 1,
      page_size: 100,
      is_active: true,
    })
    projects.value = response.items
  } catch (error) {
    console.error('Failed to load projects:', error)
    projects.value = []
    ElMessage.error('Failed to load projects')
  }
}

const handleResetFilters = () => {
  searchQuery.value = ''
  appFilter.value = []
  prUserFilter.value = ''
  reviewerFilter.value = ''
  scoredFilter.value = ''
  severityFilter.value = ''
  statusFilter.value = ''
  projectFilter.value = ''
  dateFrom.value = ''
  dateTo.value = ''
  loadReviews()
}

// Apply client-side filters (same pattern as ReviewListView)
const applyFilters = () => {
  let result = [...allReviews.value]
  
  // Apply search filter (text search not supported by backend)
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    result = result.filter(review => {
      return (
        review.pull_request_id?.toLowerCase().includes(query) ||
        review.project_key?.toLowerCase().includes(query) ||
        review.repository_slug?.toLowerCase().includes(query) ||
        review.reviewers?.some(r => r.reviewer?.toLowerCase().includes(query))
      )
    })
  }
  
  // Apply reviewer filter for unassigned (not supported by backend)
  if (reviewerFilter.value === '__unassigned__') {
    result = result.filter(review => 
      !review.reviewers || review.reviewers.length === 0 ||
      review.reviewers.every(r => !r.reviewer && !r.reviewer_info?.display_name)
    )
  }
  
  // Apply scored filter (not supported by backend)
  if (scoredFilter.value === 'yes') {
    result = result.filter(review => 
      review.metadata?.has_scores || review.completed_reviewers > 0
    )
  } else if (scoredFilter.value === 'no') {
    result = result.filter(review => 
      !review.metadata?.has_scores && review.completed_reviewers === 0
    )
  }

  result.sort((left, right) => compareReviews(left, right))

  reviews.value = result
  
  // Keep backend's total count for pagination.
  // Client-side filters reduce visible items but don't change total pages.
  // Only server-side filters (project_key, reviewer, status) affect the total count from backend.
}

const isDefaultPrioritySort = computed(
  () => sortState.value.prop === 'created_date' && sortState.value.order === 'descending'
)

const compareDateValues = (leftValue?: string | null, rightValue?: string | null) => {
  const leftTime = leftValue ? new Date(leftValue).getTime() : 0
  const rightTime = rightValue ? new Date(rightValue).getTime() : 0

  if (sortState.value.order === 'ascending') {
    return leftTime - rightTime
  }

  return rightTime - leftTime
}

const compareReviews = (left: ReviewV2, right: ReviewV2) => {
  const leftUnassigned = left.total_reviewers === 0
  const rightUnassigned = right.total_reviewers === 0

  if (isDefaultPrioritySort.value && leftUnassigned !== rightUnassigned) {
    return leftUnassigned ? -1 : 1
  }

  const primarySort = compareDateValues(left[sortState.value.prop], right[sortState.value.prop])
  if (primarySort !== 0) {
    return primarySort
  }

  if (leftUnassigned !== rightUnassigned) {
    return leftUnassigned ? -1 : 1
  }

  return compareDateValues(left.created_date, right.created_date)
}

const isActiveSort = (
  prop: 'created_date' | 'updated_date',
  order: 'ascending' | 'descending'
) => {
  return sortState.value.prop === prop && sortState.value.order === order
}

const toggleSort = (prop: 'created_date' | 'updated_date') => {
  if (sortState.value.prop === prop) {
    sortState.value.order = sortState.value.order === 'descending' ? 'ascending' : 'descending'
  } else {
    sortState.value = {
      prop,
      order: 'descending',
    }
  }
}

// Get reviewer tag type
const getReviewerTagType = (status: string) => {
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

// Get assignment status description
const getAssignmentStatusDescription = (status: string | undefined | null) => {
  if (!status) {
    return t('reviews.assignment_status_descriptions.pending', 'Pending')
  }
  return t(`reviews.assignment_status_descriptions.${status}`, status)
}

// Get progress percentage
const getProgressPercentage = (row: ReviewV2) => {
  if (row.total_reviewers === 0) return 0
  return Math.round((row.completed_reviewers / row.total_reviewers) * 100)
}

// Get status tag type
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

const getPullRequestAuthor = (review: ReviewV2 | null) => {
  if (!review) return ''
  return review.pull_request_user_info?.display_name || review.pull_request_user || 'Unknown'
}

const formatDate = (dateStr?: string | null) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString()
}

const formatReviewerOption = (user: ReviewerUser) => {
  return `${user.display_name} (${user.username})`
}

const loadAvailableReviewers = async (review: ReviewV2) => {
  loadingReviewers.value = true
  try {
    const response = await usersApi.getReviewers(500)
    const assignedReviewers = new Set(review.reviewers.map(item => item.reviewer))
    availableReviewers.value = response.items.filter(user => !assignedReviewers.has(user.username))
  } catch (error) {
    console.error('Failed to load reviewers:', error)
    availableReviewers.value = []
    ElMessage.error('Failed to load reviewers')
  } finally {
    loadingReviewers.value = false
  }
}

// View detail
const viewDetail = (id: number) => {
  router.push(`/task-assignment/${id}`)
}

// Handle assign reviewer
const handleAssignReviewer = async (review: ReviewV2) => {
  selectedReview.value = review
  assignForm.value.reviewer = ''
  assignDialogVisible.value = true
  await loadAvailableReviewers(review)
}

// Determine if a review is unassigned (no reviewers or all pending)
const isUnassigned = (review: ReviewV2): boolean => {
  // No reviewers at all
  if (!review.reviewers || review.reviewers.length === 0) {
    return true
  }
  
  // All reviewers are in 'pending' status
  const hasActiveReviewers = review.reviewers.some(
    r => r.assignment_status !== 'pending'
  )
  return !hasActiveReviewers
}

// Get row class name for styling unassigned tasks
const getRowClassName = ({ row }: { row: ReviewV2 }): string => {
  return isUnassigned(row) ? 'unassigned-row' : ''
}

// Get cell style - applies inline styles to override stripe pattern
const getCellStyle = ({ row }: { row: ReviewV2 }) => {
  if (!isUnassigned(row)) return { verticalAlign: 'middle' }
  
  // Use amber colors per project specification for "needs attention" status
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark'
  
  // Amber-100 for light theme, Amber-800 for dark theme (better contrast with light text)
  return {
    verticalAlign: 'middle',
    backgroundColor: isDark ? '#78350f' : '#fef3c7',
  }
}

// Submit assignment
const submitAssignment = async () => {
  if (!assignForm.value.reviewer || !selectedReview.value) return

  assigning.value = true
  try {
    await taskAssignmentApi.assignReviewer(selectedReview.value.id, {
      reviewer: assignForm.value.reviewer,
    })
    ElMessage.success('Reviewer assigned successfully')
    assignDialogVisible.value = false
    await loadReviews()
  } catch (error) {
    console.error('Failed to assign reviewer:', error)
    ElMessage.error('Failed to assign reviewer')
  } finally {
    assigning.value = false
  }
}

// Bulk assignment handlers
const handleSelectionChange = (selection: ReviewV2[]) => {
  selectedReviews.value = selection
}

const showBulkAssignDialog = async () => {
  if (selectedReviews.value.length === 0) {
    ElMessage.warning('Please select at least one review')
    return
  }
  bulkAssignForm.value.reviewer = ''
  showBulkAssignDialogVisible.value = true
  await loadAvailableReviewersForBulk()
}

const clearSelection = () => {
  // Clear table selection
  if (tableRef.value) {
    tableRef.value.clearSelection()
  }
  selectedReviews.value = []
}

const loadAvailableReviewersForBulk = async () => {
  try {
    const response = await usersApi.getReviewers(100)
    availableReviewers.value = response.items
  } catch (error) {
    console.error('Failed to load reviewers:', error)
    ElMessage.error('Failed to load reviewers')
  }
}

const executeBulkAssign = async () => {
  if (!bulkAssignForm.value.reviewer || selectedReviews.value.length === 0) {
    ElMessage.warning('Please select a reviewer')
    return
  }

  bulkAssigning.value = true
  let successCount = 0
  let failCount = 0

  try {
    for (const review of selectedReviews.value) {
      try {
        await taskAssignmentApi.assignReviewer(review.id, {
          reviewer: bulkAssignForm.value.reviewer,
        })
        successCount++
      } catch (error) {
        console.error(`Failed to assign reviewer to review ${review.id}:`, error)
        failCount++
      }
    }

    ElMessage.success(
      `Bulk assignment completed: ${successCount} succeeded, ${failCount} failed`
    )
    showBulkAssignDialogVisible.value = false
    clearSelection()
    await loadReviews()
  } catch (error) {
    console.error('Bulk assignment failed:', error)
    ElMessage.error('Bulk assignment failed')
  } finally {
    bulkAssigning.value = false
  }
}

// Fetch available apps for filter dropdown
const loadAvailableApps = async () => {
  try {
    const apps = await projectRegistryApi.listApps()
    availableApps.value = apps
  } catch (error) {
    console.error('Failed to load available apps:', error)
  }
}

// Load all users for PR user filter dropdown (active users only)
const loadPRUsers = async () => {
  try {
    prUsersLoading.value = true
    // Fetch all active users once - cache for client-side filtering
    const users = await usersApi.getAllBitbucketUsers(500)
    const activeUsers = users.filter(u => u.active !== false)
    allPRUsers.value = activeUsers
    availablePRUsers.value = activeUsers
  } catch (error) {
    console.error('Failed to load PR users:', error)
  } finally {
    prUsersLoading.value = false
  }
}

// Search PR users - PURE client-side filtering, NO API call
const searchPRUsers = (query: string) => {
  if (!query || query.trim() === '') {
    // If no query, show all cached users
    availablePRUsers.value = allPRUsers.value
    return
  }
  
  // Client-side filtering from cached data - NO API call
  const queryLower = query.toLowerCase()
  availablePRUsers.value = allPRUsers.value.filter(user => 
    user.username.toLowerCase().includes(queryLower) ||
    (user.display_name && user.display_name.toLowerCase().includes(queryLower))
  )
}

// Load all reviewers for filter dropdown using dedicated endpoint
const loadReviewers = async () => {
  try {
    reviewersLoading.value = true
    // Use dedicated /users/reviewers endpoint - returns active reviewers only
    const response = await usersApi.getReviewers(500)
    const reviewers = response.items || []
    allReviewers.value = reviewers
    availableReviewers.value = reviewers
  } catch (error) {
    console.error('Failed to load reviewers:', error)
  } finally {
    reviewersLoading.value = false
  }
}

// Search reviewers - PURE client-side filtering, NO API call
const searchReviewers = (query: string) => {
  if (!query || query.trim() === '') {
    // If no query, show all cached reviewers
    availableReviewers.value = allReviewers.value
    return
  }
  
  // Client-side filtering from cached data - NO API call
  const queryLower = query.toLowerCase()
  availableReviewers.value = allReviewers.value.filter(user => 
    user.username.toLowerCase().includes(queryLower) ||
    (user.display_name && user.display_name.toLowerCase().includes(queryLower))
  )
}

// Watch for filter changes and reload data
watch(
  [searchQuery, appFilter, projectFilter, prUserFilter, reviewerFilter, scoredFilter, severityFilter, statusFilter, dateFrom, dateTo],
  () => {
    // Debounce the reload to avoid multiple rapid requests
    clearTimeout(filterChangeTimeout)
    filterChangeTimeout = setTimeout(() => {
      loadReviews()
    }, 300)
  },
  { deep: true }
)

let filterChangeTimeout: ReturnType<typeof setTimeout>

onMounted(() => {
  window.addEventListener('resize', handleResize)
  loadProjects()
  loadReviews()
  loadAvailableApps()
  loadPRUsers()
  loadReviewers()

  // Connect to SSE stream for real-time review notifications
  // Backend handles authorization and filtering based on user roles
  connectSse(handleSSEReviewCreated, handleSSEError, handleSSEOpen)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  clearTimeout(filterChangeTimeout)
  disconnectSse()
})

// SSE event handlers
let sseRefreshTimeout: ReturnType<typeof setTimeout> | null = null

function handleSSEReviewCreated(_event: SSEReviewCreatedEvent) {
  console.log('[TaskAssignmentView] SSE event received')
  
  // Debounce SSE events - wait 1 second before refreshing
  // This prevents constant refreshes when multiple reviews arrive quickly
  if (sseRefreshTimeout) {
    clearTimeout(sseRefreshTimeout)
  }
  
  sseRefreshTimeout = setTimeout(() => {
    console.log('[TaskAssignmentView] Refreshing data after debounce')
    loadReviews(false) // Don't show loading indicator for SSE updates
    sseRefreshTimeout = null
  }, 1000) // 1 second debounce
}

function handleSSEError() {
  ElMessage({
    message: 'Real-time connection lost, retrying...',
    type: 'warning',
    duration: 3000,
  })
}

function handleSSEOpen() {
  ElMessage({
    message: 'Real-time updates restored',
    type: 'success',
    duration: 2000,
  })
}
</script>

<style scoped>
.task-assignment-container {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-title-group {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-title-group h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.filter-section {
  margin-bottom: 16px;
}

.task-assignment-table :deep(th.el-table__cell) {
  text-align: center;
}

.sort-header-group {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  min-height: 36px;
}

.sort-header-label {
  font-weight: 600;
}

.sort-header-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  min-height: 36px;
  padding: 6px 10px;
  border: none;
  background: transparent;
  color: inherit;
  font: inherit;
  cursor: pointer;
}

.sort-header-button:hover {
  color: var(--el-color-primary);
}

.sort-header-button.active {
  color: var(--el-color-primary);
}

.sort-header-icons {
  display: inline-flex;
  align-items: center;
  gap: 2px;
}

.sort-header-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  color: var(--el-text-color-secondary);
}

.sort-header-icon.active {
  color: var(--el-color-primary);
  opacity: 1;
}

.task-assignment-table :deep(.cell) {
  white-space: nowrap;
}

.pr-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
  overflow: hidden;
}

.pr-id {
  font-weight: 600;
  color: var(--el-color-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* PR Link Styles */
.pr-id .pr-link {
  text-decoration: none;
  color: inherit;
  transition: all 0.2s ease;
  display: inline-flex;
  align-items: center;
}

.pr-id .pr-link:hover {
  opacity: 0.7;
  text-decoration: underline;
}

.pr-project {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.pr-user {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  overflow: hidden;
}

.pr-user-name {
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.pr-user-username {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.branches {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: nowrap;
  overflow: hidden;
}

.arrow {
  color: var(--el-text-color-secondary);
  flex-shrink: 0;
}

.reviewers-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  max-height: 120px;
  overflow-y: auto;
  padding: 2px 0;
}

.reviewer-tag {
  cursor: help;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  white-space: nowrap;
}

.reviewer-tag:hover {
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

[data-theme='dark'] .reviewer-tag:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}

.status-icon {
  margin-left: 4px;
  font-weight: bold;
}

.progress-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.progress-text {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  text-align: center;
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

/* Unassigned task row highlighting - backup CSS in case inline styles don't apply */
/* This ensures coverage even if Element Plus re-renders cells */
:deep(.task-assignment-table.el-table--striped .el-table__body tr.unassigned-row td.el-table__cell) {
  background-color: #fef3c7 !important; /* Amber-100 for light theme */
}

[data-theme='dark'] :deep(.task-assignment-table.el-table--striped .el-table__body tr.unassigned-row td.el-table__cell) {
  background-color: #78350f !important; /* Amber-800 for dark theme - better contrast with light text */
}

/* Bulk Actions Toolbar */
.bulk-actions-toolbar {
  margin: 16px 0;
  padding: 12px 16px;
  background-color: var(--el-fill-color-light);
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
  transition: all 0.3s ease;
}

[data-theme='dark'] .bulk-actions-toolbar {
  background-color: var(--el-fill-color-dark);
  border-color: var(--el-border-color-light);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.bulk-actions-toolbar:hover {
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
}

[data-theme='dark'] .bulk-actions-toolbar:hover {
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3);
}

.selection-info {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 500;
  color: var(--el-text-color-primary);
}

.selection-info .el-icon {
  color: var(--el-color-success);
  font-size: 18px;
}

.bulk-actions {
  display: flex;
  gap: 8px;
}

/* Live Update Toggle Control */
.live-toggle-wrapper {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  cursor: default;
}

.live-dot {
  display: inline-block;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #c0c4cc;
  transition: background 0.3s;
  flex-shrink: 0;
}

.live-dot.active {
  background: #67c23a;
  animation: live-pulse 2s ease-in-out infinite;
}

.live-label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
}

.live-switch {
  --el-switch-on-color: #67c23a;
}

@keyframes live-pulse {
  0% {
    box-shadow: 0 0 0 0 rgba(103, 194, 58, 0.6);
  }
  50% {
    box-shadow: 0 0 0 5px rgba(103, 194, 58, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(103, 194, 58, 0);
  }
}
</style>
