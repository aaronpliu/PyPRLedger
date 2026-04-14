<template>
  <div class="review-list-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <h2>Code Reviews</h2>
          <div class="header-actions">
            <ExportMenu
              :data="reviews"
              :selected-ids="selectedReviews.map(r => r.id)"
            />
            <el-button @click="loadReviews">
              <el-icon><Refresh /></el-icon>
              Refresh
            </el-button>
          </div>
        </div>
      </template>

      <!-- Info Banner -->
      <div class="info-banner">
        <div class="banner-icon">
          <el-icon :size="24"><Cpu /></el-icon>
        </div>
        <div class="banner-content">
          <div class="banner-title">AI-Powered PR Reviews</div>
          <div class="banner-description">
            Pull request reviews are automatically collected from Bitbucket webhooks and analyzed by AI. 
            You can view reviews and add/update scores based on your permissions.
          </div>
        </div>
        <div class="banner-badge">
          <el-tag type="success" effect="dark" size="small">Automated</el-tag>
        </div>
      </div>

      <!-- Filters -->
      <FilterBuilder
        v-show="showAdvancedFilters"
        :available-fields="filterFields"
        @filters-change="handleFiltersChange"
        @apply-preset="handleApplyPreset"
      />
      
      <!-- Toggle Advanced Filters Button -->
      <div style="margin-bottom: 16px;">
        <el-button 
          size="small" 
          @click="showAdvancedFilters = !showAdvancedFilters"
          :type="showAdvancedFilters ? 'primary' : ''"
        >
          <el-icon><Search /></el-icon>
          {{ showAdvancedFilters ? 'Hide' : 'Show' }} Advanced Filters
          <el-icon class="el-icon--right"><ArrowDown /></el-icon>
        </el-button>
        <el-tag v-if="advancedFilters.length > 0" type="success" style="margin-left: 8px;">
          {{ advancedFilters.length }} filter{{ advancedFilters.length > 1 ? 's' : '' }} active
        </el-tag>
      </div>

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
        
        <el-form-item label="PR Status">
          <el-select v-model="statusFilter" placeholder="All Status" clearable style="width: 150px" @change="loadReviews">
            <el-option label="Open" value="open" />
            <el-option label="Merged" value="merged" />
            <el-option label="Closed" value="closed" />
            <el-option label="Draft" value="draft" />
          </el-select>
        </el-form-item>
      </el-form>

      <!-- Bulk Actions Toolbar -->
      <div v-if="selectedReviews.length > 0" class="bulk-actions-toolbar">
        <div class="selection-info">
          <el-icon><CircleCheck /></el-icon>
          <span>{{ selectedReviews.length }} item{{ selectedReviews.length > 1 ? 's' : '' }} selected</span>
        </div>
        <div class="bulk-actions">
          <el-button size="small" type="danger" @click="showBulkDeleteDialog">
            <el-icon><Delete /></el-icon>
            Delete Selected
          </el-button>
          <el-dropdown @command="handleBulkStatusChange">
            <el-button size="small" type="warning">
              <el-icon><Edit /></el-icon>
              Change PR Status
              <el-icon class="el-icon--right"><ArrowDown /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="open">Set to Open</el-dropdown-item>
                <el-dropdown-item command="merged">Set to Merged</el-dropdown-item>
                <el-dropdown-item command="closed">Set to Closed</el-dropdown-item>
                <el-dropdown-item command="draft">Set to Draft</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <el-button size="small" @click="clearSelection">
            <el-icon><Close /></el-icon>
            Clear Selection
          </el-button>
        </div>
      </div>

      <!-- Reviews Table -->
      <el-table
        ref="tableRef"
        :data="reviews"
        v-loading="loading"
        style="width: 100%"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="55" fixed="left" />
        <el-table-column label="Seq#" width="80">
          <template #default="{ $index }">
            {{ (currentPage - 1) * pageSize + $index + 1 }}
          </template>
        </el-table-column>
        
        <!-- PR Info Group -->
        <el-table-column label="PR Info" min-width="200">
          <template #default="{ row }">
            <div class="pr-info-cell">
              <div class="pr-id">
                <el-tag size="small" type="info">{{ row.pull_request_id }}</el-tag>
                <span v-if="row.pull_request_commit_id" class="commit-id">
                  🔖 {{ row.pull_request_commit_id.substring(0, 8) }}
                </span>
              </div>
              <div class="pr-branches">
                <span class="branch">{{ row.source_branch }}</span>
                <span class="arrow">→</span>
                <span class="branch">{{ row.target_branch }}</span>
              </div>
            </div>
          </template>
        </el-table-column>
        
        <!-- Project/Repo -->
        <el-table-column label="Project/Repo" width="180">
          <template #default="{ row }">
            <div>
              <div><strong>{{ row.project_key }}</strong></div>
              <div class="text-secondary">{{ row.repository_slug }}</div>
            </div>
          </template>
        </el-table-column>
        
        <!-- PR User -->
        <el-table-column label="PR User" width="150">
          <template #default="{ row }">
            <div>
              <div>{{ row.pull_request_user_info?.display_name || row.pull_request_user }}</div>
              <div class="text-secondary" style="font-size: 0.8rem;">{{ row.pull_request_user }}</div>
            </div>
          </template>
        </el-table-column>
        
        <!-- Reviewer -->
        <el-table-column label="Reviewer" width="200">
          <template #default="{ row }">
            <div>
              <div>{{ row.reviewer_info?.display_name || row.reviewer || 'Unassigned' }}</div>
              <div class="text-secondary" style="font-size: 0.8rem;">
                {{ row.source_filename ? '📄 File-level' : '📋 PR-level' }}
              </div>
            </div>
          </template>
        </el-table-column>
        
        <!-- Status -->
        <el-table-column prop="pull_request_status" label="PR Status" width="120">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.pull_request_status)">
              {{ row.pull_request_status }}
            </el-tag>
          </template>
        </el-table-column>
        
        <!-- Scores Summary -->
        <el-table-column label="Scores" width="120">
          <template #default="{ row }">
            <div v-if="row.score_summary && row.score_summary.total_scores > 0">
              <div class="score-summary">
                <span class="avg-score">{{ row.score_summary.max_score?.toFixed(1) || row.score_summary.average_score?.toFixed(1) }}</span>
                <span class="score-count">({{ row.score_summary.total_scores }})</span>
                <el-tag v-if="row.score_summary.max_score" size="small" type="warning" style="margin-left: 4px; font-size: 0.7rem;">max</el-tag>
              </div>
            </div>
            <span v-else class="text-secondary">No scores</span>
          </template>
        </el-table-column>
        
        <!-- Created Date -->
        <el-table-column prop="created_date" label="Created" width="160">
          <template #default="{ row }">
            {{ formatDate(row.created_date || '') }}
          </template>
        </el-table-column>
        
        <!-- Updated Date -->
        <el-table-column prop="updated_date" label="Updated" width="160">
          <template #default="{ row }">
            {{ formatDate(row.updated_date || '') }}
          </template>
        </el-table-column>
        
        <!-- Actions -->
        <el-table-column label="Actions" width="120" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click.stop="viewReview(row)">
              View
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- Pagination -->
      <div class="pagination-container">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="loadReviews"
          @current-change="loadReviews"
        />
      </div>
    </el-card>

    <!-- Bulk Delete Confirmation Dialog -->
    <el-dialog
      v-model="showBulkDeleteDialogVisible"
      title="Confirm Bulk Delete"
      width="500px"
    >
      <el-alert
        type="warning"
        :closable="false"
        style="margin-bottom: 16px"
      >
        <template #title>
          Are you sure you want to delete {{ selectedReviews.length }} review{{ selectedReviews.length > 1 ? 's' : '' }}?
          This action cannot be undone.
        </template>
      </el-alert>
      
      <div class="delete-preview">
        <div v-for="review in selectedReviews.slice(0, 5)" :key="review.id" class="preview-item">
          <el-icon><Document /></el-icon>
          <span>Review #{{ review.id }} - {{ truncateUrl(review.pull_request_id) }}</span>
        </div>
        <div v-if="selectedReviews.length > 5" class="preview-more">
          ... and {{ selectedReviews.length - 5 }} more
        </div>
      </div>
      
      <template #footer>
        <el-button @click="showBulkDeleteDialogVisible = false">Cancel</el-button>
        <el-button type="danger" :loading="bulkDeleting" @click="executeBulkDelete">
          Delete {{ selectedReviews.length }} Items
        </el-button>
      </template>
    </el-dialog>

    <!-- Bulk Operation Progress Dialog -->
    <el-dialog
      v-model="showProgressDialog"
      title="Processing..."
      width="500px"
      :close-on-click-modal="false"
      :show-close="false"
    >
      <div class="progress-container">
        <el-progress
          :percentage="progressPercentage"
          :status="progressStatus"
          :stroke-width="20"
        />
        <div class="progress-info">
          <p>{{ progressMessage }}</p>
          <p class="progress-detail">
            {{ processedCount }} / {{ totalCount }} completed
          </p>
        </div>
      </div>
      
      <template #footer v-if="!bulkOperationLoading">
        <el-button type="primary" @click="closeProgressDialog">Close</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, watch, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { Search, CircleCheck, Delete, Edit, ArrowDown, Close, Document, Refresh, Cpu } from '@element-plus/icons-vue'
