import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createI18n } from 'vue-i18n'
import AdminDashboardView from '@/views/admin/AdminDashboardView.vue'
import { usersApi } from '@/api/users'
import { rbacApi } from '@/api/rbac'
import { auditApi } from '@/api/audit'
import { authApi } from '@/api/auth'
import enMessages from '@/locales/en.json'

const api = vi.hoisted(() => ({
  getReviewers: vi.fn(),
  getRoles: vi.fn(),
  listDelegations: vi.fn(),
  getSessions: vi.fn(),
  getLogs: vi.fn(),
  push: vi.fn(),
}))

vi.mock('@/api/users', () => ({ usersApi: { getReviewers: api.getReviewers } }))
vi.mock('@/api/rbac', () => ({
  rbacApi: { getRoles: api.getRoles, listDelegations: api.listDelegations },
}))
vi.mock('@/api/audit', () => ({ auditApi: { getLogs: api.getLogs } }))
vi.mock('@/api/auth', () => ({ authApi: { getSessions: api.getSessions } }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: api.push }) }))

const mountedWrappers: any[] = []

function session(patch: Record<string, unknown> = {}) {
  return {
    id: 1,
    username: 'alice',
    ip_address: '10.0.0.1',
    created_at: '2026-11-08T09:00:00Z',
    ...patch,
  }
}

function auditLog(patch: Record<string, unknown> = {}) {
  return {
    id: 1,
    action: 'login',
    resource_type: 'session',
    resource_id: '1',
    created_at: '2026-11-08T08:00:00Z',
    ...patch,
  }
}

async function mountView() {
  const i18n = createI18n({ legacy: false, locale: 'en', messages: { en: enMessages } })
  const wrapper = mount(AdminDashboardView, { global: { plugins: [ElementPlus, i18n] } })
  mountedWrappers.push(wrapper)
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  api.getReviewers.mockResolvedValue({ total: 7 })
  api.getRoles.mockResolvedValue([{ id: 1 }, { id: 2 }])
  api.listDelegations.mockResolvedValue([{ id: 1 }])
  api.getSessions.mockResolvedValue([session()])
  api.getLogs.mockResolvedValue({ logs: [auditLog()] })
  api.push.mockReset()
})

afterEach(() => {
  while (mountedWrappers.length) mountedWrappers.pop()?.unmount()
  vi.clearAllMocks()
})

describe('AdminDashboardView', () => {
  it('shows the four headline numbers', async () => {
    const wrapper = await mountView()
    expect(wrapper.findAll('[data-test="stat-value"]').map((node) => node.text())).toEqual([
      '7',
      '2',
      '1',
      '1',
    ])
  })

  it('offers a shortcut to every management page', async () => {
    const wrapper = await mountView()
    const shortcuts = wrapper.findAll('[data-test="quick-action"] button')
    expect(shortcuts).toHaveLength(6)
    await shortcuts[0].trigger('click')
    expect(api.push).toHaveBeenCalledWith({ name: 'UserManagement' })
  })

  it('lists the most recent audit events and sessions', async () => {
    const wrapper = await mountView()
    expect(wrapper.text()).toContain('login')
    expect(wrapper.text()).toContain('alice')
  })

  it('explains itself when there is no recent activity', async () => {
    api.getLogs.mockResolvedValue({ logs: [] })
    api.getSessions.mockResolvedValue([])
    const wrapper = await mountView()
    expect(wrapper.text()).toContain('No Data Available')
  })

  it('keeps the dashboard usable when a backend call fails', async () => {
    api.getReviewers.mockRejectedValue(new Error('offline'))
    api.getLogs.mockRejectedValue(new Error('offline'))
    const wrapper = await mountView()
    expect(wrapper.findAll('[data-test="stat-value"]')[0].text()).toBe('0')
    expect(wrapper.text()).toContain('No Data Available')
  })

  it('asks for sessions only once to fill both the count and the list', async () => {
    await mountView()
    expect(api.getSessions).toHaveBeenCalledTimes(1)
  })

  it('reloads every panel from the header refresh button', async () => {
    const wrapper = await mountView()
    await wrapper.find('[data-test="dashboard-refresh"]').trigger('click')
    await flushPromises()
    expect(api.getReviewers).toHaveBeenCalledTimes(2)
    expect(api.getLogs).toHaveBeenCalledTimes(2)
  })
})
