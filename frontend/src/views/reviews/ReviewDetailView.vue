<template>
  <div class="review-detail" v-loading="loading">
    <el-page-header @back="$router.back()" title="Back">
      <template #content>
        <span class="page-title">Review #{{ review?.id }}</span>
      </template>
    </el-page-header>

    <el-row :gutter="20" class="content-row" v-if="review">
      <!-- Review Info -->
      <el-col :span="16">
        <el-card class="info-card">
          <template #header>
            <div class="card-header">
              <span>Review Information</span>
              <el-button type="primary" size="small" @click="showEditDialog = true">
                Edit
              </el-button>
            </div>
          </template>

          <el-descriptions :column="1" border>
            <el-descriptions-item label="PR ID">
              {{ review.pull_request_id }}
            </el-descriptions-item>
            <el-descriptions-item label="Commit ID" v-if="review.pull_request_commit_id">
              {{ review.pull_request_commit_id.substring(0, 8) }}
            </el-descriptions-item>
            <el-descriptions-item label="Project">
              {{ review.project_key }} / {{ review.repository_slug }}
            </el-descriptions-item>
            <el-descriptions-item label="Reviewer">
              {{ review.reviewer_info?.display_name || review.reviewer }}
            </el-descriptions-item>
            <el-descriptions-item label="Status">
              <el-tag :type="getStatusType(review.pull_request_status)">
                {{ review.pull_request_status }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="Summary">
              {{ review.reviewer_comments || 'No summary provided' }}
            </el-descriptions-item>
            <el-descriptions-item label="Created At">
              {{ formatDate(review.created_date || '') }}
            </el-descriptions-item>
            <el-descriptions-item label="Updated At">
              {{ formatDate(review.updated_date || '') }}
            </el-descriptions-item>
          </el-descriptions>
        </el-card>

        <!-- Code Diff Viewer -->
        <el-card class="diff-card" style="margin-top: 20px">
          <CodeDiffViewer
            v-if="review.diff_content || review.git_code_diff"
            :diff="review.diff_content || review.git_code_diff || ''"
            v-model:output-format="diffFormat"
          />
          <el-empty v-else description="No diff content available" />
        </el-card>

        <!-- AI Review Results -->
        <el-card v-if="review.ai_suggestions" class="ai-review-card" style="margin-top: 20px">
          <template #header>
            <div class="card-header">
              <span>🤖 AI Review Results</span>
            </div>
          </template>
          <AIReviewResults :suggestions="review.ai_suggestions" />
        </el-card>

        <!-- Scores Section -->
        <el-card class="scores-card" style="margin-top: 20px">
          <template #header>
            <div class="card-header">
              <span>Scores</span>
              <el-button type="primary" size="small" @click="showScoreDialog = true">
                Add Score
              </el-button>
            </div>
          </template>

          <el-table :data="scores" stripe>
            <el-table-column prop="category" label="Category" width="150" />
            <el-table-column prop="score" label="Score" width="100">
              <template #default="{ row }">
                {{ row.score }} / {{ row.max_score }}
              </template>
            </el-table-column>
            <el-table-column prop="weight" label="Weight" width="100" />
            <el-table-column prop="comment" label="Comment" min-width="200" show-overflow-tooltip />
            <el-table-column prop="created_date" label="Created" width="180">
              <template #default="{ row }">
                {{ formatDate(row.created_date || '') }}
              </template>
            </el-table-column>
            <el-table-column label="Actions" width="100">
              <template #default="{ row }">
                <el-button size="small" type="danger" @click="deleteScore(row.id)">
                  Delete
                </el-button>
              </template>
            </el-table-column>
          </el-table>

          <el-empty v-if="scores.length === 0" description="No scores yet" />
        </el-card>
      </el-col>

      <!-- Actions Sidebar -->
      <el-col :span="8">
        <el-card class="actions-card">
          <template #header>
            <span>Actions</span>
          </template>

          <el-space direction="vertical" style="width: 100%">
            <el-button type="primary" style="width: 100%" @click="showEditDialog = true">
              Edit Review
            </el-button>
            <el-button type="success" style="width: 100%" @click="showScoreDialog = true">
              Add Score
            </el-button>
            <el-button type="danger" style="width: 100%" @click="confirmDelete">
              Delete Review
            </el-button>
          </el-space>
        </el-card>
      </el-col>
    </el-row>

    <!-- Edit Review Dialog -->
    <el-dialog v-model="showEditDialog" title="Edit Review" width="600px">
      <el-form :model="editForm" ref="editFormRef" label-width="120px">
        <el-form-item label="Status">
          <el-select v-model="editForm.status" style="width: 100%">
            <el-option label="Pending" value="pending" />
            <el-option label="In Progress" value="in_progress" />
            <el-option label="Completed" value="completed" />
          </el-select>
        </el-form-item>
        
        <el-form-item label="Summary">
          <el-input
            v-model="editForm.summary"
            type="textarea"
            :rows="4"
            placeholder="Review summary..."
          />
        </el-form-item>
      </el-form>
      
      <template #footer>
        <el-button @click="showEditDialog = false">Cancel</el-button>
        <el-button type="primary" :loading="updating" @click="handleUpdate">
          Update
        </el-button>
      </template>
    </el-dialog>

    <!-- Add Score Dialog -->
    <el-dialog v-model="showScoreDialog" title="Add Score" width="700px">
      <!-- Quick Score Buttons -->
      <QuickScoreButtons @select="handleQuickScoreSelect" />
      
      <!-- Score Range Guide -->
      <ScoreRangeGuide />
      
      <el-form :model="scoreForm" :rules="scoreRules" ref="scoreFormRef" label-width="120px">
        <el-form-item label="Category" prop="category">
          <el-input v-model="scoreForm.category" placeholder="e.g., Code Quality" />
        </el-form-item>
        
        <el-form-item label="Score" prop="score">
          <el-input-number v-model="scoreForm.score" :min="0" :max="100" style="width: 100%" />
        </el-form-item>
        
        <el-form-item label="Max Score">
          <el-input-number v-model="scoreForm.max_score" :min="1" :max="100" style="width: 100%" />
        </el-form-item>
        
        <el-form-item label="Weight">
          <el-input-number v-model="scoreForm.weight" :min="0" :max="10" :precision="1" style="width: 100%" />
        </el-form-item>
        
        <el-form-item label="Comment">
          <el-input
            v-model="scoreForm.comment"
            type="textarea"
            :rows="3"
            placeholder="Optional comment..."
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
import { reviewsApi } from '@/api/reviews'
import { scoresApi } from '@/api/scores'
import type { Review, ReviewUpdate } from '@/api/reviews'
import type { Score, ScoreCreate } from '@/api/scores'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import dayjs from 'dayjs'
import CodeDiffViewer from '@/components/review/CodeDiffViewer.vue'
import QuickScoreButtons from '@/components/review/QuickScoreButtons.vue'
import ScoreRangeGuide from '@/components/review/ScoreRangeGuide.vue'
import AIReviewResults from '@/components/review/AIReviewResults.vue'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const updating = ref(false)
const addingScore = ref(false)
const review = ref<Review | null>(null)
const scores = ref<Score[]>([])
const showEditDialog = ref(false)
const showScoreDialog = ref(false)
const editFormRef = ref<FormInstance>()
const scoreFormRef = ref<FormInstance>()
const diffFormat = ref<'line-by-line' | 'side-by-side'>('line-by-line')

const editForm = reactive<ReviewUpdate>({
  status: '',
  summary: null,
})

const scoreForm = reactive<ScoreCreate>({
  review_id: 0,
  category: '',
  score: 0,
  max_score: 100,
  weight: 1.0,
  comment: null,
})

const scoreRules: FormRules = {
  category: [
    { required: true, message: 'Please input category', trigger: 'blur' },
  ],
  score: [
    { required: true, message: 'Please input score', trigger: 'blur' },
  ],
}

const formatDate = (dateStr: string) => {
  return dayjs(dateStr).format('YYYY-MM-DD HH:mm:ss')
}

const getStatusType = (status: string) => {
  const types: Record<string, any> = {
    completed: 'success',
    in_progress: 'warning',
    pending: 'info',
  }
  return types[status] || 'info'
}

const loadReview = async () => {
  const id = Number(route.params.id)
  if (!id) return

  loading.value = true
  try {
    review.value = await reviewsApi.getReviewById(id)
    scores.value = await scoresApi.getScoresByReview(id)
    
    // Populate edit form
    editForm.status = review.value.status
    editForm.summary = review.value.summary
    
    // Set review_id for score form
    scoreForm.review_id = id
  } catch (error) {
    ElMessage.error('Failed to load review')
    router.push('/reviews')
  } finally {
    loading.value = false
  }
}

const handleUpdate = async () => {
  if (!review.value) return
  
  updating.value = true
  try {
    await reviewsApi.updateReview(review.value.id, editForm)
    ElMessage.success('Review updated successfully')
    showEditDialog.value = false
    loadReview()
  } catch (error) {
    ElMessage.error('Failed to update review')
  } finally {
    updating.value = false
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
        scoreForm.category = ''
        scoreForm.score = 0
        scoreForm.comment = null
        loadReview()
      } catch (error) {
        ElMessage.error('Failed to add score')
      } finally {
        addingScore.value = false
      }
    }
  })
}

const deleteScore = async (scoreId: number) => {
  try {
    await ElMessageBox.confirm('Are you sure you want to delete this score?', 'Confirm', {
      type: 'warning',
    })
    
    await scoresApi.deleteScore(scoreId)
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
  // Auto-select category based on score
  if (value >= 90) {
    scoreForm.category = 'Overall Quality'
  } else if (value >= 80) {
    scoreForm.category = 'Code Quality'
  } else if (value >= 70) {
    scoreForm.category = 'Acceptability'
  } else {
    scoreForm.category = 'Needs Improvement'
  }
}

onMounted(() => {
  loadReview()
})
</script>

<style scoped>
.review-detail {
  padding: 20px;
}

.page-title {
  font-size: 18px;
  font-weight: bold;
}

.content-row {
  margin-top: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.actions-card {
  position: sticky;
  top: 20px;
}

.diff-card :deep(.el-card__body) {
  padding: 0;
}

.ai-review-card :deep(.el-card__body) {
  padding: 0;
}
</style>
