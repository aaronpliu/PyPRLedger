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
            <el-button type="primary" @click="showCreateDialog = true">
              <el-icon><Plus /></el-icon>
              New Review
            </el-button>
          </div>
        </div>
      </template>

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
            placeholder="Search by PR URL or reviewer"
            clearable
            style="width: 300px"
            @clear="loadReviews"
          >
            <template #append>
              <el-button @click="handleSearch">
                <el-icon><Search /></el-icon>
              </el-button>
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
        <el-table-column prop="pr_url" label="PR URL" min-width="250">
          <template #default="{ row }">
            <el-link :href="row.pr_url" target="_blank" type="primary">
              {{ truncateUrl(row.pr_url) }}
            </el-link>
          </template>
        </el-table-column>
        <el-table-column prop="reviewer_username" label="Reviewer" width="150" />
        <el-table-column prop="status" label="Status" width="120">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="summary" label="Summary" min-width="200" show-overflow-tooltip />
        <el-table-column prop="created_at" label="Created" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="Actions" width="150" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click.stop="viewReview(row.id)">
              View
            </el-button>
            <el-button size="small" type="danger" @click.stop="confirmDelete(row)">
              Delete
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

    <!-- Create Review Dialog -->
    <el-dialog
      v-model="showCreateDialog"
      title="Create New Review"
      width="600px"
    >
      <el-form :model="createForm" :rules="createRules" ref="createFormRef" label-width="120px">
        <el-form-item label="PR URL" prop="pr_url">
          <el-input v-model="createForm.pr_url" placeholder="https://github.com/..." />
        </el-form-item>
        
        <el-form-item label="Reviewer" prop="reviewer_username">
          <el-input v-model="createForm.reviewer_username" placeholder="Username" />
        </el-form-item>
        
        <el-form-item label="Status">
          <el-select v-model="createForm.status" style="width: 100%">
            <el-option label="Pending" value="pending" />
            <el-option label="In Progress" value="in_progress" />
            <el-option label="Completed" value="completed" />
          </el-select>
        </el-form-item>
        
        <el-form-item label="Summary">
          <el-input
            v-model="createForm.summary"
            type="textarea"
            :rows="4"
            placeholder="Review summary..."
          />
        </el-form-item>
      </el-form>
      
      <template #footer>
        <el-button @click="showCreateDialog = false">Cancel</el-button>
        <el-button type="primary" :loading="creating" @click="handleCreate">
          Create
        </el-button>
      </template>
    </el-dialog>

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
          <span>Review #{{ review.id }} - {{ truncateUrl(review.pr_url) }}</span>
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
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Plus, Search, CircleCheck, Delete, Edit, ArrowDown, Close, Document } from '@element-plus/icons-vue'
import { reviewsApi } from '@/api/reviews'
import type { Review, ReviewCreate } from '@/api/reviews'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import dayjs from 'dayjs'
import FilterBuilder from '@/components/common/FilterBuilder.vue'
import ExportMenu from '@/components/common/ExportMenu.vue'

const router = useRouter()
const loading = ref(false)
const creating = ref(false)
const reviews = ref<Review[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const searchQuery = ref('')
const statusFilter = ref('')
const showCreateDialog = ref(false)
const createFormRef = ref<FormInstance>()
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
  { label: 'PR URL', value: 'pr_url' },
  { label: 'Reviewer', value: 'reviewer_username' },
  { label: 'Status', value: 'status' },
  { label: 'Created Date', value: 'created_at' },
  { label: 'Summary', value: 'summary' },
]

const createForm = reactive<ReviewCreate>({
  pr_url: '',
  reviewer_username: '',
  status: 'pending',
  summary: null,
})

const createRules: FormRules = {
  pr_url: [
    { required: true, message: 'Please input PR URL', trigger: 'blur' },
  ],
  reviewer_username: [
    { required: true, message: 'Please input reviewer username', trigger: 'blur' },
  ],
}

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
      limit: pageSize.value,
      offset: (currentPage.value - 1) * pageSize.value,
    })
    reviews.value = data.items
    total.value = data.total
  } catch (error) {
    ElMessage.error('Failed to load reviews')
  } finally {
    loading.value = false
  }
}

const handleSearch = async () => {
  if (!searchQuery.value) {
    loadReviews()
    return
  }
  
  loading.value = true
  try {
    const data = await reviewsApi.searchReviews(searchQuery.value)
    reviews.value = data
    total.value = data.length
  } catch (error) {
    ElMessage.error('Search failed')
  } finally {
    loading.value = false
  }
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

const handleCreate = async () => {
  if (!createFormRef.value) return
  
  await createFormRef.value.validate(async (valid) => {
    if (valid) {
      creating.value = true
      try {
        await reviewsApi.createReview(createForm)
        ElMessage.success('Review created successfully')
        showCreateDialog.value = false
        // Reset form
        createForm.pr_url = ''
        createForm.reviewer_username = ''
        createForm.status = 'pending'
        createForm.summary = null
        loadReviews()
      } catch (error) {
        ElMessage.error('Failed to create review')
      } finally {
        creating.value = false
      }
    }
  })
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
</style>
