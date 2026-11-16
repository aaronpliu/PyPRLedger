<template>
  <div class="insights-page">
    <div class="page-head">
      <div class="titles">
        <h2>{{ t('insights.title') }}</h2>
        <p class="subtitle">
          {{ t('insights.subtitle') }}
          <span v-if="lastUpdated" class="updated" data-test="insights-updated">
            · {{ t('insights.updated_at', { time: lastUpdated }) }}
          </span>
        </p>
      </div>

      <div class="controls">
        <RepositoryScopePicker v-model="scope" />
        <el-select v-model="days" class="narrow" data-test="insights-days">
          <el-option v-for="option in DAY_OPTIONS" :key="option" :label="t('insights.days_option', { days: option })" :value="option" />
        </el-select>
        <el-select v-model="period" class="narrow" data-test="insights-period">
          <el-option :label="t('insights.period_daily')" value="daily" />
          <el-option :label="t('insights.period_weekly')" value="weekly" />
          <el-option :label="t('insights.period_monthly')" value="monthly" />
        </el-select>
        <el-tooltip :content="t('insights.refresh')" placement="top">
          <el-button :icon="Refresh" circle data-test="insights-refresh" @click="load(false)" />
        </el-tooltip>
      </div>
    </div>

    <el-empty
      v-if="!scope.projectKey"
      :description="t('insights.select_project_hint')"
      data-test="insights-no-scope"
    />

    <template v-else>
      <div v-loading="loading" class="surface">
        <!-- The numbers first: what the repository looks like before any chart. -->
        <div class="kpi-grid" data-test="insights-kpis">
          <div v-for="card in kpiCards" :key="card.key" class="kpi-card" :class="`kpi-${card.tone}`">
            <span class="kpi-label">{{ card.label }}</span>
            <span class="kpi-value" :data-test="`insights-kpi-${card.key}`">{{ card.value }}</span>
            <span v-if="card.hint" class="kpi-hint">{{ card.hint }}</span>
          </div>
        </div>

        <el-row v-if="reading" :gutter="16" class="chart-grid">
          <el-col :xs="24" :md="12">
            <el-card shadow="never" class="chart-card">
              <template #header>{{ t('insights.chart_trend') }}</template>
              <MultiLineChart :series="trendSeries" height="300px" />
            </el-card>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-card shadow="never" class="chart-card">
              <template #header>{{ t('insights.chart_score') }}</template>
              <LineChart :data="scoreSeries" :color="SCORE_COLOR" height="300px" />
            </el-card>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-card shadow="never" class="chart-card">
              <template #header>{{ t('insights.chart_status') }}</template>
              <PieChart :data="statusData" height="300px" />
            </el-card>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-card shadow="never" class="chart-card">
              <template #header>{{ t('insights.chart_reviewers') }}</template>
              <BarChart :data="reviewerData" height="300px" />
            </el-card>
          </el-col>
        </el-row>

        <el-card v-if="reading" shadow="never" class="recent-card">
          <template #header>{{ t('insights.recent_title') }}</template>
          <el-table :data="reading.recent" style="width: 100%" data-test="insights-recent">
            <el-table-column :label="t('insights.col_pr')" min-width="200">
              <template #default="{ row }">
                <span class="pr-id">#{{ row.pull_request_id }}</span>
                <span class="pr-repo">{{ row.project_key }} / {{ row.repository_slug }}</span>
              </template>
            </el-table-column>
            <el-table-column :label="t('insights.col_status')" width="120">
              <template #default="{ row }">
                <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column :label="t('insights.col_score')" width="120">
              <template #default="{ row }">
                <span v-if="row.avg_score" class="score">{{ row.avg_score.toFixed(1) }}</span>
                <span v-else class="muted">—</span>
              </template>
            </el-table-column>
            <el-table-column :label="t('insights.col_created')" width="180">
              <template #default="{ row }">
                <span class="muted">{{ formatDate(row.created_date) }}</span>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Refresh } from '@element-plus/icons-vue'
import MultiLineChart from '@/components/charts/MultiLineChart.vue'
import LineChart from '@/components/charts/LineChart.vue'
import PieChart from '@/components/charts/PieChart.vue'
import BarChart from '@/components/charts/BarChart.vue'
import RepositoryScopePicker, {
  type RepositoryScope,
} from '@/components/insights/RepositoryScopePicker.vue'
import { insightsApi, type RepositoryInsights } from '@/api/insights'

const { t } = useI18n()

const DAY_OPTIONS = [7, 30, 90, 180]
// A dashboard is read while it is on screen; a minute-old reading is close
// enough, and the server caches each one for that long anyway.
const POLL_INTERVAL_MS = 30_000

const SCORE_COLOR = '#e6a23c'
const REVIEW_COLOR = '#409eff'
const ASSIGNED_COLOR = '#67c23a'
const COMPLETED_COLOR = '#909399'

const scope = ref<RepositoryScope>({ projectKey: '', repositorySlug: '' })
const days = ref(30)
const period = ref<'daily' | 'weekly' | 'monthly'>('weekly')

const reading = ref<RepositoryInsights | null>(null)
const loading = ref(false)
const lastUpdated = ref('')

let pollTimer: ReturnType<typeof setInterval> | null = null

function percent(value: number): string {
  return `${Math.round(value * 100)}%`
}

