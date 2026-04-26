<template>
  <div class="score-list-container">
    <el-card>
      <template #header>
        <h2>Scores Management</h2>
      </template>

      <!-- Filters -->
      <el-form :inline="true" class="filter-form">
        <el-form-item label="Project">
          <el-select 
            v-model="projectFilter" 
            placeholder="All Projects" 
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
        
        <el-form-item label="Score Level">
          <el-select 
            v-model="levelFilter" 
            placeholder="All Levels" 
            clearable 
            style="width: 200px" 
            @change="loadScores"
          >
            <el-option label="PR-Level" value="pr" />
            <el-option label="File-Level" value="file" />
          </el-select>
        </el-form-item>
      </el-form>

      <!-- Scores Table -->
      <el-table :data="scores" v-loading="loading" stripe style="width: 100%">
        <template #empty>
          <div class="empty-data">
            <el-empty description="No scores found">
              <el-button type="primary" @click="loadScores">Refresh</el-button>
            </el-empty>
          </div>
        </template>
        <el-table-column prop="id" label="Seq#" width="70" />
        <el-table-column prop="project_key" label="Project" width="120">
          <template #default="{ row }">
            <span class="project-key">{{ row.project_name || row.project_key }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="pull_request_user" label="PR User" width="150">
          <template #default="{ row }">
            <div class="user-cell">
              <el-avatar :size="24" v-if="row.pull_request_user_info?.avatar_url">
                <img :src="row.pull_request_user_info.avatar_url" alt="" />
              </el-avatar>
              <el-avatar :size="24" v-else>{{ getInitials(row.pull_request_user_info?.display_name || row.pull_request_user) }}</el-avatar>
              <div class="user-info">
                <span class="user-display-name">{{ row.pull_request_user_info?.display_name || row.pull_request_user }}</span>
                <span class="user-username" v-if="row.pull_request_user_info?.display_name">@{{ row.pull_request_user }}</span>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="reviewer" label="Reviewer" width="150">
          <template #default="{ row }">
            <div class="reviewer-cell">
              <el-avatar :size="28" v-if="row.reviewer_info?.avatar_url">
                <img :src="row.reviewer_info.avatar_url" alt="" />
              </el-avatar>
              <el-avatar :size="28" v-else>{{ getInitials(row.reviewer_info?.display_name || row.reviewer) }}</el-avatar>
              <div class="reviewer-info">
                <span class="reviewer-display-name">{{ row.reviewer_info?.display_name || row.reviewer }}</span>
                <span class="reviewer-username" v-if="row.reviewer_info?.display_name">@{{ row.reviewer }}</span>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="pull_request_id" label="PR ID" width="110">
          <template #default="{ row }">
            <el-link 
              type="primary" 
              @click="viewReview(row.pull_request_id)"
            >
              {{ truncateId(row.pull_request_id) }}
            </el-link>
          </template>
        </el-table-column>
        <el-table-column prop="branch_info" label="Branch" width="180">
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
        <el-table-column prop="source_filename" label="Scope" width="130">
          <template #default="{ row }">
            <el-tag 
              :type="row.source_filename ? 'info' : 'success'" 
              size="small"
            >
              {{ row.source_filename ? 'File-Level' : 'PR-Level' }}
            </el-tag>
            <div v-if="row.source_filename" class="filename-text" :title="row.source_filename">
              {{ truncateFilename(row.source_filename) }}
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="score" label="Score" width="160">
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
        <el-table-column prop="reviewer_comments" label="Comments" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.reviewer_comments" class="comments-text">
              {{ row.reviewer_comments }}
            </span>
            <span v-else class="no-comments">No comments</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_date" label="Created" width="160">
          <template #default="{ row }">
            {{ formatDate(row.created_date) }}
          </template>
        </el-table-column>
        <el-table-column prop="updated_date" label="Updated" width="160">
          <template #default="{ row }">
            {{ formatDate(row.updated_date || row.created_date) }}
          </template>
        </el-table-column>
        <el-table-column label="Actions" width="90" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="danger" @click="confirmDelete(row)">
              Delete
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- Statistics -->
      <el-divider />
      <el-row :gutter="20" class="stats-row">
        <el-col :span="8">
          <el-statistic title="Average Score" :value="stats.average_score" :precision="1" class="theme-aware-statistic" />
        </el-col>
        <el-col :span="8">
          <el-statistic title="Total Reviews" :value="stats.total_reviews" class="theme-aware-statistic" />
        </el-col>
        <el-col :span="8">
          <el-statistic title="Total Scores" :value="scores.length" class="theme-aware-statistic" />
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { scoresApi } from '@/api/scores'
import { reviewsApi } from '@/api/reviews'
import { projectsApi } from '@/api/projects'
import type { Score, ScoreStats } from '@/api/scores'
import type { ProjectSummary } from '@/api/projects'
import { ElMessage, ElMessageBox } from 'element-plus'
import dayjs from 'dayjs'

const router = useRouter()
const loading = ref(false)
const projectsLoading = ref(false)
const scores = ref<Score[]>([])
const projects = ref<ProjectSummary[]>([])
const projectFilter = ref('')
const levelFilter = ref('') // 'pr' or 'file'
const stats = ref<ScoreStats>({
  average_score: 0,
  total_reviews: 0,
  score_distribution: {},
})

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

    // Load reviews with optional project filter
    const reviewsParams: any = {
      page: 1,
      page_size: 50,
    }
    if (projectFilter.value) {
      reviewsParams.project_key = projectFilter.value
    }
    
    console.log('Loading reviews with params:', reviewsParams)
    const reviewsResponse = await reviewsApi.getReviews(reviewsParams)
    
    console.log('Reviews response:', reviewsResponse)
    
    // Safely check if reviewsResponse and items exist
    if (!reviewsResponse || !reviewsResponse.items) {
      console.warn('Reviews response is invalid or has no items:', reviewsResponse)
      scores.value = []
      ElMessage.warning('No reviews found')
      return
    }
    
    console.log('Number of reviews:', reviewsResponse.items.length)

    // Extract unique review targets and fetch their scores
    const allScores: Score[] = []
    const reviewTargets = new Set<string>()

    if (reviewsResponse.items.length === 0) {
      console.log('No reviews found')
      scores.value = []
      ElMessage.info('No reviews found')
      return
    }

    for (const review of reviewsResponse.items) {
      const targetKey = `${review.project_key}/${review.repository_slug}/${review.pull_request_id}`
      if (!reviewTargets.has(targetKey)) {
        reviewTargets.add(targetKey)
        
        try {
          console.log(`Fetching scores for PR: ${review.pull_request_id}, Project: ${review.project_key}, Repo: ${review.repository_slug}`)
          const reviewScores = await scoresApi.getScoresByReview(
            review.pull_request_id,
            review.project_key,
            review.repository_slug
          )
          
          console.log(`Got ${reviewScores.length} scores for PR ${review.pull_request_id}`)
          
          // Enrich each score with complete review context
          const enrichedScores = reviewScores.map(score => ({
            ...score,
            // Composite key fields
            pull_request_id: review.pull_request_id,
            project_key: review.project_key,
            repository_slug: review.repository_slug,
            // Additional review context fields
            project_name: review.project?.project_name || review.project_key,
            pull_request_user: review.pull_request_user,
            pull_request_user_info: review.pull_request_user_info,
            source_branch: review.source_branch,
            target_branch: review.target_branch,
            updated_date: review.updated_date,
          }))
          
          // Apply level filter if specified
          let filteredScores = enrichedScores
          if (levelFilter.value === 'pr') {
            filteredScores = enrichedScores.filter(s => !s.source_filename)
          } else if (levelFilter.value === 'file') {
            filteredScores = enrichedScores.filter(s => s.source_filename)
          }
          
          allScores.push(...filteredScores)
        } catch (error) {
          console.warn(`Failed to load scores for review ${review.pull_request_id}:`, error)
        }
      }
    }

    console.log(`Total scores loaded: ${allScores.length}`)
    scores.value = allScores
    
    if (allScores.length === 0) {
      ElMessage.info('No scores found for the selected filters')
    }
  } catch (error) {
    console.error('Failed to load scores:', error)
    ElMessage.error('Failed to load scores: ' + (error instanceof Error ? error.message : String(error)))
  } finally {
    loading.value = false
  }
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
    
    // TODO: Need composite key for deletion
    ElMessage.warning('Delete not implemented - requires composite key')
    // await scoresApi.deleteScore(score.reviewer, ...)
    // loadScores()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('Failed to delete score')
    }
  }
}

onMounted(() => {
  loadProjects()
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
  gap: 8px;
}

.reviewer-info {
  display: flex;
  flex-direction: column;
  line-height: 1.2;
}

.reviewer-display-name {
  color: var(--el-text-color-primary);
  font-weight: 500;
  font-size: 13px;
}

.reviewer-username {
  color: var(--el-text-color-secondary);
  font-size: 11px;
  margin-top: 2px;
}

/* PR User cell styling */
.user-cell {
  display: flex;
  align-items: center;
  gap: 6px;
}

.user-info {
  display: flex;
  flex-direction: column;
  line-height: 1.2;
}

.user-display-name {
  color: var(--el-text-color-primary);
  font-weight: 500;
  font-size: 12px;
}

.user-username {
  color: var(--el-text-color-secondary);
  font-size: 10px;
  margin-top: 1px;
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

:deep(.el-statistic__title) {
  color: var(--el-text-color-secondary);
}

/* Empty data state */
.empty-data {
  padding: 40px 0;
}
</style>