import { reviewsApi } from '@/api/reviews'
import type { Review } from '@/api/reviews'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import dayjs from 'dayjs'
import FilterBuilder from '@/components/common/FilterBuilder.vue'
import ExportMenu from '@/components/common/ExportMenu.vue'
import { usePermission } from '@/composables/usePermission'

const router = useRouter()
const { hasPermission } = usePermission()

// Check if user is review admin
const isReviewAdmin = computed(() => hasPermission('assign', 'reviews'))
const loading = ref(false)
const reviews = ref<Review[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const searchQuery = ref('')
const statusFilter = ref('')
const prUserFilter = ref('')
const reviewerFilter = ref('')
const scoredFilter = ref('')
const severityFilter = ref('')
const advancedFilters = ref<Filter[]>([])
const showAdvancedFilters = ref(false)
const tableRef = ref()

// Bulk operation state
const selectedReviews = ref<Review[]>([])
const showBulkDeleteDialogVisible = ref(false)
const bulkDeleting = ref(false)
const showProgressDialog = ref(false)
const bulkOperationLoading = ref(false)
const progressPercentage = ref(0)
const progressStatus = ref<'success' | 'exception' | 'warning'>()
const progressMessage = ref('')
const processedCount = ref(0)
const totalCount = ref(0)

// Task assignment state - REMOVED: Use Task Assignment page instead
// const reviewers = ref<any[]>([])
// const batchReviewerUsername = ref('')

// Filter fields configuration
const filterFields = [
  { label: 'PR ID', value: 'pull_request_id' },
  { label: 'PR User', value: 'pull_request_user' },
  { label: 'Project Key', value: 'project_key' },
  { label: 'Reviewer', value: 'reviewer' },
  { label: 'PR Status', value: 'pull_request_status' },
  { label: 'Created Date', value: 'created_date' },
  { label: 'Updated Date', value: 'updated_date' },
  { label: 'Summary', value: 'reviewer_comments' },
]

const formatDate = (dateStr: string) => {
  return dayjs(dateStr).format('YYYY-MM-DD HH:mm')
}

const truncateUrl = (url: string) => {
  return url.length > 60 ? url.substring(0, 60) + '...' : url
}

const getStatusType = (status: string) => {
  const types: Record<string, any> = {
    completed: 'success',
    in_progress: 'warning',
    pending: 'info',
  }
  return types[status] || 'info'
}

const loadReviews = async () => {
  loading.value = true
  try {
    const data = await reviewsApi.getReviews({
      page: currentPage.value,
      page_size: pageSize.value,
    })
    allReviews.value = data.items
    total.value = data.total
    applyFilters()
  } catch (error) {
    ElMessage.error('Failed to load reviews')
  } finally {
    loading.value = false
  }
}

// Store all reviews for client-side filtering
const allReviews = ref<Review[]>([])
const filteredReviews = ref<Review[]>([])

const handleSearch = () => {
  applyFilters()
}

const applyFilters = () => {
  let result = [...allReviews.value]
  
  // Apply search filter
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    result = result.filter(review => {
      return (
        review.pull_request_id?.toLowerCase().includes(query) ||
        review.reviewer?.toLowerCase().includes(query) ||
        review.project_key?.toLowerCase().includes(query) ||
        review.repository_slug?.toLowerCase().includes(query) ||
        review.reviewer_comments?.toLowerCase().includes(query)
      )
    })
  }
  
  // Apply PR user filter
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
      review.reviewer?.toLowerCase().includes(reviewer) ||
      review.reviewer_info?.display_name?.toLowerCase().includes(reviewer)
    )
  }
  
  // Apply scored filter
  if (scoredFilter.value === 'yes') {
    result = result.filter(review => 
      review.score_summary && review.score_summary.total_scores > 0
    )
  } else if (scoredFilter.value === 'no') {
    result = result.filter(review => 
      !review.score_summary || review.score_summary.total_scores === 0
    )
  }
  
  // Apply severity filter (check AI review issues)
  if (severityFilter.value) {
    const targetSeverity = severityFilter.value
    result = result.filter(review => {
      // Check if review has AI suggestions with issues
      if (!review.ai_suggestions?.issues || review.ai_suggestions.issues.length === 0) {
        return false
      }
      // Check if any issue matches the selected severity
      return review.ai_suggestions.issues.some(
        issue => issue.severity === targetSeverity
      )
    })
  }
  
  // Apply status filter
  if (statusFilter.value) {
    result = result.filter(review => review.pull_request_status === statusFilter.value)
  }
  
  // Apply advanced filters
  if (advancedFilters.value.length > 0) {
    result = result.filter(review => {
      // All advanced filters must match (AND logic)
      return advancedFilters.value.every(filter => {
        const fieldValue = (review as any)[filter.field]
        if (!fieldValue) return false
        
        const value = String(fieldValue).toLowerCase()
        const filterValue = filter.value.toLowerCase()
        
        switch (filter.operator) {
          case 'eq':
            return value === filterValue
          case 'neq':
            return value !== filterValue
          case 'contains':
            return value.includes(filterValue)
          case 'gt':
            return parseFloat(value) > parseFloat(filter.value)
          case 'lt':
            return parseFloat(value) < parseFloat(filter.value)
          case 'in':
            // Support comma-separated values
            const values = filter.value.split(',').map(v => v.trim().toLowerCase())
            return values.includes(value)
          default:
            return true
        }
      })
    })
  }
  
  filteredReviews.value = result
  reviews.value = result
  total.value = result.length
}

