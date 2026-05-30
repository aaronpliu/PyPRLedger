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
              <div class="chart-actions">
                <el-tag type="info">{{ t('dashboard.assigned_vs_self_raised') }}</el-tag>
                <el-tooltip 
                  :content="fullscreenChart === 'activity' ? t('common.exitFullscreen') : t('common.fullscreen')"
                  placement="top"
                >
                  <el-button 
                    text 
                    size="small" 
                    @click="toggleFullscreen('activity')"
                    :icon="fullscreenChart === 'activity' ? Close : FullScreen"
                  />
                </el-tooltip>
              </div>
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
              <div class="chart-actions">
                <el-tag type="success">{{ t('dashboard.average_scores_given') }}</el-tag>
                <el-tooltip 
                  :content="fullscreenChart === 'score' ? t('common.exitFullscreen') : t('common.fullscreen')"
                  placement="top"
                >
                  <el-button 
                    text 
                    size="small" 
                    @click="toggleFullscreen('score')"
                    :icon="fullscreenChart === 'score' ? Close : FullScreen"
                  />
                </el-tooltip>
              </div>
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
              <div class="chart-actions">
                <el-tag type="warning">{{ t('dashboard.unique_projects_repos') }}</el-tag>
                <el-tooltip 
                  :content="fullscreenChart === 'project' ? t('common.exitFullscreen') : t('common.fullscreen')"
                  placement="top"
                >
                  <el-button 
                    text 
                    size="small" 
                    @click="toggleFullscreen('project')"
                    :icon="fullscreenChart === 'project' ? Close : FullScreen"
                  />
                </el-tooltip>
              </div>
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
              <div class="chart-actions">
                <el-tag type="danger">{{ t('dashboard.score_gte_8') }}</el-tag>
                <el-tooltip 
                  :content="fullscreenChart === 'suggestions' ? t('common.exitFullscreen') : t('common.fullscreen')"
                  placement="top"
                >
                  <el-button 
                    text 
                    size="small" 
                    @click="toggleFullscreen('suggestions')"
                    :icon="fullscreenChart === 'suggestions' ? Close : FullScreen"
                  />
                </el-tooltip>
              </div>
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
                <a 
                  v-if="getPrUrl(row)" 
                  :href="getPrUrl(row) || undefined" 
                  target="_blank" 
                  rel="noopener noreferrer"
                  class="pr-link"
                >
                  <el-tag size="small" type="info" effect="plain">
                    {{ row.pull_request_id }}
                    <el-icon style="margin-left: 4px;"><Link /></el-icon>
                  </el-tag>
                </a>
                <el-tag v-else size="small" type="info">{{ row.pull_request_id }}</el-tag>
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
      
      <!-- Load More Button -->
      <div class="load-more-container" v-if="hasMoreReviews">
        <el-button 
          type="primary" 
          @click="loadMoreReviews" 
          :loading="loadingMore"
          plain
        >
          {{ t('dashboard.load_more') }} ({{ recentReviews.length }} / {{ totalReviews }})
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { TrendCharts, Refresh, Link, FullScreen, Close } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import type { EChartsOption } from 'echarts'
import { reviewsApi } from '@/api/reviews'
import type { Review } from '@/api/reviews'
import dayjs from 'dayjs'
import { useI18n } from 'vue-i18n'

const { t, locale } = useI18n()
const router = useRouter()

// Helper function to get chart axis colors based on theme
const getAxisColors = () => {
  // Check current theme from DOM
  const isDarkMode = document.documentElement.getAttribute('data-theme') === 'dark'
  return {
    axisLabelColor: isDarkMode ? '#cbd5e1' : '#64748b',
    axisLineColor: isDarkMode ? '#475569' : '#e2e8f0',
    splitLineColor: isDarkMode ? '#334155' : '#f1f5f9',
    nameColor: isDarkMode ? '#94a3b8' : '#64748b',
  }
}

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

// Fullscreen state
const fullscreenChart = ref<'activity' | 'score' | 'project' | 'suggestions' | null>(null)

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
const currentPage = ref(1)
const pageSize = ref(10)
const totalReviews = ref(0)
const loadingMore = ref(false)

// Computed property for showing load more button
const hasMoreReviews = computed(() => {
  return recentReviews.value.length < totalReviews.value
})

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

