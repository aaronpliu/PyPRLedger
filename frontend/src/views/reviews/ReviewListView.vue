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
              size="small"
            />
            <el-button @click="loadReviews">
              <el-icon><Refresh /></el-icon>
              Refresh
            </el-button>
          </div>
        </div>
      </template>

      <!-- Info Banner -->
      <el-alert
        title="PR Reviews are submitted by AI system"
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 16px"
      >
        <template #default>
          Pull request reviews are automatically collected from Bitbucket webhooks and AI analysis. 
          You can view reviews and add/update scores based on your permissions.
        </template>
      </el-alert>

      <!-- Filters -->
      <FilterBuilder
        :available-fields="filterFields"
        @filters-change="handleFiltersChange"
        @apply-preset="handleApplyPreset"
      />

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
        
        <el-form-item label="Status">
          <el-select v-model="statusFilter" placeholder="All Status" clearable style="width: 150px" @change="loadReviews">
            <el-option label="Completed" value="completed" />
            <el-option label="In Progress" value="in_progress" />
            <el-option label="Pending" value="pending" />
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
              Change Status
              <el-icon class="el-icon--right"><ArrowDown /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="completed">Set to Completed</el-dropdown-item>
                <el-dropdown-item command="in_progress">Set to In Progress</el-dropdown-item>
                <el-dropdown-item command="pending">Set to Pending</el-dropdown-item>
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
        stripe
        style="width: 100%"
        @row-click="handleRowClick"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="55" fixed="left" />
        <el-table-column prop="id" label="ID" width="80" />
        
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
        
        <!-- Reviewer -->
        <el-table-column label="Reviewer" width="150">
          <template #default="{ row }">
            <div>
              <div>{{ row.reviewer_info?.display_name || row.reviewer }}</div>
              <div class="text-secondary" style="font-size: 0.8rem;">
                {{ row.source_filename ? '📄 File-level' : '📋 PR-level' }}
              </div>
            </div>
          </template>
        </el-table-column>
        
        <!-- Status -->
        <el-table-column prop="pull_request_status" label="Status" width="120">
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
                <span class="avg-score">{{ row.score_summary.average_score?.toFixed(1) }}</span>
                <span class="score-count">({{ row.score_summary.total_scores }})</span>
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
        
        <!-- Actions -->
        <el-table-column label="Actions" width="120" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click.stop="viewReview(row.id)">
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
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Search, CircleCheck, Delete, Edit, ArrowDown, Close, Document, Refresh } from '@element-plus/icons-vue'
import { reviewsApi } from '@/api/reviews'
import type { Review } from '@/api/reviews'
import { ElMessage, ElMessageBox } from 'element-plus'
import dayjs from 'dayjs'
import FilterBuilder from '@/components/common/FilterBuilder.vue'
import ExportMenu from '@/components/common/ExportMenu.vue'

const router = useRouter()
const loading = ref(false)
const reviews = ref<Review[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const searchQuery = ref('')
const statusFilter = ref('')
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

// Filter fields configuration
const filterFields = [
  { label: 'PR ID', value: 'pull_request_id' },
  { label: 'Project Key', value: 'project_key' },
  { label: 'Reviewer', value: 'reviewer' },
  { label: 'Status', value: 'pull_request_status' },
  { label: 'Created Date', value: 'created_date' },
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
  
  // Apply status filter
  if (statusFilter.value) {
    result = result.filter(review => review.pull_request_status === statusFilter.value)
  }
  
  filteredReviews.value = result
  reviews.value = result
  total.value = result.length
}

const viewReview = (id: number) => {
  router.push(`/reviews/${id}`)
}

const handleRowClick = (row: Review) => {
  viewReview(row.id)
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
    
    await reviewsApi.deleteReview(review.id)
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
  console.log('Filters changed:', filters)
  // TODO: Apply filters to API request
  // For now, just reload with current pagination
  loadReviews()
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
      const id = idsToDelete[i]
      try {
        await reviewsApi.deleteReview(id)
        successCount++
      } catch (error) {
        console.error(`Failed to delete review ${id}:`, error)
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
</style>
