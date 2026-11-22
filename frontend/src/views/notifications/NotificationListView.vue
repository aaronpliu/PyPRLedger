<template>
  <div class="notification-page">
    <!-- Page header -->
    <div class="page-header">
      <div class="header-title-group">
        <h2>{{ t('notifications.title') }}</h2>
        <el-tooltip :content="t('notifications.visibility_tooltip')" placement="right">
          <el-icon><QuestionFilled /></el-icon>
        </el-tooltip>
      </div>
      <div class="header-actions">
        <el-button type="primary" @click="markAllAsRead" :disabled="unreadCount === 0">
          {{ t('notifications.mark_all_read') }}
        </el-button>
        <el-button @click="loadNotifications">
          <el-icon><Refresh /></el-icon>
        </el-button>
      </div>
    </div>

    <!-- Stats chips + filters share one toolbar row so the board below keeps
         every pixel of the page height -->
    <div class="toolbar">
      <div class="stat-chips" v-if="stats">
        <span class="stat-chip">
          {{ t('notifications.stat_total') }} <b>{{ stats.total_count }}</b>
        </span>
        <span class="stat-chip chip-unread" v-if="stats.unread_count > 0">
          {{ t('notifications.stat_unread') }} <b>{{ stats.unread_count }}</b>
        </span>
        <span class="stat-chip chip-high" v-if="(stats.by_priority?.high || 0) > 0">
          {{ t('notifications.stat_high_priority') }} <b>{{ stats.by_priority?.high || 0 }}</b>
        </span>
        <span class="stat-chip chip-urgent" v-if="(stats.by_priority?.urgent || 0) > 0">
          {{ t('notifications.stat_urgent') }} <b>{{ stats.by_priority?.urgent || 0 }}</b>
        </span>
      </div>

      <div class="filters">
        <el-select v-model="filters.type" clearable :placeholder="t('notifications.filter_type')" style="width: 170px">
          <el-option :label="t('notifications.all_types')" value="" />
          <el-option :label="t('notifications.type_review_assigned')" value="review_assigned" />
          <el-option :label="t('notifications.type_review_completed')" value="review_completed" />
          <el-option :label="t('notifications.type_delegation_expiry')" value="delegation_expiry" />
          <el-option :label="t('notifications.type_system_alert')" value="system_alert" />
        </el-select>

        <el-select v-model="filters.priority" clearable :placeholder="t('notifications.filter_priority')" style="width: 130px">
          <el-option :label="t('notifications.all_priorities')" value="" />
          <el-option :label="t('notifications.priority_urgent')" value="urgent" />
          <el-option :label="t('notifications.priority_high')" value="high" />
          <el-option :label="t('notifications.priority_normal')" value="normal" />
          <el-option :label="t('notifications.priority_low')" value="low" />
        </el-select>

        <el-select v-model="filters.is_read" clearable :placeholder="t('notifications.filter_status')" style="width: 130px">
          <el-option :label="t('notifications.status_unread')" :value="false" />
          <el-option :label="t('notifications.status_read')" :value="true" />
        </el-select>

        <el-button type="primary" @click="applyFilters">{{ t('common.apply') }}</el-button>
        <el-button @click="resetFilters">{{ t('common.reset') }}</el-button>
      </div>
    </div>

    <!-- Priority board: one column per level, most severe first. The board
         itself fills the page; only the columns scroll, so urgent items stay
         on screen no matter how deep the backlog runs. -->
    <div class="board" v-loading="loading">
      <el-empty
        v-if="!loading && notifications.length === 0"
        :description="t('notifications.empty_state')"
        class="board-empty"
      />

      <section
        v-for="col in columns"
        :key="col.key"
        class="board-column"
        :class="`column-${col.key}`"
      >
        <header class="column-header">
          <span class="column-dot"></span>
          <span class="column-title">{{ col.label }}</span>
          <span class="column-count">{{ col.items.length }}</span>
          <span class="column-unread" v-if="col.unread > 0">{{ col.unread }}</span>
        </header>

        <div class="column-body">
          <div v-if="col.items.length === 0" class="column-empty">
            {{ t('notifications.column_empty') }}
          </div>
          <article
            v-for="notif in col.items"
            :key="notif.id"
            class="notif-card"
            :class="{ 'is-read': notif.is_read }"
            @click="handleNotificationClick(notif)"
          >
            <div class="card-top">
              <span class="unread-dot" v-if="!notif.is_read"></span>
              <span class="card-type">{{ getTypeLabel(notif.type) }}</span>
              <span class="card-time">{{ formatTime(notif.created_at) }}</span>
            </div>

            <h4 class="card-title">{{ notif.title }}</h4>
            <p class="card-message">{{ notif.message }}</p>

            <div class="card-actions">
              <el-link
                v-if="notif.related_id"
                type="primary"
                :underline="false"
                @click.stop="navigateToRelated(notif)"
              >
                {{ t('notifications.view_related', { target: getRelatedTypeLabel(notif.related_type) }) }}
              </el-link>
              <span class="card-actions-spacer"></span>
              <el-button
                v-if="!notif.is_read"
                size="small"
                type="primary"
                link
                @click.stop="markAsRead(notif.id)"
              >
                {{ t('notifications.mark_read') }}
              </el-button>
              <el-tooltip :content="t('common.delete')" placement="top">
                <el-button size="small" type="danger" link @click.stop="deleteNotification(notif.id)">
                  <el-icon><Delete /></el-icon>
                </el-button>
              </el-tooltip>
            </div>
          </article>
        </div>
      </section>
    </div>

    <!-- Pagination -->
    <div class="pagination-section">
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        @size-change="handleSizeChange"
        @current-change="handlePageChange"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, QuestionFilled, Delete } from '@element-plus/icons-vue'
