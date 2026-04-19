<template>
  <div class="dashboard">
    <h1>{{ t('dashboard.title') }}</h1>
    
    <!-- Time Period Controls -->
    <el-card class="controls-card">
      <el-form :inline="true" class="trend-controls">
        <el-form-item :label="t('dashboard.period')">
          <el-radio-group v-model="selectedPeriod" @change="loadTrendData">
            <el-radio-button value="daily">{{ t('dashboard.daily') }}</el-radio-button>
            <el-radio-button value="weekly">{{ t('dashboard.weekly') }}</el-radio-button>
            <el-radio-button value="monthly">{{ t('dashboard.monthly') }}</el-radio-button>
          </el-radio-group>
        </el-form-item>
        
        <el-form-item :label="t('dashboard.days')">
          <el-select v-model="selectedDays" @change="loadTrendData" style="width: 120px">
            <el-option :label="t('dashboard.last_7_days')" :value="7" />
            <el-option :label="t('dashboard.last_30_days')" :value="30" />
            <el-option :label="t('dashboard.last_90_days')" :value="90" />
            <el-option :label="t('dashboard.last_180_days')" :value="180" />
          </el-select>
        </el-form-item>
        
        <el-form-item>
          <el-button type="primary" @click="loadTrendData" :loading="loading">
            <el-icon><Refresh /></el-icon>
            {{ t('common.refresh') }}
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- Trend Charts Grid -->
    <el-row :gutter="20" class="charts-row">
      <!-- Chart 1: Reviewer Activity Trends -->
      <el-col :span="24">
        <el-card class="chart-card" v-loading="loadingCharts.activity">
          <template #header>
            <div class="chart-header">
              <span>{{ t('dashboard.reviewer_activity_trend') }}</span>
              <el-tag type="info">{{ t('dashboard.assigned_vs_self_raised') }}</el-tag>
            </div>
          </template>
          <div class="chart-container" ref="activityChartRef"></div>
        </el-card>
      </el-col>
      
      <!-- Chart 2: Score Trends -->
      <el-col :span="24">
        <el-card class="chart-card" v-loading="loadingCharts.score">
          <template #header>
            <div class="chart-header">
              <span>{{ t('dashboard.score_trend') }}</span>
              <el-tag type="success">{{ t('dashboard.average_scores_given') }}</el-tag>
            </div>
          </template>
          <div class="chart-container" ref="scoreChartRef"></div>
        </el-card>
      </el-col>
      
      <!-- Chart 3: Project & Repository Activity -->
      <el-col :span="24">
        <el-card class="chart-card" v-loading="loadingCharts.project">
          <template #header>
            <div class="chart-header">
              <span>{{ t('dashboard.project_repo_activity') }}</span>
              <el-tag type="warning">{{ t('dashboard.unique_projects_repos') }}</el-tag>
            </div>
          </template>
          <div class="chart-container" ref="projectChartRef"></div>
        </el-card>
      </el-col>
      
      <!-- Chart 4: Good Suggestions Trend -->
      <el-col :span="24">
        <el-card class="chart-card" v-loading="loadingCharts.suggestions">
          <template #header>
            <div class="chart-header">
              <span>{{ t('dashboard.good_suggestions_trend') }}</span>
              <el-tag type="danger">{{ t('dashboard.score_gte_8') }}</el-tag>
            </div>
          </template>
          <div class="chart-container" ref="suggestionsChartRef"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Recent Reviews Table -->
    <el-card class="recent-reviews" v-loading="loading">
      <template #header>
        <div class="card-header">
          <span>{{ t('dashboard.recent_reviews') }}</span>
          <div class="header-actions">
            <el-button type="success" size="small" @click="$router.push('/scores/analytics')">
              <el-icon><TrendCharts /></el-icon>
              {{ t('dashboard.view_analytics') }}
            </el-button>
            <el-button type="primary" size="small" @click="$router.push('/reviews')">
              {{ t('dashboard.view_all') }}
            </el-button>
          </div>
        </div>
      </template>
      
      <el-table :data="recentReviews" style="width: 100%">
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
        <el-table-column label="PR User" width="150">
          <template #default="{ row }">
            <div>
              <div>{{ row.pull_request_user_info?.display_name || row.pull_request_user }}</div>
              <div class="text-secondary" style="font-size: 0.8rem;">{{ row.pull_request_user }}</div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="PR Status" width="120">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.pull_request_status)">
              {{ row.pull_request_status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="Scores" width="120">
          <template #default="{ row }">
            <div v-if="row.score_summary && row.score_summary.total_scores > 0">
              <span class="avg-score">{{ row.score_summary.max_score?.toFixed(1) || row.score_summary.average_score?.toFixed(1) }}</span>
              <span class="score-count">({{ row.score_summary.total_scores }})</span>
              <el-tag v-if="row.score_summary.max_score" size="small" type="warning" style="margin-left: 4px; font-size: 0.7rem;">max</el-tag>
            </div>
            <span v-else class="text-secondary">No scores</span>
          </template>
        </el-table-column>
        <el-table-column label="Created" width="160">
          <template #default="{ row }">
            {{ formatDate(row.created_date) }}
          </template>
        </el-table-column>
        <el-table-column label="Updated" width="160">
          <template #default="{ row }">
            {{ formatDate(row.updated_date || '') }}
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { TrendCharts, Refresh } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import type { EChartsOption } from 'echarts'
import { reviewsApi } from '@/api/reviews'
import type { Review } from '@/api/reviews'
import dayjs from 'dayjs'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
const router = useRouter()

// Time period controls
const selectedPeriod = ref<'daily' | 'weekly' | 'monthly'>('weekly')
const selectedDays = ref(90)

// Chart refs
const activityChartRef = ref<HTMLElement>()
const scoreChartRef = ref<HTMLElement>()
const projectChartRef = ref<HTMLElement>()
const suggestionsChartRef = ref<HTMLElement>()

// Chart instances
let activityChart: echarts.ECharts | null = null
let scoreChart: echarts.ECharts | null = null
let projectChart: echarts.ECharts | null = null
let suggestionsChart: echarts.ECharts | null = null

// Loading states
const loading = ref(false)
const loadingCharts = ref({
  activity: false,
  score: false,
  project: false,
  suggestions: false,
})

// Recent reviews
const recentReviews = ref<Review[]>([])

// Trend data
const trendData = ref({
  activity: [] as Array<{ date: string; assigned_reviews: number; self_raised_prs: number; total: number }>,
  scores: [] as Array<{ date: string; average_score: number; score_count: number; min_score: number; max_score: number }>,
  projects: [] as Array<{ date: string; unique_projects: number; unique_repositories: number }>,
  suggestions: [] as Array<{ date: string; good_suggestions: number; total_scores: number; percentage: number }>,
})

// Initialize charts
const initCharts = () => {
  if (activityChartRef.value) {
    activityChart = echarts.init(activityChartRef.value)
  }
  if (scoreChartRef.value) {
    scoreChart = echarts.init(scoreChartRef.value)
  }
  if (projectChartRef.value) {
    projectChart = echarts.init(projectChartRef.value)
  }
  if (suggestionsChartRef.value) {
    suggestionsChart = echarts.init(suggestionsChartRef.value)
  }
}

// Update chart sizes on window resize
const handleResize = () => {
  activityChart?.resize()
  scoreChart?.resize()
  projectChart?.resize()
  suggestionsChart?.resize()
}

// Load reviewer activity trends
const loadActivityTrends = async () => {
  loadingCharts.value.activity = true
  try {
    const response = await reviewsApi.getReviewerActivityTrends({
      period: selectedPeriod.value,
      days: selectedDays.value,
    })
    trendData.value.activity = response.trends
    renderActivityChart()
  } catch (error) {
    console.error('Failed to load activity trends:', error)
    ElMessage.error(t('dashboard.failed_load_activity'))
  } finally {
    loadingCharts.value.activity = false
  }
}

// Render activity chart
const renderActivityChart = () => {
  if (!activityChart) return

  const dates = trendData.value.activity.map(d => d.date)
  const assignedData = trendData.value.activity.map(d => d.assigned_reviews)
  const selfRaisedData = trendData.value.activity.map(d => d.self_raised_prs)
  const totalData = trendData.value.activity.map(d => d.total)

  const option: EChartsOption = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
    },
    legend: {
      data: [t('dashboard.assigned_reviews'), t('dashboard.self_raised_prs'), t('dashboard.total')],
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '15%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: { 
        rotate: 45,
        interval: 0,
      },
    },
    yAxis: {
      type: 'value',
      name: t('dashboard.count'),
    },
    series: [
      {
        name: t('dashboard.assigned_reviews'),
        type: 'bar',
        stack: 'total',
        data: assignedData,
        itemStyle: { color: '#409eff' },
      },
      {
        name: t('dashboard.self_raised_prs'),
        type: 'bar',
        stack: 'total',
        data: selfRaisedData,
        itemStyle: { color: '#67c23a' },
      },
      {
        name: t('dashboard.total'),
        type: 'line',
        data: totalData,
        itemStyle: { color: '#f56c6c' },
        lineStyle: { width: 2 },
      },
    ],
  }

  activityChart.setOption(option)
}

