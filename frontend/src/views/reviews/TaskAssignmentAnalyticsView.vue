<template>
  <div class="task-assignment-analytics">
    <!-- Header -->
    <div class="page-header">
      <h1>{{ t('task_assignment.analytics.page_title') }}</h1>
      <el-button type="primary" @click="refreshData" :loading="loading">
        <el-icon><Refresh /></el-icon>
        {{ t('common.refresh') }}
      </el-button>
    </div>

    <!-- Filters -->
    <el-card class="filters-card">
      <el-form :inline="true" class="filter-form">
        <el-form-item :label="t('task_assignment.analytics.period.daily')">
          <el-radio-group v-model="selectedPeriod" @change="loadAnalytics">
            <el-radio-button value="daily">{{ t('task_assignment.analytics.period.daily') }}</el-radio-button>
            <el-radio-button value="weekly">{{ t('task_assignment.analytics.period.weekly') }}</el-radio-button>
            <el-radio-button value="monthly">{{ t('task_assignment.analytics.period.monthly') }}</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <el-form-item :label="t('task_assignment.analytics.filters.date_range')">
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            range-separator="to"
            :start-placeholder="t('task_assignment.analytics.filters.start_date')"
            :end-placeholder="t('task_assignment.analytics.filters.end_date')"
            style="width: 240px"
            @change="loadAnalytics"
          />
        </el-form-item>

        <el-form-item :label="t('task_assignment.analytics.filters.project')">
          <el-select
            v-model="projectFilter"
            :placeholder="t('task_assignment.analytics.filters.all_projects')"
            clearable
            style="width: 200px"
            @change="loadAnalytics"
          >
            <el-option
              v-for="option in projectOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </el-form-item>

        <el-form-item :label="t('task_assignment.analytics.filters.reviewer')">
          <el-select
            v-model="reviewerFilter"
            :placeholder="t('task_assignment.analytics.filters.all_reviewers')"
            clearable
            style="width: 200px"
            @change="loadAnalytics"
          >
            <el-option
              v-for="option in reviewerOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- Summary Cards - Hybrid Design -->
    <el-row :gutter="20" class="summary-cards">
      <!-- Card 1: Total Reviews - Gradient Border + Animated Counter -->
      <el-col :xs="24" :sm="12" :md="6">
        <div class="stat-card stat-card--gradient-border">
          <div class="stat-card__border"></div>
          <div class="stat-card__content">
            <div class="stat-card__icon">
              <el-icon :size="28"><Document /></el-icon>
            </div>
            <div class="stat-card__value animated-counter">{{ animatedTotalReviews.toLocaleString() }}</div>
            <div class="stat-card__label">{{ t('task_assignment.analytics.summary.total_reviews') }}</div>
            <div class="stat-card__trend">
              <span class="trend-indicator">📊</span>
              <span>All Time</span>
            </div>
          </div>
        </div>
      </el-col>

      <!-- Card 2: Active Reviews - Glassmorphism + Pulse -->
      <el-col :xs="24" :sm="12" :md="6">
        <div class="stat-card stat-card--glassmorphism">
          <div class="glass-overlay"></div>
          <div class="stat-card__content">
            <div class="stat-card__header">
              <div class="stat-card__icon">
                <el-icon :size="28"><TrendCharts /></el-icon>
              </div>
              <div class="live-indicator">
                <span class="pulse-dot"></span>
                <span>Live</span>
              </div>
            </div>
            <div class="stat-card__value">{{ animatedActiveReviews.toLocaleString() }}</div>
            <div class="stat-card__label">{{ t('task_assignment.analytics.summary.active_reviews') }}</div>
          </div>
        </div>
      </el-col>

      <!-- Card 3: Avg Assignments - Minimalist + Sparkline -->
      <el-col :xs="24" :sm="12" :md="6">
        <div class="stat-card stat-card--minimalist">
          <div class="stat-card__accent"></div>
          <div class="stat-card__content">
            <Sparkline 
              :data="avgAssignmentsSparkline"
              :width="180"
              height="50px"
              color="#e6a23c"
              :stroke-width="2.5"
              :show-area="true"
            />
            <div class="stat-card__value minimalist-value">{{ summaryStats.avgAssignments }}</div>
            <div class="stat-card__label">{{ t('task_assignment.analytics.summary.avg_assignments') }}</div>
          </div>
        </div>
      </el-col>

      <!-- Card 4: Scoring Rate - Progress Ring -->
      <el-col :xs="24" :sm="12" :md="6">
        <div class="stat-card stat-card--progress-ring">
          <div class="stat-card__content">
            <ProgressRing
              :percentage="summaryStats.scoringRate"
              :size="100"
              :stroke-width="8"
              color="#67c23a"
              :value="summaryStats.scoringRate"
              suffix="%"
            />
            <div class="stat-card__label ring-label">{{ t('task_assignment.analytics.summary.scoring_rate') }}</div>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- Charts Grid -->
    <div class="charts-container">
      <!-- Loading Progress -->
      <el-alert
        v-if="loading && loadingProgress"
        :title="loadingProgress"
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 20px"
      />
      
      <div v-loading="loading" element-loading-text="Loading analytics data...">
      <!-- Chart Row 1: Time-Based Trends -->
      <el-card class="chart-card" shadow="hover">
        <template #header>
          <div class="chart-header">
            <span>{{ t('task_assignment.analytics.charts.reviews_raised_trend') }}</span>
            <div class="chart-actions">
              <el-tag type="info">{{ selectedPeriod }}</el-tag>
              <el-tooltip 
                :content="fullscreenChart === 'timeTrend' ? t('common.exitFullscreen') : t('common.fullscreen')"
                placement="top"
              >
                <el-button 
                  text 
                  size="small" 
                  @click="toggleFullscreen('timeTrend')"
                  :icon="fullscreenChart === 'timeTrend' ? Close : FullScreen"
                />
              </el-tooltip>
            </div>
          </div>
        </template>
        <div ref="timeTrendChartRef">
          <LineChart
            v-if="timePeriodData.length > 0"
            :title="''"
            :data="timePeriodData.map(d => ({ date: d.date, value: d.count }))"
            color="#409eff"
            height="350px"
            :axis-label-color="getAxisColors().axisLabelColor"
            :axis-line-color="getAxisColors().axisLineColor"
            :split-line-color="getAxisColors().splitLineColor"
          />
          <el-empty v-else :description="t('task_assignment.analytics.messages.no_data')" />
        </div>
      </el-card>

      <!-- Chart Row 2: Distribution Charts -->
      <el-row :gutter="20" class="chart-row">
        <!-- By PR User -->
        <el-col :xs="24" :md="12">
          <el-card class="chart-card" shadow="hover">
            <template #header>
              <span>{{ t('task_assignment.analytics.charts.by_pr_user') }}</span>
            </template>
            <BarChart
              v-if="prUserData.length > 0"
              :title="''"
              :data="prUserData.slice(0, 10).map(d => ({ name: d.username, value: d.count }))"
              color="#67c23a"
              height="300px"
            />
            <el-empty v-else :description="t('task_assignment.analytics.messages.no_data')" />
          </el-card>
        </el-col>

        <!-- By Project/Repository -->
        <el-col :xs="24" :md="12">
          <el-card class="chart-card" shadow="hover">
            <template #header>
              <span>{{ t('task_assignment.analytics.charts.by_project_repo') }}</span>
            </template>
            <PieChart
              v-if="projectData.length > 0"
              :title="''"
              :data="projectData.slice(0, 8).map(d => ({
                name: `${d.project_key}/${d.repository_slug}`,
                value: d.count
              }))"
              height="300px"
            />
            <el-empty v-else :description="t('task_assignment.analytics.messages.no_data')" />
          </el-card>
        </el-col>
      </el-row>

      <!-- Chart Row 3: Reviewer Analytics -->
      <el-row :gutter="20" class="chart-row">
        <!-- Assignments per Reviewer -->
        <el-col :xs="24" :md="12">
          <el-card class="chart-card" shadow="hover">
            <template #header>
              <span>{{ t('task_assignment.analytics.charts.assignments_per_reviewer') }}</span>
            </template>
            <BarChart
              v-if="reviewerData.length > 0"
              :title="''"
              :data="reviewerData.slice(0, 10).map(d => ({
                name: d.display_name || d.reviewer,
                value: d.assigned
              }))"
              color="#e6a23c"
              height="350px"
            />
            <el-empty v-else :description="t('task_assignment.analytics.messages.no_data')" />
          </el-card>
        </el-col>

        <!-- Scored Reviews per Reviewer -->
        <el-col :xs="24" :md="12">
          <el-card class="chart-card" shadow="hover">
            <template #header>
              <span>{{ t('task_assignment.analytics.charts.scored_per_reviewer') }}</span>
            </template>
            <ProgressChart
              v-if="reviewerProgressData.length > 0"
              :title="''"
              :data="reviewerProgressData.slice(0, 10)"
              height="350px"
            />
            <el-empty v-else :description="t('task_assignment.analytics.messages.no_data')" />
          </el-card>
        </el-col>
      </el-row>

      <!-- Chart Row 4: Scoring Trend -->
      <el-card class="chart-card" shadow="hover">
        <template #header>
          <div class="chart-header">
            <span>{{ t('task_assignment.analytics.charts.scoring_trend') }}</span>
            <div class="chart-actions">
              <el-tag type="success">{{ selectedPeriod }}</el-tag>
              <el-tooltip 
                :content="fullscreenChart === 'scoringTrend' ? t('common.exitFullscreen') : t('common.fullscreen')"
                placement="top"
              >
                <el-button 
                  text 
                  size="small" 
                  @click="toggleFullscreen('scoringTrend')"
                  :icon="fullscreenChart === 'scoringTrend' ? Close : FullScreen"
                />
              </el-tooltip>
            </div>
          </div>
        </template>
        <div ref="scoringTrendChartRef">
          <LineChart
            v-if="scoringTrendData.length > 0"
            :title="''"
            :data="scoringTrendData.map(d => ({ date: d.date, value: d.completed || 0 }))"
            color="#67c23a"
            height="350px"
            :axis-label-color="getAxisColors().axisLabelColor"
            :axis-line-color="getAxisColors().axisLineColor"
            :split-line-color="getAxisColors().splitLineColor"
          />
          <el-empty v-else :description="t('task_assignment.analytics.messages.no_data')" />
        </div>
      </el-card>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { Refresh, Document, TrendCharts, User, CircleCheck, FullScreen, Close } from '@element-plus/icons-vue'
