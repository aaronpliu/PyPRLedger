import { describe, it, expect, beforeEach } from 'vitest'
import { useNotificationStore } from '@/stores/notifications'
import { createPinia, setActivePinia } from 'pinia'

describe('Notification Store', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
  })

  it('should initialize with empty notifications', () => {
    const store = useNotificationStore()
    expect(store.notifications).toEqual([])
    expect(store.unreadCount).toBe(0)
  })

  it('should add notification', () => {
    const store = useNotificationStore()
    const notification = {
      id: '1',
      title: 'Test Notification',
      message: 'This is a test',
      type: 'info' as const,
      created_at: new Date().toISOString(),
    }

    store.addNotification(notification)

    expect(store.notifications.length).toBe(1)
    expect(store.unreadCount).toBe(1)
  })

  it('should mark notification as read', () => {
    const store = useNotificationStore()
    store.addNotification({
      id: '1',
      title: 'Test',
      message: 'Message',
      type: 'info' as const,
      created_at: new Date().toISOString(),
    })

    store.markAsRead('1')

    expect(store.notifications[0].read).toBe(true)
    expect(store.unreadCount).toBe(0)
  })

  it('should mark all as read', () => {
    const store = useNotificationStore()

    store.addNotification({
      id: '1',
      title: 'Test 1',
      message: 'Message 1',
      type: 'info' as const,
      created_at: new Date().toISOString(),
    })

    store.addNotification({
      id: '2',
      title: 'Test 2',
      message: 'Message 2',
      type: 'success' as const,
      created_at: new Date().toISOString(),
    })

    expect(store.unreadCount).toBe(2)

    store.markAllAsRead()

    expect(store.unreadCount).toBe(0)
    expect(store.notifications.every(n => n.read)).toBe(true)
  })

  it('should remove notification', () => {
    const store = useNotificationStore()

    store.addNotification({
      id: '1',
      title: 'Test',
      message: 'Message',
      type: 'info' as const,
      created_at: new Date().toISOString(),
    })

    expect(store.notifications.length).toBe(1)

    store.removeNotification('1')

    expect(store.notifications.length).toBe(0)
  })

  it('should clear all notifications', () => {
    const store = useNotificationStore()

    store.addNotification({
      id: '1',
      title: 'Test 1',
      message: 'Message 1',
      type: 'info' as const,
      created_at: new Date().toISOString(),
    })

    store.addNotification({
      id: '2',
      title: 'Test 2',
      message: 'Message 2',
      type: 'warning' as const,
      created_at: new Date().toISOString(),
    })

    expect(store.notifications.length).toBe(2)

    store.clearAll()

    expect(store.notifications.length).toBe(0)
    expect(store.unreadCount).toBe(0)
  })

  it('should get unread notifications', () => {
    const store = useNotificationStore()

    store.addNotification({
      id: '1',
      title: 'Unread',
      message: 'Message',
      type: 'info' as const,
      created_at: new Date().toISOString(),
    })

    store.addNotification({
      id: '2',
      title: 'Read',
      message: 'Message',
      type: 'info' as const,
      created_at: new Date().toISOString(),
    })
    store.markAsRead('2')

    const unread = store.getUnreadNotifications()
    expect(unread.length).toBe(1)
    expect(unread[0].id).toBe('1')
  })
})