import {
  notificationsApi,
  type Notification,
  type NotificationStats,
} from '@/api/notifications'

const router = useRouter()
const { t } = useI18n()

const loading = ref(false)
const notifications = ref<Notification[]>([])
const stats = ref<NotificationStats | null>(null)
const unreadCount = ref(0)

const filters = ref({
  type: '',
  priority: '',
  is_read: undefined as boolean | undefined,
})

const pagination = ref({
  page: 1,
  pageSize: 20,
  total: 0,
})

let pollingInterval: number | null = null

// The board reads left to right by severity; a priority filter simply empties
// the columns it excludes rather than changing the layout
const PRIORITY_ORDER = ['urgent', 'high', 'normal', 'low'] as const

const columns = computed(() =>
  PRIORITY_ORDER.map((priority) => {
    const items = notifications.value.filter((n) => n.priority === priority)
    return {
      key: priority,
      label: getPriorityLabel(priority),
      unread: items.filter((n) => !n.is_read).length,
      items,
    }
  }),
)

onMounted(() => {
  loadNotifications()
  loadStats()
  startPolling()
})

onUnmounted(() => {
  stopPolling()
})

async function loadNotifications() {
  loading.value = true
  try {
    const response = await notificationsApi.getNotifications({
      page: pagination.value.page,
      page_size: pagination.value.pageSize,
      notification_type: filters.value.type || undefined,
      priority: filters.value.priority || undefined,
      is_read: filters.value.is_read,
    })

    notifications.value = response.items
    pagination.value.total = response.total
    unreadCount.value = response.items.filter((n: Notification) => !n.is_read).length
  } catch (error) {
    ElMessage.error(t('notifications.load_error'))
    console.error('Failed to load notifications:', error)
  } finally {
    loading.value = false
  }
}

async function loadStats() {
  try {
    stats.value = await notificationsApi.getStats()
    if (stats.value) {
      unreadCount.value = stats.value.unread_count
    }
  } catch (error) {
    console.error('Failed to load stats:', error)
  }
}

async function applyFilters() {
  pagination.value.page = 1
  await loadNotifications()
}

function resetFilters() {
  filters.value = {
    type: '',
    priority: '',
    is_read: undefined,
  }
  pagination.value.page = 1
  loadNotifications()
}

async function markAsRead(id: number) {
  try {
    await notificationsApi.markAsRead(id)
    ElMessage.success(t('notifications.marked_read'))
    await loadNotifications()
    await loadStats()
  } catch (error) {
    ElMessage.error(t('notifications.mark_read_error'))
    console.error('Failed to mark as read:', error)
  }
}