// Toggle fullscreen for a specific chart
const toggleFullscreen = (chartName: 'activity' | 'score' | 'project' | 'suggestions') => {
  if (fullscreenChart.value === chartName) {
    // Exit fullscreen
    fullscreenChart.value = null
    document.exitFullscreen().catch(console.error)
  } else {
    // Enter fullscreen
    fullscreenChart.value = chartName
    const chartRef = 
      chartName === 'activity' ? activityChartRef.value :
      chartName === 'score' ? scoreChartRef.value :
      chartName === 'project' ? projectChartRef.value :
      suggestionsChartRef.value
    
    if (chartRef) {
      const cardElement = chartRef.closest('.chart-card')
      if (cardElement && cardElement.requestFullscreen) {
        cardElement.requestFullscreen().catch(console.error)
      }
    }
  }
  
  // Resize chart after fullscreen transition
  setTimeout(() => {
    handleResize()
  }, 300)
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

  const colors = getAxisColors()

  // Calculate y-axis max value with padding for better visualization
  const maxValue = Math.max(...totalData, ...assignedData, ...selfRaisedData)
  const yAxisMax = maxValue > 0 ? Math.ceil(maxValue * 1.2) : 10 // Add 20% padding

  const option: EChartsOption = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
    },
    legend: {
      data: [t('dashboard.assigned_reviews'), t('dashboard.self_raised_prs'), t('dashboard.total')],
      textStyle: {
        color: colors.axisLabelColor,
      },
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '15%',
      top: '10%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: { 
        rotate: 45,
        interval: 'auto', // Auto-adjust interval to prevent overlap
        color: colors.axisLabelColor,
      },
      axisLine: {
        lineStyle: {
          color: colors.axisLineColor,
        },
      },
    },
    yAxis: {
      type: 'value',
      name: t('dashboard.count'),
      min: 0,
      max: yAxisMax,
      nameTextStyle: {
        color: colors.nameColor,
      },
      axisLabel: {
        color: colors.axisLabelColor,
        formatter: (value: number) => {
          // Format large numbers with K suffix
          if (value >= 1000) {
            return (value / 1000).toFixed(1) + 'K'
          }
          return value.toString()
        },
      },
      axisLine: {
        lineStyle: {
          color: colors.axisLineColor,
        },
      },
      splitLine: {
        lineStyle: {
          color: colors.splitLineColor,
        },
      },
    },
    // Add dataZoom for cases with many data points
    dataZoom: [
      {
        type: 'inside', // Enable mouse wheel zoom
        start: 0,
        end: 100,
      },
      {
        type: 'slider', // Show slider at bottom
        show: totalData.length > 30, // Only show if more than 30 data points
        start: 0,
        end: 100,
        bottom: '5%',
        height: 20,
      },
    ],
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

  const colors = getAxisColors()

  const option: EChartsOption = {
    tooltip: {
      trigger: 'axis',
    },
    legend: {
      data: [t('dashboard.avg_score'), t('dashboard.min_score'), t('dashboard.max_score')],
      textStyle: {
        color: colors.axisLabelColor,
      },
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
        color: colors.axisLabelColor,
      },
      axisLine: {
        lineStyle: {
          color: colors.axisLineColor,
        },
      },
    },
    yAxis: {
      type: 'value',
      name: t('dashboard.score'),
      min: 0,
      max: 10,
      nameTextStyle: {
        color: colors.nameColor,
      },
      axisLabel: {
        color: colors.axisLabelColor,
      },
      axisLine: {
        lineStyle: {
          color: colors.axisLineColor,
        },
      },
      splitLine: {
        lineStyle: {
          color: colors.splitLineColor,
        },
      },
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
          silent: true,
          data: [{ type: 'average', name: t('dashboard.average') }],
          label: {
            backgroundColor: 'transparent',
          },
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

  const colors = getAxisColors()

  const option: EChartsOption = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
    },
    legend: {
      data: [t('dashboard.unique_projects'), t('dashboard.unique_repos')],
      textStyle: {
        color: colors.axisLabelColor,
      },
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
        color: colors.axisLabelColor,
      },
      axisLine: {
        lineStyle: {
          color: colors.axisLineColor,
        },
      },
    },
    yAxis: {
      type: 'value',
      name: t('dashboard.count'),
      nameTextStyle: {
        color: colors.nameColor,
      },
      axisLabel: {
        color: colors.axisLabelColor,
      },
      axisLine: {
        lineStyle: {
          color: colors.axisLineColor,
        },
      },
      splitLine: {
        lineStyle: {
          color: colors.splitLineColor,
        },
      },
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

  const colors = getAxisColors()

  const option: EChartsOption = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
    },
    legend: {
      data: [t('dashboard.good_suggestions'), t('dashboard.percentage')],
      textStyle: {
        color: colors.axisLabelColor,
      },
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
        color: colors.axisLabelColor,
      },
      axisLine: {
        lineStyle: {
          color: colors.axisLineColor,
        },
      },
    },
    yAxis: [
      {
        type: 'value',
        name: t('dashboard.count'),
        position: 'left',
        nameTextStyle: {
          color: colors.nameColor,
        },
        axisLabel: {
          color: colors.axisLabelColor,
        },
        axisLine: {
          lineStyle: {
            color: colors.axisLineColor,
          },
        },
        splitLine: {
          lineStyle: {
            color: colors.splitLineColor,
          },
        },
      },
      {
        type: 'value',
        name: t('dashboard.percentage'),
        position: 'right',
        nameTextStyle: {
          color: colors.nameColor,
        },
        axisLabel: { 
          formatter: '{value}%',
          color: colors.axisLabelColor,
        },
        axisLine: {
          lineStyle: {
            color: colors.axisLineColor,
          },
        },
        splitLine: {
          show: false,
        },
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
          silent: true,
          data: [{ type: 'average', name: t('dashboard.average') }],
          label: {
            backgroundColor: 'transparent',
            position: 'start',
          },
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
const loadRecentReviews = async (reset = true) => {
  if (reset) {
    currentPage.value = 1
    recentReviews.value = []
  }
  
  loading.value = true
  try {
    const reviewsData = await reviewsApi.getReviews({ 
      page: currentPage.value, 
      page_size: pageSize.value 
    })
    
    if (reset) {
      recentReviews.value = reviewsData.items
    } else {
      // Append new items to existing list
      recentReviews.value = [...recentReviews.value, ...reviewsData.items]
    }
    
    totalReviews.value = reviewsData.total
  } catch (error) {
    console.error('Failed to load recent reviews:', error)
    ElMessage.error(t('dashboard.failed_load_reviews'))
  } finally {
    loading.value = false
  }
}

// Load more reviews
const loadMoreReviews = async () => {
  loadingMore.value = true
  currentPage.value++
  await loadRecentReviews(false) // Don't reset, append to existing
  loadingMore.value = false
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

// Generate PR URL for external navigation
const getPrUrl = (review: Review): string | null => {
  if (!review.project?.project_url || !review.repository_slug || !review.pull_request_commit_id) {
    return null
  }
  
  // Construct URL: <project_url>/repos/<repository_slug>/commits/<commit_id>
  const baseUrl = review.project.project_url.replace(/\/$/, '') // Remove trailing slash
  return `${baseUrl}/repos/${review.repository_slug}/commits/${review.pull_request_commit_id}`
}

onMounted(() => {
  initCharts()
  window.addEventListener('resize', handleResize)
  
  // Listen for fullscreen changes
  document.addEventListener('fullscreenchange', handleFullscreenChange)
  
  loadTrendData()
  loadRecentReviews()
  
  // Watch for theme changes via MutationObserver
  const observer = new MutationObserver(() => {
    // Re-render all charts with new theme colors when theme changes
    if (trendData.value.activity.length > 0) renderActivityChart()
    if (trendData.value.scores.length > 0) renderScoreChart()
    if (trendData.value.projects.length > 0) renderProjectChart()
    if (trendData.value.suggestions.length > 0) renderSuggestionsChart()
  })
  
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['data-theme']
  })
  
  // Store observer reference for cleanup
  ;(window as any).__themeObserver = observer
})

// Watch for locale changes and re-render charts with new translations
watch(locale, () => {
  // Re-render all charts with new language labels
  if (trendData.value.activity.length > 0) renderActivityChart()
  if (trendData.value.scores.length > 0) renderScoreChart()
  if (trendData.value.projects.length > 0) renderProjectChart()
  if (trendData.value.suggestions.length > 0) renderSuggestionsChart()
})

// Handle fullscreen change events
const handleFullscreenChange = () => {
  if (!document.fullscreenElement) {
    // Exited fullscreen
    fullscreenChart.value = null
    setTimeout(() => {
      handleResize()
    }, 100)
  }
}

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  document.removeEventListener('fullscreenchange', handleFullscreenChange)
  activityChart?.dispose()
  scoreChart?.dispose()
  projectChart?.dispose()
  suggestionsChart?.dispose()
  
  // Cleanup theme observer
  if ((window as any).__themeObserver) {
    (window as any).__themeObserver.disconnect()
    delete (window as any).__themeObserver
  }
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

.chart-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.chart-container {
  width: 100%;
  height: 350px;
  transition: all 0.3s ease;
  overflow: hidden; /* Prevent any overflow */
}

/* Fullscreen mode styles */
.chart-card:fullscreen {
  padding: 20px;
  background: var(--el-bg-color);
}

.chart-card:fullscreen .chart-container {
  height: calc(100vh - 150px);
  min-height: 600px;
}

.chart-card:fullscreen .chart-header {
  margin-bottom: 20px;
}

/* Webkit browsers (Chrome, Safari, Edge) */
.chart-card:-webkit-full-screen {
  padding: 20px;
  background: var(--el-bg-color);
}

.chart-card:-webkit-full-screen .chart-container {
  height: calc(100vh - 150px);
  min-height: 600px;
}

/* Firefox */
.chart-card:-moz-full-screen {
  padding: 20px;
  background: var(--el-bg-color);
}

.chart-card:-moz-full-screen .chart-container {
  height: calc(100vh - 150px);
  min-height: 600px;
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

/* Load More Button Container */
.load-more-container {
  margin-top: 16px;
  display: flex;
  justify-content: center;
  padding: 12px 0;
  border-top: 1px solid var(--el-border-color-lighter);
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

/* PR Link Styles */
.pr-link {
  text-decoration: none;
  color: inherit;
  transition: all 0.2s ease;
}

.pr-link:hover {
  opacity: 0.8;
}

.pr-link :deep(.el-tag) {
  cursor: pointer;
  transition: all 0.2s ease;
}

.pr-link:hover :deep(.el-tag) {
  border-color: var(--el-color-primary);
  background-color: var(--el-color-primary-light-9);
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
