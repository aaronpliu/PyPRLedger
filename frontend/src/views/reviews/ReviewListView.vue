<template>
  <div class="review-list-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <div class="header-title-group">
            <h2>{{ t('reviews.code_reviews') }}</h2>
            <el-tooltip placement="bottom" effect="light">
              <template #content>
                <div class="review-tooltip">
                  <p><strong>{{ t('reviews.visibility_title', 'You can see:') }}</strong></p>
                  <ul>
                    <li>{{ t('reviews.visibility_assigned', 'Reviews assigned to you') }}</li>
                    <li>{{ t('reviews.visibility_raised', 'PRs you raised (all reviewers)') }}</li>
                    <li v-if="isReviewAdmin">{{ t('reviews.visibility_admin', 'All reviews (Admin access)') }}</li>
                  </ul>
                </div>
              </template>
              <el-icon class="help-icon" :size="18"><QuestionFilled /></el-icon>
            </el-tooltip>
            <el-tag type="success" effect="dark" size="small" class="ai-badge">{{ t('reviews.ai_powered') }}</el-tag>
          </div>
          <div class="header-actions">
            <ExportMenu
              :data="reviews"
              :selected-ids="selectedReviews.map(r => r.id)"
              :fetch-all-data="fetchAllDataForExport"
            />
            <el-button @click="loadReviews">
              <el-icon><Refresh /></el-icon>
              {{ t('reviews.refresh') }}
            </el-button>
          </div>
        </div>
      </template>

      <!-- Filters with Archived Toggle -->
      <div class="filters-with-toggle">
        <FilterPopover
          v-model:search-query="searchQuery"
          v-model:app-filter="appFilter"
          v-model:pr-user-filter="prUserFilter"
          v-model:reviewer-filter="reviewerFilter"
          v-model:scored-filter="scoredFilter"
          v-model:severity-filter="severityFilter"
          v-model:status-filter="statusFilter"
          :app-options="availableApps"
          :pr-user-options="availablePRUsers"
          :reviewer-options="availableReviewers"
          :pr-users-loading="prUsersLoading"
          :reviewers-loading="reviewersLoading"
          @search-pr-users="searchPRUsers"
          @search-reviewers="searchReviewers"
          @reset="handleResetFilters"
        />
        
        <!-- Archived Toggle -->
        <el-tooltip
          :content="hideArchived ? t('reviews.archived_hint_hide', 'Showing only unscored reviews') : t('reviews.archived_hint_show', 'Showing all reviews including scored')"
          placement="bottom"
        >
          <el-switch
            v-model="hideArchived"
            inline-prompt
            :active-text="t('reviews.hide_archived', 'Hide Archived')"
            :inactive-text="t('reviews.show_all', 'Show All')"
            class="archived-toggle-switch"
          />
        </el-tooltip>
      </div>

      <!-- Bulk Actions Toolbar - Only for Review Admins -->
      <div v-if="selectedReviews.length > 0 && isReviewAdmin" class="bulk-actions-toolbar">
        <div class="selection-info">
          <el-icon><CircleCheck /></el-icon>
          <span>{{ t('reviews.bulk_actions.selected_count', { count: selectedReviews.length, plural: selectedReviews.length > 1 ? 's' : '' }) }}</span>
        </div>
        <div class="bulk-actions">
          <el-button size="small" type="danger" @click="showBulkDeleteDialog">
            <el-icon><Delete /></el-icon>
            {{ t('reviews.bulk_actions.delete_selected') }}
          </el-button>
          <el-button size="small" @click="clearSelection">
            <el-icon><Close /></el-icon>
            {{ t('reviews.bulk_actions.clear_selection') }}
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
        @expand-change="handleExpandChange"
        :expand-row-keys="expandedRows"
        row-key="id"
      >
        <!-- Expandable column for scores -->
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="expanded-scores-section">
              <!-- Loading State -->
              <div v-if="loadingScores[row.id]" class="scores-loading">
                <el-icon class="is-loading"><Loading /></el-icon>
                <span>{{ t('common.loading') }}</span>
              </div>
              
              <!-- No Scores -->
              <el-empty 
                v-else-if="!reviewScores[row.id] || reviewScores[row.id].length === 0"
                :description="t('reviews.detail.no_scores', 'No scores available')"
                :image-size="80"
              />
              
              <!-- Scores Table - Match ReviewDetailView structure -->
              <el-card v-else class="nested-scores-card">
                <template #header>
                  <div class="card-header">
                    <span class="card-title">{{ t('reviews.detail.scores', 'Scores') }} ({{ reviewScores[row.id].length }})</span>
                  </div>
                </template>
                
                <el-table :data="reviewScores[row.id]" stripe size="small">
                  <!-- Reviewer Column -->
                  <el-table-column prop="reviewer" :label="t('reviews.detail.reviewer')" width="200">
                    <template #default="{ row: scoreRow }">
                      <div class="reviewer-cell">
                        <span>{{ scoreRow.reviewer_info?.display_name || scoreRow.reviewer }}</span>
                        <el-tag 
                          v-if="scoreRow.reviewer === row.reviewer" 
                          size="small" 
                          type="primary" 
                          effect="plain"
                          class="primary-reviewer-badge"
                        >
                          {{ t('reviews.detail.primary_reviewer', 'Primary') }}
                        </el-tag>
                      </div>
                    </template>
                  </el-table-column>
                  
                  <!-- AI Review ID Column -->
                  <el-table-column :label="t('reviews.detail.ai_review_id')" min-width="200" align="center">
                    <template #default>
                      <div v-if="row.ai_review_id" class="ai-review-id-cell">
                        <el-tag size="small" type="info">
                          {{ row.ai_review_id }}
                        </el-tag>
                        <el-button
                          size="small"
                          text
                          @click="copyToClipboard(row.ai_review_id)"
                        >
                          <el-icon><CopyDocument /></el-icon>
                        </el-button>
                      </div>
                      <span v-else class="empty-value">{{ t('reviews.detail.na', 'N/A') }}</span>
                    </template>
                  </el-table-column>
                  
                  <!-- Score Column -->
                  <el-table-column prop="score" :label="t('reviews.detail.score')" width="120">
                    <template #default="{ row: scoreRow }">
                      <span :class="['score-value', getScoreColorClass(scoreRow.score)]">{{ scoreRow.score }}</span>
                      <span v-if="scoreRow.max_score" class="score-max"> / {{ scoreRow.max_score }}</span>
                    </template>
                  </el-table-column>
                  
                  <!-- Comments Column -->
                  <el-table-column prop="reviewer_comments" :label="t('reviews.detail.comments')" min-width="200" show-overflow-tooltip />
                  
                  <!-- Created Date Column -->
                  <el-table-column prop="created_date" :label="t('reviews.detail.created')" width="160">
                    <template #default="{ row: scoreRow }">
                      {{ formatDate(scoreRow.created_date || '') }}
                    </template>
                  </el-table-column>
                  
                  <!-- Updated Date Column -->
                  <el-table-column prop="updated_date" :label="t('reviews.detail.updated')" width="160">
                    <template #default="{ row: scoreRow }">
                      {{ scoreRow.updated_date ? formatDate(scoreRow.updated_date) : '-' }}
                    </template>
                  </el-table-column>
                </el-table>
              </el-card>
            </div>
          </template>
        </el-table-column>
        
        <!-- Selection column only for review admins -->
        <el-table-column v-if="isReviewAdmin" type="selection" width="55" fixed="left" />
        <el-table-column :label="t('reviews.seq_number')" width="80">
          <template #default="{ $index }">
            {{ (currentPage - 1) * pageSize + $index + 1 }}
          </template>
        </el-table-column>
        
        <!-- App Name -->
        <el-table-column :label="t('reviews.app_name')" width="150">
          <template #default="{ row }">
            <el-tag v-if="row.app_name && row.app_name !== 'Unknown'" type="primary" size="small">
              {{ row.app_name }}
            </el-tag>
            <span v-else class="text-secondary">{{ t('reviews.unknown') }}</span>
          </template>
        </el-table-column>
        
        <!-- PR Info Group -->
        <el-table-column :label="t('reviews.pr_info')" min-width="200">
          <template #default="{ row }">
            <div class="pr-info-cell">
              <div class="pr-id">
                <a 
                  v-if="getPrUrl(row)" 
                  :href="getPrUrl(row) || undefined" 
                  target="_blank" 
                  rel="noopener noreferrer"
                  class="pr-link"
                >
                  <el-tag size="small" type="info" effect="plain">
                    {{ row.pull_request_id }}
                    <el-icon style="margin-left: 4px;"><Link /></el-icon>
                  </el-tag>
                </a>
                <el-tag v-else size="small" type="info">{{ row.pull_request_id }}</el-tag>
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
        <el-table-column :label="t('scores.project_repo')" width="180">
          <template #default="{ row }">
            <div>
              <div><strong>{{ row.project_key }}</strong></div>
              <div class="text-secondary">{{ row.repository_slug }}</div>
            </div>
          </template>
        </el-table-column>
        
        <!-- PR User -->
        <el-table-column :label="t('reviews.pr_user')" width="150">
          <template #default="{ row }">
            <div>
              <div>{{ row.pull_request_user_info?.display_name || row.pull_request_user }}</div>
              <div class="text-secondary" style="font-size: 0.8rem;">{{ row.pull_request_user }}</div>
            </div>
          </template>
        </el-table-column>
        
        <!-- Reviewer -->
        <el-table-column :label="t('reviews.reviewer')" width="200">
          <template #default="{ row }">
            <div>
              <!-- Case 1: Multi-reviewer (PR owner view with all_reviewers) -->
              <div v-if="row.all_reviewers && row.all_reviewers.length > 0">
                <el-tooltip placement="top" effect="light">
                  <template #content>
                    <div class="reviewer-tooltip">
                      <div
                        v-for="rev in row.all_reviewers"
                        :key="rev.username"
                        class="tooltip-item"
                      >
                        {{ rev.display_name }} ({{ rev.username }})
                      </div>
                    </div>
                  </template>
                  <div class="reviewer-display">
                    <!-- Show primary reviewer (current user if in list, otherwise first) -->
                    <span>{{ getPrimaryReviewer(row) }}</span>
                    <!-- Show compact "+N more" if multiple reviewers -->
                    <span v-if="row.total_reviewers > 1" class="more-indicator">
                      +{{ row.total_reviewers - 1 }} {{ t('reviews.more', 'more') }}
                    </span>
                  </div>
                </el-tooltip>
                <div class="text-secondary" style="font-size: 0.8rem">
                  {{ row.source_filename ? '📄 File-level' : ' PR-level' }}
                </div>
              </div>

              <!-- Case 2: Single reviewer (normal assignment view) -->
              <div v-else-if="row.reviewer || row.reviewer_info?.display_name">
                {{ row.reviewer_info?.display_name || row.reviewer }}
                <div class="text-secondary" style="font-size: 0.8rem">
                  {{ row.source_filename ? ' File-level' : '📋 PR-level' }}
                </div>
              </div>

              <!-- Case 3: Truly unassigned (no reviewers at all) -->
              <el-tag v-else type="warning" effect="dark" size="small">
                ⚠️ {{ t('reviews.unassigned', 'Unassigned') }}
              </el-tag>
            </div>
          </template>
        </el-table-column>
        
        <!-- Status -->
        <el-table-column prop="pull_request_status" :label="t('reviews.pr_status')" width="120">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.pull_request_status)">
              {{ row.pull_request_status }}
            </el-tag>
          </template>
        </el-table-column>
        
        <!-- Scores Summary -->
        <el-table-column :label="t('reviews.scores')" width="120">
          <template #default="{ row }">
            <div v-if="row.score_summary && row.score_summary.total_scores > 0">
              <div class="score-summary">
                <span class="avg-score">{{ row.score_summary.max_score?.toFixed(1) || row.score_summary.average_score?.toFixed(1) }}</span>
                <span class="score-count">({{ row.score_summary.total_scores }})</span>
                <el-tag v-if="row.score_summary.max_score" size="small" type="warning" style="margin-left: 4px; font-size: 0.7rem;">{{ t('reviews.max_score_label') }}</el-tag>
              </div>
            </div>
            <span v-else class="text-secondary">{{ t('reviews.no_scores') }}</span>
          </template>
        </el-table-column>
        
        <!-- Created Date -->
        <el-table-column prop="created_date" :label="t('reviews.created')" width="160">
          <template #default="{ row }">
            {{ formatDate(row.created_date || '') }}
          </template>
        </el-table-column>
        
        <!-- Updated Date -->
        <el-table-column prop="updated_date" :label="t('common.update')" width="160">
          <template #default="{ row }">
            {{ formatDate(row.updated_date || '') }}
          </template>
        </el-table-column>
        
        <!-- Actions -->
        <el-table-column :label="t('reviews.actions')" width="120" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click.stop="viewReview(row)">
              {{ t('reviews.view') }}
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
      :title="t('common.confirm')"
      width="500px"
    >
      <el-alert
        type="warning"
        :closable="false"
        style="margin-bottom: 16px"
      >
        <template #title>
          {{ t('reviews.bulk_delete_confirm', { count: selectedReviews.length }) }}
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
import { ref, onMounted, onUnmounted, computed, watch, reactive } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Search, CircleCheck, Delete, Close, Document, Refresh, Cpu, Link, QuestionFilled, Loading } from '@element-plus/icons-vue'
import { reviewsApi } from '@/api/reviews'
import type { Review } from '@/api/reviews'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import dayjs from 'dayjs'
import { useI18n } from 'vue-i18n'
import FilterPopover from '@/components/common/FilterPopover.vue'
import ExportMenu from '@/components/common/ExportMenu.vue'
import { usePermission } from '@/composables/usePermission'
import { useReviewNavigationStore } from '@/stores/reviewNavigation'
import { useAuthStore } from '@/stores/auth'
import { projectRegistryApi } from '@/api/projectRegistry'
import type { AppInfo } from '@/api/projectRegistry'
import { usersApi, type ReviewerUser } from '@/api/users'
import { usePrUrl } from '@/composables/usePrUrl'

