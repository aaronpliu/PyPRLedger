<template>
  <div class="review-detail" v-loading="loading">
    <el-page-header @back="$router.back()" title="Back">
      <template #content>
        <span class="page-title">Review Details</span>
      </template>
    </el-page-header>

    <el-row :gutter="20" class="content-row" v-if="review">
      <!-- Main Content -->
      <el-col :span="24">
        <!-- Review Info Card -->
        <el-card class="info-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <span class="card-title">📋 Review Information</span>
              <el-space>
                <el-button type="success" size="small" @click="showScoreDialog = true">
                  <el-icon><Plus /></el-icon>
                  Add Score
                </el-button>
                <el-button type="danger" size="small" @click="confirmDelete">
                  <el-icon><Delete /></el-icon>
                  Delete
                </el-button>
              </el-space>
            </div>
          </template>

          <el-descriptions :column="3" border size="default">
            <el-descriptions-item label="PR ID" label-align="right">
              <el-tag type="info" size="small">{{ review.pull_request_id }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="Commit ID" v-if="review.pull_request_commit_id" label-align="right">
              <el-tag type="success" size="small">{{ review.pull_request_commit_id.substring(0, 8) }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="Project" label-align="right">
              <strong>{{ review.project_key }}</strong> / {{ review.repository_slug }}
            </el-descriptions-item>
            <el-descriptions-item label="Reviewer" label-align="right">
              <el-avatar :size="24" style="vertical-align: middle; margin-right: 8px;">{{ getInitials(review.reviewer_info?.display_name || review.reviewer) }}</el-avatar>
              {{ review.reviewer_info?.display_name || review.reviewer }}
            </el-descriptions-item>
            <el-descriptions-item label="Status" label-align="right">
              <el-tag :type="getStatusType(review.pull_request_status)" effect="dark">
                {{ review.pull_request_status }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="Level" label-align="right">
              <el-tag :type="review.source_filename ? 'warning' : 'success'" size="small">
                {{ review.source_filename ? '📄 File-Level' : '📋 PR-Level' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="Summary" :span="3" label-align="right">
              <div class="summary-text">{{ review.reviewer_comments || 'No summary provided' }}</div>
            </el-descriptions-item>
            <el-descriptions-item label="Created" label-align="right">
              <el-icon><Clock /></el-icon> {{ formatDate(review.created_date || '') }}
            </el-descriptions-item>
            <el-descriptions-item label="Updated" label-align="right">
              <el-icon><Clock /></el-icon> {{ formatDate(review.updated_date || '') }}
            </el-descriptions-item>
          </el-descriptions>
        </el-card>

        <!-- Dual Column Layout: Code Diff + AI Review -->
        <el-row :gutter="16" style="margin-top: 16px" v-if="review.git_code_diff || review.ai_suggestions">
          <!-- Code Diff Column -->
          <el-col :span="review.ai_suggestions ? 12 : 24">
            <div class="analysis-column">
              <div class="analysis-column-header">
                <span>📝 Code Changes</span>
                <el-radio-group v-model="diffFormat" size="small">
                  <el-radio-button value="line-by-line">📄 Unified</el-radio-button>
                  <el-radio-button value="side-by-side">↔️ Side by Side</el-radio-button>
                </el-radio-group>
              </div>
              <div class="analysis-column-body">
                <CodeDiffViewer
                  v-if="review.diff_content || review.git_code_diff"
                  :diff="review.diff_content || review.git_code_diff || ''"
                  v-model:output-format="diffFormat"
                />
              </div>
            </div>
          </el-col>

          <!-- AI Review Column -->
          <el-col :span="review.ai_suggestions ? 12 : 0" v-if="review.ai_suggestions">
            <div class="analysis-column">
              <div class="analysis-column-header">
                🤖 AI Review Results
              </div>
              <div class="analysis-column-body">
                <AIReviewResults :suggestions="review.ai_suggestions" />
              </div>
            </div>
          </el-col>
        </el-row>

        <!-- Scores Section -->
        <el-card class="scores-card" style="margin-top: 20px">
          <template #header>
            <div class="card-header">
              <span class="card-title">📊 Scores ({{ scores.length }})</span>
              <el-button type="primary" size="small" @click="showScoreDialog = true">
                <el-icon><Plus /></el-icon>
                Add Score
              </el-button>
            </div>
          </template>

          <el-table :data="scores" stripe>
            <el-table-column prop="reviewer" label="Reviewer" width="150">
              <template #default="{ row }">
                {{ row.reviewer_info?.display_name || row.reviewer }}
              </template>
            </el-table-column>
            <el-table-column prop="score" label="Score" width="120">
              <template #default="{ row }">
                <span class="score-value">{{ row.score }}</span>
                <span v-if="row.max_score" class="score-max"> / {{ row.max_score }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="weight" label="Weight" width="80" />
            <el-table-column prop="reviewer_comments" label="Comments" min-width="200" show-overflow-tooltip />
            <el-table-column prop="created_date" label="Created" width="160">
              <template #default="{ row }">
                {{ formatDate(row.created_date || '') }}
              </template>
            </el-table-column>
            <el-table-column label="Actions" width="100">
              <template #default="{ row }">
                <el-button size="small" type="danger" @click="deleteScore(row)">
                  Delete
                </el-button>
              </template>
            </el-table-column>
          </el-table>

          <el-empty v-if="scores.length === 0" description="No scores yet" />
        </el-card>
      </el-col>
    </el-row>

    <!-- Add Score Dialog -->
    <el-dialog v-model="showScoreDialog" title="Add Score" width="700px">
      <!-- Quick Score Buttons -->
      <QuickScoreButtons @select="handleQuickScoreSelect" />
      
      <!-- Score Range Guide -->
      <ScoreRangeGuide />
      
      <el-form :model="scoreForm" :rules="scoreRules" ref="scoreFormRef" label-width="120px">
        <el-form-item label="Reviewer">
          <el-input 
            v-model="scoreForm.reviewer" 
            disabled
            placeholder="Current user"
          >
            <template #prefix>
              <el-icon><User /></el-icon>
            </template>
          </el-input>
          <div style="font-size: 0.8rem; color: var(--el-text-color-secondary); margin-top: 4px;">
            Score will be attributed to your account
          </div>
        </el-form-item>
        
        <el-form-item label="Score" prop="score">
          <div class="score-input-container">
            <el-slider 
              v-model="scoreForm.score" 
              :min="0" 
              :max="10" 
              :step="0.5"
              :marks="{ 0: '0', 2: '2', 4: '4', 6: '6', 8: '8', 10: '10' }"
              show-input
              style="width: 100%"
            />
            <div class="score-value-display">{{ scoreForm.score.toFixed(1) }}</div>
          </div>
        </el-form-item>
        
        <el-form-item label="Comments">
          <el-input
            v-model="scoreForm.reviewer_comments"
            type="textarea"
            :rows="3"
            placeholder="Optional comments..."
          />
        </el-form-item>
      </el-form>
      
      <template #footer>
        <el-button @click="showScoreDialog = false">Cancel</el-button>
        <el-button type="primary" :loading="addingScore" @click="handleAddScore">
          Add Score
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Clock, Plus, Delete, User } from '@element-plus/icons-vue'
import { reviewsApi } from '@/api/reviews'
import { scoresApi } from '@/api/scores'
import type { Review } from '@/api/reviews'
import type { Score, ScoreCreate } from '@/api/scores'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import dayjs from 'dayjs'
import CodeDiffViewer from '@/components/review/CodeDiffViewer.vue'
import QuickScoreButtons from '@/components/review/QuickScoreButtons.vue'
import ScoreRangeGuide from '@/components/review/ScoreRangeGuide.vue'
import AIReviewResults from '@/components/review/AIReviewResults.vue'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const loading = ref(false)
const addingScore = ref(false)
const review = ref<Review | null>(null)
const scores = ref<Score[]>([])
const showScoreDialog = ref(false)
const scoreFormRef = ref<FormInstance>()
const diffFormat = ref<'line-by-line' | 'side-by-side'>('line-by-line')

const scoreForm = reactive<ScoreCreate>({
  pull_request_id: '',
  pull_request_commit_id: '',
  project_key: '',
  repository_slug: '',
  reviewer: '',
  score: 0,
  reviewer_comments: null,
  source_filename: null,
})

const scoreRules: FormRules = {
  score: [
    { required: true, message: 'Please input score', trigger: 'blur' },
  ],
}

const formatDate = (dateStr: string) => {
  return dayjs(dateStr).format('YYYY-MM-DD HH:mm:ss')
}

const getStatusType = (status: string) => {
  const types: Record<string, any> = {
    open: 'success',
    merged: 'primary',
    closed: 'info',
    draft: 'warning',
    completed: 'success',
    in_progress: 'warning',
    pending: 'info',
  }
  return types[status] || 'info'
}

const getInitials = (name: string) => {
  if (!name) return '?'
  return name
    .split(' ')
    .map(n => n[0])
    .join('')
    .toUpperCase()
    .substring(0, 2)
}

const loadReview = async () => {
  const id = Number(route.params.id)
  if (!id) return

  loading.value = true
  try {
    // Get review by ID (fetches from list)
    review.value = await reviewsApi.getReviewById(id)
    
    if (!review.value) {
      throw new Error('Review not found')
    }
    
    // Load scores using composite key (match the review's level)
    scores.value = await scoresApi.getScoresByReview(
      review.value.pull_request_id,
      review.value.project_key,
      review.value.repository_slug,
      review.value.source_filename || null  // null for PR-level, filename for file-level
    )
    
    // Debug info
    ElMessage.info(`Loaded ${scores.value.length} score(s) for ${review.value.source_filename ? 'file-level' : 'PR-level'} review`)
    
    // Set score form defaults
    scoreForm.pull_request_id = review.value.pull_request_id
    scoreForm.pull_request_commit_id = review.value.pull_request_commit_id || ''
    scoreForm.project_key = review.value.project_key
    scoreForm.repository_slug = review.value.repository_slug
    scoreForm.reviewer = authStore.currentUser?.username || ''
    scoreForm.source_filename = review.value.source_filename || null
  } catch (error) {
    console.error('Failed to load review:', error)
    ElMessage.error('Failed to load review')
    router.push('/reviews')
  } finally {
    loading.value = false
  }
}

const handleAddScore = async () => {
  if (!scoreFormRef.value) return
  
  await scoreFormRef.value.validate(async (valid) => {
    if (valid) {
      addingScore.value = true
      try {
        await scoresApi.createScore(scoreForm)
        ElMessage.success('Score added successfully')
        showScoreDialog.value = false
        // Reset form
        scoreForm.score = 0
        scoreForm.reviewer_comments = null
        loadReview()
      } catch (error) {
        ElMessage.error('Failed to add score')
      } finally {
        addingScore.value = false
      }
    }
  })
}

const deleteScore = async (score: Score) => {
  if (!review.value) return
  
  try {
    await ElMessageBox.confirm('Are you sure you want to delete this score?', 'Confirm', {
      type: 'warning',
    })
    
    await scoresApi.deleteScore(
      score.reviewer,
      review.value.pull_request_id,
      review.value.project_key,
      review.value.repository_slug,
      score.source_filename || null
    )
    ElMessage.success('Score deleted successfully')
    loadReview()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('Failed to delete score')
    }
  }
}

const confirmDelete = async () => {
  if (!review.value) return
  
  try {
    await ElMessageBox.confirm(
      `Are you sure you want to delete review #${review.value.id}?`,
      'Confirm Delete',
      {
        type: 'warning',
      }
    )
    
    await reviewsApi.deleteReview(review.value.id)
    ElMessage.success('Review deleted successfully')
    router.push('/reviews')
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('Failed to delete review')
    }
  }
}

const handleQuickScoreSelect = (value: number) => {
  scoreForm.score = value
}

onMounted(() => {
  loadReview()
})
</script>

<style scoped>
.review-detail {
  padding: 20px;
  background: var(--el-bg-color-page);
  min-height: calc(100vh - 60px);
}

.page-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.content-row {
  margin-top: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.summary-text {
  line-height: 1.6;
  color: var(--el-text-color-regular);
  white-space: pre-wrap;
  word-break: break-word;
}

.actions-card {
  position: sticky;
  top: 20px;
}

/* Analysis Column - Match web/index.html */
.analysis-column {
  border: 2px solid var(--el-border-color);
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.06);
  background: white;
  height: 600px; /* Fixed height for the entire column */
  display: flex;
  flex-direction: column;
}

[data-theme='dark'] .analysis-column {
  background: #1e293b;
  border-color: #334155;
}

.analysis-column-header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 12px 16px;
  font-weight: 700;
  font-size: 0.95rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-shrink: 0; /* Prevent header from shrinking */
  overflow: hidden; /* Ensure no scrollbar in header */
}

.analysis-column-body {
  padding: 0;
  flex: 1;
  overflow: auto; /* Enable both vertical and horizontal scrolling */
  min-height: 0;
}

/* Custom scrollbar styling */
.analysis-column-body::-webkit-scrollbar {
  width: 8px;
}

.analysis-column-body::-webkit-scrollbar-track {
  background: transparent;
}

.analysis-column-body::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 4px;
}

.analysis-column-body::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}

[data-theme='dark'] .analysis-column-body::-webkit-scrollbar-thumb {
  background: #475569;
}

[data-theme='dark'] .analysis-column-body::-webkit-scrollbar-thumb:hover {
  background: #64748b;
}

.score-value {
  font-size: 1.2rem;
  font-weight: 700;
  color: var(--el-color-success);
}

.score-max {
  font-size: 0.9rem;
  color: var(--el-text-color-secondary);
}

.score-input-container {
  width: 100%;
}

.score-value-display {
  text-align: center;
  font-size: 2rem;
  font-weight: 800;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin-top: 12px;
  text-shadow: 0 2px 4px rgba(102, 126, 234, 0.2);
}

/* Element Plus enhancements */
:deep(.el-descriptions__label) {
  font-weight: 500;
  width: 120px;
}

:deep(.el-descriptions__content) {
  color: var(--el-text-color-regular);
}

:deep(.el-table) {
  --el-table-border-color: var(--el-border-color-lighter);
}

:deep(.el-button) {
  border-radius: 6px;
  transition: all 0.3s ease;
}

:deep(.el-button:hover) {
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

:deep(.el-card) {
  border-radius: 8px;
  transition: all 0.3s ease;
}

:deep(.el-card:hover) {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}
</style>