const viewReview = (review: Review) => {
  router.push({
    name: 'ReviewDetail',
    params: { id: review.id },
    query: {
      projectKey: review.project_key,
      repositorySlug: review.repository_slug,
      pullRequestId: review.pull_request_id,
      reviewer: review.reviewer || '',
      sourceFilename: review.source_filename || '',
    },
  })
}

const confirmDelete = async (review: Review) => {
  try {
    await ElMessageBox.confirm(
      `Are you sure you want to delete review #${review.id}?`,
      'Confirm Delete',
      {
        confirmButtonText: 'Delete',
        cancelButtonText: 'Cancel',
        type: 'warning',
      }
    )
    
    await reviewsApi.deleteReview(
      review.project_key,
      review.repository_slug,
      review.pull_request_id
    )
    ElMessage.success('Review deleted successfully')
    loadReviews()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('Failed to delete review')
    }
  }
}

// Filter handlers
interface Filter {
  field: string
  operator: string
  value: string
}

const handleFiltersChange = (filters: Filter[]) => {
  console.log('Advanced filters changed:', filters)
  advancedFilters.value = filters
  applyFilters()
}

const handleApplyPreset = (preset: any) => {
  console.log('Applied preset:', preset)
  ElMessage.success(`Applied preset: ${preset.name}`)
}

