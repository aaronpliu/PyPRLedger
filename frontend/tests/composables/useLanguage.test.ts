import { describe, it, expect, beforeEach, vi } from 'vitest'
import { ref } from 'vue'
import { useLanguage } from '@/composables/useLanguage'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    locale: ref('en'),
    t: (key: string) => key,
  }),
}))

describe('useLanguage Composable', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('should initialize with default language', () => {
    const languageStore = useLanguage()
    expect(languageStore.currentLanguage.value).toBe('en')
  })

  it('should get available languages', () => {
    const languageStore = useLanguage()
    expect(languageStore.availableLanguages).toBeInstanceOf(Array)
    expect(languageStore.availableLanguages.length).toBe(3)
  })

  it('should describe each language by the script it is written in', () => {
    const languageStore = useLanguage()
    // A flag names a country rather than a language, which is how both Chinese
    // variants ended up sharing one.
    languageStore.availableLanguages.forEach((language) => {
      expect(['latin', 'cjk']).toContain(language.script)
      expect(language).not.toHaveProperty('flag')
    })
  })

  it('should set language correctly', () => {
    const languageStore = useLanguage()
    languageStore.setLanguage('zh-CN')
    expect(languageStore.locale.value).toBe('zh-CN')
    expect(localStorage.getItem('language')).toBe('zh-CN')
  })

  it('should get language name', () => {
    const languageStore = useLanguage()
    const name = languageStore.getLanguageName('en')
    expect(name).toBe('English')
  })

  it('should offer a glyph per script for the switcher', () => {
    const languageStore = useLanguage()
    expect(languageStore.glyphForScript('latin')).toBe('A')
    expect(languageStore.glyphForScript('cjk')).toBe('文')
  })

  it('should report the script of the language in effect', () => {
    const languageStore = useLanguage()
    expect(languageStore.currentScript.value).toBe('latin')

    languageStore.setLanguage('zh-CN')

    expect(languageStore.currentScript.value).toBe('cjk')
  })

  it('should handle unknown language code', () => {
    const languageStore = useLanguage()
    expect(languageStore.getLanguageName('unknown')).toBe('unknown')
  })
})