// Load score trends
const loadScoreTrends = async () => {
  loadingCharts.value.score = true
  try {
    const response = await reviewsApi.getScoreTrends({
      period: selectedPeriod.value,
      days: selectedDays.value,
    })
    trendData.value.scores = response.trends
    renderScoreChart()
  } catch (error) {
    console.error('Failed to load score trends:', error)
    ElMessage.error(t('dashboard.failed_load_scores'))
  } finally {
    loadingCharts.value.score = false
  }
}

// Render score chart
const renderScoreChart = () => {
  if (!scoreChart) return

  const dates = trendData.value.scores.map(d => d.date)
  const avgScores = trendData.value.scores.map(d => d.average_score)
  const minScores = trendData.value.scores.map(d => d.min_score)
  const maxScores = trendData.value.scores.map(d => d.max_score)

  const option: EChartsOption = {
    tooltip: {
      trigger: 'axis',
    },
    legend: {
      data: [t('dashboard.avg_score'), t('dashboard.min_score'), t('dashboard.max_score')],
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '15%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: { 
        rotate: 45,
        interval: 0,
      },
    },
    yAxis: {
      type: 'value',
      name: t('dashboard.score'),
      min: 0,
      max: 10,
    },
    series: [
      {
        name: t('dashboard.avg_score'),
        type: 'line',
        data: avgScores,
        smooth: true,
        areaStyle: { opacity: 0.3 },
        itemStyle: { color: '#67c23a' },
        markLine: {
          data: [{ type: 'average', name: t('dashboard.average') }],
        },
      },
      {
        name: t('dashboard.min_score'),
        type: 'line',
        data: minScores,
        smooth: true,
        lineStyle: { type: 'dashed' },
        itemStyle: { color: '#e6a23c' },
      },
      {
        name: t('dashboard.max_score'),
        type: 'line',
        data: maxScores,
        smooth: true,
        lineStyle: { type: 'dashed' },
        itemStyle: { color: '#f56c6c' },
      },
    ],
  }

  scoreChart.setOption(option)
}