import LineChart from '@/components/charts/LineChart.vue'
import BarChart from '@/components/charts/BarChart.vue'
import PieChart from '@/components/charts/PieChart.vue'
import ProgressChart from '@/components/charts/ProgressChart.vue'
import ProgressRing from '@/components/stats/ProgressRing.vue'
import Sparkline from '@/components/stats/Sparkline.vue'
import { taskAssignmentApi } from '@/api/taskAssignment'
import { usersApi } from '@/api/users'
import { projectsApi } from '@/api/projects'
import { useTaskAssignmentAnalytics } from '@/composables/useTaskAssignmentAnalytics'
import dayjs from 'dayjs'

const { t } = useI18n()

// Helper function to get chart axis colors based on theme
const getAxisColors = () => {
  const isDarkMode = document.documentElement.getAttribute('data-theme') === 'dark'
  return {
    axisLabelColor: isDarkMode ? '#cbd5e1' : '#64748b',
    axisLineColor: isDarkMode ? '#475569' : '#e2e8f0',
    splitLineColor: isDarkMode ? '#334155' : '#f1f5f9',
    nameColor: isDarkMode ? '#94a3b8' : '#64748b',
  }
}

// Composable
const {
  setReviews,
  aggregateByTimePeriod,
  aggregateByPRUser,
  aggregateByProject,
  aggregateByReviewer,
  getSummaryStats,
} = useTaskAssignmentAnalytics()