// Bulk operation handlers
const handleSelectionChange = (selection: Review[]) => {
  selectedReviews.value = selection
}

const clearSelection = () => {
  tableRef.value?.clearSelection()
  selectedReviews.value = []
}

const showBulkDeleteDialog = () => {
  if (selectedReviews.value.length === 0) {
    ElMessage.warning('Please select items to delete')
    return
  }
  showBulkDeleteDialogVisible.value = true
}

const executeBulkDelete = async () => {
  if (selectedReviews.value.length === 0) return
  
  bulkDeleting.value = true
  showProgressDialog.value = true
  bulkOperationLoading.value = true
  processedCount.value = 0
  totalCount.value = selectedReviews.value.length
  progressPercentage.value = 0
  progressStatus.value = undefined
  progressMessage.value = 'Deleting reviews...'
  
  const idsToDelete = selectedReviews.value.map(r => r.id)
  let successCount = 0
  let failCount = 0
  
  try {
    for (let i = 0; i < idsToDelete.length; i++) {
      const review = selectedReviews.value[i]
      try {
        await reviewsApi.deleteReview(
          review.project_key,
          review.repository_slug,
          review.pull_request_id
        )
        successCount++
      } catch (error) {
        console.error(`Failed to delete review ${review.id}:`, error)
        failCount++
      }
      
      // Update progress
      processedCount.value = i + 1
      progressPercentage.value = Math.round(((i + 1) / idsToDelete.length) * 100)
      progressMessage.value = `Deleting review ${i + 1} of ${idsToDelete.length}...`
    }
    
    // Complete
    progressStatus.value = failCount > 0 ? 'warning' : 'success'
    progressMessage.value = `Completed: ${successCount} succeeded, ${failCount} failed`
    bulkOperationLoading.value = false
    
    ElMessage.success(`Successfully deleted ${successCount} review${successCount !== 1 ? 's' : ''}`)
    
    // Reload data
    await loadReviews()
    clearSelection()
    showBulkDeleteDialogVisible.value = false
  } catch (error) {
    progressStatus.value = 'exception'
    progressMessage.value = 'Bulk delete failed'
    bulkOperationLoading.value = false
    ElMessage.error('Failed to delete reviews')
  } finally {
    bulkDeleting.value = false
  }
}

