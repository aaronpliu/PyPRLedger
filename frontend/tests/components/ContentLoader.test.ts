import { describe, expect, it } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createI18n } from 'vue-i18n'
import ContentLoader from '@/components/common/ContentLoader.vue'
import enMessages from '@/locales/en.json'

function mountLoader(props: Record<string, unknown> = {}) {
  const i18n = createI18n({ legacy: false, locale: 'en', messages: { en: enMessages } })
  return mount(ContentLoader, { props, global: { plugins: [ElementPlus, i18n] } })
}

describe('ContentLoader', () => {
  it('renders nothing when not loading', () => {
    const wrapper = mountLoader({ loading: false })
    expect(wrapper.find('[role="status"]').exists()).toBe(false)
  })

  it('renders a translation key as its label', () => {
    const wrapper = mountLoader({ label: 'releaseNotes.tags_loading' })
    expect(wrapper.text()).toContain('Loading tags and branches...')
  })

  it('renders a caller-supplied phrase as-is', () => {
    const wrapper = mountLoader({ label: 'Fetching from Bitbucket' })
    expect(wrapper.text()).toContain('Fetching from Bitbucket')
  })

  it('renders a skeleton, and no spinner, when rows are asked for', async () => {
    const wrapper = mountLoader({ rows: 5 })
    await flushPromises()
    expect(wrapper.findComponent({ name: 'ElSkeleton' }).exists()).toBe(true)
    expect(wrapper.find('.content-loader-spinner').exists()).toBe(false)
  })

  it('renders a spinner, and no skeleton, when no rows are asked for', () => {
    const wrapper = mountLoader()
    expect(wrapper.find('.content-loader-spinner').exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'ElSkeleton' }).exists()).toBe(false)
  })

  it('falls back to the generic label', () => {
    const wrapper = mountLoader()
    expect(wrapper.text()).toContain('Loading...')
  })
})