async function markAllAsRead() {
  try {
    await ElMessageBox.confirm(
      t('notifications.confirm_mark_all'),
      t('common.confirm'),
      {
        confirmButtonText: t('common.confirm'),
        cancelButtonText: t('common.cancel'),
        type: 'warning',
      }
    )

    await notificationsApi.markAllAsRead()
    ElMessage.success(t('notifications.all_marked_read'))
    await loadNotifications()
    await loadStats()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(t('notifications.mark_all_error'))
      console.error('Failed to mark all as read:', error)
    }
  }
}

async function deleteNotification(id: number) {
  try {
    await ElMessageBox.confirm(
      t('notifications.confirm_delete'),
      t('common.confirm'),
      {
        confirmButtonText: t('common.confirm'),
        cancelButtonText: t('common.cancel'),
        type: 'warning',
      }
    )

    await notificationsApi.deleteNotification(id)
    ElMessage.success(t('notifications.deleted'))
    await loadNotifications()
    await loadStats()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(t('notifications.delete_error'))
      console.error('Failed to delete notification:', error)
    }
  }
}

function handleNotificationClick(notif: Notification) {
  if (!notif.is_read) {
    markAsRead(notif.id)
  }
  if (notif.related_id) {
    navigateToRelated(notif)
  }
}

function navigateToRelated(notif: Notification) {
  if (!notif.related_id || !notif.related_type) return

  switch (notif.related_type) {
    case 'pull_request':
      // Navigate to reviews list filtered by PR ID with from_notification flag
      // This ensures archived/scored reviews are visible
      router.push(`/reviews?pr_id=${notif.related_id}&from_notification=true`)
      break
    case 'project':
      router.push(`/projects/${notif.related_id}`)
      break
    case 'delegation':
      // Delegation notices point at the delegation board, where access can
      // be extended or revoked
      router.push('/delegations')
      break
    default:
      ElMessage.info(t('notifications.no_related_link'))
  }
}

function handlePageChange(page: number) {
  pagination.value.page = page
  loadNotifications()
}

function handleSizeChange(size: number) {
  pagination.value.pageSize = size
  pagination.value.page = 1
  loadNotifications()
}

function getPriorityLabel(priority: string): string {
  const labels: Record<string, string> = {
    urgent: t('notifications.priority_urgent'),
    high: t('notifications.priority_high'),
    normal: t('notifications.priority_normal'),
    low: t('notifications.priority_low'),
  }
  return labels[priority] || priority
}

function getTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    review_assigned: t('notifications.type_review_assigned'),
    review_completed: t('notifications.type_review_completed'),
    delegation_expiry: t('notifications.type_delegation_expiry'),
    system_alert: t('notifications.type_system_alert'),
  }
  return labels[type] || type
}

function getRelatedTypeLabel(type?: string): string {
  if (!type) return ''
  const labels: Record<string, string> = {
    pull_request: 'PR',
    project: 'Project',
  }
  return labels[type] || type
}

function formatTime(dateString: string): string {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 1) return t('time.just_now')
  if (diffMins < 60) return `${diffMins} ${t('time.minutes_ago')}`
  if (diffHours < 24) return `${diffHours} ${t('time.hours_ago')}`
  if (diffDays < 7) return `${diffDays} ${t('time.days_ago')}`

  return date.toLocaleDateString()
}

function startPolling() {
  pollingInterval = window.setInterval(() => {
    loadStats()
  }, 30000) // Poll every 30 seconds
}

function stopPolling() {
  if (pollingInterval) {
    clearInterval(pollingInterval)
    pollingInterval = null
  }
}
</script>

<style scoped>
/* The page is a flex column that fills the layout's main area: the board
   stretches to whatever the window gives it and only its columns scroll */
