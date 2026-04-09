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
            <el-option label="Project A" value="project-a" />
            <el-option label="Project B" value="project-b" />
          </el-select>
        </el-form-item>
        
        <el-form-item label="Reviewer">
          <el-select v-model="reviewerFilter" placeholder="All Reviewers" clearable style="width: 200px" @change="loadAnalytics">
            <el-option label="John Doe" value="john" />
            <el-option label="Jane Smith" value="jane" />
          </el-select>
        </el-form-item>
        
        <el-form-item>
          <el-button @click="resetFilters">Reset</el-button>
        </el-form-item>
      </el-form>

      <!-- Summary Cards -->
      <el-row :gutter="20" class="summary-cards">
        <el-col :span="6">
          <el-card shadow="hover" class="summary-card">
            <div class="summary-content">
              <div class="summary-icon" style="background: #409eff">
                <el-icon size="32"><TrendCharts /></el-icon>
              </div>
              <div class="summary-info">
                <div class="summary-value">{{ summary.avgScore.toFixed(1) }}</div>
                <div class="summary-label">Average Score</div>
                <div class="summary-trend" :class="summary.scoreTrend >= 0 ? 'up' : 'down'">
                  <el-icon><component :is="summary.scoreTrend >= 0 ? CaretTop : CaretBottom" /></el-icon>
                  {{ Math.abs(summary.scoreTrend) }}%
                </div>
              </div>
            </div>
          </el-card>
        </el-col>
        
        <el-col :span="6">
          <el-card shadow="hover" class="summary-card">
            <div class="summary-content">
              <div class="summary-icon" style="background: #67c23a">
                <el-icon size="32"><Document /></el-icon>
              </div>
              <div class="summary-info">
                <div class="summary-value">{{ summary.totalReviews }}</div>
                <div class="summary-label">Total Reviews</div>
                <div class="summary-trend up">
                  <el-icon><CaretTop /></el-icon>
                  12%
                </div>
              </div>
            </div>
          </el-card>
        </el-col>
        
        <el-col :span="6">
          <el-card shadow="hover" class="summary-card">
            <div class="summary-content">
              <div class="summary-icon" style="background: #e6a23c">
                <el-icon size="32"><User /></el-icon>
              </div>
              <div class="summary-info">
                <div class="summary-value">{{ summary.activeReviewers }}</div>
                <div class="summary-label">Active Reviewers</div>
              </div>
            </div>
          </el-card>
        </el-col>
        
        <el-col :span="6">
          <el-card shadow="hover" class="summary-card">
            <div class="summary-content">
              <div class="summary-icon" style="background: #f56c6c">
                <el-icon size="32"><Star /></el-icon>
              </div>
              <div class="summary-info">
                <div class="summary-value">{{ summary.totalScores }}</div>
                <div class="summary-label">Total Scores</div>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <!-- Charts Grid -->
      <el-row :gutter="20" class="charts-grid">
        <!-- Score Trend Line Chart -->
        <el-col :span="24">
          <el-card shadow="hover">
            <LineChart
              title="Score Trend Over Time"
              :data="trendData"
              color="#409eff"
              height="300px"
            />
          </el-card>
        </el-col>
      </el-row>

      <el-row :gutter="20" class="charts-grid">
        <!-- Category Distribution Bar Chart -->
        <el-col :span="12">
          <el-card shadow="hover">
            <BarChart
              title="Score Distribution by Category"
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
              title="Review Status Distribution"
              :data="statusData"
              height="300px"
            />
          </el-card>
        </el-col>
      </el-row>

      <el-row :gutter="20" class="charts-grid">
        <!-- Reviewer Performance Radar Chart -->
        <el-col :span="24">
          <el-card shadow="hover">
            <RadarChart
              title="Reviewer Performance Comparison"
              :indicators="radarIndicators"
              :data="radarData"
              height="400px"
            />
          </el-card>
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { Refresh, TrendCharts, Document, User, Star, CaretTop, CaretBottom } from '@element-plus/icons-vue'
import LineChart from '@/components/charts/LineChart.vue'
import BarChart from '@/components/charts/BarChart.vue'
import PieChart from '@/components/charts/PieChart.vue'
import RadarChart from '@/components/charts/RadarChart.vue'
import dayjs from 'dayjs'

const loading = ref(false)
const dateRange = ref<[Date, Date] | null>(null)
const projectFilter = ref('')
const reviewerFilter = ref('')

// Summary data
const summary = reactive({
  avgScore: 0,
  totalReviews: 0,
  activeReviewers: 0,
  totalScores: 0,
  scoreTrend: 0,
})

// Chart data
const trendData = ref<Array<{ date: string; value: number }>>([])
const categoryData = ref<Array<{ name: string; value: number }>>([])
const statusData = ref<Array<{ name: string; value: number }>>([])
const radarIndicators = ref<Array<{ name: string; max: number }>>([])
const radarData = ref<Array<{ name: string; value: number[] }>>([])

const loadAnalytics = async () => {
  loading.value = true
  try {
    // TODO: Replace with actual API calls
    // Mock data for demonstration
    
    // Summary
    summary.avgScore = 85.5
    summary.totalReviews = 156
    summary.activeReviewers = 12
    summary.totalScores = 624
    summary.scoreTrend = 5.2

    // Trend data (last 30 days)
    trendData.value = Array.from({ length: 30 }, (_, i) => ({
      date: dayjs().subtract(29 - i, 'day').format('MM-DD'),
      value: 75 + Math.random() * 20,
    }))

    // Category distribution
    categoryData.value = [
      { name: 'Code Quality', value: 88 },
      { name: 'Performance', value: 75 },
      { name: 'Security', value: 92 },
      { name: 'Maintainability', value: 82 },
      { name: 'Documentation', value: 70 },
    ]

    // Status distribution
    statusData.value = [
      { name: 'Completed', value: 120 },
      { name: 'In Progress', value: 25 },
      { name: 'Pending', value: 11 },
    ]

    // Radar chart - reviewer comparison
    radarIndicators.value = [
      { name: 'Code Quality', max: 100 },
      { name: 'Performance', max: 100 },
      { name: 'Security', max: 100 },
      { name: 'Maintainability', max: 100 },
      { name: 'Documentation', max: 100 },
      { name: 'Testing', max: 100 },
    ]

    radarData.value = [
      {
        name: 'John Doe',
        value: [85, 78, 90, 82, 75, 88],
      },
      {
        name: 'Jane Smith',
        value: [90, 85, 88, 90, 85, 92],
      },
      {
        name: 'Bob Wilson',
        value: [78, 82, 85, 75, 80, 78],
      },
    ]
  } catch (error) {
    console.error('Failed to load analytics:', error)
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
}

.filter-form {
  margin-bottom: 20px;
}

.summary-cards {
  margin-bottom: 20px;
}

.summary-card {
  height: 120px;
}

.summary-content {
  display: flex;
  align-items: center;
  gap: 16px;
}

.summary-icon {
  width: 64px;
  height: 64px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
}

.summary-info {
  flex: 1;
}

.summary-value {
  font-size: 28px;
  font-weight: bold;
  color: #303133;
  margin-bottom: 4px;
}

.summary-label {
  font-size: 14px;
  color: #909399;
  margin-bottom: 4px;
}

.summary-trend {
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: 2px;
}

.summary-trend.up {
  color: #67c23a;
}

.summary-trend.down {
  color: #f56c6c;
}

.charts-grid {
  margin-bottom: 20px;
}
</style>
