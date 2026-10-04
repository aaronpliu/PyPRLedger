import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import { DEFAULT_PRIMARY_COLOR, buildPrimaryRamp } from '@/utils/themeColor'

/**
 * `useTheme` applies the stored palette as a side effect of being imported, and
 * the app relies on that happening before the first paint. Each case therefore
 * loads the module fresh against the storage state it wants to see.
 */
async function loadTheme() {
  vi.resetModules()
  return import('@/composables/useTheme')
}

const root = () => document.documentElement

function matchMediaMock() {
  return window.matchMedia as unknown as ReturnType<typeof vi.fn>
}

/** The system-preference query the module created, so its listener can be driven by hand. */
function systemQuery() {
  return matchMediaMock().mock.results[0]?.value as { addEventListener: ReturnType<typeof vi.fn> }
}

function systemThemeHandler(): (event: { matches: boolean }) => void {
  return systemQuery().addEventListener.mock.calls[0][1] as (event: { matches: boolean }) => void
}

beforeEach(() => {
  localStorage.clear()
  root().removeAttribute('style')
  root().removeAttribute('data-theme')
  root().classList.remove('dark')
  // Counts are per test: the module asks for the query as it loads.
  matchMediaMock().mockClear()
})

afterEach(() => {
  localStorage.clear()
})

describe('useTheme accent colour', () => {
  it('applies the stored accent as soon as the module loads', async () => {
    localStorage.setItem('theme_color', '#e11d48')

    const { useTheme } = await loadTheme()

    expect(useTheme().primaryColor.value).toBe('#e11d48')
    expect(root().style.getPropertyValue('--el-color-primary')).toBe('#e11d48')
    expect(root().style.getPropertyValue('--el-color-primary-rgb')).toBe('225, 29, 72')
  })

  it('leaves the palette alone when no accent was ever chosen', async () => {
    const { useTheme } = await loadTheme()

    expect(useTheme().primaryColor.value).toBe(DEFAULT_PRIMARY_COLOR)
    // The default is applied by removing the override rather than writing the
    // same values back, so an Element Plus upgrade can still adjust it.
    expect(root().style.getPropertyValue('--el-color-primary')).toBe('')
    expect(useTheme().isCustomPrimaryColor.value).toBe(false)
  })

  it('persists a chosen accent and reports it as custom', async () => {
    const { useTheme } = await loadTheme()
    const theme = useTheme()

    theme.setPrimaryColor('#0d9488')
    await nextTick()

    expect(localStorage.getItem('theme_color')).toBe('#0d9488')
    expect(root().style.getPropertyValue('--el-color-primary')).toBe('#0d9488')
    expect(theme.isCustomPrimaryColor.value).toBe(true)
  })

  it('normalises whatever the colour picker hands over', async () => {
    const { useTheme } = await loadTheme()
    const theme = useTheme()

    theme.setPrimaryColor('#ABC')
    await nextTick()

    expect(theme.primaryColor.value).toBe('#aabbcc')
  })

  it('ignores a stored value that is not a colour', async () => {
    localStorage.setItem('theme_color', 'chartreuse-ish')

    const { useTheme } = await loadTheme()

    expect(useTheme().primaryColor.value).toBe(DEFAULT_PRIMARY_COLOR)
  })

  it('clears the override when the default is chosen again', async () => {
    localStorage.setItem('theme_color', '#0d9488')
    const { useTheme } = await loadTheme()
    const theme = useTheme()
    expect(root().style.getPropertyValue('--el-color-primary')).toBe('#0d9488')

    theme.resetPrimaryColor()
    await nextTick()

    expect(theme.isCustomPrimaryColor.value).toBe(false)
    expect(root().style.getPropertyValue('--el-color-primary')).toBe('')
  })

  it('rebuilds the ramp for the mode in effect, not the one at startup', async () => {
    localStorage.setItem('theme_color', '#0d9488')
    const { useTheme } = await loadTheme()
    const theme = useTheme()

    // Light shades blend towards white…
    expect(root().style.getPropertyValue('--el-color-primary-light-9')).toBe(
      buildPrimaryRamp('#0d9488', false)['--el-color-primary-light-9'],
    )

    theme.setTheme('dark')
    await nextTick()

    // …and towards the dark surface once the mode flips.
    expect(root().classList.contains('dark')).toBe(true)
    expect(root().style.getPropertyValue('--el-color-primary-light-9')).toBe(
      buildPrimaryRamp('#0d9488', true)['--el-color-primary-light-9'],
    )
  })
})

