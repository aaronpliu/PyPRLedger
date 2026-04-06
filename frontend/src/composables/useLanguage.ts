import { useI18n } from 'vue-i18n'
import { computed } from 'vue'

export function useLanguage() {
  const { locale, t } = useI18n()

  const currentLanguage = computed(() => locale.value)

  const availableLanguages = [
    { code: 'en', name: 'English', flag: '🇺🇸' },
    { code: 'zh-CN', name: '简体中文', flag: '🇨🇳' },
    { code: 'zh-TW', name: '繁體中文', flag: '🇹🇼' },
  ]

  const setLanguage = (lang: string) => {
    locale.value = lang
    localStorage.setItem('language', lang)
    // Update document title if needed
    document.documentElement.lang = lang
  }

  const getLanguageName = (code: string) => {
    return availableLanguages.find(l => l.code === code)?.name || code
  }

  const getLanguageFlag = (code: string) => {
    return availableLanguages.find(l => l.code === code)?.flag || '🌐'
  }

  return {
    locale,
    t,
    currentLanguage,
    availableLanguages,
    setLanguage,
    getLanguageName,
    getLanguageFlag,
  }
}
