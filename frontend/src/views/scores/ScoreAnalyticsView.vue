<template>
  <div class="score-analytics">
    <el-card>
      <template #header>
        <div class="card-header">
          <h2>Score Analytics Dashboard</h2>
          <el-button type="primary" @click="refreshData">
            <el-icon><Refresh /></el-icon>
            Refresh
          </el-button>
        </div>
      </template>

      <!-- Filters -->
      <el-form :inline="true" class="filter-form">
        <el-form-item label="Date Range">
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            range-separator="to"
            start-placeholder="Start date"
            end-placeholder="End date"
            style="width: 240px"
            @change="loadAnalytics"
          />
        </el-form-item>
        
        <el-form-item label="Project">
          <el-select v-model="projectFilter" placeholder="All Projects" clearable style="width: 200px" @change="loadAnalytics">
            <el-option
              v-for="option in projectOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </el-form-item>
        
        <el-form-item label="Reviewer">
          <el-select v-model="reviewerFilter" placeholder="All Reviewers" clearable style="width: 200px" @change="loadAnalytics">
            <el-option
              v-for="option in reviewerOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </el-form-item>
        
        <el-form-item>
          <el-button @click="resetFilters">Reset</el-button>
        </el-form-item>
      </el-form>

      <!-- Summary Cards -->
      <el-row :gutter="20" class="summary-cards">
        <el-col :span="6">
          <el-card shadow="hover" class="summary-card theme-aware-card">
            <div class="summary-content">
              <div class="summary-icon summary-icon-primary">
                <el-icon size="32"><TrendCharts /></el-icon>
              </div>
              <div class="summary-info">
                <div class="summary-value">{{ summary.avgScore.toFixed(1) }}</div>
                <div class="summary-label">Average Score</div>
              </div>
            </div>
          </el-card>
        </el-col>
        
        <el-col :span="6">
          <el-card shadow="hover" class="summary-card theme-aware-card">
            <div class="summary-content">
              <div class="summary-icon summary-icon-success">
                <el-icon size="32"><Document /></el-icon>
              </div>
              <div class="summary-info">
                <div class="summary-value">{{ summary.totalReviews }}</div>
                <div class="summary-label">Total Reviews</div>
              </div>
            </div>
          </el-card>
        </el-col>
        
        <el-col :span="6">
          <el-card shadow="hover" class="summary-card theme-aware-card">
            <div class="summary-content">
              <div class="summary-icon summary-icon-warning">
                <el-icon size="32"><Calendar /></el-icon>
              </div>
              <div class="summary-info">
                <div class="summary-value">{{ summary.reviewsThisWeek }}</div>
                <div class="summary-label">Reviews This Week</div>
              </div>
            </div>
          </el-card>
        </el-col>
        
        <el-col :span="6">
          <el-card shadow="hover" class="summary-card theme-aware-card">
            <div class="summary-content">
              <div class="summary-icon summary-icon-danger">
                <el-icon size="32"><Star /></el-icon>
              </div>
              <div class="summary-info">
                <div class="summary-value">{{ summary.reviewsToday }}</div>
                <div class="summary-label">Reviews Today</div>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <!-- Charts Grid -->
      <el-row :gutter="20" class="charts-grid">
        <!-- PR Status Distribution Bar Chart -->
        <el-col :span="12">
          <el-card shadow="hover">
            <BarChart
              title="Pull Request Status Distribution"
              :data="categoryData"
              color="#67c23a"
              height="300px"
            />
          </el-card>
        </el-col>

        <!-- Status Pie Chart -->
        <el-col :span="12">
          <el-card shadow="hover">
            <PieChart
              title="Review Status Breakdown"
              :data="statusData"
              height="300px"
            />
          </el-card>
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { Refresh, TrendCharts, Document, Calendar, Star } from '@element-plus/icons-vue'
import BarChart from '@/components/charts/BarChart.vue'
import PieChart from '@/components/charts/PieChart.vue'
import { reviewsApi } from '@/api/reviews'
import { scoresApi } from '@/api/scores'
import { usersApi } from '@/api/users'
import { projectsApi } from '@/api/projects'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'

const loading = ref(false)
const dateRange = ref<[Date, Date] | null>(null)
const projectFilter = ref('')
const reviewerFilter = ref('')

// Summary data
const summary = reactive({
  avgScore: 0,
  totalReviews: 0,
  reviewsToday: 0,
  reviewsThisWeek: 0,
})

