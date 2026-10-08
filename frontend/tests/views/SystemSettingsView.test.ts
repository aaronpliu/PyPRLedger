import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus, { ElMessageBox } from 'element-plus'
import { createI18n } from 'vue-i18n'
import dayjs from 'dayjs'
import SystemSettingsView from '@/views/admin/SystemSettingsView.vue'
import { rbacApi, type BannerItem } from '@/api/rbac'
import enMessages from '@/locales/en.json'

// `createBanner` is a real helper the view uses, so the module is only partly faked.
vi.mock('@/api/rbac', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/rbac')>()
  return {
    ...actual,
    rbacApi: {
      getRegistrationEnabled: vi.fn(),
      updateRegistrationEnabled: vi.fn(),
      getLlmConfig: vi.fn(),
      updateLlmConfig: vi.fn(),
      getBanner: vi.fn(),
      updateBanner: vi.fn(),
    },
  }
})

/* eslint-disable @typescript-eslint/no-explicit-any */
type AnyWrapper = any

const messages = enMessages.admin.systemSettings
const mountedWrappers: AnyWrapper[] = []
const START = '2026-10-01T00:00:00+08:00'

function banner(patch: Partial<BannerItem> = {}): BannerItem {
  return {
    id: 'b1',
    enabled: true,
    content: 'A notice',
    start_date: '',
    end_date: '',
    level: 'info',
    link_url: '',
    link_label: '',
    priority: 0,
    ...patch,
  }
}

async function mountView(banners: BannerItem[]) {
  vi.mocked(rbacApi.getRegistrationEnabled).mockResolvedValue({ registration_enabled: true })
  vi.mocked(rbacApi.getLlmConfig).mockResolvedValue({
    enabled: false,
    model: '',
    base_url: '',
    has_api_key: false,
  })
  vi.mocked(rbacApi.getBanner).mockResolvedValue({ banners })
  // Answer the way the endpoint does, so the list the view keeps is the list it sent.
  vi.mocked(rbacApi.updateBanner).mockImplementation(async (data) => ({
    message: 'ok',
    banners: data.banners,
  }))

  const i18n = createI18n({ legacy: false, locale: 'en', messages: { en: enMessages } })
  const wrapper = mount(SystemSettingsView, { global: { plugins: [ElementPlus, i18n] } })
  mountedWrappers.push(wrapper)
  await flushPromises()
  return { wrapper, dialog: () => wrapper.findComponent({ name: 'ElDialog' }) }
}

function lastSent(): BannerItem[] {
  const calls = vi.mocked(rbacApi.updateBanner).mock.calls
  return calls.length ? calls[calls.length - 1][0].banners : []
}

