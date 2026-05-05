<template>
  <el-dropdown trigger="click" @command="handleCommand" class="notification-bell">
    <el-badge :value="unreadCount" :hidden="unreadCount === 0" :max="99">
      <el-icon :size="20" style="cursor: pointer; color: var(--el-text-color-primary)">
        <Bell />
      </el-icon>
    </el-badge>
    
    <template #dropdown>
      <el-dropdown-menu class="notification-dropdown">
        <div class="notification-header">
          <span class="title">{{ t('notifications.title') }}</span>
          <el-button link size="small" @click="markAllAsRead" v-if="unreadCount > 0">
            {{ t('notifications.mark_all_read') }}
          </el-button>
        </div>
        
        <el-divider style="margin: 8px 0" />
        
        <div class="notification-list">
          <div v-if="recentNotifications.length === 0" class="empty-state">
            <el-icon :size="40" color="var(--el-text-color-secondary)">
              <Bell />
            </el-icon>
            <p>{{ t('notifications.no_notifications') }}</p>
          </div>
          
          <el-dropdown-item
            v-for="notif in recentNotifications"
            :key="notif.id"
            :command="`view_${notif.id}`"
            class="notification-item"
            :class="{ unread: !notif.is_read }"
            @click="handleNotificationClick(notif)"
          >
            <div class="notification-content">
              <div class="notification-title">
                <el-tag
                  v-if="!notif.is_read"
                  size="small"
                  type="danger"
                  style="margin-right: 8px"
                >
                  ●
                </el-tag>
                {{ notif.title }}
              </div>
              <div class="notification-message">{{ notif.message }}</div>
              <div class="notification-meta">
                <el-tag :type="getPriorityType(notif.priority)" size="small">
                  {{ getPriorityLabel(notif.priority) }}
                </el-tag>
                <span class="time">{{ formatTime(notif.created_at) }}</span>
              </div>
            </div>
          </el-dropdown-item>
        </div>
        
        <el-divider style="margin: 8px 0" />
        
        <div class="notification-footer">
          <el-button link size="small" @click="viewAll">
            {{ t('notifications.view_all') }}
          </el-button>
        </div>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Bell } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { notificationsApi, type Notification } from '@/api/notifications'

const router = useRouter()
const { t } = useI18n()

// State
const notifications = ref<Notification[]>([])
const unreadCount = ref(0)
let pollTimer: ReturnType<typeof setInterval> | null = null

// Computed
const recentNotifications = computed(() => notifications.value.slice(0, 5))

// Methods
const loadUnreadCount = async () => {
  try {
    const response = await notificationsApi.getUnreadCount()
    unreadCount.value = response.unread_count
  } catch (error) {
    console.error('Failed to load unread count:', error)
  }
}

const loadRecentNotifications = async () => {
  try {
    const response = await notificationsApi.getNotifications({
      page: 1,
      page_size: 5,
      is_read: false,
    })
    notifications.value = response.items
  } catch (error) {
    console.error('Failed to load notifications:', error)
  }
}

const markAllAsRead = async () => {
  try {
    await notificationsApi.markAllAsRead()
    ElMessage.success(t('notifications.marked_all_read'))
    await refreshData()
  } catch (error) {
    console.error('Failed to mark all as read:', error)
    ElMessage.error(t('notifications.operation_failed'))
  }
}

const handleNotificationClick = async (notification: Notification) => {
  if (!notification.is_read) {
    try {
      await notificationsApi.markAsRead(notification.id)
      await refreshData()
    } catch (error) {
      console.error('Failed to mark as read:', error)
    }
  }
  
  // Navigate to related content if available
  if (notification.related_type === 'pull_request' && notification.related_id) {
    router.push(`/reviews?pr_id=${notification.related_id}&from_notification=true`)
  }
}

const handleCommand = (command: string) => {
  if (command.startsWith('view_')) {
    const id = parseInt(command.replace('view_', ''))
    const notification = notifications.value.find((n) => n.id === id)
    if (notification) {
      handleNotificationClick(notification)
    }
  }
}

const viewAll = () => {
  router.push('/notifications')
}

const getPriorityType = (priority: string) => {
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

const getPriorityLabel = (priority: string) => {
  return t(`notifications.priority.${priority}`, priority)
}

const formatTime = (dateString: string) => {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)
  
  if (diffMins < 1) return t('notifications.just_now')
  if (diffMins < 60) return t('notifications.minutes_ago', { count: diffMins })
  if (diffHours < 24) return t('notifications.hours_ago', { count: diffHours })
  if (diffDays < 7) return t('notifications.days_ago', { count: diffDays })
  
  return date.toLocaleDateString()
}

const refreshData = async () => {
  await Promise.all([loadUnreadCount(), loadRecentNotifications()])
}

// Smart polling for real-time updates
const startPolling = () => {
  pollTimer = setInterval(async () => {
    await loadUnreadCount()
    // Only reload list if there are new unread notifications
    if (unreadCount.value > notifications.value.filter((n) => !n.is_read).length) {
      await loadRecentNotifications()
    }
  }, 30000) // Poll every 30 seconds
}

const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

// Lifecycle
onMounted(() => {
  refreshData()
  startPolling()
})

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped>
.notification-bell {
  display: inline-flex;
  align-items: center;
  margin: 0 8px;
}

.notification-dropdown {
  width: 380px;
  max-height: 500px;
  padding: 0;
}

.notification-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
}

.notification-header .title {
  font-weight: 600;
  font-size: 14px;
  color: var(--el-text-color-primary);
}

.notification-list {
  max-height: 350px;
  overflow-y: auto;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  color: var(--el-text-color-secondary);
}

.empty-state p {
  margin-top: 12px;
  font-size: 14px;
}

.notification-item {
  padding: 0 !important;
  height: auto !important;
  line-height: normal !important;
}

.notification-item.unread {
  background-color: var(--el-fill-color-light);
}

.notification-content {
  padding: 12px 16px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.notification-content:hover {
  background-color: var(--el-fill-color);
}

.notification-title {
  font-weight: 600;
  font-size: 13px;
  color: var(--el-text-color-primary);
  margin-bottom: 4px;
  display: flex;
  align-items: center;
}

.notification-message {
  font-size: 12px;
  color: var(--el-text-color-regular);
  margin-bottom: 8px;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.notification-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.notification-meta .time {
  font-size: 11px;
  color: var(--el-text-color-secondary);
}

.notification-footer {
  padding: 8px 16px;
  text-align: center;
}

/* Dark theme adjustments */
[data-theme='dark'] .notification-item.unread {
  background-color: var(--el-fill-color-dark);
}
</style>
