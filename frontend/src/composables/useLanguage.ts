import { useI18n } from 'vue-i18n'
import { computed } from 'vue'

/** How a language is written, which is what the switcher shows. */
export type LanguageScript = 'latin' | 'cjk'

export interface LanguageOption {
  code: string
  name: string
  script: LanguageScript
}

/**
 * The glyph each script is recognised by.
 *
 * Scripts rather than flags: a flag names a country rather than a language, which
 * is how Simplified and Traditional Chinese both ended up under the same one.
 */
export const SCRIPT_GLYPHS: Record<LanguageScript, string> = {
  latin: 'A',
  cjk: '文',
}

export function useLanguage() {
  const { locale, t } = useI18n()

  const currentLanguage = computed(() => locale.value)

  const availableLanguages: LanguageOption[] = [
    { code: 'en', name: 'English', script: 'latin' },
    { code: 'zh-CN', name: '简体中文', script: 'cjk' },
    { code: 'zh-TW', name: '繁體中文', script: 'cjk' },
  ]

  const currentScript = computed<LanguageScript>(
    () => availableLanguages.find((language) => language.code === locale.value)?.script ?? 'latin',
  )

  const setLanguage = (lang: string) => {
    locale.value = lang
    localStorage.setItem('language', lang)
    // Update document title if needed
    document.documentElement.lang = lang
  }

  const getLanguageName = (code: string) => {
    return availableLanguages.find(l => l.code === code)?.name || code
  }

  const glyphForScript = (script: LanguageScript) => SCRIPT_GLYPHS[script]

  return {
    locale,
    t,
    currentLanguage,
    currentScript,
    availableLanguages,
    setLanguage,
    getLanguageName,
    glyphForScript,
  }
}