describe('SystemSettingsView banner management', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    mountedWrappers.splice(0).forEach((wrapper) => wrapper.unmount())
    vi.restoreAllMocks()
  })

  it('lists every stored banner with the state that matters', async () => {
    const { wrapper } = await mountView([
      banner({
        id: 'a',
        content: 'Freeze on Friday',
        level: 'warning',
        priority: 4,
        enabled: false,
        start_date: START,
      }),
      banner({ id: 'b', content: 'Shipped', level: 'success' }),
    ])

    const rows = wrapper.findAll('.el-table__row')
    expect(rows).toHaveLength(2)

    expect(rows[0].text()).toContain('Freeze on Friday')
    expect(rows[0].text()).toContain(messages.bannerLevelWarning)
    expect(rows[0].text()).toContain(enMessages.common.disabled)
    expect(rows[0].text()).toContain(dayjs(START).format('YYYY-MM-DD HH:mm'))
    expect(rows[0].text()).toContain('4')

    expect(rows[1].text()).toContain(messages.bannerLevelSuccess)
    // No bound at all reads as always on.
    expect(rows[1].text()).toContain(messages.bannerAlways)
  })

  it('says so when there is nothing to manage', async () => {
    const { wrapper } = await mountView([])

    expect(wrapper.findAll('.el-table__row')).toHaveLength(0)
    expect(wrapper.text()).toContain(messages.bannerEmpty)
  })

  it('adds a banner from the dialog', async () => {
    const { wrapper, dialog } = await mountView([])

    await wrapper.find('[data-test="banner-add"]').trigger('click')
    await dialog().find('textarea').setValue('New notice')
    await dialog().find('[data-test="banner-save"]').trigger('click')
    await flushPromises()

    expect(lastSent()).toHaveLength(1)
    expect(lastSent()[0]).toMatchObject({ content: 'New notice' })
    // The saved banner is on the page now, without reopening anything.
    expect(wrapper.findAll('.el-table__row')).toHaveLength(1)
  })

  it('opens one banner for editing and saves it back', async () => {
    const { wrapper, dialog } = await mountView([banner({ id: 'a', content: 'Before' })])

    await wrapper.find('[data-test="banner-edit"]').trigger('click')
    const textarea = dialog().find('textarea')
    expect((textarea.element as HTMLTextAreaElement).value).toBe('Before')

    await textarea.setValue('After')
    await dialog().find('[data-test="banner-save"]').trigger('click')
    await flushPromises()

    expect(lastSent()).toHaveLength(1)
    expect(lastSent()[0]).toMatchObject({ id: 'a', content: 'After' })
  })

  it('deletes the banner that was asked for, once confirmed', async () => {
    const confirm = vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm' as any)
    const { wrapper } = await mountView([
      banner({ id: 'a', content: 'Keep' }),
      banner({ id: 'b', content: 'Drop' }),
    ])

    await wrapper.findAll('[data-test="banner-remove"]')[1].trigger('click')
    await flushPromises()

    expect(confirm).toHaveBeenCalled()
    expect(lastSent().map((item) => item.content)).toEqual(['Keep'])
    expect(wrapper.findAll('.el-table__row')).toHaveLength(1)
  })

  it('leaves everything alone when the delete is dismissed', async () => {
    vi.spyOn(ElMessageBox, 'confirm').mockRejectedValue('dismissed')
    const { wrapper } = await mountView([banner({ id: 'a', content: 'Still here' })])

    await wrapper.find('[data-test="banner-remove"]').trigger('click')
    await flushPromises()

    expect(rbacApi.updateBanner).not.toHaveBeenCalled()
    expect(wrapper.findAll('.el-table__row')).toHaveLength(1)
  })

  it('flips one banner on or off from the list, leaving the others alone', async () => {
    const { wrapper } = await mountView([
      banner({ id: 'a', content: 'Notice', enabled: true }),
      banner({ id: 'b', content: 'Other', enabled: true }),
    ])

    await wrapper.findAll('[data-test="banner-enabled"] input')[0].setValue(false)
    await flushPromises()

    expect(lastSent().map((item) => [item.id, item.enabled])).toEqual([
      ['a', false],
      ['b', true],
    ])
  })

  it('leaves the switch where it was when the write fails', async () => {
    // The view logs the failure; that noise is not what this test is about.
    vi.spyOn(console, 'error').mockImplementation(() => {})
    const { wrapper } = await mountView([banner({ id: 'a', content: 'Notice', enabled: true })])
    vi.mocked(rbacApi.updateBanner).mockRejectedValue(new Error('nope'))

    await wrapper.find('[data-test="banner-enabled"] input').setValue(false)
    await flushPromises()

    // The switch reports the stored state, not the click that failed to save.
    expect(wrapper.findComponent({ name: 'ElSwitch' }).props('modelValue')).toBe(true)
  })

  it('will not save a banner without a message', async () => {
    const { wrapper, dialog } = await mountView([])

    await wrapper.find('[data-test="banner-add"]').trigger('click')
    await dialog().find('[data-test="banner-save"]').trigger('click')
    await flushPromises()

    expect(rbacApi.updateBanner).not.toHaveBeenCalled()
  })
})
