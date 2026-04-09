import { createI18n } from 'vue-i18n'
import en from './locales/en.json'
import zhCN from './locales/zh-CN.json'
import zhTW from './locales/zh-TW.json'

const messages = {
  en,
  'zh-CN': zhCN,
  'zh-TW': zhTW,
}

// Get browser language or default to English
const getBrowserLanguage = (): string => {
  const lang = navigator.language
  if (lang.startsWith('zh')) {
    return lang === 'zh-TW' || lang === 'zh-HK' ? 'zh-TW' : 'zh-CN'
  }
  return 'en'
}

// Get saved language or use browser language
const savedLanguage = localStorage.getItem('language')
const defaultLocale = savedLanguage || getBrowserLanguage()

const i18n = createI18n({
  legacy: false, // Use Composition API
  locale: defaultLocale,
  fallbackLocale: 'en',
  messages,
})

export default i18n
