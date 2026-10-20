import { createI18n } from 'vue-i18n'
import { applyDayjsLocale } from './utils/dayjsLocale'
import en from './locales/en.json'
import zhCN from './locales/zh-CN.json'
import zhTW from './locales/zh-TW.json'

const messages = {
  en,
  'zh-CN': zhCN,
  'zh-TW': zhTW,
}

export const SUPPORTED_LOCALES = ['en', 'zh-CN', 'zh-TW'] as const
export type AppLocale = (typeof SUPPORTED_LOCALES)[number]

// Get browser language or default to English
const getBrowserLanguage = (): AppLocale => {
  const lang = navigator.language.toLowerCase()
  if (lang.startsWith('zh')) {
    return lang === 'zh-tw' || lang === 'zh-hk' ? 'zh-TW' : 'zh-CN'
  }
  return 'en'
}

// The reader's choice wins over the browser's guess
export const resolveLocale = (): AppLocale => {
  const saved = localStorage.getItem('language')
  if (saved && (SUPPORTED_LOCALES as readonly string[]).includes(saved)) {
    return saved as AppLocale
  }
  return getBrowserLanguage()
}

applyDayjsLocale(resolveLocale())

const i18n = createI18n({
  legacy: false, // Use Composition API
  locale: resolveLocale(),
  fallbackLocale: 'en',
  messages,
})

export default i18n
