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
            @input="handleSearch"
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
            @input="applyFilters"
          />
        </el-form-item>
        
        <el-form-item label="Reviewer">
          <el-input
            v-model="reviewerFilter"
            placeholder="Filter by reviewer"
            clearable
            style="width: 180px"
            @input="applyFilters"
          />
        </el-form-item>
        
        <el-form-item label="Scored">
          <el-select v-model="scoredFilter" placeholder="All" clearable style="width: 120px" @change="applyFilters">
            <el-option label="Scored" value="yes" />
            <el-option label="Not Scored" value="no" />
          </el-select>
        </el-form-item>
        
        <el-form-item label="Severity">
          <el-select v-model="severityFilter" placeholder="All" clearable style="width: 140px" @change="applyFilters">
            <el-option label="Critical" value="critical" />
            <el-option label="High" value="high" />
            <el-option label="Medium" value="medium" />
            <el-option label="Low" value="low" />
          </el-select>
        </el-form-item>
        
        <el-form-item label="Status">
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
      <el-table :data="reviews" v-loading="loading" stripe border>
        <el-table-column prop="id" label="ID" width="80" />
        
        <el-table-column label="PR Info" min-width="200">
          <template #default="{ row }">
            <div class="pr-info">
              <div class="pr-id">{{ row.pull_request_id }}</div>
              <div class="pr-project">{{ row.project_key }}/{{ row.repository_slug }}</div>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="Branches" min-width="180">
          <template #default="{ row }">
            <div class="branches">
              <el-tag size="small">{{ row.source_branch }}</el-tag>
              <span class="arrow">→</span>
              <el-tag size="small" type="success">{{ row.target_branch }}</el-tag>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="Reviewers" min-width="250">
          <template #default="{ row }">
            <div class="reviewers-list">
              <el-tag
                v-for="reviewer in row.reviewers"
                :key="reviewer.id"
                :type="getReviewerTagType(reviewer.assignment_status)"
                size="small"
                style="margin: 2px"
              >
                {{ reviewer.reviewer }}
                <span v-if="reviewer.assignment_status === 'completed'" class="status-icon">✓</span>
              </el-tag>
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

        <el-table-column label="Progress" width="120">
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

        <el-table-column label="Status" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.pull_request_status)">
              {{ row.pull_request_status }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="Actions" width="150" fixed="right">
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
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="loadReviews"
        @current-change="loadReviews"
        style="margin-top: 20px; justify-content: flex-end"
      />
    </el-card>

    <!-- Assign Reviewer Dialog -->
    <el-dialog v-model="assignDialogVisible" title="Assign Reviewer" width="500px">
      <el-form :model="assignForm" label-width="100px">
        <el-form-item label="PR ID">
          <el-input :value="selectedReview?.pull_request_id" disabled />
        </el-form-item>
        <el-form-item label="Reviewer" required>
          <el-select v-model="assignForm.reviewer" placeholder="Select reviewer" style="width: 100%">
            <el-option
              v-for="user in availableReviewers"
              :key="user.username"
              :label="`${user.display_name} (${user.username})`"
              :value="user.username"
            />
          </el-select>
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
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Refresh, Search } from '@element-plus/icons-vue'
import { taskAssignmentApi, type ReviewV2 } from '@/api/taskAssignment'

const router = useRouter()

// State
const loading = ref(false)
const reviews = ref<ReviewV2[]>([])
const allReviews = ref<ReviewV2[]>([]) // Store all reviews for client-side filtering
const total = ref(0)
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
const projects = ref<any[]>([])

// Assign dialog
const assignDialogVisible = ref(false)
const selectedReview = ref<ReviewV2 | null>(null)
const assigning = ref(false)
const assignForm = ref({
  reviewer: '',
})
const availableReviewers = ref<any[]>([])

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
    total.value = response.total
    applyFilters() // Apply client-side filters
  } catch (error) {
    console.error('Failed to load reviews:', error)
    ElMessage.error('Failed to load reviews')
  } finally {
    loading.value = false
  }
}

// Handle search input
const handleSearch = () => {
  applyFilters()
}

// Apply client-side filters
const applyFilters = () => {
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
      review.reviewers?.some(r => 
        r.reviewer?.toLowerCase().includes(prUser) ||
        r.reviewer_info?.display_name?.toLowerCase().includes(prUser)
      )
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
  
  reviews.value = result
  total.value = result.length
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

// View detail
const viewDetail = (id: number) => {
  router.push(`/task-assignment/${id}`)
}

// Handle assign reviewer
const handleAssignReviewer = (review: ReviewV2) => {
  selectedReview.value = review
  assignForm.value.reviewer = ''
  assignDialogVisible.value = true
  // TODO: Load available reviewers
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
    loadReviews()
  } catch (error) {
    console.error('Failed to assign reviewer:', error)
    ElMessage.error('Failed to assign reviewer')
  } finally {
    assigning.value = false
  }
}

onMounted(() => {
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

.pr-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.pr-id {
  font-weight: 600;
  color: var(--el-color-primary);
}

.pr-project {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.branches {
  display: flex;
  align-items: center;
  gap: 8px;
}

.arrow {
  color: var(--el-text-color-secondary);
}

.reviewers-list {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
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
</style>
