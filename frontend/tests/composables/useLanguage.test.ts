import { describe, it, expect, beforeEach } from 'vitest'
import { useLanguage } from '@/composables/useLanguage'
import { createPinia, setActivePinia } from 'pinia'

describe('useLanguage Composable', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('should initialize with default language', () => {
    const languageStore = useLanguage()
    expect(languageStore.currentLanguage).toBeDefined()
  })

  it('should get available languages', () => {
    const languageStore = useLanguage()
    expect(languageStore.availableLanguages).toBeInstanceOf(Array)
    expect(languageStore.availableLanguages.length).toBeGreaterThan(0)
  })

  it('should set language correctly', () => {
    const languageStore = useLanguage()
    languageStore.setLanguage('en' as any)
    expect(languageStore.currentLanguage).toBe('en')
  })

  it('should get language name', () => {
    const languageStore = useLanguage()
    const name = languageStore.getLanguageName('en')
    expect(name).toBeDefined()
    expect(typeof name).toBe('string')
  })

  it('should get language flag', () => {
    const languageStore = useLanguage()
    const flag = languageStore.getLanguageFlag('en')
    expect(flag).toBeDefined()
    expect(typeof flag).toBe('string')
  })

  it('should persist language preference', () => {
    const languageStore = useLanguage()
    languageStore.setLanguage('zh-CN' as any)
    
    // Create new instance to test persistence
    const newStore = useLanguage()
    expect(newStore.currentLanguage).toBe('zh-CN')
  })
})
