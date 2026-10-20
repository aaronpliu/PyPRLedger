import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'
import 'dayjs/locale/zh-tw'

const DAYJS_LOCALES: Record<string, string> = {
  en: 'en',
  'zh-CN': 'zh-cn',
  'zh-TW': 'zh-tw',
}

/**
 * Relative dates ("3 days ago") follow the UI language, not the browser's.
 *
 * Kept apart from the i18n instance so anything can align dayjs without importing
 * vue-i18n - a module that pulls it in cannot be used by a test that mocks it.
 */
export function applyDayjsLocale(locale: string) {
  dayjs.locale(DAYJS_LOCALES[locale] ?? 'en')
}