// State
const loading = ref(false)
const loadingProgress = ref('')
const selectedPeriod = ref<'daily' | 'weekly' | 'monthly'>('weekly')
const dateRange = ref<[Date, Date] | null>(null)
const projectFilter = ref('')
const reviewerFilter = ref('')

// Filter options
const projectOptions = ref<Array<{ label: string; value: string }>>([])
const reviewerOptions = ref<Array<{ label: string; value: string }>>([])

// Fullscreen state
const fullscreenChart = ref<'timeTrend' | 'scoringTrend' | null>(null)

// Chart refs for fullscreen
const timeTrendChartRef = ref<HTMLElement>()
const scoringTrendChartRef = ref<HTMLElement>()

// Computed data
const summaryStats = computed(() => getSummaryStats.value)

const timePeriodData = computed(() => aggregateByTimePeriod(selectedPeriod.value))
const prUserData = computed(() => aggregateByPRUser())
const projectData = computed(() => aggregateByProject())
const reviewerData = computed(() => aggregateByReviewer())

const reviewerProgressData = computed(() => {
  return reviewerData.value.map(r => ({
    label: r.display_name || r.reviewer,
    total: r.assigned,
    completed: r.completed,
    percentage: r.assigned > 0 ? (r.completed / r.assigned) * 100 : 0,
  }))
})

