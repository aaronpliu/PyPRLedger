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
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="pr_url" label="PR URL" min-width="200">
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
        <el-table-column prop="created_at" label="Created" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
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
    stats.value.pendingReviews = reviewsData.items.filter(r => r.status === 'pending').length
    
    // Load score stats
    const scoreStats = await scoresApi.getStats()
    stats.value.avgScore = scoreStats.average_score
    
    // Calculate active reviewers (unique usernames)
    const uniqueReviewers = new Set(reviewsData.items.map(r => r.reviewer_username))
    stats.value.activeReviewers = uniqueReviewers.size
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

h1 {
  margin-bottom: 24px;
  color: #303133;
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
  color: #303133;
  margin-bottom: 4px;
}

.stat-label {
  font-size: 14px;
  color: #909399;
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
</style>
