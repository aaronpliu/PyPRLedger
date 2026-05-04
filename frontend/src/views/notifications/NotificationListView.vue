<template>
  <div class="notification-list-container">
    <el-card>
      <template #header>
        <div class="card-header">
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
      </template>

      <!-- Filters -->
      <div class="filters-section">
        <el-form :inline="true" :model="filters">
          <el-form-item :label="t('notifications.filter_type')">
            <el-select v-model="filters.type" clearable style="width: 180px">
              <el-option :label="t('notifications.all_types')" value="" />
              <el-option :label="t('notifications.type_review_assigned')" value="review_assigned" />
              <el-option :label="t('notifications.type_review_completed')" value="review_completed" />
              <el-option :label="t('notifications.type_delegation_expiry')" value="delegation_expiry" />
              <el-option :label="t('notifications.type_system_alert')" value="system_alert" />
            </el-select>
          </el-form-item>

          <el-form-item :label="t('notifications.filter_priority')">
            <el-select v-model="filters.priority" clearable style="width: 140px">
              <el-option :label="t('notifications.all_priorities')" value="" />
              <el-option :label="t('notifications.priority_urgent')" value="urgent" />
              <el-option :label="t('notifications.priority_high')" value="high" />
              <el-option :label="t('notifications.priority_normal')" value="normal" />
              <el-option :label="t('notifications.priority_low')" value="low" />
            </el-select>
          </el-form-item>

          <el-form-item :label="t('notifications.filter_status')">
            <el-select v-model="filters.is_read" clearable style="width: 140px">
              <el-option :label="t('notifications.status_all')" :value="undefined" />
              <el-option :label="t('notifications.status_unread')" :value="false" />
              <el-option :label="t('notifications.status_read')" :value="true" />
            </el-select>
          </el-form-item>

          <el-form-item>
            <el-button type="primary" @click="applyFilters">
              {{ t('common.apply') }}
            </el-button>
            <el-button @click="resetFilters">
              {{ t('common.reset') }}
            </el-button>
          </el-form-item>
        </el-form>
      </div>

      <!-- Statistics -->
      <div class="stats-section" v-if="stats">
        <el-row :gutter="16">
          <el-col :span="6">
            <el-statistic :title="t('notifications.stat_total')" :value="stats.total_count" />
          </el-col>
          <el-col :span="6">
            <el-statistic :title="t('notifications.stat_unread')" :value="stats.unread_count">
              <template #suffix>
                <el-tag size="small" type="danger" v-if="stats.unread_count > 0">{{ t('notifications.badge_new') }}</el-tag>
              </template>
            </el-statistic>
          </el-col>
          <el-col :span="6">
            <el-statistic :title="t('notifications.stat_high_priority')" :value="stats.by_priority?.high || 0" />
          </el-col>
          <el-col :span="6">
            <el-statistic :title="t('notifications.stat_urgent')" :value="stats.by_priority?.urgent || 0">
              <template #suffix>
                <el-tag size="small" type="danger" v-if="(stats.by_priority?.urgent || 0) > 0">!</el-tag>
              </template>
            </el-statistic>
          </el-col>
        </el-row>
      </div>

      <el-divider />

      <!-- Notification List -->
      <div class="notification-list">
        <el-empty v-if="!loading && notifications.length === 0" :description="t('notifications.empty_state')" />

        <div v-else>
          <div
            v-for="notif in notifications"
            :key="notif.id"
            class="notification-item"
            :class="{ 'is-read': notif.is_read, 'is-urgent': notif.priority === 'urgent' }"
            @click="handleNotificationClick(notif)"
          >
            <div class="notification-content">
              <div class="notification-header">
                <el-tag
                  :type="getPriorityType(notif.priority)"
                  size="small"
                  class="priority-tag"
                >
                  {{ getPriorityLabel(notif.priority) }}
                </el-tag>
                <el-tag size="small" class="type-tag">
                  {{ getTypeLabel(notif.type) }}
                </el-tag>
                <span class="timestamp">{{ formatTime(notif.created_at) }}</span>
              </div>

              <h3 class="notification-title">{{ notif.title }}</h3>
              <p class="notification-message">{{ notif.message }}</p>

              <div class="notification-footer" v-if="notif.related_id">
                <el-link type="primary" @click.stop="navigateToRelated(notif)">
                  View Related {{ getRelatedTypeLabel(notif.related_type) }}
                </el-link>
              </div>
            </div>

            <div class="notification-actions">
              <el-button
                v-if="!notif.is_read"
                size="small"
                type="primary"
                link
                @click.stop="markAsRead(notif.id)"
              >
                {{ t('notifications.mark_read') }}
              </el-button>
              <el-button
                size="small"
                type="danger"
                link
                @click.stop="deleteNotification(notif.id)"
              >
                {{ t('common.delete') }}
              </el-button>
            </div>
          </div>

          <!-- Pagination -->
          <div class="pagination-section">
            <el-pagination
              v-model:current-page="pagination.page"
              v-model:page-size="pagination.pageSize"
              :total="pagination.total"
              :page-sizes="[10, 20, 50, 100]"
              layout="total, sizes, prev, pager, next, jumper"
              @size-change="handleSizeChange"
              @current-change="handlePageChange"
            />
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, QuestionFilled } from '@element-plus/icons-vue'
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

function getPriorityType(priority: string): 'success' | 'warning' | 'danger' | 'info' {
  switch (priority) {
    case 'urgent':
      return 'danger'
    case 'high':
      return 'warning'
    case 'normal':
      return 'info'
    case 'low':
      return 'success'
    default:
      return 'info'
  }
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
.notification-list-container {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
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

.filters-section {
  margin-bottom: 20px;
}

.stats-section {
  margin-bottom: 20px;
}

.notification-list {
  min-height: 300px;
}

.notification-item {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 16px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  margin-bottom: 12px;
  cursor: pointer;
  transition: all 0.2s;
  background: var(--el-bg-color);
}

.notification-item:hover {
  border-color: var(--el-color-primary);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.notification-item.is-read {
  opacity: 0.7;
  background: var(--el-fill-color-lighter);
}

.notification-item.is-urgent {
  border-left: 4px solid var(--el-color-danger);
}

.notification-content {
  flex: 1;
  min-width: 0;
}

.notification-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.priority-tag,
.type-tag {
  font-weight: 500;
}

.timestamp {
  margin-left: auto;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.notification-title {
  margin: 0 0 8px 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.notification-message {
  margin: 0 0 12px 0;
  font-size: 14px;
  color: var(--el-text-color-regular);
  line-height: 1.5;
}

.notification-footer {
  margin-top: 8px;
}

.notification-actions {
  display: flex;
  gap: 8px;
  margin-left: 16px;
}

.pagination-section {
  margin-top: 24px;
  display: flex;
  justify-content: center;
}

@media (max-width: 768px) {
  .notification-item {
    flex-direction: column;
  }

  .notification-actions {
    margin-left: 0;
    margin-top: 12px;
    width: 100%;
    justify-content: flex-end;
  }

  .timestamp {
    margin-left: 0;
  }
}
</style>