const scoringTrendData = computed(() => {
  // Use the same time period aggregation but show completed counts
  return timePeriodData.value
})

// Sparkline data for Avg Assignments (last 7 periods)
const avgAssignmentsSparkline = computed(() => {
  const data = timePeriodData.value.slice(-7)
  return data.map(d => d.count || 0)
})

// Animated counter state
const animatedTotalReviews = ref(0)
const animatedActiveReviews = ref(0)

// Animate counters on data load
watch(
  () => summaryStats.value.totalReviews,
  (newValue) => {
    animateCounter(animatedTotalReviews, newValue, 1000)
  }
)

watch(
  () => summaryStats.value.activeReviews,
  (newValue) => {
    animateCounter(animatedActiveReviews, newValue, 1000)
  }
)

// Counter animation helper
const animateCounter = (targetRef: any, targetValue: number, duration: number) => {
  const startValue = targetRef.value
  const startTime = performance.now()
  
  const updateCounter = (currentTime: number) => {
    const elapsed = currentTime - startTime
    const progress = Math.min(elapsed / duration, 1)
    
    // Ease-out cubic function
    const easeOut = 1 - Math.pow(1 - progress, 3)
    targetRef.value = Math.floor(startValue + (targetValue - startValue) * easeOut)
    
    if (progress < 1) {
      requestAnimationFrame(updateCounter)
    }
  }
  
  requestAnimationFrame(updateCounter)
}

// Toggle fullscreen for charts
const toggleFullscreen = (chartName: 'timeTrend' | 'scoringTrend') => {
  if (fullscreenChart.value === chartName) {
    // Exit fullscreen
    fullscreenChart.value = null
    document.exitFullscreen().catch(console.error)
  } else {
    // Enter fullscreen
    fullscreenChart.value = chartName
    const chartRef = 
      chartName === 'timeTrend' ? timeTrendChartRef.value :
      scoringTrendChartRef.value
    
    if (chartRef) {
      const cardElement = chartRef.closest('.chart-card')
      if (cardElement) {
        cardElement.requestFullscreen().catch(console.error)
      }
    }
  }
}

// Watch for theme changes and update charts
watch(
  () => document.documentElement.getAttribute('data-theme'),
  () => {
    // Charts will re-render with new theme colors automatically
    // due to reactive computed properties using getAxisColors()
  }
)

// Load filter options
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