const { t } = useI18n()
const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const { hasPermission } = usePermission()
const reviewNavigationStore = useReviewNavigationStore()
const { getPrUrl } = usePrUrl()

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

// Check if user is review admin
const isReviewAdmin = computed(() => {
  const result = hasPermission('assign', 'reviews')
  console.log('[isReviewAdmin] Permission check:', {
    username: authStore.currentUser?.username,
    roles: authStore.currentUser?.roles,
    hasPermission: result
  })
  return result
})
const loading = ref(false)
const reviews = ref<Review[]>([])
const total = ref(0)
const currentPage = ref(1)
const searchQuery = ref('')
const statusFilter = ref('')
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
const hideArchived = ref(true) // Default to hiding scored/archived reviews
const tableRef = ref()

// Expandable scores section state
const expandedRows = ref<number[]>([])
const reviewScores = ref<Record<number, any[]>>({})
const loadingScores = ref<Record<number, boolean>>({})

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

const formatDate = (dateStr: string) => {
  return dayjs(dateStr).format('YYYY-MM-DD HH:mm')
}

// Get score color class for visual indication
const getScoreColorClass = (score: number) => {
  if (score >= 8) return 'score-high'
  if (score >= 6) return 'score-medium'
  if (score >= 4) return 'score-low'
  return 'score-critical'
}

