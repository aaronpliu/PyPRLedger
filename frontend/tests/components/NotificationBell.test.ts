import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createI18n } from 'vue-i18n'
import { createMemoryHistory, createRouter } from 'vue-router'
import NotificationBell from '@/components/common/NotificationBell.vue'
import { notificationsApi, type Notification } from '@/api/notifications'
import enMessages from '@/locales/en.json'

vi.mock('@/api/notifications', () => ({
  notificationsApi: {
    getUnreadCount: vi.fn(),
    getNotifications: vi.fn(),
    markAsRead: vi.fn(),
    markAllAsRead: vi.fn(),
  },
}))

const getUnreadCount = vi.mocked(notificationsApi.getUnreadCount)
const getNotifications = vi.mocked(notificationsApi.getNotifications)

const POLL_INTERVAL_MS = 30000

/* eslint-disable @typescript-eslint/no-explicit-any */
type AnyWrapper = any

const mountedWrappers: AnyWrapper[] = []

function emptyList() {
  return { items: [] as Notification[], total: 0, page: 1, page_size: 5 }
}

function assignedTask(): Notification {
  return {
    id: 7,
    user_id: 'u1',
    type: 'task_assigned',
    title: 'New review assigned',
    message: 'PR 1203 in BAR/pyrag was assigned to you',
    is_read: false,
    priority: 'normal',
    channel: 'in_app',
    created_at: new Date().toISOString(),
  }
}

function mountBell() {
  const i18n = createI18n({ legacy: false, locale: 'en', messages: { en: enMessages } })
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/notifications', component: { template: '<div />' } },
    ],
  })
  const wrapper = mount(NotificationBell, { global: { plugins: [ElementPlus, i18n, router] } })
  mountedWrappers.push(wrapper)
  return wrapper
}

/** One poll cycle, including the promises it chains. */
async function pollOnce() {
  await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)
  await flushPromises()
}

beforeEach(() => {
  vi.useFakeTimers()
  getUnreadCount.mockReset()
  getNotifications.mockReset()
  getUnreadCount.mockResolvedValue({ unread_count: 0 })
  getNotifications.mockResolvedValue(emptyList())
})

afterEach(() => {
  mountedWrappers.splice(0).forEach((wrapper) => wrapper.unmount())
  // The dropdown menu is teleported out of the component.
  document.body.innerHTML = ''
  vi.useRealTimers()
})

describe('NotificationBell', () => {
  it('fills the popup when the first task is assigned to an empty list', async () => {
    const wrapper = mountBell()
    await flushPromises()
    expect(getNotifications).toHaveBeenCalledTimes(1)

    // A reviewer gets a task: the badge moves from 0 to 1 while the list is empty
    getUnreadCount.mockResolvedValue({ unread_count: 1 })
    getNotifications.mockResolvedValue({
      items: [assignedTask()],
      total: 1,
      page: 1,
      page_size: 5,
    })

    await pollOnce()

    expect(getNotifications).toHaveBeenCalledTimes(2)
    expect(getNotifications).toHaveBeenLastCalledWith(expect.objectContaining({ is_read: false }))
    expect(wrapper.find('.el-badge__content').text()).toBe('1')
  })

  it('leaves the list alone while the unread count does not move', async () => {
    mountBell()
    await flushPromises()
    expect(getNotifications).toHaveBeenCalledTimes(1)

    await pollOnce()
    await pollOnce()

    expect(getNotifications).toHaveBeenCalledTimes(1)
  })

  it('refetches when a notification was read elsewhere', async () => {
    getUnreadCount.mockResolvedValue({ unread_count: 3 })
    mountBell()
    await flushPromises()
    expect(getNotifications).toHaveBeenCalledTimes(1)

    // Read on another device: the badge drops, so the list is stale too
    getUnreadCount.mockResolvedValue({ unread_count: 2 })

    await pollOnce()

    expect(getNotifications).toHaveBeenCalledTimes(2)
  })

  it('does not duplicate the list when the count request fails', async () => {
    mountBell()
    await flushPromises()
    expect(getNotifications).toHaveBeenCalledTimes(1)

    getUnreadCount.mockRejectedValue(new Error('server restarting'))

    await pollOnce()

    expect(getNotifications).toHaveBeenCalledTimes(1)
  })
})
