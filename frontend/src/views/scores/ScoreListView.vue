<template>
  <div class="score-list-container">
    <el-card>
      <template #header>
        <h2>{{ t('scores.page_title_list') }}</h2>
      </template>

      <!-- Filters -->
      <el-form :inline="true" class="filter-form">
        <el-form-item label="App Name">
          <el-select
            v-model="appNameFilter"
            clearable
            filterable
            placeholder="All Applications"
            style="width: 200px"
            @change="loadScores"
          >
            <el-option
              v-for="app in appOptions"
              :key="app.app_name"
              :label="app.app_name"
              :value="app.app_name"
            />
          </el-select>
        </el-form-item>
        
        <el-form-item :label="t('scores.filters.project_filter')">
          <el-select 
            v-model="projectFilter" 
            :placeholder="t('scores.filters.all_projects')" 
            clearable 
            style="width: 200px" 
            @change="loadScores"
            :loading="projectsLoading"
          >
            <el-option
              v-for="project in projects"
              :key="project.project_key"
              :label="project.project_name"
              :value="project.project_key"
            />
          </el-select>
        </el-form-item>
        
        <el-form-item :label="t('scores.filters.score_range')">
          <el-select 
            v-model="levelFilter" 
            :placeholder="t('scores.filters.all_levels')" 
            clearable 
            style="width: 200px" 
            @change="loadScores"
          >
            <el-option :label="t('scores.filters.pr_level')" value="pr" />
            <el-option :label="t('scores.filters.file_level')" value="file" />
          </el-select>
        </el-form-item>
      </el-form>

      <!-- Scores Table -->
      <el-table :data="scores" v-loading="loading" stripe style="width: 100%" row-key="id">
        <template #empty>
          <div class="empty-data">
            <el-empty description="No scores found">
              <el-button type="primary" @click="loadScores">Refresh</el-button>
            </el-empty>
          </div>
        </template>
        <el-table-column :label="t('scores.seq_number')" width="70">
          <template #default="{ $index }">
            <span class="seq-number">{{ (currentPage - 1) * pageSize + $index + 1 }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="project_key" :label="t('scores.project_repo')" width="120">
          <template #default="{ row }">
            <span class="project-key">{{ row.project_name || row.project_key }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="pull_request_user" :label="t('scores.pr_user')" width="180">
          <template #default="{ row }">
            <div class="user-cell">
              <el-tooltip 
                :content="row.pull_request_user_info?.display_name || row.pull_request_user" 
                placement="top"
                :disabled="!row.pull_request_user_info?.display_name"
              >
                <el-avatar 
                  :size="32" 
                  v-if="row.pull_request_user_info?.avatar_url"
                  class="user-avatar"
                >
                  <img :src="row.pull_request_user_info.avatar_url" alt="" />
                </el-avatar>
                <el-avatar 
                  :size="32" 
                  v-else
                  class="user-avatar user-avatar-fallback"
                  :style="{ background: getAvatarColor(row.pull_request_user) }"
                >
                  {{ getInitials(row.pull_request_user_info?.display_name || row.pull_request_user) }}
                </el-avatar>
              </el-tooltip>
              <div class="user-info">
                <span class="user-display-name">{{ row.pull_request_user_info?.display_name || row.pull_request_user }}</span>
                <span class="user-username" v-if="row.pull_request_user_info?.display_name">@{{ row.pull_request_user }}</span>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="reviewer" :label="t('scores.reviewer')" width="180">
          <template #default="{ row }">
            <div class="reviewer-cell">
              <el-tooltip 
                :content="row.reviewer_info?.display_name || row.reviewer" 
                placement="top"
                :disabled="!row.reviewer_info?.display_name"
              >
                <el-avatar 
                  :size="36" 
                  v-if="row.reviewer_info?.avatar_url"
                  class="reviewer-avatar"
                >
                  <img :src="row.reviewer_info.avatar_url" alt="" />
                </el-avatar>
                <el-avatar 
                  :size="36" 
                  v-else
                  class="reviewer-avatar reviewer-avatar-fallback"
                  :style="{ background: getAvatarColor(row.reviewer) }"
                >
                  {{ getInitials(row.reviewer_info?.display_name || row.reviewer) }}
                </el-avatar>
              </el-tooltip>
              <div class="reviewer-info">
                <span class="reviewer-display-name">{{ row.reviewer_info?.display_name || row.reviewer }}</span>
                <span class="reviewer-username" v-if="row.reviewer_info?.display_name">@{{ row.reviewer }}</span>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="pull_request_id" :label="t('reviews.detail.pull_request_id', 'PR ID')" width="110">
          <template #default="{ row }">
            <el-link 
              v-if="getPRUrl(row)"
              :href="getPRUrl(row)!"
              type="primary"
              target="_blank"
              rel="noopener noreferrer"
              class="pr-link"
            >
              {{ truncateId(row.pull_request_id) }}
            </el-link>
            <el-tag v-else size="small">{{ truncateId(row.pull_request_id) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="branch_info" :label="t('scores.filters.branch', 'Branch')" width="180">
          <template #default="{ row }">
            <div class="branch-info" :class="{ 'branch-info-multiline': isLongBranch(row.source_branch, row.target_branch) }">
              <div class="branch-line">
                <span class="source-branch" :title="row.source_branch">{{ truncateBranch(row.source_branch) }}</span>
                <span class="branch-arrow">→</span>
                <span class="target-branch" :title="row.target_branch">{{ truncateBranch(row.target_branch) }}</span>
              </div>
              <div v-if="isLongBranch(row.source_branch, row.target_branch)" class="branch-line-full">
                <span class="source-branch-full" :title="row.source_branch">{{ row.source_branch }}</span>
                <span class="branch-arrow">→</span>
                <span class="target-branch-full" :title="row.target_branch">{{ row.target_branch }}</span>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="source_filename" :label="t('scores.scope', 'Scope')" width="130">
          <template #default="{ row }">
            <el-tag 
              :type="row.source_filename ? 'info' : 'success'" 
              size="small"
            >
              {{ row.source_filename ? t('scores.filters.file_level') : t('scores.filters.pr_level') }}
            </el-tag>
            <div v-if="row.source_filename" class="filename-text" :title="row.source_filename">
              {{ truncateFilename(row.source_filename) }}
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="score" :label="t('scores.score')" width="160">
          <template #default="{ row }">
            <div class="score-cell">
              <el-progress
                :percentage="(row.score / 10) * 100"
                :color="getScoreColor(row.score)"
                :format="() => `${row.score.toFixed(1)}/10.0`"
                :stroke-width="12"
              />
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="reviewer_comments" :label="t('scores.comments')" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.reviewer_comments" class="comments-text">
              {{ row.reviewer_comments }}
            </span>
            <span v-else class="no-comments">{{ t('scores.no_comments') }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_date" :label="t('scores.created')" width="160">
          <template #default="{ row }">
            {{ formatDate(row.created_date) }}
          </template>
        </el-table-column>
        <el-table-column prop="updated_date" :label="t('scores.updated')" width="160">
          <template #default="{ row }">
            {{ formatDate(row.updated_date || row.created_date) }}
          </template>
        </el-table-column>
        <el-table-column :label="t('scores.actions')" width="90" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="danger" @click="confirmDelete(row)" :disabled="!canDeleteScore(row)">
              {{ t('scores.delete') }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- Pagination -->
      <div class="pagination-container" v-if="totalScores > 0">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="totalScores"
          layout="total, sizes, prev, pager, next, jumper"
          @current-change="handlePageChange"
          @size-change="handlePageSizeChange"
        />
      </div>

      <!-- Statistics -->
      <el-divider />
      <el-row :gutter="20" class="stats-row">
        <el-col :span="8">
          <el-statistic :title="t('scores.statistics.average_score')" :value="stats.average_score" :precision="1" class="theme-aware-statistic" />
        </el-col>
        <el-col :span="8">
          <el-statistic :title="t('scores.statistics.total_reviews')" :value="stats.total_reviews" class="theme-aware-statistic" />
        </el-col>
        <el-col :span="8">
          <el-statistic :title="t('scores.statistics.total_scores')" :value="totalScores" class="theme-aware-statistic" />
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { scoresApi } from '@/api/scores'
import { reviewsApi } from '@/api/reviews'
import { projectsApi } from '@/api/projects'
import { projectRegistryApi } from '@/api/projectRegistry'
import type { Score, ScoreStats } from '@/api/scores'
import type { ProjectSummary } from '@/api/projects'
import type { AppInfo } from '@/api/projectRegistry'
import { ElMessage, ElMessageBox } from 'element-plus'
import dayjs from 'dayjs'
import { useAuthStore } from '@/stores/auth'
import { GitProvider } from '@/constants/gitProvider'

const { t } = useI18n()

const router = useRouter()
const authStore = useAuthStore()
const loading = ref(false)
const projectsLoading = ref(false)
const scores = ref<Score[]>([])
const projects = ref<ProjectSummary[]>([])
const projectFilter = ref('')
const appNameFilter = ref('')
const appOptions = ref<AppInfo[]>([])
const levelFilter = ref('') // 'pr' or 'file'
const stats = ref<ScoreStats>({
  average_score: 0,
  total_reviews: 0,
  score_distribution: {},
})

// Pagination state
const currentPage = ref(1)
const pageSize = ref(20)
const totalScores = ref(0)

const formatDate = (dateStr: string) => {
  return dayjs(dateStr).format('YYYY-MM-DD HH:mm')
}

const getInitials = (name: string) => {
  if (!name) return '??'
  // Get initials from display name (could be full name or username)
  const parts = name.trim().split(/\s+/)
  if (parts.length >= 2) {
    // Full name: take first letter of first and last name
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
  }
  // Single word: take first 2 characters
  return name.substring(0, 2).toUpperCase()
}

const getAvatarColor = (username: string) => {
  // Generate a consistent gradient color based on username
  const colors = [
    'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
    'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
    'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)',
    'linear-gradient(135deg, #fa709a 0%, #fee140 100%)',
    'linear-gradient(135deg, #30cfd0 0%, #330867 100%)',
    'linear-gradient(135deg, #a8edea 0%, #fed6e3 100%)',
    'linear-gradient(135deg, #ff9a9e 0%, #fecfef 100%)',
  ]
  
  // Use username to deterministically select a color
  let hash = 0
  for (let i = 0; i < username.length; i++) {
    hash = ((hash << 5) - hash) + username.charCodeAt(i)
    hash = hash & hash // Convert to 32-bit integer
  }
  
  return colors[Math.abs(hash) % colors.length]
}

const truncateId = (id: string | undefined | null) => {
  if (!id) return 'N/A'
  return id.length > 12 ? `${id.substring(0, 12)}...` : id
}

const truncateFilename = (filename: string | undefined | null) => {
  if (!filename) return ''
  const parts = filename.split('/')
  if (parts.length > 2) {
    return `.../${parts.slice(-2).join('/')}`
  }
  return filename.length > 30 ? `...${filename.slice(-30)}` : filename
}

const truncateBranch = (branch: string | undefined | null) => {
  if (!branch) return 'N/A'
  // For long branch names, show first and last parts
  const maxLength = 15
  if (branch.length <= maxLength) return branch
  
  // If it contains slashes (path-like), show first/last segments
  const parts = branch.split('/')
  if (parts.length > 1) {
    const first = parts[0]
    const last = parts[parts.length - 1]
    if ((first + '/' + last).length <= maxLength) {
      return `${first}/.../${last}`
    }
  }
  
  // Otherwise just truncate with ellipsis
  return `${branch.substring(0, maxLength - 3)}...`
}

const isLongBranch = (sourceBranch: string | undefined | null, targetBranch: string | undefined | null) => {
  // Consider branches "long" if combined display would exceed column width
  const sourceLen = sourceBranch?.length || 0
  const targetLen = targetBranch?.length || 0
  const totalLen = sourceLen + targetLen + 3 // +3 for arrow and spaces
  
  // If total length exceeds threshold, use multiline display
  return totalLen > 35 || (sourceLen > 20 || targetLen > 20)
}

const getScoreColor = (score: number) => {
  if (score >= 8.0) return '#67c23a'  // Green - Excellent
  if (score >= 6.0) return '#409eff'  // Blue - Good
  if (score >= 4.0) return '#e6a23c'  // Orange - Average
  return '#f56c6c'  // Red - Poor
}

const getPRUrl = (score: Score): string | null => {
  // Need project_url, repository_slug, and pull_request_id to construct URL
  if (!score.project_url || !score.repository_slug || !score.pull_request_id) {
    return null
  }
  
  const baseUrl = score.project_url.replace(/\/$/, '') // Remove trailing slash
  const gitProvider = score.git_provider

  if (gitProvider === GitProvider.GITHUB_ENTERPRISE) {
    // GitHub Enterprise: <project_url>/<repo>/pull/<id>
    return `${baseUrl}/${score.repository_slug}/pull/${score.pull_request_id}`
  }

  // Bitbucket Server (default): <project_url>/repos/<slug>/pull-requests/<id>/diff
  return `${baseUrl}/repos/${score.repository_slug}/pull-requests/${score.pull_request_id}/diff`
}

const canDeleteScore = (score: Score): boolean => {
  const currentUsername = authStore.currentUser?.username
  // Users can only delete their own scores
  return currentUsername === score.reviewer
}

const viewReview = (pullRequestId: string) => {
  // Navigate to review detail page
  router.push(`/reviews`)
}

const loadProjects = async () => {
  projectsLoading.value = true
  try {
    const response = await projectsApi.listProjects({ page_size: 100 })
    projects.value = response.items || []
  } catch (error) {
    console.error('Failed to load projects:', error)
    ElMessage.error('Failed to load projects')
  } finally {
    projectsLoading.value = false
  }
}

const loadAppOptions = async () => {
  try {
    appOptions.value = await projectRegistryApi.listApps()
  } catch (error) {
    console.error('Failed to load app options:', error)
  }
}

const loadScores = async () => {
  loading.value = true
  try {
    // Load stats with filter
    const statsParams: any = {}
    if (projectFilter.value) {
      statsParams.project_key = projectFilter.value
    }
    
    console.log('Loading stats with params:', statsParams)
    const statsData = await scoresApi.getStats(statsParams)
    console.log('Stats loaded:', statsData)
    stats.value = statsData

    // Load scores using new efficient paginated endpoint
    const scoresParams: any = {
      page: currentPage.value,
      page_size: pageSize.value,
    }
    
    // Apply project filter if specified
    if (projectFilter.value) {
      scoresParams.project_key = projectFilter.value
    }
    
    // Apply app name filter if specified
    if (appNameFilter.value) {
      scoresParams.app_names = appNameFilter.value
    }
    
    console.log('Loading scores with params:', scoresParams)
    const scoresResponse = await scoresApi.listScores(scoresParams)
    
    console.log('Scores response:', scoresResponse)
    console.log(`Loaded ${scoresResponse.items?.length || 0} scores (total: ${scoresResponse.total})`)
    
    // Safely check if scoresResponse and items exist
    if (!scoresResponse || !scoresResponse.items) {
      console.warn('Scores response is invalid or has no items:', scoresResponse)
      scores.value = []
      totalScores.value = 0
      ElMessage.warning('No scores found')
      return
    }
    
    // Update pagination info
    totalScores.value = scoresResponse.total
    
    // Enrich scores with review context (branch info, PR user, etc.)
    const enrichedScores: Score[] = []
    
    for (const score of scoresResponse.items) {
      try {
        // Fetch review details to get branch info and PR user
        const reviewsResponse = await reviewsApi.getReviews({
          page: 1,
          page_size: 1,
          project_key: score.project_key,
        })
        
        // Find matching review
        const matchingReview = reviewsResponse.items?.find(
          r => r.pull_request_id === score.pull_request_id
        )
        
        if (matchingReview) {
          // Enrich score with review context
          enrichedScores.push({
            ...score,
            project_name: matchingReview.project?.project_name || score.project_key,
            project_url: matchingReview.project?.project_url,
            git_provider: matchingReview.project?.git_provider,
            repository_slug: score.repository_slug || matchingReview.repository_slug,
            pull_request_commit_id: score.pull_request_commit_id || matchingReview.pull_request_commit_id || undefined,
            pull_request_user: matchingReview.pull_request_user,
            pull_request_user_info: matchingReview.pull_request_user_info,
            source_branch: matchingReview.source_branch,
            target_branch: matchingReview.target_branch,
            updated_date: matchingReview.updated_date,
          })
        } else {
          // If review not found, use score data as-is
          enrichedScores.push(score)
        }
      } catch (error) {
        console.warn(`Failed to enrich score ${score.id}:`, error)
        // Still include the score even if enrichment fails
        enrichedScores.push(score)
      }
    }
    
    // Apply level filter if specified
    let filteredScores = enrichedScores
    if (levelFilter.value === 'pr') {
      filteredScores = enrichedScores.filter(s => !s.source_filename)
    } else if (levelFilter.value === 'file') {
      filteredScores = enrichedScores.filter(s => s.source_filename)
    }
    
    scores.value = filteredScores
    
    if (filteredScores.length === 0) {
      nextTick(() => {
        ElMessage.info('No scores found for the selected filters')
      })
    }
  } catch (error) {
    console.error('Failed to load scores:', error)
    ElMessage.error('Failed to load scores: ' + (error instanceof Error ? error.message : String(error)))
  } finally {
    loading.value = false
  }
}

const handlePageChange = (page: number) => {
  currentPage.value = page
  loadScores()
}

const handlePageSizeChange = (size: number) => {
  pageSize.value = size
  currentPage.value = 1  // Reset to first page
  loadScores()
}

const confirmDelete = async (score: Score) => {
  try {
    await ElMessageBox.confirm(
      `Are you sure you want to delete this score?`,
      'Confirm Delete',
      {
        type: 'warning',
      }
    )
    
    // Delete score using composite key
    await scoresApi.deleteScore(
      score.reviewer,
      score.pull_request_id,
      score.project_key,
      score.repository_slug,
      score.source_filename || null
    )
    
    ElMessage.success('Score deleted successfully')
    
    // Reload scores to reflect changes
    loadScores()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('Failed to delete score:', error)
      ElMessage.error('Failed to delete score: ' + (error instanceof Error ? error.message : String(error)))
    }
  }
}

onMounted(() => {
  loadProjects()
  loadAppOptions()
  loadScores()
})
</script>

<style scoped>
.score-list-container {
  padding: 20px;
}

h2 {
  margin: 0;
  font-size: 20px;
  color: var(--el-text-color-primary);
}

.filter-form {
  margin-bottom: 20px;
}

.stats-row {
  margin-top: 20px;
}

/* Reviewer cell styling */
.reviewer-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}

.reviewer-avatar {
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  cursor: pointer;
}

.reviewer-avatar:hover {
  transform: scale(1.1);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.reviewer-avatar-fallback {
  color: white;
  font-weight: 600;
  font-size: 14px;
  border: 2px solid var(--el-border-color-light);
}

.reviewer-info {
  display: flex;
  flex-direction: column;
  line-height: 1.3;
  min-width: 0;
  flex: 1;
}

.reviewer-display-name {
  color: var(--el-text-color-primary);
  font-weight: 500;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.reviewer-username {
  color: var(--el-text-color-secondary);
  font-size: 11px;
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* PR User cell styling */
.user-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.user-avatar {
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  cursor: pointer;
}

.user-avatar:hover {
  transform: scale(1.1);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.user-avatar-fallback {
  color: white;
  font-weight: 600;
  font-size: 12px;
  border: 2px solid var(--el-border-color-light);
}

.user-info {
  display: flex;
  flex-direction: column;
  line-height: 1.3;
  min-width: 0;
  flex: 1;
}

.user-display-name {
  color: var(--el-text-color-primary);
  font-weight: 500;
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-username {
  color: var(--el-text-color-secondary);
  font-size: 10px;
  margin-top: 1px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Project key styling */
.project-key {
  color: var(--el-text-color-primary);
  font-weight: 500;
  font-size: 13px;
}

/* Branch info styling */
.branch-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 12px;
}

.branch-info-multiline {
  min-height: 40px;
  justify-content: center;
}

.branch-line {
  display: flex;
  align-items: center;
  gap: 4px;
  white-space: nowrap;
}

.branch-line-full {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
  opacity: 0.85;
}

.source-branch {
  color: var(--el-color-success);
  font-weight: 500;
  max-width: 70px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.source-branch-full {
  color: var(--el-color-success);
  font-weight: 500;
  word-break: break-all;
  line-height: 1.3;
}

.branch-arrow {
  color: var(--el-text-color-secondary);
  font-size: 14px;
  flex-shrink: 0;
}

.target-branch {
  color: var(--el-color-primary);
  font-weight: 500;
  max-width: 70px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.target-branch-full {
  color: var(--el-color-primary);
  font-weight: 500;
  word-break: break-all;
  line-height: 1.3;
}

/* Score cell styling */
.score-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

/* Filename text styling */
.filename-text {
  font-size: 11px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Comments styling */
.comments-text {
  color: var(--el-text-color-regular);
}

.no-comments {
  color: var(--el-text-color-disabled, #c0c4cc);
  font-style: italic;
}

/* No data placeholder */
.no-data {
  color: var(--el-text-color-disabled, #c0c4cc);
  font-style: italic;
}

/* Ensure statistic values use theme-aware colors */
:deep(.el-statistic__content) {
  color: var(--el-text-color-primary);
}

/* PR link styling */
.pr-link {
  font-weight: 500;
  transition: all 0.2s ease;
}

.pr-link:hover {
  text-decoration: underline;
}

/* Empty data state */
.empty-data {
  padding: 40px 0;
}

/* Pagination container */
.pagination-container {
  display: flex;
  justify-content: center;
  margin-top: 20px;
  padding: 16px 0;
}

/* Sequence number styling */
.seq-number {
  font-weight: 600;
  color: var(--el-text-color-primary);
  text-align: center;
  display: inline-block;
  width: 100%;
}
</style>