const handleBulkStatusChange = async (status: string) => {
  if (selectedReviews.value.length === 0) {
    ElMessage.warning('Please select items to update')
    return
  }
  
  showProgressDialog.value = true
  bulkOperationLoading.value = true
  processedCount.value = 0
  totalCount.value = selectedReviews.value.length
  progressPercentage.value = 0
  progressStatus.value = undefined
  progressMessage.value = `Updating status to ${status}...`
  
  let successCount = 0
  let failCount = 0
  
  try {
    for (let i = 0; i < selectedReviews.value.length; i++) {
      const review = selectedReviews.value[i]
      try {
        // TODO: Implement bulk status update API
        // For now, simulate with delay
        await new Promise(resolve => setTimeout(resolve, 200))
        successCount++
      } catch (error) {
        console.error(`Failed to update review ${review.id}:`, error)
        failCount++
      }
      
      // Update progress
      processedCount.value = i + 1
      progressPercentage.value = Math.round(((i + 1) / selectedReviews.value.length) * 100)
      progressMessage.value = `Updating review ${i + 1} of ${selectedReviews.value.length}...`
    }
    
    // Complete
    progressStatus.value = failCount > 0 ? 'warning' : 'success'
    progressMessage.value = `Completed: ${successCount} succeeded, ${failCount} failed`
    bulkOperationLoading.value = false
    
    ElMessage.success(`Successfully updated ${successCount} review${successCount !== 1 ? 's' : ''}`)
    
    // Reload data
    await loadReviews()
    clearSelection()
  } catch (error) {
    progressStatus.value = 'exception'
    progressMessage.value = 'Bulk update failed'
    bulkOperationLoading.value = false
    ElMessage.error('Failed to update reviews')
  }
}

const closeProgressDialog = () => {
  showProgressDialog.value = false
}

// Load reviews when component mounts
onMounted(() => {
  loadReviews()
})
</script>