// Load analytics data
const loadAnalytics = async () => {
  loading.value = true
  try {
    // Build query params
    const baseParams: any = {}

    if (projectFilter.value) {
      baseParams.project_key = projectFilter.value
    }

    if (reviewerFilter.value) {
      baseParams.reviewer = reviewerFilter.value
    }

    if (dateRange.value && dateRange.value.length === 2) {
      baseParams.date_from = dayjs(dateRange.value[0]).format('YYYY-MM-DD')
      baseParams.date_to = dayjs(dateRange.value[1]).format('YYYY-MM-DD')
    }

    // Fetch all reviews by paginating (max 100 per request)
    const allReviews: any[] = []
    let currentPage = 1
    const pageSize = 100 // Backend max limit
    let hasMore = true
    let totalRecords = 0

    while (hasMore) {
      loadingProgress.value = `Loading page ${currentPage}...`
      
      const params = {
        ...baseParams,
        page: currentPage,
        page_size: pageSize,
      }

      const response = await taskAssignmentApi.getReviewsForAnalytics(params)
      
      if (response.items && response.items.length > 0) {
        allReviews.push(...response.items)
        totalRecords = response.total
        
        // Update progress
        const loadedCount = allReviews.length
        loadingProgress.value = `Loaded ${loadedCount} of ${totalRecords} reviews...`
        
        // Check if there are more pages
        const totalPages = Math.ceil(response.total / pageSize)
        if (currentPage >= totalPages || response.items.length < pageSize) {
          hasMore = false
        } else {
          currentPage++
        }
      } else {
        hasMore = false
      }
    }

    loadingProgress.value = 'Processing data...'

    // Set data in composable for aggregation
    setReviews(allReviews)

    if (allReviews.length === 0) {
      ElMessage.info(t('task_assignment.analytics.messages.no_data'))
    }
  } catch (error) {
    console.error('Failed to load analytics data:', error)
    ElMessage.error(t('task_assignment.analytics.messages.load_failed'))
  } finally {
    loading.value = false
    loadingProgress.value = ''
  }
}

// Refresh data
const refreshData = () => {
  loadAnalytics()
}

// Initialize
onMounted(() => {
  loadFilterOptions()
  loadAnalytics()
})
</script>

<style scoped>
.task-assignment-analytics {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.page-header h1 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.filters-card {
  margin-bottom: 20px;
}

.filter-form {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.summary-cards {
  margin-bottom: 20px;
}

.summary-cards {
  margin-bottom: 24px;
}

/* ===== Base Stat Card Styles ===== */
.stat-card {
  position: relative;
  border-radius: 16px;
  padding: 24px;
  height: 180px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
}

.stat-card__content {
  position: relative;
  z-index: 2;
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.stat-card__icon {
  color: var(--el-text-color-primary);
  opacity: 0.9;
  margin-bottom: 12px;
}

.stat-card__value {
  font-size: 36px;
  font-weight: 700;
  color: var(--el-text-color-primary);
  line-height: 1.2;
  margin-bottom: 8px;
}

.stat-card__label {
  font-size: 14px;
  color: var(--el-text-color-secondary);
  font-weight: 500;
}

.stat-card__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  margin-bottom: 12px;
}

/* ===== Card 1: Gradient Border ===== */
.stat-card--gradient-border {
  background: var(--el-bg-color);
  border: 3px solid transparent;
  background-clip: padding-box;
}

[data-theme='dark'] .stat-card--gradient-border {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.stat-card--gradient-border::before {
  content: '';
  position: absolute;
  top: -3px;
  left: -3px;
  right: -3px;
  bottom: -3px;
  background: linear-gradient(135deg, #3b82f6 0%, #06b6d4 50%, #8b5cf6 100%);
  border-radius: 16px;
  z-index: 0;
  animation: gradient-rotate 8s linear infinite;
}

.stat-card--gradient-border .stat-card__border {
  position: absolute;
  inset: 0;
  border-radius: 16px;
  padding: 3px;
  background: linear-gradient(135deg, #3b82f6 0%, #06b6d4 50%, #8b5cf6 100%);
  -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
  pointer-events: none;
  box-shadow: inset 0 0 20px rgba(59, 130, 246, 0.1);
}

.stat-card--gradient-border:hover {
  transform: translateY(-4px) scale(1.02);
  box-shadow: 0 12px 24px rgba(59, 130, 246, 0.3);
}

.stat-card--gradient-border .stat-card__trend {
  margin-top: 12px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 12px;
  background: rgba(59, 130, 246, 0.08);
  border-radius: 12px;
  transition: all 0.3s ease;
}

.stat-card--gradient-border:hover .stat-card__trend {
  background: rgba(59, 130, 246, 0.15);
}

.animated-counter {
  font-variant-numeric: tabular-nums;
}

@keyframes gradient-rotate {
  0% { filter: hue-rotate(0deg); }
  100% { filter: hue-rotate(360deg); }
}

/* ===== Card 2: Glassmorphism ===== */
.stat-card--glassmorphism {
  background: rgba(255, 255, 255, 0.15);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.25);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1), inset 0 1px 0 rgba(255, 255, 255, 0.2);
}

[data-theme='dark'] .stat-card--glassmorphism {
  background: rgba(30, 30, 30, 0.5);
  border: 1px solid rgba(255, 255, 255, 0.15);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.1);
}

.stat-card--glassmorphism .glass-overlay {
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.15) 0%, rgba(118, 75, 162, 0.15) 100%);
  pointer-events: none;
  animation: glass-shimmer 4s ease-in-out infinite;
}