// Load project/repo activity trends
const loadProjectRepoTrends = async () => {
  loadingCharts.value.project = true
  try {
    const response = await reviewsApi.getProjectRepoActivityTrends({
      period: selectedPeriod.value,
      days: selectedDays.value,
    })
    trendData.value.projects = response.trends
    renderProjectChart()
  } catch (error) {
    console.error('Failed to load project/repo trends:', error)
    ElMessage.error(t('dashboard.failed_load_projects'))
  } finally {
    loadingCharts.value.project = false
  }
}

// Render project/repo chart
const renderProjectChart = () => {
  if (!projectChart) return

  const dates = trendData.value.projects.map(d => d.date)
  const projects = trendData.value.projects.map(d => d.unique_projects)
  const repos = trendData.value.projects.map(d => d.unique_repositories)

  const option: EChartsOption = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
    },
    legend: {
      data: [t('dashboard.unique_projects'), t('dashboard.unique_repos')],
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '15%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: { 
        rotate: 45,
        interval: 0,
      },
    },
    yAxis: {
      type: 'value',
      name: t('dashboard.count'),
    },
    series: [
      {
        name: t('dashboard.unique_projects'),
        type: 'bar',
        data: projects,
        itemStyle: { color: '#409eff' },
      },
      {
        name: t('dashboard.unique_repos'),
        type: 'bar',
        data: repos,
        itemStyle: { color: '#e6a23c' },
      },
    ],
  }

  projectChart.setOption(option)
}

