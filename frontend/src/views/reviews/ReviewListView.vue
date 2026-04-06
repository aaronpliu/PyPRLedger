<template>
  <div class="review-list-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <h2>Code Reviews</h2>
          <el-button type="primary" @click="showCreateDialog = true">
            <el-icon><Plus /></el-icon>
            New Review
          </el-button>
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

      <!-- Reviews Table -->
      <el-table
        :data="reviews"
        v-loading="loading"
        stripe
        style="width: 100%"
        @row-click="handleRowClick"
      >
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
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Plus, Search } from '@element-plus/icons-vue'
import { reviewsApi } from '@/api/reviews'
import type { Review, ReviewCreate } from '@/api/reviews'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import dayjs from 'dayjs'
import FilterBuilder from '@/components/common/FilterBuilder.vue'

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
</style>
