<template>
  <el-dropdown trigger="click" @command="handleCommand">
    <div class="notification-bell">
      <el-badge :value="notificationStore.unreadCount" :hidden="notificationStore.unreadCount === 0" :max="99">
        <el-icon :size="20">
          <Bell />
        </el-icon>
      </el-badge>
    </div>

    <template #dropdown>
      <el-dropdown-menu class="notification-dropdown">
        <div class="notification-header">
          <span class="title">Notifications</span>
          <div class="actions">
            <el-button link type="primary" size="small" @click="markAllAsRead" v-if="notificationStore.unreadCount > 0">
              Mark all read
            </el-button>
            <el-button link type="danger" size="small" @click="clearAll" v-if="notificationStore.notifications.length > 0">
              Clear all
            </el-button>
          </div>
        </div>

        <el-divider style="margin: 8px 0" />

        <div class="notification-list">
          <div
            v-for="notif in notificationStore.recentNotifications"
            :key="notif.id"
            class="notification-item"
            :class="{ unread: !notif.read }"
            @click="handleNotificationClick(notif)"
          >
            <div class="notification-icon">
              <el-icon :color="getNotificationColor(notif.type)">
                <component :is="getNotificationIcon(notif.type)" />
              </el-icon>
            </div>
            <div class="notification-content">
              <div class="notification-title">{{ notif.title }}</div>
              <div class="notification-message">{{ notif.message }}</div>
              <div class="notification-time">{{ formatTime(notif.created_at) }}</div>
            </div>
            <div class="notification-actions">
              <el-button
                link
                size="small"
                @click.stop="removeNotification(notif.id)"
              >
                <el-icon><Close /></el-icon>
              </el-button>
            </div>
          </div>

          <el-empty
            v-if="notificationStore.notifications.length === 0"
            description="No notifications"
            :image-size="80"
          />
        </div>

        <el-divider style="margin: 8px 0" />

        <div class="notification-footer">
          <el-button link type="primary" size="small" @click="viewAll">
            View all notifications
          </el-button>
        </div>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
</template>

<script setup lang="ts">
import { Bell, Close, SuccessFilled, WarningFilled, CircleCloseFilled, InfoFilled } from '@element-plus/icons-vue'
import { useNotificationStore } from '@/stores/notifications'
import type { Notification } from '@/stores/notifications'
import dayjs from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'

dayjs.extend(relativeTime)

const notificationStore = useNotificationStore()

const getNotificationIcon = (type: string) => {
  const icons: Record<string, any> = {
    success: SuccessFilled,
    warning: WarningFilled,
    error: CircleCloseFilled,
    info: InfoFilled,
  }
  return icons[type] || InfoFilled
}

const getNotificationColor = (type: string) => {
  const colors: Record<string, string> = {
    success: '#67c23a',
    warning: '#e6a23c',
    error: '#f56c6c',
    info: '#409eff',
  }
  return colors[type] || '#409eff'
}

const formatTime = (dateStr: string) => {
  return dayjs(dateStr).fromNow()
}

const handleCommand = (command: string) => {
  // Handle dropdown commands if needed
}

const handleNotificationClick = (notification: Notification) => {
  notificationStore.markAsRead(notification.id)
  
  // Handle notification click based on data
  if (notification.data?.url) {
    window.location.href = notification.data.url
  }
}

const markAllAsRead = () => {
  notificationStore.markAllAsRead()
}

const clearAll = () => {
  notificationStore.clearAll()
}

const removeNotification = (id: string) => {
  notificationStore.removeNotification(id)
}

const viewAll = () => {
  // Navigate to notifications page (if exists)
  console.log('View all notifications')
}

// Listen for WebSocket notifications
window.addEventListener('notification-received', ((event: CustomEvent) => {
  notificationStore.addNotification(event.detail)
}) as EventListener)
</script>

<style scoped>
.notification-bell {
  cursor: pointer;
  padding: 8px;
  border-radius: 4px;
  transition: background-color 0.3s;
  color: white;
}

.notification-bell:hover {
  background-color: rgba(255, 255, 255, 0.1);
}

.notification-dropdown {
  width: 380px;
  max-height: 500px;
}

.notification-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
}

.notification-header .title {
  font-weight: bold;
  font-size: 14px;
}

.notification-header .actions {
  display: flex;
  gap: 8px;
}

.notification-list {
  max-height: 350px;
  overflow-y: auto;
}

.notification-item {
  display: flex;
  gap: 12px;
  padding: 12px 16px;
  cursor: pointer;
  transition: background-color 0.2s;
  border-bottom: 1px solid #f0f0f0;
}

.notification-item:hover {
  background-color: #f5f7fa;
}

.notification-item.unread {
  background-color: #ecf5ff;
}

.notification-item.unread:hover {
  background-color: #d9ecff;
}

.notification-icon {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background-color: #f5f7fa;
}

.notification-content {
  flex: 1;
  min-width: 0;
}

.notification-title {
  font-size: 14px;
  font-weight: 500;
  color: #303133;
  margin-bottom: 4px;
}

.notification-message {
  font-size: 12px;
  color: #606266;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.notification-time {
  font-size: 11px;
  color: #909399;
}

.notification-actions {
  flex-shrink: 0;
  opacity: 0;
  transition: opacity 0.2s;
}

.notification-item:hover .notification-actions {
  opacity: 1;
}

.notification-footer {
  padding: 8px 16px;
  text-align: center;
}
</style>
