import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import FestivalOverlay from '@/components/common/FestivalOverlay.vue'
import { rbacApi } from '@/api/rbac'
import type { FestivalConfig } from '@/api/rbac'
import enMessages from '@/locales/en.json'

vi.mock('@/api/rbac', () => ({
  rbacApi: { getFestivalAnimation: vi.fn() },
}))

const mountedWrappers: any[] = []

function config(patch: Partial<FestivalConfig> = {}): FestivalConfig {
  return {
    enabled: false,
    effect: 'christmas',
    start_date: '',
    end_date: '',
    duration_seconds: 10,
    speed: 1,
    custom_name: '',
    custom_emoji: '',
    custom_colors: [],
    ...patch,
  }
}

async function mountOverlay() {
  const i18n = createI18n({ legacy: false, locale: 'en', messages: { en: enMessages } })
  const wrapper = mount(FestivalOverlay, { global: { plugins: [i18n] } })
  mountedWrappers.push(wrapper)
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  vi.mocked(rbacApi.getFestivalAnimation).mockResolvedValue({ festival: config() })
})

afterEach(() => {
  while (mountedWrappers.length) {
    mountedWrappers.pop()?.unmount()
  }
  window.dispatchEvent(new Event('festival-unmount-helper'))
})

describe('FestivalOverlay', () => {
  it('stays hidden when the festival is disabled', async () => {
    const wrapper = await mountOverlay()
    expect(wrapper.find('canvas').exists()).toBe(false)
  })

  it('plays when the preview event arrives', async () => {
    const wrapper = await mountOverlay()
    window.dispatchEvent(
      new CustomEvent('festival-preview', { detail: config({ enabled: true, effect: 'christmas' }) })
    )
    await flushPromises()
    expect(wrapper.find('canvas').exists()).toBe(true)
    expect(wrapper.text()).toContain('Merry Christmas')
  })

  it('shows the custom greeting for the custom effect', async () => {
    const wrapper = await mountOverlay()
    window.dispatchEvent(
      new CustomEvent('festival-preview', {
        detail: config({
          enabled: true,
          effect: 'custom',
          custom_name: 'Happy Anniversary!',
          custom_emoji: '🎂',
          custom_colors: ['#ef4444'],
        }),
      })
    )
    await flushPromises()
    expect(wrapper.find('canvas').exists()).toBe(true)
    expect(wrapper.text()).toContain('Happy Anniversary!')
  })
})
