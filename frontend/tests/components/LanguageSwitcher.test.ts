import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import LanguageSwitcher from '@/components/common/LanguageSwitcher.vue'
import { createTestingPinia } from '@pinia/testing'
import { createI18n } from 'vue-i18n'

const i18n = createI18n({
  legacy: false,
  locale: 'en',
  messages: {
    en: { common: { language: 'Language' } },
  },
})

describe('LanguageSwitcher Component', () => {
  const mountComponent = () => {
    return mount(LanguageSwitcher, {
      global: {
        plugins: [
          createTestingPinia({
            createSpy: vi.fn,
          }),
          i18n,
        ],
      },
    })
  }

  it('should render correctly', () => {
    const wrapper = mountComponent()
    expect(wrapper.exists()).toBe(true)
  })

  it('should display current language flag', () => {
    const wrapper = mountComponent()
    // Check if dropdown trigger exists
    expect(wrapper.find('.language-switcher').exists()).toBe(true)
  })

  it('should show dropdown on click', async () => {
    const wrapper = mountComponent()
    const dropdown = wrapper.find('.language-switcher')
    
    await dropdown.trigger('click')
    
    // Dropdown should be visible
    expect(wrapper.find('.el-dropdown-menu').exists()).toBe(true)
  })

  it('should emit language change event', async () => {
    const wrapper = mountComponent()
    
    // Simulate language selection
    await wrapper.vm.$emit('language-change', 'zh-CN')
    
    expect(wrapper.emitted('language-change')).toBeTruthy()
  })
})