@keyframes glass-shimmer {
  0%, 100% {
    opacity: 0.5;
  }
  50% {
    opacity: 1;
  }
}

.stat-card--glassmorphism:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 40px rgba(102, 126, 234, 0.2);
}

.live-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #67c23a;
  font-weight: 600;
  padding: 4px 10px;
  background: rgba(103, 194, 58, 0.1);
  border-radius: 12px;
  border: 1px solid rgba(103, 194, 58, 0.2);
  transition: all 0.3s ease;
}

.stat-card--glassmorphism:hover .live-indicator {
  background: rgba(103, 194, 58, 0.15);
  border-color: rgba(103, 194, 58, 0.3);
}

.pulse-dot {
  width: 8px;
  height: 8px;
  background: #67c23a;
  border-radius: 50%;
  animation: pulse 2s ease-in-out infinite;
  box-shadow: 0 0 8px rgba(103, 194, 58, 0.6);
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.5;
    transform: scale(1.2);
  }
}

/* ===== Card 3: Minimalist + Sparkline ===== */
.stat-card--minimalist {
  background: var(--el-bg-color);
  border-left: 4px solid #e6a23c;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

[data-theme='dark'] .stat-card--minimalist {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}

.stat-card--minimalist .stat-card__accent {
  position: absolute;
  top: 0;
  left: 0;
  width: 4px;
  height: 100%;
  background: linear-gradient(180deg, #e6a23c 0%, #f5d9a0 100%);
}

.stat-card--minimalist:hover {
  transform: translateX(4px);
  box-shadow: 0 4px 16px rgba(230, 162, 60, 0.2);
}

.stat-card--minimalist .minimalist-value {
  font-size: 42px;
  margin-top: 8px;
}

/* ===== Card 4: Progress Ring ===== */
.stat-card--progress-ring {
  background: var(--el-bg-color);
  border-radius: 16px;
}

[data-theme='dark'] .stat-card--progress-ring {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.stat-card--progress-ring:hover {
  transform: scale(1.03);
  box-shadow: 0 8px 24px rgba(103, 194, 58, 0.2);
}

.stat-card--progress-ring .ring-label {
  margin-top: 12px;
}

.charts-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.chart-card {
  margin-bottom: 0;
}

.chart-row {
  margin-bottom: 0;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.chart-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* Responsive adjustments */
@media (max-width: 768px) {
  .task-assignment-analytics {
    padding: 12px;
  }

  .page-header {
    flex-direction: column;
    gap: 12px;
    align-items: flex-start;
  }

  .filter-form {
    flex-direction: column;
  }

  .filter-form :deep(.el-form-item) {
    width: 100%;
  }

  .filter-form :deep(.el-form-item__content) {
    width: 100%;
  }

  .summary-value {
    font-size: 24px;
  }
}

/* Dark theme adjustments */
[data-theme='dark'] .summary-icon {
  opacity: 0.9;
}
</style>