// Copy text to clipboard
const copyToClipboard = (text: string) => {
  navigator.clipboard.writeText(text).then(() => {
    ElMessage.success('Copied to clipboard')
  }).catch(() => {
    ElMessage.error('Failed to copy to clipboard')
  })
}

// Handle row expand/collapse - load scores when expanded
const handleExpandChange = (row: Review, expandedRows: Review[]) => {
  // Check if this row is now expanded
  const isExpanded = expandedRows.some(r => r.id === row.id)
  if (isExpanded) {
    loadScoresForReview(row)
  }
}

// Load scores for a specific review when expanded
const loadScoresForReview = async (review: Review) => {
  console.log('[ReviewListView] Loading scores for review:', review.id, review.pull_request_id)
  
  // If already loaded, skip
  if (reviewScores.value[review.id]) {
    console.log('[ReviewListView] Scores already cached for review:', review.id)
    return
  }
  
  loadingScores.value[review.id] = true
  try {
    // Match ReviewDetailView behavior: get ALL scores for the PR (no reviewer filter)
    const params = {
      project_key: review.project_key,
      repository_slug: review.repository_slug,
      pull_request_id: review.pull_request_id,
      source_filename: review.source_filename || undefined,
    }
    console.log('[ReviewListView] API params:', params)
    
    const response = await reviewsApi.getReviewScores(params)
    console.log('[ReviewListView] API response:', response)
    
    reviewScores.value[review.id] = response.items || []
    console.log('[ReviewListView] Loaded', reviewScores.value[review.id].length, 'scores for review:', review.id)
  } catch (error) {
    console.error('[ReviewListView] Failed to load scores:', error)
    ElMessage.error('Failed to load scores')
    reviewScores.value[review.id] = []
  } finally {
    loadingScores.value[review.id] = false
  }
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

// Get primary reviewer for multi-reviewer display
// Prioritize current user if they're in the reviewer list
const getPrimaryReviewer = (row: any) => {
  if (!row.all_reviewers || row.all_reviewers.length === 0) {
    return row.reviewer_info?.display_name || row.reviewer || ''
  }
  
  // Get current user's username from auth store
  const authStore = useAuthStore()
  const currentUsername = authStore.currentUser?.username
  
  // Find current user in reviewer list
  const currentUserReviewer = row.all_reviewers.find(
    (rev: any) => rev.username === currentUsername
  )
  
  // If current user is a reviewer, show them first
  if (currentUserReviewer) {
    return currentUserReviewer.display_name
  }
  
  // Otherwise show first reviewer
  return row.all_reviewers[0].display_name
}

const loadReviews = async () => {
  loading.value = true
  try {
    const params: any = {
      page: currentPage.value,
      page_size: pageSize.value,
    }
    
    // Add ALL filter parameters for server-side filtering
    if (appFilter.value && appFilter.value.length > 0) params.app_names = appFilter.value.join(',')
    if (prUserFilter.value) params.pull_request_user = prUserFilter.value
    if (reviewerFilter.value) {
      // Send reviewer parameter including __unassigned__ special value
      params.reviewer = reviewerFilter.value
    }
    if (statusFilter.value) params.pull_request_status = statusFilter.value
    if (searchQuery.value) params.search_query = searchQuery.value
    
    // Convert scored filter to has_scores parameter
    if (scoredFilter.value === 'yes') {
      params.has_scores = true
    } else if (scoredFilter.value === 'no') {
      params.has_scores = false
    }
    // If scoredFilter is empty, don't send has_scores (shows all)
    
    // Convert hideArchived toggle to has_scores (hideArchived=true means show only unscored)
    if (hideArchived.value && !scoredFilter.value) {
      // Only apply if scoredFilter is not already set
      params.has_scores = false
    }
    
    if (severityFilter.value) params.severity = severityFilter.value

    console.log('Loading reviews with params:', params)
    const data = await reviewsApi.getReviews(params)
    console.log('Reviews loaded:', data.items.length, 'items, total:', data.total)
    
    // All filtering is now done server-side, just display the results
    allReviews.value = data.items
    filteredReviews.value = data.items
    reviews.value = data.items
    total.value = data.total
  } catch (error: any) {
    console.error('Failed to load reviews:', error)
    console.error('Error details:', error.response?.data || error.message)
    ElMessage.error(`Failed to load reviews: ${error.response?.data?.detail || error.message}`)
  } finally {
    loading.value = false
  }
}

// Store all reviews for client-side filtering
const allReviews = ref<Review[]>([])
const filteredReviews = ref<Review[]>([])

// Fetch all data for export (bypassing pagination)
const fetchAllDataForExport = async (): Promise<Review[]> => {
  try {
    const params: any = {
      page: 1,
      page_size: 10000, // Large page size to get all data
    }
    
    // Add ALL filter parameters for server-side filtering
    if (appFilter.value && appFilter.value.length > 0) params.app_names = appFilter.value.join(',')
    if (prUserFilter.value) params.pull_request_user = prUserFilter.value
    if (reviewerFilter.value) {
      // Send reviewer parameter including __unassigned__ special value
      params.reviewer = reviewerFilter.value
    }
    if (statusFilter.value) params.pull_request_status = statusFilter.value
    if (searchQuery.value) params.search_query = searchQuery.value
    
    // Convert scored filter to has_scores parameter
    if (scoredFilter.value === 'yes') {
      params.has_scores = true
    } else if (scoredFilter.value === 'no') {
      params.has_scores = false
    }
    
    // Convert hideArchived toggle to has_scores
    if (hideArchived.value && !scoredFilter.value) {
      params.has_scores = false
    }
    
    if (severityFilter.value) params.severity = severityFilter.value

    const data = await reviewsApi.getReviews(params)
    return data.items
  } catch (error) {
    console.error('Failed to fetch all data for export:', error)
    throw error
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
  hideArchived.value = true // Reset to default (hide scored reviews)
  currentPage.value = 1 // Reset to first page
  loadReviews() // Reload from backend with reset filters
}

const viewReview = (review: Review) => {
  // Calculate if there are more pages
  const totalPages = Math.ceil(total.value / pageSize.value)
  const hasMorePages = currentPage.value < totalPages

  // Build filter parameters to maintain consistency when navigating
  const filterParams: any = {}
  if (appFilter.value && appFilter.value.length > 0) filterParams.app_names = appFilter.value.join(',')
  if (prUserFilter.value) filterParams.pull_request_user = prUserFilter.value
  if (reviewerFilter.value) {
    // Include __unassigned__ in navigation filters
    filterParams.reviewer = reviewerFilter.value
  }
  if (statusFilter.value) filterParams.pull_request_status = statusFilter.value
  if (searchQuery.value) filterParams.search_query = searchQuery.value
  
  // Convert scored filter to has_scores parameter
  if (scoredFilter.value === 'yes') {
    filterParams.has_scores = true
  } else if (scoredFilter.value === 'no') {
    filterParams.has_scores = false
  }
  
  // Convert hideArchived toggle to has_scores
  if (hideArchived.value && !scoredFilter.value) {
    filterParams.has_scores = false
  }
  
  if (severityFilter.value) filterParams.severity = severityFilter.value

  reviewNavigationStore.setContext({
    items: reviews.value.map(item => ({
      id: item.id,
      projectKey: item.project_key,
      repositorySlug: item.repository_slug,
      pullRequestId: item.pull_request_id,
      reviewer: item.reviewer || '',
      sourceFilename: item.source_filename || '',
    })),
    currentPage: currentPage.value,
    pageSize: pageSize.value,
    totalItems: total.value,
    hasMorePages: hasMorePages,
    filters: filterParams, // Store filters for pagination consistency
  })

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

const closeProgressDialog = () => {
  showProgressDialog.value = false
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

// Load all PR users for filter dropdown (active users only)
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

// Watch for filter changes and reload data from backend
watch(
  [searchQuery, appFilter, prUserFilter, reviewerFilter, scoredFilter, severityFilter, statusFilter, hideArchived],
  () => {
    // Debounce the reload to avoid multiple rapid requests
    clearTimeout(filterChangeTimeout)
    filterChangeTimeout = setTimeout(() => {
      currentPage.value = 1 // Reset to first page when filters change
      loadReviews()
    }, 300)
  },
  { deep: true }
)

let filterChangeTimeout: ReturnType<typeof setTimeout>

// Load reviews when component mounts
onMounted(() => {
  window.addEventListener('resize', handleResize)
  
  // Check for query parameters from notification navigation
  const prId = route.query.pr_id as string | undefined
  const fromNotification = route.query.from_notification === 'true'
  
  // If coming from notification, disable hideArchived filter to show all reviews
  if (fromNotification) {
    hideArchived.value = false
  }
  
  // If PR ID is specified in query, set it as search query
  if (prId) {
    searchQuery.value = prId
  }
  
  loadReviews()
  loadAvailableApps()
  loadPRUsers()
  loadReviewers()
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  clearTimeout(filterChangeTimeout)
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

.header-title-group {
  display: flex;
  align-items: center;
  gap: 12px;
}

.card-header h2 {
  margin: 0;
  font-size: 20px;
}

.help-icon {
  color: #909399;
  cursor: help;
  transition: color 0.2s;
}

.help-icon:hover {
  color: #409eff;
}

[data-theme="dark"] .help-icon {
  color: #a0aec0;
}

[data-theme="dark"] .help-icon:hover {
  color: #63b3ed;
}

.review-tooltip {
  max-width: 300px;
  padding: 4px 0;
}

.review-tooltip p {
  margin: 0 0 8px 0;
  font-weight: 600;
}

.review-tooltip ul {
  margin: 0;
  padding-left: 20px;
}

.review-tooltip li {
  margin: 4px 0;
  font-size: 0.9em;
}

.ai-badge {
  margin-top: 2px; /* Optional: slight adjustment for vertical alignment */
}

.header-actions {
  display: flex;
  gap: 8px;
}

.filter-form {
  margin-bottom: 20px;
}

/* Filters with Toggle Layout */
.filters-with-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

/* Archived Toggle Switch Styling */
.archived-toggle-switch {
  --el-switch-on-color: #409eff;
  --el-switch-off-color: #dcdfe6;
}

[data-theme='dark'] .archived-toggle-switch {
  --el-switch-on-color: #409eff;
  --el-switch-off-color: #4c4d4f;
}

.pagination-container {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

.el-table {
  cursor: pointer;
}

/* Reviewer display styling */
.reviewer-display {
  display: flex;
  align-items: center;
  gap: 4px;
}

.more-indicator {
  color: #909399;
  font-size: 0.85em;
}

[data-theme="dark"] .more-indicator {
  color: #a0aec0;
}

.reviewer-tooltip {
  max-width: 300px;
}

.tooltip-item {
  padding: 4px 0;
  border-bottom: 1px solid #eee;
}

[data-theme="dark"] .tooltip-item {
  border-bottom-color: #334155;
}

.tooltip-item:last-child {
  border-bottom: none;
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
  color: var(--el-text-color-secondary);
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

/* PR Link Styles */
.pr-link {
  text-decoration: none;
  color: inherit;
  transition: all 0.2s ease;
}

.pr-link:hover {
  opacity: 0.8;
}

.pr-link :deep(.el-tag) {
  cursor: pointer;
  transition: all 0.2s ease;
}

.pr-link:hover :deep(.el-tag) {
  border-color: var(--el-color-primary);
  background-color: var(--el-color-primary-light-9);
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
  flex-wrap: wrap;
  line-height: 1.4;
}

.branch {
  color: var(--el-text-color-primary);
  font-weight: 500;
  word-break: break-all;
  overflow-wrap: break-word;
}

.arrow {
  color: var(--el-text-color-secondary);
  flex-shrink: 0;
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

/* Expanded Scores Section */
.expanded-scores-section {
  padding: 16px;
}

.scores-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 40px 0;
  color: var(--el-text-color-secondary);
}

.nested-scores-card {
  margin-top: 0;
}

.nested-scores-card :deep(.el-card__header) {
  padding: 12px 20px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-title {
  font-weight: 600;
  font-size: 1rem;
  color: var(--el-text-color-primary);
}

/* Reviewer Cell */
.reviewer-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.primary-reviewer-badge {
  font-size: 0.7rem;
  padding: 2px 6px;
  white-space: nowrap;
}

/* AI Review ID Cell */
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

/* Score Value Styles - Match ReviewDetailView */
.score-value {
  font-size: 1.2rem;
  font-weight: 700;
}

.score-high {
  color: #10b981;
}

.score-medium {
  color: #3b82f6;
}

.score-low {
  color: #f59e0b;
}

.score-critical {
  color: #ef4444;
}

.score-max {
  font-size: 0.9rem;
  color: var(--el-text-color-secondary);
}

/* Dark mode adjustments */
[data-theme='dark'] .score-high {
  color: #10b981;
}

[data-theme='dark'] .score-medium {
  color: #3b82f6;
}

[data-theme='dark'] .score-low {
  color: #f59e0b;
}

[data-theme='dark'] .score-critical {
  color: #ef4444;
}
</style>
