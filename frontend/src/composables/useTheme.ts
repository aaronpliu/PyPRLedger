import { ref, watch, computed } from 'vue'
import {
  DEFAULT_PRIMARY_COLOR,
  applyPrimaryColor,
  normalizeHex,
  resetPrimaryColor as clearPrimaryColor,
} from '@/utils/themeColor'

const THEME_STORAGE_KEY = 'theme'
const PRIMARY_COLOR_STORAGE_KEY = 'theme_color'
const DARK_MEDIA_QUERY = '(prefers-color-scheme: dark)'

const currentTheme = ref<'light' | 'dark' | 'auto'>('auto')

/**
 * The accent colour in effect for this browser.
 *
 * Element Plus bakes its palette into the stylesheet, so this is applied at
 * runtime by regenerating the whole ramp — see `utils/themeColor.ts`.
 */
const primaryColor = ref<string>(DEFAULT_PRIMARY_COLOR)

/**
 * The single system-preference query for the whole app.
 *
 * This used to be created inside `applyTheme`, which also registered a `change`
 * listener there — so every theme change attached another listener, and each of
 * them re-applied the palette. One query, one listener, attached at module load.
 */
const prefersDarkQuery = window.matchMedia(DARK_MEDIA_QUERY)

/**
 * Whether the system is asking for dark.
 *
 * Held as a ref rather than read on demand so that `isDark` reacts when the
 * system switches while the mode is `auto`; a stale `isDark` would rebuild the
 * palette's shades for the wrong surface.
 */
const systemPrefersDark = ref(prefersDarkQuery.matches)

// Computed property to determine if dark mode is active
const isDark = computed(() =>
  currentTheme.value === 'auto' ? systemPrefersDark.value : currentTheme.value === 'dark',
)

/** Whether the accent is the palette default rather than a personalised one. */
const isCustomPrimaryColor = computed(() => primaryColor.value !== DEFAULT_PRIMARY_COLOR)

function readStoredTheme(): 'light' | 'dark' | 'auto' | null {
  const saved = localStorage.getItem(THEME_STORAGE_KEY)
  return saved === 'light' || saved === 'dark' || saved === 'auto' ? saved : null
}

function readStoredPrimaryColor(): string {
  return normalizeHex(localStorage.getItem(PRIMARY_COLOR_STORAGE_KEY)) ?? DEFAULT_PRIMARY_COLOR
}

// Initialize theme on module load — imported by `main.ts` before the app mounts,
// so the palette is in place before the first paint.
const initTheme = () => {
  const savedTheme = readStoredTheme()
  if (savedTheme) {
    currentTheme.value = savedTheme
  }
  primaryColor.value = readStoredPrimaryColor()
  applyTheme(currentTheme.value)
}

// Watch for theme changes and apply them
watch(currentTheme, (newTheme) => {
  applyTheme(newTheme)
  localStorage.setItem(THEME_STORAGE_KEY, newTheme)
})

// The ramp blends towards a different surface per mode, so a colour change has
// to be re-applied through the same path the mode change uses.
watch(primaryColor, (newColor) => {
  updateElementPlusTheme(isDark.value)
  try {
    localStorage.setItem(PRIMARY_COLOR_STORAGE_KEY, newColor)
  } catch {
    // Storage can be unavailable; the colour still applies for this session.
  }
})

const applyTheme = (theme: 'light' | 'dark' | 'auto') => {
  const actualTheme: 'light' | 'dark' =
    theme === 'auto' ? (systemPrefersDark.value ? 'dark' : 'light') : theme

  document.documentElement.setAttribute('data-theme', actualTheme)
  updateElementPlusTheme(actualTheme === 'dark')
}

const updateElementPlusTheme = (isDark: boolean) => {
  if (isDark) {
    document.documentElement.classList.add('dark')
    // Also set data-theme for custom styles
    document.documentElement.setAttribute('data-theme', 'dark')
  } else {
    document.documentElement.classList.remove('dark')
    document.documentElement.setAttribute('data-theme', 'light')
  }

  applyAccentColor(isDark)
}

/**
 * Put the chosen accent in place, rebuilt for the mode now in effect.
 *
 * The palette default is applied by *removing* the override rather than writing
 * the same values back, so an Element Plus upgrade can still adjust it.
 */
const applyAccentColor = (isDark: boolean) => {
  if (primaryColor.value === DEFAULT_PRIMARY_COLOR) {
    clearPrimaryColor()
    return
  }
  applyPrimaryColor(primaryColor.value, isDark)
}

/**
 * Follow the system preference while the mode is `auto`.
 *
 * The recorded preference is updated whatever the mode, so switching to `auto`
 * later resolves against the system's current answer rather than a stale one.
 */
const handleSystemThemeChange = (event: MediaQueryListEvent) => {
  systemPrefersDark.value = event.matches
  if (currentTheme.value !== 'auto') {
    return
  }
  const actualTheme: 'light' | 'dark' = event.matches ? 'dark' : 'light'
  document.documentElement.setAttribute('data-theme', actualTheme)
  updateElementPlusTheme(event.matches)
}

prefersDarkQuery.addEventListener('change', handleSystemThemeChange)

export const useTheme = () => {
  return {
    currentTheme,
    isDark,
    primaryColor,
    isCustomPrimaryColor,
    setTheme: (theme: 'light' | 'dark' | 'auto') => {
      currentTheme.value = theme
    },
    setPrimaryColor: (color: string) => {
      const normalized = normalizeHex(color)
      if (normalized) {
        primaryColor.value = normalized
      }
    },
    resetPrimaryColor: () => {
      primaryColor.value = DEFAULT_PRIMARY_COLOR
    },
  }
}

// Auto-initialize
initTheme()
