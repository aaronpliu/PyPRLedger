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

    <!-- Summary Cards -->
    <el-row :gutter="20" class="summary-cards">
      <el-col :xs="24" :sm="12" :md="6">
        <el-card shadow="hover" class="summary-card">
          <div class="summary-content">
            <div class="summary-icon total">
              <el-icon :size="32"><Document /></el-icon>
            </div>
            <div class="summary-info">
              <div class="summary-value">{{ summaryStats.totalReviews }}</div>
              <div class="summary-label">{{ t('task_assignment.analytics.summary.total_reviews') }}</div>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :sm="12" :md="6">
        <el-card shadow="hover" class="summary-card">
          <div class="summary-content">
            <div class="summary-icon active">
              <el-icon :size="32"><TrendCharts /></el-icon>
            </div>
            <div class="summary-info">
              <div class="summary-value">{{ summaryStats.activeReviews }}</div>
              <div class="summary-label">{{ t('task_assignment.analytics.summary.active_reviews') }}</div>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :sm="12" :md="6">
        <el-card shadow="hover" class="summary-card">
          <div class="summary-content">
            <div class="summary-icon avg">
              <el-icon :size="32"><User /></el-icon>
            </div>
            <div class="summary-info">
              <div class="summary-value">{{ summaryStats.avgAssignments }}</div>
              <div class="summary-label">{{ t('task_assignment.analytics.summary.avg_assignments') }}</div>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :sm="12" :md="6">
        <el-card shadow="hover" class="summary-card">
          <div class="summary-content">
            <div class="summary-icon rate">
              <el-icon :size="32"><CircleCheck /></el-icon>
            </div>
            <div class="summary-info">
              <div class="summary-value">{{ summaryStats.scoringRate }}%</div>
              <div class="summary-label">{{ t('task_assignment.analytics.summary.scoring_rate') }}</div>
            </div>
          </div>
        </el-card>
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
              height="300px"
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

.summary-card {
  height: 100%;
}

.summary-content {
  display: flex;
  align-items: center;
  gap: 16px;
}

.summary-icon {
  width: 60px;
  height: 60px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
}

.summary-icon.total {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.summary-icon.active {
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
}

.summary-icon.avg {
  background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
}

.summary-icon.rate {
  background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);
}

.summary-info {
  flex: 1;
}

.summary-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--el-text-color-primary);
  line-height: 1.2;
}

.summary-label {
  font-size: 14px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
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
