import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createI18n } from 'vue-i18n'
import LanguageSwitcher from '@/components/common/LanguageSwitcher.vue'
import { SCRIPT_GLYPHS } from '@/composables/useLanguage'
import enMessages from '@/locales/en.json'
import zhCNMessages from '@/locales/zh-CN.json'
import zhTWMessages from '@/locales/zh-TW.json'

const MESSAGES = { en: enMessages, 'zh-CN': zhCNMessages, 'zh-TW': zhTWMessages }

/* eslint-disable @typescript-eslint/no-explicit-any */
type AnyWrapper = any

const mountedWrappers: AnyWrapper[] = []

function mountSwitcher(locale = 'en') {
  const i18n = createI18n({ legacy: false, locale, fallbackLocale: 'en', messages: MESSAGES })
  const wrapper = mount(LanguageSwitcher, { global: { plugins: [ElementPlus, i18n] } })
  mountedWrappers.push(wrapper)
  return { wrapper, i18n }
}

function currentGlyph(wrapper: AnyWrapper): string {
  return wrapper.find('.language-mark__glyph.is-current').text()
}

describe('LanguageSwitcher', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  afterEach(() => {
    mountedWrappers.splice(0).forEach((wrapper) => wrapper.unmount())
    // The dropdown menu is teleported out of the component.
    document.body.innerHTML = ''
  })

  it('shows every script on offer, marking the one in effect', () => {
    const { wrapper } = mountSwitcher('en')

    const glyphs = wrapper.findAll('.language-mark__glyph').map((glyph: AnyWrapper) => glyph.text())
    expect(glyphs).toEqual([SCRIPT_GLYPHS.latin, SCRIPT_GLYPHS.cjk])
    expect(currentGlyph(wrapper)).toBe(SCRIPT_GLYPHS.latin)
    // A two-glyph control cannot say which language it is; the name can.
    expect(wrapper.find('.language-mark').attributes('title')).toBe('English')
  })

  it('marks the CJK glyph once a Chinese language is in effect', () => {
    const { wrapper } = mountSwitcher('zh-TW')

    expect(currentGlyph(wrapper)).toBe(SCRIPT_GLYPHS.cjk)
    expect(wrapper.find('.language-mark').attributes('title')).toBe('繁體中文')
  })

  it('offers each language under its own glyph', async () => {
    const { wrapper } = mountSwitcher()

    await wrapper.find('.language-mark').trigger('click')
    await flushPromises()

    const items = Array.from(document.querySelectorAll('.el-dropdown-menu__item')).map((item) =>
      item.textContent?.trim(),
    )
    expect(items).toEqual(['A English', '文 简体中文', '文 繁體中文'])
  })

  it('switches to the chosen language and remembers it', async () => {
    const { wrapper, i18n } = mountSwitcher('en')

    wrapper.findComponent({ name: 'ElDropdown' }).vm.$emit('command', 'zh-CN')
    await flushPromises()

    expect(i18n.global.locale.value).toBe('zh-CN')
    expect(localStorage.getItem('language')).toBe('zh-CN')
    expect(document.documentElement.lang).toBe('zh-CN')
    // The trigger follows the switch, so the control says where you now are.
    expect(currentGlyph(wrapper)).toBe(SCRIPT_GLYPHS.cjk)
  })
})