// Chart data
const categoryData = ref<Array<{ name: string; value: number }>>([])
const statusData = ref<Array<{ name: string; value: number }>>([])

// Filter options
const projectOptions = ref<Array<{ label: string; value: string }>>([])
const reviewerOptions = ref<Array<{ label: string; value: string }>>([])

const loadFilterOptions = async () => {
  try {
    // Load projects
    const projectsResponse = await projectsApi.listProjects({ page_size: 100 })
    projectOptions.value = (projectsResponse.items || []).map((p) => ({
      label: p.project_name,
      value: p.project_key,
    }))

    // Load reviewers
    const reviewersResponse = await usersApi.getReviewers(100)
    reviewerOptions.value = (reviewersResponse.items || []).map((r) => ({
      label: r.display_name || r.username,
      value: r.username,
    }))
  } catch (error) {
    console.error('Failed to load filter options:', error)
  }
}

const loadAnalytics = async () => {
  loading.value = true
  try {
    // Fetch review statistics
    const stats = await reviewsApi.getStats({
      project_key: projectFilter.value || undefined,
    })

    // Update summary cards with real data
    summary.avgScore = stats.average_score || 0
    summary.totalReviews = stats.total_reviews || 0
    summary.reviewsToday = stats.reviews_today || 0
    summary.reviewsThisWeek = stats.reviews_this_week || 0
    
    // Calculate open/merged/closed distribution
    const openCount = stats.open_reviews || 0
    const mergedCount = stats.merged_reviews || 0
    const closedCount = stats.closed_reviews || 0
    
    // Category distribution - PR status breakdown
    categoryData.value = [
      { name: 'Open', value: openCount },
      { name: 'Merged', value: mergedCount },
      { name: 'Closed', value: closedCount },
    ]

    // Status distribution - calculate percentages for pie chart
    const totalPRs = openCount + mergedCount + closedCount
    if (totalPRs > 0) {
      statusData.value = [
        { name: 'Open', value: openCount },
        { name: 'Merged', value: mergedCount },
        { name: 'Closed', value: closedCount },
      ]
    } else {
      statusData.value = []
    }
  } catch (error) {
    console.error('Failed to load analytics:', error)
    ElMessage.error('Failed to load analytics data')
  } finally {
    loading.value = false
  }
}

const refreshData = () => {
  loadAnalytics()
}

const resetFilters = () => {
  dateRange.value = null
  projectFilter.value = ''
  reviewerFilter.value = ''
  loadAnalytics()
}

onMounted(() => {
  loadFilterOptions()
  loadAnalytics()
})
</script>

<style scoped>
.score-analytics {
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
  color: var(--el-text-color-primary);
}

.filter-form {
  margin-bottom: 20px;
}

.summary-cards {
  margin-bottom: 20px;
}

.summary-card {
  height: 120px;
  transition: all 0.3s ease;
}

.summary-card:hover {
  transform: translateY(-2px);
}

.summary-content {
  display: flex;
  align-items: center;
  gap: 16px;
}

/* Theme-aware icon backgrounds using CSS variables */
.summary-icon {
  width: 64px;
  height: 64px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  transition: all 0.3s ease;
}

.summary-icon-primary {
  background: var(--el-color-primary, #409eff);
}

.summary-icon-success {
  background: var(--el-color-success, #67c23a);
}

.summary-icon-warning {
  background: var(--el-color-warning, #e6a23c);
}

.summary-icon-danger {
  background: var(--el-color-danger, #f56c6c);
}

/* Dark mode adjustments for icons */
[data-theme='dark'] .summary-icon {
  opacity: 0.9;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}

.summary-info {
  flex: 1;
}

.summary-value {
  font-size: 28px;
  font-weight: bold;
  color: var(--el-text-color-primary);
  margin-bottom: 4px;
  line-height: 1;
}

.summary-label {
  font-size: 14px;
  color: var(--el-text-color-secondary);
  margin-bottom: 4px;
}

.summary-trend {
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: 2px;
}

.summary-trend.up {
  color: var(--el-color-success, #67c23a);
}

.summary-trend.down {
  color: var(--el-color-danger, #f56c6c);
}

.charts-grid {
  margin-bottom: 20px;
}

/* Ensure chart cards have proper theme support */
:deep(.el-card__header) {
  border-bottom-color: var(--el-border-color-lighter);
}

:deep(.el-card__body) {
  background-color: transparent;
}
</style>
