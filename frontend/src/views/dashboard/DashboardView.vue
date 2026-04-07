<template>
  <div class="dashboard">
    <h1>Dashboard</h1>
    
    <!-- Statistics Cards -->
    <el-row :gutter="20" class="stats-row">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #409eff">
              <el-icon size="32"><Document /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.totalReviews }}</div>
              <div class="stat-label">Total Reviews</div>
            </div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #67c23a">
              <el-icon size="32"><TrendCharts /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.avgScore.toFixed(1) }}</div>
              <div class="stat-label">Average Score</div>
            </div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #e6a23c">
              <el-icon size="32"><User /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.activeReviewers }}</div>
              <div class="stat-label">Active Reviewers</div>
            </div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #f56c6c">
              <el-icon size="32"><Clock /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.pendingReviews }}</div>
              <div class="stat-label">Pending Reviews</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Recent Reviews -->
    <el-card class="recent-reviews" v-loading="loading">
      <template #header>
        <div class="card-header">
          <span>Recent Reviews</span>
          <div class="header-actions">
            <el-button type="success" size="small" @click="$router.push('/scores/analytics')">
              <el-icon><TrendCharts /></el-icon>
              View Analytics
            </el-button>
            <el-button type="primary" size="small" @click="$router.push('/reviews')">
              View All
            </el-button>
          </div>
        </div>
      </template>
      
      <el-table :data="recentReviews" stripe style="width: 100%">
        <el-table-column label="Seq#" width="80">
          <template #default="{ $index }">
            {{ $index + 1 }}
          </template>
        </el-table-column>
        <el-table-column label="PR Info" min-width="200">
          <template #default="{ row }">
            <div class="pr-info-cell">
              <div class="pr-id">
                <el-tag size="small" type="info">{{ row.pull_request_id }}</el-tag>
              </div>
              <div class="project-repo">
                <strong>{{ row.project_key }}</strong> / {{ row.repository_slug }}
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="Reviewer" width="150">
          <template #default="{ row }">
            {{ row.reviewer_info?.display_name || row.reviewer }}
          </template>
        </el-table-column>
        <el-table-column label="Status" width="120">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.pull_request_status)">
              {{ row.pull_request_status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="Scores" width="100">
          <template #default="{ row }">
            <div v-if="row.score_summary && row.score_summary.total_scores > 0">
              <span class="avg-score">{{ row.score_summary.average_score?.toFixed(1) }}</span>
              <span class="score-count">({{ row.score_summary.total_scores }})</span>
            </div>
            <span v-else class="text-secondary">No scores</span>
          </template>
        </el-table-column>
        <el-table-column label="Created" width="160">
          <template #default="{ row }">
            {{ formatDate(row.created_date) }}
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Document, TrendCharts, User, Clock } from '@element-plus/icons-vue'
import { reviewsApi } from '@/api/reviews'
import { scoresApi } from '@/api/scores'
import type { Review } from '@/api/reviews'
import dayjs from 'dayjs'

const loading = ref(false)
const recentReviews = ref<Review[]>([])
const stats = ref({
  totalReviews: 0,
  avgScore: 0,
  activeReviewers: 0,
  pendingReviews: 0,
})

const formatDate = (dateStr: string) => {
  return dayjs(dateStr).format('YYYY-MM-DD HH:mm')
}

const truncateUrl = (url: string) => {
  return url.length > 50 ? url.substring(0, 50) + '...' : url
}

const getStatusType = (status: string) => {
  const types: Record<string, any> = {
    completed: 'success',
    in_progress: 'warning',
    pending: 'info',
  }
  return types[status] || 'info'
}

const loadDashboardData = async () => {
  loading.value = true
  try {
    // Load recent reviews
    const reviewsData = await reviewsApi.getReviews({ page: 1, page_size: 10 })
    recentReviews.value = reviewsData.items
    stats.value.totalReviews = reviewsData.total
    stats.value.pendingReviews = reviewsData.items.filter(r => r.pull_request_status === 'pending').length
    
    // Load score stats
    const scoreStats = await scoresApi.getStats()
    stats.value.avgScore = scoreStats.average_score || 0
    
    // Calculate active reviewers (fetch all reviews with pagination)
    const allReviewers = new Set<string>()
    let currentPage = 1
    const pageSize = 100 // API max limit
    
    // Fetch first page to get total count
    const firstPage = await reviewsApi.getReviews({ page: 1, page_size: pageSize })
    firstPage.items.forEach(r => allReviewers.add(r.reviewer))
    
    // Calculate total pages and fetch remaining
    const totalPages = Math.ceil(firstPage.total / pageSize)
    
    // Fetch remaining pages in parallel (limit to avoid too many requests)
    if (totalPages > 1) {
      const pagesToFetch = Math.min(totalPages - 1, 9) // Max 10 pages total (1000 reviews)
      const promises = []
      
      for (let i = 2; i <= pagesToFetch + 1; i++) {
        promises.push(
          reviewsApi.getReviews({ page: i, page_size: pageSize })
            .then(data => data.items.forEach(r => allReviewers.add(r.reviewer)))
            .catch(err => console.warn(`Failed to fetch page ${i}:`, err))
        )
      }
      
      await Promise.all(promises)
    }
    
    stats.value.activeReviewers = allReviewers.size
  } catch (error) {
    console.error('Failed to load dashboard data:', error)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadDashboardData()
})
</script>

<style scoped>
.dashboard {
  padding: 20px;
}

.dashboard h1 {
  margin-bottom: 24px;
  color: var(--el-text-color-primary);
}

.stats-row {
  margin-bottom: 24px;
}

.stat-card {
  height: 120px;
}

.stat-content {
  display: flex;
  align-items: center;
  gap: 16px;
}

.stat-icon {
  width: 64px;
  height: 64px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 28px;
  font-weight: bold;
  color: var(--el-text-color-primary);
  margin-bottom: 4px;
}

.stat-label {
  font-size: 14px;
  color: var(--el-text-color-secondary);
}

.recent-reviews {
  margin-top: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-actions {
  display: flex;
  gap: 8px;
}

/* PR Info Cell Styles */
.pr-info-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.pr-id {
  display: flex;
  align-items: center;
}

.project-repo {
  font-size: 0.85rem;
  color: var(--el-text-color-secondary);
}

.text-secondary {
  color: var(--el-text-color-secondary);
  font-size: 0.85rem;
}

.avg-score {
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--el-color-success);
}

.score-count {
  font-size: 0.8rem;
  color: var(--el-text-color-secondary);
  margin-left: 2px;
}
</style>