.notification-page {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* ---- Page header ---- */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.header-title-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-title-group h2 {
  margin: 0;
  font-size: 20px;
}

.header-title-group .el-icon {
  color: var(--el-text-color-secondary);
  cursor: help;
}

.header-actions {
  display: flex;
  gap: 8px;
}

/* ---- Toolbar: stats and filters on one row ---- */
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.stat-chips {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.stat-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  background: var(--el-fill-color-light);
  border: 1px solid var(--el-border-color-lighter);
}

.stat-chip b {
  font-size: 13px;
  color: var(--el-text-color-primary);
}

.stat-chip.chip-unread {
  background: var(--el-color-danger-light-9);
  border-color: var(--el-color-danger-light-7);
  color: var(--el-color-danger);
}

.stat-chip.chip-unread b {
  color: var(--el-color-danger);
}

.stat-chip.chip-high {
  background: var(--el-color-warning-light-9);
  border-color: var(--el-color-warning-light-7);
  color: var(--el-color-warning);
}

.stat-chip.chip-high b {
  color: var(--el-color-warning);
}

.stat-chip.chip-urgent {
  background: var(--el-color-danger-light-9);
  border-color: var(--el-color-danger-light-5);
  color: var(--el-color-danger);
  font-weight: 600;
}

.stat-chip.chip-urgent b {
  color: var(--el-color-danger);
}

.filters {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

/* ---- Board ---- */
.board {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  align-items: stretch;
}

.board-empty {
  grid-column: 1 / -1;
}

.board-column {
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: var(--el-fill-color-lighter);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 12px;
  overflow: hidden;
}

.column-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  background: var(--el-bg-color);
  flex-shrink: 0;
}

.column-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.column-urgent .column-dot {
  background: var(--el-color-danger);
  box-shadow: 0 0 0 3px var(--el-color-danger-light-8);
}

.column-high .column-dot {
  background: var(--el-color-warning);
  box-shadow: 0 0 0 3px var(--el-color-warning-light-8);
}

.column-normal .column-dot {
  background: var(--el-color-primary);
  box-shadow: 0 0 0 3px var(--el-color-primary-light-8);
}

.column-low .column-dot {
  background: var(--el-color-success);
  box-shadow: 0 0 0 3px var(--el-color-success-light-8);
}

.column-title {
  font-weight: 600;
  font-size: 13px;
  color: var(--el-text-color-primary);
}

.column-count {
  margin-left: auto;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  background: var(--el-fill-color);
  border-radius: 10px;
  padding: 1px 8px;
}

.column-unread {
  font-size: 12px;
  font-weight: 700;
  color: var(--el-color-danger);
  background: var(--el-color-danger-light-9);
  border-radius: 10px;
  padding: 1px 8px;
}

/* the column scrolls, the page does not */
.column-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* the column keeps its slot on the board even when it has nothing to hold */
.column-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  border: 1px dashed var(--el-border-color-light);
  border-radius: 10px;
}

/* ---- Card ---- */
.notif-card {
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  border-left: 3px solid var(--el-border-color-light);
  border-radius: 10px;
  padding: 10px 12px;
  cursor: pointer;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.notif-card:hover {
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.08);
}

.column-urgent .notif-card {
  border-left-color: var(--el-color-danger);
}

.column-high .notif-card {
  border-left-color: var(--el-color-warning);
}

.column-normal .notif-card {
  border-left-color: var(--el-color-primary);
}

.column-low .notif-card {
  border-left-color: var(--el-color-success);
}

.notif-card.is-read {
  opacity: 0.72;
}

.notif-card.is-read .card-title {
  font-weight: 500;
}

.card-top {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}

.unread-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--el-color-danger);
  flex-shrink: 0;
}

.card-type {
  font-size: 11px;
  color: var(--el-text-color-secondary);
  background: var(--el-fill-color);
  border-radius: 4px;
  padding: 1px 6px;
}

.card-time {
  margin-left: auto;
  font-size: 11px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
}

.card-title {
  margin: 0 0 4px 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  line-height: 1.4;
  overflow-wrap: anywhere;
}

.card-message {
  margin: 0 0 8px 0;
  font-size: 12px;
  color: var(--el-text-color-regular);
  line-height: 1.5;
  overflow-wrap: anywhere;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.card-actions-spacer {
  flex: 1;
}

/* ---- Pagination ---- */
.pagination-section {
  display: flex;
  justify-content: center;
  flex-shrink: 0;
}

/* ---- Responsive: the four columns fold onto fewer tracks ---- */
@media (max-width: 1280px) {
  .board {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    overflow-y: auto;
  }

  .board-column {
    min-height: 320px;
  }
}

@media (max-width: 720px) {
  .board {
    grid-template-columns: 1fr;
  }

  .toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .filters {
    justify-content: flex-start;
  }
}
</style>