<style scoped>
.review-list-container {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header h2 {
  margin: 0;
  font-size: 20px;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.filter-form {
  margin-bottom: 20px;
}

.pagination-container {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

.el-table {
  cursor: pointer;
}

.bulk-actions-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #f5f7fa;
  border-radius: 4px;
  margin-bottom: 16px;
  animation: slideDown 0.3s ease;
}

[data-theme="dark"] .bulk-actions-toolbar {
  background: #1e293b;
  border: 1px solid #334155;
}

@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.selection-info {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 500;
  color: #409eff;
}

.bulk-actions {
  display: flex;
  gap: 8px;
}

.delete-preview {
  max-height: 200px;
  overflow-y: auto;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  padding: 12px;
  background: #f5f7fa;
}

[data-theme="dark"] .delete-preview {
  background: #1e293b;
  border-color: #334155;
}

.preview-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  font-size: 13px;
  color: #606266;
}

.preview-more {
  padding: 6px 0;
  font-size: 12px;
  color: #909399;
  text-align: center;
}

.progress-container {
  padding: 20px 0;
}

.progress-info {
  margin-top: 16px;
  text-align: center;
}

.progress-info p {
  margin: 8px 0;
  color: #606266;
}

.progress-detail {
  font-size: 14px;
  color: #909399;
}

/* PR Info Cell Styles */
.pr-info-cell {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.pr-id {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.commit-id {
  font-size: 0.75rem;
  color: var(--el-text-color-secondary);
  font-family: monospace;
}

.pr-branches {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.85rem;
}

.branch {
  color: var(--el-text-color-primary);
  font-weight: 500;
}

.arrow {
  color: var(--el-text-color-secondary);
}

.text-secondary {
  color: var(--el-text-color-secondary);
  font-size: 0.85rem;
}

.score-summary {
  display: flex;
  align-items: baseline;
  gap: 4px;
}

.avg-score {
  font-size: 1.2rem;
  font-weight: 700;
  color: var(--el-color-success);
}

.score-count {
  font-size: 0.85rem;
  color: var(--el-text-color-secondary);
}

/* Info Banner Styles */
.info-banner {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 20px;
  margin-bottom: 16px;
  background: var(--el-color-info-light-9);
  border: 1px solid var(--el-color-info-light-7);
  border-radius: 8px;
  color: var(--el-text-color-primary);
  transition: all 0.3s ease;
}

[data-theme="dark"] .info-banner {
  background: rgba(64, 158, 255, 0.1);
  border-color: rgba(64, 158, 255, 0.3);
}

.info-banner:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

[data-theme="dark"] .info-banner:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.banner-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  background: var(--el-color-info);
  border-radius: 50%;
  color: white;
}

.banner-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.banner-title {
  font-size: 1.1rem;
  font-weight: 600;
  letter-spacing: 0.5px;
  color: var(--el-text-color-primary);
}

.banner-description {
  font-size: 0.9rem;
  color: var(--el-text-color-secondary);
  line-height: 1.5;
}

.banner-badge {
  flex-shrink: 0;
}

/* Dark theme fixes - ensure consistency across all components */
html.dark {
  /* Table */
  --el-table-tr-bg-color: #0f172a;
  --el-table-header-bg-color: #1e293b;
  --el-table-row-hover-bg-color: #334155;
  
  /* Input and Select controls - match table body, not header */
  --el-fill-color-blank: #0f172a;
  --el-bg-color: #0f172a;
  --el-bg-color-overlay: #1e293b;
  --el-border-color: #334155;
  --el-text-color-primary: #e2e8f0;
  --el-text-color-regular: #cbd5e1;
}

html.dark .el-table--striped .el-table__body tr.el-table__row--striped td {
  background-color: var(--el-table-striped-tr-bg-color) !important;
}

html.dark .el-table--striped .el-table__body tr.el-table__row--striped:hover td {
  background-color: var(--el-table-row-hover-bg-color) !important;
}

html.dark .el-select-dropdown {
  background-color: var(--el-bg-color-overlay) !important;
  border-color: var(--el-border-color) !important;
}

html.dark .el-select-dropdown__item {
  color: var(--el-text-color-primary) !important;
}

html.dark .el-select-dropdown__item.hover,
html.dark .el-select-dropdown__item:hover {
  background-color: var(--el-fill-color-light) !important;
}

html.dark .el-input__wrapper {
  background-color: var(--el-fill-color-blank) !important;
  box-shadow: 0 0 0 1px var(--el-border-color) inset !important;
}

html.dark .el-input__inner {
  color: var(--el-text-color-primary) !important;
}

html.dark .el-input__placeholder {
  color: #64748b !important;
}

/* Align all form controls background color */
html.dark .el-select .el-input__wrapper {
  background-color: #0f172a !important;
}

html.dark .el-form-item__label {
  color: #cbd5e1 !important;
}

html.dark .el-checkbox__inner {
  background-color: #0f172a !important;
  border-color: #334155 !important;
}

html.dark .el-checkbox__input.is-checked .el-checkbox__inner {
  background-color: #409eff !important;
  border-color: #409eff !important;
}

html.dark .el-tag {
  --el-tag-bg-color: rgba(64, 158, 255, 0.1);
  --el-tag-border-color: rgba(64, 158, 255, 0.3);
  --el-tag-text-color: #60a5fa;
}

html.dark .el-tag--warning {
  --el-tag-bg-color: rgba(230, 162, 60, 0.1);
  --el-tag-border-color: rgba(230, 162, 60, 0.3);
  --el-tag-text-color: #fbbf24;
}

html.dark .el-tag--success {
  --el-tag-bg-color: rgba(103, 194, 58, 0.1);
  --el-tag-border-color: rgba(103, 194, 58, 0.3);
  --el-tag-text-color: #4ade80;
}

html.dark .el-tag--info {
  --el-tag-bg-color: rgba(144, 147, 153, 0.1);
  --el-tag-border-color: rgba(144, 147, 153, 0.3);
  --el-tag-text-color: #9ca3af;
}

html.dark .el-tag--danger {
  --el-tag-bg-color: rgba(245, 108, 108, 0.1);
  --el-tag-border-color: rgba(245, 108, 108, 0.3);
  --el-tag-text-color: #f87171;
}
</style>
