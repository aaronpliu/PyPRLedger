import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface Notification {
  id: string
  title: string
  message: string
  type: 'success' | 'warning' | 'error' | 'info'
  read: boolean
  data?: any
  created_at: string
}

export const useNotificationStore = defineStore('notifications', () => {
  // State
  const notifications = ref<Notification[]>([])
  const maxNotifications = 50

  // Getters
  const unreadCount = computed(() => 
    notifications.value.filter(n => !n.read).length
  )

  const recentNotifications = computed(() => 
    notifications.value.slice(0, 10)
  )

  // Actions
  function addNotification(notification: Omit<Notification, 'read'>) {
    const newNotification: Notification = {
      ...notification,
      read: false,
    }

    notifications.value.unshift(newNotification)

    // Keep only recent notifications
    if (notifications.value.length > maxNotifications) {
      notifications.value = notifications.value.slice(0, maxNotifications)
    }

    // Save to localStorage
    saveToStorage()
  }

  function markAsRead(id: string) {
    const notification = notifications.value.find(n => n.id === id)
    if (notification) {
      notification.read = true
      saveToStorage()
    }
  }

  function markAllAsRead() {
    notifications.value.forEach(n => n.read = true)
    saveToStorage()
  }

  function removeNotification(id: string) {
    const index = notifications.value.findIndex(n => n.id === id)
    if (index !== -1) {
      notifications.value.splice(index, 1)
      saveToStorage()
    }
  }

  function clearAll() {
    notifications.value = []
    saveToStorage()
  }

  function getUnreadNotifications() {
    return notifications.value.filter(n => !n.read)
  }

  // Persistence
  function saveToStorage() {
    try {
      localStorage.setItem('notifications', JSON.stringify(notifications.value))
    } catch (error) {
      console.error('Failed to save notifications:', error)
    }
  }

  function loadFromStorage() {
    try {
      const stored = localStorage.getItem('notifications')
      if (stored) {
        notifications.value = JSON.parse(stored)
      }
    } catch (error) {
      console.error('Failed to load notifications:', error)
    }
  }

  // Initialize
  loadFromStorage()

  return {
    notifications,
    unreadCount,
    recentNotifications,
    addNotification,
    markAsRead,
    markAllAsRead,
    removeNotification,
    clearAll,
    getUnreadNotifications,
  }
})