// Load good suggestions trends
const loadSuggestionsTrends = async () => {
  loadingCharts.value.suggestions = true
  try {
    const response = await reviewsApi.getGoodSuggestionsTrends({
      period: selectedPeriod.value,
      days: selectedDays.value,
      threshold: 8.0,
    })
    trendData.value.suggestions = response.trends
    renderSuggestionsChart()
  } catch (error) {
    console.error('Failed to load suggestions trends:', error)
    ElMessage.error(t('dashboard.failed_load_suggestions'))
  } finally {
    loadingCharts.value.suggestions = false
  }
}

// Render suggestions chart
const renderSuggestionsChart = () => {
  if (!suggestionsChart) return

  const dates = trendData.value.suggestions.map(d => d.date)
  const goodSuggestions = trendData.value.suggestions.map(d => d.good_suggestions)
  const percentages = trendData.value.suggestions.map(d => d.percentage)

  const option: EChartsOption = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
    },
    legend: {
      data: [t('dashboard.good_suggestions'), t('dashboard.percentage')],
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '15%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: { rotate: 45 },
    },
    yAxis: [
      {
        type: 'value',
        name: t('dashboard.count'),
        position: 'left',
      },
      {
        type: 'value',
        name: t('dashboard.percentage'),
        position: 'right',
        axisLabel: { formatter: '{value}%' },
      },
    ],
    series: [
      {
        name: t('dashboard.good_suggestions'),
        type: 'bar',
        data: goodSuggestions,
        itemStyle: { color: '#67c23a' },
      },
      {
        name: t('dashboard.percentage'),
        type: 'line',
        yAxisIndex: 1,
        data: percentages,
        smooth: true,
        itemStyle: { color: '#f56c6c' },
        lineStyle: { width: 2 },
        markLine: {
          data: [{ type: 'average', name: t('dashboard.average') }],
        },
      },
    ],
  }

  suggestionsChart.setOption(option)
}

// Load all trend data
const loadTrendData = async () => {
  await Promise.all([
    loadActivityTrends(),
    loadScoreTrends(),
    loadProjectRepoTrends(),
    loadSuggestionsTrends(),
  ])
}

// Load recent reviews
const loadRecentReviews = async () => {
  loading.value = true
  try {
    const reviewsData = await reviewsApi.getReviews({ page: 1, page_size: 10 })
    recentReviews.value = reviewsData.items
  } catch (error) {
    console.error('Failed to load recent reviews:', error)
  } finally {
    loading.value = false
  }
}

const formatDate = (dateStr: string) => {
  return dayjs(dateStr).format('YYYY-MM-DD HH:mm')
}

const getStatusType = (status: string) => {
  const types: Record<string, any> = {
    completed: 'success',
    in_progress: 'warning',
    pending: 'info',
  }
  return types[status] || 'info'
}

onMounted(() => {
  initCharts()
  window.addEventListener('resize', handleResize)
  loadTrendData()
  loadRecentReviews()
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  activityChart?.dispose()
  scoreChart?.dispose()
  projectChart?.dispose()
  suggestionsChart?.dispose()
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

.controls-card {
  margin-bottom: 20px;
}

.trend-controls {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
}

.charts-row {
  margin-bottom: 24px;
}

.chart-card {
  margin-bottom: 20px;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.chart-container {
  width: 100%;
  height: 350px;
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
