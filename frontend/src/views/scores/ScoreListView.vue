<template>
  <div class="score-list-container">
    <el-card>
      <template #header>
        <h2>Scores Management</h2>
      </template>

      <!-- Filters -->
      <el-form :inline="true" class="filter-form">
        <el-form-item label="Project">
          <el-select v-model="projectFilter" placeholder="All Projects" clearable style="width: 200px" @change="loadScores">
            <el-option label="Project A" value="project-a" />
            <el-option label="Project B" value="project-b" />
          </el-select>
        </el-form-item>
        
        <el-form-item label="Category">
          <el-select v-model="categoryFilter" placeholder="All Categories" clearable style="width: 200px" @change="loadScores">
            <el-option label="Code Quality" value="code_quality" />
            <el-option label="Performance" value="performance" />
            <el-option label="Security" value="security" />
          </el-select>
        </el-form-item>
      </el-form>

      <!-- Scores Table -->
      <el-table :data="scores" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="review_id" label="Review ID" width="100">
          <template #default="{ row }">
            <el-link type="primary" @click="viewReview(row.review_id)">
              #{{ row.review_id }}
            </el-link>
          </template>
        </el-table-column>
        <el-table-column prop="category" label="Category" width="150" />
        <el-table-column prop="score" label="Score" width="120">
          <template #default="{ row }">
            <el-progress
              :percentage="(row.score / row.max_score) * 100"
              :color="getScoreColor(row.score, row.max_score)"
              :format="() => `${row.score}/${row.max_score}`"
            />
          </template>
        </el-table-column>
        <el-table-column prop="weight" label="Weight" width="100" />
        <el-table-column prop="comment" label="Comment" min-width="200" show-overflow-tooltip />
        <el-table-column prop="created_at" label="Created" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="Actions" width="100" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="danger" @click="confirmDelete(row)">
              Delete
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- Statistics -->
      <el-divider />
      <el-row :gutter="20" class=\"stats-row\">
        <el-col :span=\"8\">
          <el-statistic title=\"Average Score\" :value=\"stats.average_score\" :precision=\"1\" />
        </el-col>
        <el-col :span=\"8\">
          <el-statistic title=\"Total Reviews\" :value=\"stats.total_reviews\" />
        </el-col>
        <el-col :span=\"8\">
          <el-statistic title=\"Total Scores\" :value=\"scores.length\" />
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { scoresApi } from '@/api/scores'
import type { Score, ScoreStats } from '@/api/scores'
import { ElMessage, ElMessageBox } from 'element-plus'
import dayjs from 'dayjs'

const router = useRouter()
const loading = ref(false)
const scores = ref<Score[]>([])
const projectFilter = ref('')
const categoryFilter = ref('')
const stats = ref<ScoreStats>({
  average_score: 0,
  total_reviews: 0,
  score_distribution: {},
})

const formatDate = (dateStr: string) => {
  return dayjs(dateStr).format('YYYY-MM-DD HH:mm')
}

const getScoreColor = (score: number, maxScore: number) => {
  const percentage = (score / maxScore) * 100
  if (percentage >= 80) return '#67c23a'
  if (percentage >= 60) return '#e6a23c'
  return '#f56c6c'
}

const viewReview = (reviewId: number) => {
  router.push(`/reviews/${reviewId}`)
}

const loadScores = async () => {
  loading.value = true
  try {
    // Load stats
    const statsData = await scoresApi.getStats(
      projectFilter.value ? { project_id: projectFilter.value } : undefined
    )
    stats.value = statsData

    // For demo, we'll load scores from a review
    // In production, you'd have a dedicated endpoint
    scores.value = []
  } catch (error) {
    ElMessage.error('Failed to load scores')
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
    
    await scoresApi.deleteScore(score.id)
    ElMessage.success('Score deleted successfully')
    loadScores()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('Failed to delete score')
    }
  }
}

onMounted(() => {
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
}

.filter-form {
  margin-bottom: 20px;
}

.stats-row {
  margin-top: 20px;
}
</style>