describe('useTheme mode', () => {
  it('restores the stored mode', async () => {
    localStorage.setItem('theme', 'dark')

    const { useTheme } = await loadTheme()

    expect(useTheme().currentTheme.value).toBe('dark')
    expect(root().classList.contains('dark')).toBe(true)
  })

  it('persists a mode change', async () => {
    const { useTheme } = await loadTheme()

    useTheme().setTheme('light')
    await nextTick()

    expect(localStorage.getItem('theme')).toBe('light')
    expect(root().getAttribute('data-theme')).toBe('light')
  })

  it('ignores a stored mode that is not one of the three', async () => {
    localStorage.setItem('theme', 'sepia')

    const { useTheme } = await loadTheme()

    expect(useTheme().currentTheme.value).toBe('auto')
  })
})

describe('following the system preference', () => {
  it('attaches one listener however many times the theme changes', async () => {
    const { useTheme } = await loadTheme()
    const theme = useTheme()

    // Attaching inside `applyTheme` used to add one more listener per change,
    // and every one of them re-applied the palette.
    theme.setTheme('dark')
    await nextTick()
    theme.setTheme('auto')
    await nextTick()
    theme.setTheme('light')
    await nextTick()

    expect(matchMediaMock()).toHaveBeenCalledTimes(1)
    expect(systemQuery().addEventListener).toHaveBeenCalledTimes(1)
  })

  it('switches the mode when the system does, while in auto', async () => {
    const { useTheme } = await loadTheme()
    const theme = useTheme()

    systemThemeHandler()({ matches: true })
    await nextTick()

    expect(theme.isDark.value).toBe(true)
    expect(root().classList.contains('dark')).toBe(true)
    expect(root().getAttribute('data-theme')).toBe('dark')
  })

  it('ignores the system once a mode has been chosen explicitly', async () => {
    const { useTheme } = await loadTheme()
    const theme = useTheme()

    theme.setTheme('light')
    await nextTick()

    systemThemeHandler()({ matches: true })
    await nextTick()

    expect(theme.isDark.value).toBe(false)
    expect(root().classList.contains('dark')).toBe(false)
  })

  it('rebuilds the palette for the mode the system switched to', async () => {
    localStorage.setItem('theme_color', '#e11d48')
    const { useTheme } = await loadTheme()
    const theme = useTheme()

    // The system goes dark while in auto, then the user picks a colour: the ramp
    // must blend towards the dark surface. A stale `isDark` would have used the
    // light one, which is the bug the single listener had to fix.
    systemThemeHandler()({ matches: true })
    await nextTick()
    theme.setPrimaryColor('#0d9488')
    await nextTick()

    expect(root().style.getPropertyValue('--el-color-primary-light-9')).toBe(
      buildPrimaryRamp('#0d9488', true)['--el-color-primary-light-9'],
    )
  })

  it('remembers the last system answer for a later switch to auto', async () => {
    const { useTheme } = await loadTheme()
    const theme = useTheme()

    theme.setTheme('light')
    await nextTick()
    systemThemeHandler()({ matches: true })
    await nextTick()
    expect(theme.isDark.value).toBe(false)

    theme.setTheme('auto')
    await nextTick()

    expect(theme.isDark.value).toBe(true)
    expect(root().classList.contains('dark')).toBe(true)
  })
})