const kpiCards = computed(() => {
  const kpis = reading.value?.kpis
  return [
    {
      key: 'reviews_total',
      label: t('insights.kpi_reviews_total'),
      value: kpis?.reviews_total ?? 0,
      tone: 'neutral',
    },
    {
      key: 'reviews_open',
      label: t('insights.kpi_reviews_open'),
      value: kpis?.reviews_open ?? 0,
      tone: 'info',
    },
    {
      key: 'avg_score',
      label: t('insights.kpi_avg_score'),
      value: (kpis?.avg_score ?? 0).toFixed(1),
      tone: 'warning',
    },
    {
      key: 'good_rate',
      label: t('insights.kpi_good_rate'),
      value: percent(kpis?.good_suggestion_rate ?? 0),
      tone: 'success',
      hint: t('insights.kpi_good_rate_hint'),
    },
    {
      key: 'unassigned',
      label: t('insights.kpi_unassigned'),
      value: kpis?.unassigned_count ?? 0,
      tone: (kpis?.unassigned_count ?? 0) > 0 ? 'danger' : 'neutral',
    },
    {
      key: 'reviewers',
      label: t('insights.kpi_active_reviewers'),
      value: kpis?.active_reviewers ?? 0,
      tone: 'neutral',
      hint: t('insights.kpi_in_progress_hint', { count: kpis?.assigned_in_progress ?? 0 }),
    },
  ]
})

const trendSeries = computed(() => {
  const points = reading.value?.trends ?? []
  return [
    {
      name: t('insights.series_reviews'),
      color: REVIEW_COLOR,
      data: points.map((point) => ({ date: point.period_start, value: point.reviews })),
    },
    {
      name: t('insights.series_assigned'),
      color: ASSIGNED_COLOR,
      data: points.map((point) => ({ date: point.period_start, value: point.assigned })),
    },
    {
      name: t('insights.series_completed'),
      color: COMPLETED_COLOR,
      data: points.map((point) => ({ date: point.period_start, value: point.completed })),
    },
  ]
})

const scoreSeries = computed(() =>
  (reading.value?.trends ?? []).map((point) => ({
    date: point.period_start,
    value: point.avg_score,
  })),
)

const statusData = computed(() =>
  (reading.value?.breakdown.by_status ?? []).map((item) => ({
    name: statusLabel(item.key),
    value: item.count,
  })),
)

const reviewerData = computed(() =>
  (reading.value?.breakdown.by_reviewer ?? []).map((item) => ({
    name: item.reviewer,
    value: item.assigned,
  })),
)

function statusLabel(status: string): string {
  const key = `insights.status_${status}`
  return t(key)
}

function statusType(status: string): 'success' | 'danger' | 'info' | 'warning' {
  if (status === 'merged') return 'success'
  if (status === 'closed') return 'danger'
  if (status === 'draft') return 'info'
  return 'warning'
}

function formatDate(value: string): string {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleString()
}

async function load(quiet = true) {
  if (!scope.value.projectKey) {
    reading.value = null
    return
  }
  if (!quiet) loading.value = true
  try {
    reading.value = await insightsApi.getRepositoryInsights({
      project_key: scope.value.projectKey,
      repository_slug: scope.value.repositorySlug || undefined,
      days: days.value,
      period: period.value,
    })
    lastUpdated.value = new Date().toLocaleTimeString()
  } catch {
    // A failed poll keeps the last good reading on screen instead of blanking
    // the page under the reader.
  } finally {
    loading.value = false
  }
}

function startPolling() {
  stopPolling()
  pollTimer = setInterval(() => {
    if (!document.hidden) void load()
  }, POLL_INTERVAL_MS)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

// A page left in a background tab has nobody reading it: no polling until it is
// back, and a fresh reading the moment it returns.
function handleVisibility() {
  if (document.hidden) {
    stopPolling()
  } else {
    void load()
    startPolling()
  }
}

watch(
  [() => scope.value.projectKey, () => scope.value.repositorySlug, days, period],
  () => load(false),
)

onMounted(() => {
  startPolling()
  document.addEventListener('visibilitychange', handleVisibility)
})

onUnmounted(() => {
  stopPolling()
  document.removeEventListener('visibilitychange', handleVisibility)
})
</script>

<style scoped>
.insights-page {
  padding: 0 4px;
}

.page-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
}

.titles h2 {
  margin: 0;
  font-size: 18px;
}

.subtitle {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.updated {
  margin-left: 4px;
}

.controls {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.narrow {
  width: 120px;
}

.surface {
  min-height: 200px;
}

/* The six numbers a reader scans before reading any chart. */
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.kpi-card {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px 14px;
  border: 1px solid var(--el-border-color-lighter);
  border-left-width: 3px;
  border-radius: 6px;
  background: var(--el-bg-color);
}

.kpi-neutral {
  border-left-color: var(--el-border-color);
}

.kpi-info {
  border-left-color: var(--el-color-info);
}

.kpi-warning {
  border-left-color: var(--el-color-warning);
}

.kpi-success {
  border-left-color: var(--el-color-success);
}

.kpi-danger {
  border-left-color: var(--el-color-danger);
}

.kpi-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.kpi-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--el-text-color-primary);
}

.kpi-hint {
  font-size: 11px;
  color: var(--el-text-color-placeholder);
}

.chart-grid {
  margin-bottom: 8px;
}

.chart-card {
  margin-bottom: 16px;
}

.recent-card {
  margin-bottom: 16px;
}

.pr-id {
  font-weight: 600;
}

.pr-repo {
  margin-left: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.score {
  font-weight: 600;
  color: var(--el-color-warning);
}

.muted {
  color: var(--el-text-color-secondary);
}
</style>
