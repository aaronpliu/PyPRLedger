import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import GlobalProgress from '@/components/common/GlobalProgress.vue'
import {
  PROGRESS_SHOW_DELAY_MS,
  beginProgress,
  endProgress,
  resetProgress,
} from '@/composables/useProgress'
import enMessages from '@/locales/en.json'

function mountBar() {
  const i18n = createI18n({ legacy: false, locale: 'en', messages: { en: enMessages } })
  return mount(GlobalProgress, { global: { plugins: [i18n] } })
}

describe('GlobalProgress', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    resetProgress()
  })
  afterEach(() => {
    resetProgress()
    vi.useRealTimers()
  })

  it('renders nothing while idle', () => {
    const wrapper = mountBar()
    expect(wrapper.find('[role="status"]').exists()).toBe(false)
  })

  it('shows the bar while a request is running', async () => {
    const wrapper = mountBar()
    const id = beginProgress()
    vi.advanceTimersByTime(PROGRESS_SHOW_DELAY_MS + 1)
    await wrapper.vm.$nextTick()

    expect(wrapper.find('[role="status"]').exists()).toBe(true)
    expect(wrapper.find('[role="progressbar"]').exists()).toBe(true)
    endProgress(id)
  })
})
