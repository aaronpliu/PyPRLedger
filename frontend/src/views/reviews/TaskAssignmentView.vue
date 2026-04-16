<template>
  <div class="task-assignment-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>Task Assignment Management</span>
          <el-tag type="info">Review Admin Only</el-tag>
        </div>
      </template>

      <!-- Filters -->
      <el-form :inline="true" class="filter-form">
        <el-form-item label="Search">
          <el-input
            v-model="searchQuery"
            placeholder="Filter by PR ID, reviewer, or project"
            clearable
            style="width: 300px"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </el-form-item>
        
        <el-form-item label="Project">
          <el-select v-model="projectFilter" placeholder="All Projects" clearable style="width: 200px" @change="loadReviews">
            <el-option label="All Projects" value="" />
            <el-option v-for="proj in projects" :key="proj.project_key" :label="proj.project_name" :value="proj.project_key" />
          </el-select>
        </el-form-item>
        
        <el-form-item label="PR User">
          <el-input
            v-model="prUserFilter"
            placeholder="Filter by PR user"
            clearable
            style="width: 180px"
          />
        </el-form-item>
        
        <el-form-item label="Reviewer">
          <el-input
            v-model="reviewerFilter"
            placeholder="Filter by reviewer"
            clearable
            style="width: 180px"
          />
        </el-form-item>
        
        <el-form-item label="Scored">
          <el-select v-model="scoredFilter" placeholder="All" clearable style="width: 120px">
            <el-option label="Scored" value="yes" />
            <el-option label="Not Scored" value="no" />
          </el-select>
        </el-form-item>
        
        <el-form-item label="Severity">
          <el-select v-model="severityFilter" placeholder="All" clearable style="width: 140px">
            <el-option label="Critical" value="critical" />
            <el-option label="High" value="high" />
            <el-option label="Medium" value="medium" />
            <el-option label="Low" value="low" />
          </el-select>
        </el-form-item>
        
        <el-form-item label="PR Status">
          <el-select v-model="statusFilter" placeholder="All Status" clearable style="width: 150px" @change="loadReviews">
            <el-option label="Open" value="open" />
            <el-option label="Merged" value="merged" />
            <el-option label="Closed" value="closed" />
            <el-option label="Draft" value="draft" />
          </el-select>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="loadReviews">
            <el-icon><Refresh /></el-icon>
            Refresh
          </el-button>
        </el-form-item>
      </el-form>

      <!-- Reviews Table -->
      <el-table
        :data="displayedReviews"
        v-loading="loading"
        stripe
        border
        table-layout="auto"
        class="task-assignment-table"
        :header-cell-style="{ textAlign: 'center' }"
        :cell-style="{ verticalAlign: 'middle' }"
      >
        <el-table-column prop="id" label="ID" width="80" />
        
        <el-table-column label="PR Info" min-width="220">
          <template #default="{ row }">
            <div class="pr-info" :title="`${row.pull_request_id} | ${row.project_key}/${row.repository_slug}`">
              <div class="pr-id">{{ row.pull_request_id }}</div>
              <div class="pr-project">{{ row.project_key }}/{{ row.repository_slug }}</div>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="Branches" min-width="220">
          <template #default="{ row }">
            <div class="branches" :title="`${row.source_branch} -> ${row.target_branch}`">
              <el-tag size="small">{{ row.source_branch }}</el-tag>
              <span class="arrow">→</span>
              <el-tag size="small" type="success">{{ row.target_branch }}</el-tag>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="PR User" min-width="180">
          <template #default="{ row }">
            <div class="pr-user" :title="row.pull_request_user_info?.display_name || row.pull_request_user || '-'">
              <div class="pr-user-name">{{ row.pull_request_user_info?.display_name || row.pull_request_user || '-' }}</div>
              <div v-if="row.pull_request_user_info?.username && row.pull_request_user_info?.display_name !== row.pull_request_user_info?.username" class="pr-user-username">
                {{ row.pull_request_user_info.username }}
              </div>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="Reviewers" min-width="260">
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
                  style="margin: 2px; cursor: help"
                >
                  {{ reviewer.reviewer }}
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
                + Assign
              </el-button>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="Progress" min-width="120">
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

        <el-table-column label="PR Status" min-width="120">
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
              <span class="sort-header-label">Created</span>
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

        <el-table-column label="Actions" min-width="150" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" link @click="viewDetail(row.id)">
              View
            </el-button>
            <el-button size="small" type="success" link @click="handleAssignReviewer(row)">
              Assign
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- Pagination -->
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="displayedTotal"
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
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowDown, ArrowUp, Refresh, Search } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'
import { taskAssignmentApi, type ReviewV2 } from '@/api/taskAssignment'
import { usersApi, type ReviewerUser } from '@/api/users'
import { projectsApi, type ProjectSummary } from '@/api/projects'

