import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import GlobalProgress from '@/components/common/GlobalProgress.vue'
import {
  PROGRESS_SHOW_DELAY_MS,
  beginProgress,
  endProgress,
  progressLabelFor,
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

  it('shows the bar and the name of a running provider call', async () => {
    const wrapper = mountBar()
    const id = beginProgress(progressLabelFor('/release/diff/refs'))
    vi.advanceTimersByTime(PROGRESS_SHOW_DELAY_MS + 1)
    await wrapper.vm.$nextTick()

    expect(wrapper.find('[role="status"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="progress-caption"]').text()).toContain(
      'Fetching tags and branches',
    )
    endProgress(id)
  })

  it('names an unnamed call once it has run long enough', async () => {
    const wrapper = mountBar()
    const id = beginProgress()
    vi.advanceTimersByTime(PROGRESS_SHOW_DELAY_MS + 1)
    // a short run has no caption of its own
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-test="progress-caption"]').exists()).toBe(false)

    vi.advanceTimersByTime(3000)
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-test="progress-caption"]').text()).toContain('3s')
    endProgress(id)
  })
})
