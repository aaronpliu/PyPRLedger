import { describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createI18n } from 'vue-i18n'
import ServiceUnavailableNotice from '@/components/common/ServiceUnavailableNotice.vue'
import enMessages from '@/locales/en.json'

const checkBackend = vi.fn()

vi.mock('@/composables/useBackendAvailability', () => ({
  checkBackend: () => checkBackend(),
}))

function mountNotice(confirmed: boolean) {
  const i18n = createI18n({ legacy: false, locale: 'en', messages: { en: enMessages } })
  return mount(ServiceUnavailableNotice, {
    props: { confirmed },
    global: { plugins: [ElementPlus, i18n] },
  })
}

describe('ServiceUnavailableNotice', () => {
  it('says the connection is in doubt without taking the page away', () => {
    const wrapper = mountNotice(false)

    expect(wrapper.text()).toContain(enMessages.errors.connection_lost)
    // a doubt is not an outage: the page underneath is still the reader's
    expect(wrapper.find('[role="alertdialog"]').exists()).toBe(false)
    expect(wrapper.find('[role="status"]').exists()).toBe(true)
    expect(wrapper.text()).not.toContain(enMessages.errors.service_unavailable)
  })

  it('covers the page once the outage is confirmed', () => {
    const wrapper = mountNotice(true)

    expect(wrapper.find('[role="alertdialog"]').exists()).toBe(true)
    expect(wrapper.text()).toContain(enMessages.errors.service_unavailable)
    expect(wrapper.text()).toContain(enMessages.errors.retry)
    // the banner is for the doubt; the outage is not also a banner
    expect(wrapper.text()).not.toContain(enMessages.errors.connection_lost)
  })

  it('says that it is still unavailable when the retry gets no answer', async () => {
    checkBackend.mockResolvedValue(false)
    const wrapper = mountNotice(true)

    await wrapper.find('button').trigger('click')
    await flushPromises()

    expect(checkBackend).toHaveBeenCalled()
    expect(wrapper.text()).toContain(enMessages.errors.service_unavailable_retry_failed)
  })

  it('says nothing extra on a retry that answers', async () => {
    checkBackend.mockResolvedValue(true)
    const wrapper = mountNotice(true)

    await wrapper.find('button').trigger('click')
    await flushPromises()

    expect(wrapper.text()).not.toContain(enMessages.errors.service_unavailable_retry_failed)
  })
})
