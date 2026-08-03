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

  it('should get language flag', () => {
    const languageStore = useLanguage()
    const flag = languageStore.getLanguageFlag('en')
    expect(flag).toBe('🇺🇸')
  })

  it('should handle unknown language code', () => {
    const languageStore = useLanguage()
    expect(languageStore.getLanguageName('unknown')).toBe('unknown')
    expect(languageStore.getLanguageFlag('unknown')).toBe('🌐')
  })
})