const router = useRouter()
const { t } = useI18n()

// State
const loading = ref(false)
const allReviews = ref<ReviewV2[]>([]) // Store all reviews for client-side filtering
const currentPage = ref(1)
const pageSize = ref(20)

// Filters
const searchQuery = ref('')
const projectFilter = ref('')
const prUserFilter = ref('')
const reviewerFilter = ref('')
const scoredFilter = ref('')
const severityFilter = ref('')
const statusFilter = ref('')
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
const availableReviewers = ref<ReviewerUser[]>([])

// Load reviews
const loadReviews = async () => {
  loading.value = true
  try {
    const params: any = {
      page: currentPage.value,
      page_size: pageSize.value,
    }
    if (projectFilter.value) params.project_key = projectFilter.value
    if (statusFilter.value) params.status = statusFilter.value

    const response = await taskAssignmentApi.getReviews(params)
    allReviews.value = response.items // Store all reviews
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

const displayedReviews = computed(() => {
  let result = [...allReviews.value]
  
  // Apply search filter
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
  
  // Apply PR user filter (check from reviewers or metadata)
  if (prUserFilter.value) {
    const prUser = prUserFilter.value.toLowerCase()
    result = result.filter(review => 
      review.pull_request_user?.toLowerCase().includes(prUser) ||
      review.pull_request_user_info?.display_name?.toLowerCase().includes(prUser)
    )
  }
  
  // Apply reviewer filter
  if (reviewerFilter.value) {
    const reviewer = reviewerFilter.value.toLowerCase()
    result = result.filter(review => 
      review.reviewers?.some(r => 
        r.reviewer?.toLowerCase().includes(reviewer) ||
        r.reviewer_info?.display_name?.toLowerCase().includes(reviewer)
      )
    )
  }
  
  // Apply scored filter (check if has scores in metadata)
  if (scoredFilter.value === 'yes') {
    result = result.filter(review => 
      review.metadata?.has_scores || review.completed_reviewers > 0
    )
  } else if (scoredFilter.value === 'no') {
    result = result.filter(review => 
      !review.metadata?.has_scores && review.completed_reviewers === 0
    )
  }
  
  // Apply severity filter (check AI suggestions)
  if (severityFilter.value) {
    const targetSeverity = severityFilter.value
    result = result.filter(review => {
      if (!review.ai_suggestions?.issues || review.ai_suggestions.issues.length === 0) {
        return false
      }
      return review.ai_suggestions.issues.some(
        (issue: any) => issue.severity === targetSeverity
      )
    })
  }

  result.sort((left, right) => compareReviews(left, right))

  return result
})

const displayedTotal = computed(() => displayedReviews.value.length)

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
const getAssignmentStatusDescription = (status: string) => {
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
    const response = await usersApi.getReviewers()
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

onMounted(() => {
  loadProjects()
  loadReviews()
})
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

.filter-form {
  margin-bottom: 20px;
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
  flex-wrap: nowrap;
  gap: 4px;
  align-items: center;
  overflow-x: auto;
  overflow-y: hidden;
  padding-bottom: 2px;
  scrollbar-width: thin;
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
</style>
