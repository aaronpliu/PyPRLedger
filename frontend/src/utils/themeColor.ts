/**
 * Runtime accent-colour theming for the Element Plus palette.
 *
 * Element Plus exposes its palette as CSS variables, but every value is already
 * baked into the prebuilt stylesheet (`element-plus/dist/index.css`, and
 * `theme-chalk/dark/css-vars.css` for dark mode) — including the shades derived
 * from the primary colour. Setting `--el-color-primary` alone therefore
 * recolours buttons while leaving hover, disabled, striped and selected states
 * blue, so the whole ramp has to be regenerated here.
 *
 * The shades reproduce the arithmetic Element Plus compiles from SCSS: `light-N`
 * blends N×10% towards the surface colour and `dark-2` blends 20% the other way.
 * The surface differs by mode — white on light, `#141414` on dark — and `dark-2`
 * moves *lighter* in dark mode, which is why the ramp is rebuilt whenever the
 * mode changes rather than once at startup.
 *
 * Values are applied as inline styles on `<html>`, which outranks both the
 * library's `html.dark` rule and the `[data-theme='dark']` overrides in
 * `App.vue` without needing `!important`.
 */

/** Element Plus's own primary, which is what the palette falls back to. */
export const DEFAULT_PRIMARY_COLOR = '#409eff'

/** The surface colour `light-N` blends towards in dark mode (Element Plus `$bg-color`). */
const DARK_SURFACE = '#141414'

/**
 * Below this, white text on the accent is hard enough to read that the user
 * should be told. Element Plus's own primary scores 2.78, and its warning
 * colour 2.2, so this is deliberately a nudge rather than a gate.
 */
export const MIN_READABLE_CONTRAST = 2.5

export interface ThemeColorPreset {
  key: string
  label: string
  value: string
}

/** Curated accents, all of which read acceptably with the white text buttons use. */
export const THEME_COLOR_PRESETS: ThemeColorPreset[] = [
  { key: 'blue', label: 'Blue', value: DEFAULT_PRIMARY_COLOR },
  { key: 'indigo', label: 'Indigo', value: '#4f46e5' },
  { key: 'violet', label: 'Violet', value: '#7c3aed' },
  { key: 'teal', label: 'Teal', value: '#0d9488' },
  { key: 'green', label: 'Green', value: '#16a34a' },
  { key: 'amber', label: 'Amber', value: '#d97706' },
  { key: 'rose', label: 'Rose', value: '#e11d48' },
  { key: 'slate', label: 'Slate', value: '#475569' },
]

interface Rgb {
  r: number
  g: number
  b: number
}

/** Parse `#rgb` / `#rrggbb` (with or without `#`), or return null. */
export function parseHex(value: string | null | undefined): Rgb | null {
  if (!value) {
    return null
  }
  const hex = value.trim().replace(/^#/, '')
  const expanded =
    hex.length === 3
      ? hex
          .split('')
          .map((char) => char + char)
          .join('')
      : hex
  if (!/^[0-9a-fA-F]{6}$/.test(expanded)) {
    return null
  }
  return {
    r: Number.parseInt(expanded.slice(0, 2), 16),
    g: Number.parseInt(expanded.slice(2, 4), 16),
    b: Number.parseInt(expanded.slice(4, 6), 16),
  }
}

/** Normalise a colour to `#rrggbb`, or null when it is not a hex colour. */
export function normalizeHex(value: string | null | undefined): string | null {
  const rgb = parseHex(value)
  return rgb ? toHex(rgb) : null
}

function toHex({ r, g, b }: Rgb): string {
  const channel = (value: number) => clamp(Math.round(value)).toString(16).padStart(2, '0')
  return `#${channel(r)}${channel(g)}${channel(b)}`
}

function clamp(value: number): number {
  return Math.min(255, Math.max(0, value))
}

/** Blend `amount` of `to` into `from` — the arithmetic behind Sass's `mix()`. */
function blend(from: Rgb, to: Rgb, amount: number): Rgb {
  return {
    r: from.r * (1 - amount) + to.r * amount,
    g: from.g * (1 - amount) + to.g * amount,
    b: from.b * (1 - amount) + to.b * amount,
  }
}

const WHITE: Rgb = { r: 255, g: 255, b: 255 }
const BLACK: Rgb = { r: 0, g: 0, b: 0 }

/**
 * Build the full palette ramp for one accent colour in one mode.
 *
 * Returns the same variable names Element Plus defines, so applying these
 * replaces the baked-in blue rather than layering on top of it.
 */
export function buildPrimaryRamp(hex: string, isDark: boolean): Record<string, string> {
  const primary = parseHex(hex)
  if (!primary) {
    return {}
  }

  const surface = isDark ? (parseHex(DARK_SURFACE) as Rgb) : WHITE
  // In dark mode Element Plus lifts dark-2 towards white instead of shading it down.
  const darkShift = isDark ? WHITE : BLACK

  const ramp: Record<string, string> = {
    '--el-color-primary': toHex(primary),
    // Element Plus defines this but never uses it; the app needs it for the
    // rgba() shadows and washes around the accent.
    '--el-color-primary-rgb': `${primary.r}, ${primary.g}, ${primary.b}`,
    '--el-color-primary-dark-2': toHex(blend(primary, darkShift, 0.2)),
  }

  for (let step = 1; step <= 9; step += 1) {
    ramp[`--el-color-primary-light-${step}`] = toHex(blend(primary, surface, step / 10))
  }

  return ramp
}

/**
 * WCAG contrast ratio between a colour and white.
 *
 * Element Plus renders white text on the primary colour, so this is what decides
 * whether a custom accent is usable.
 */
export function contrastWithWhite(hex: string): number {
  const rgb = parseHex(hex)
  if (!rgb) {
    return 0
  }
  const luminance =
    0.2126 * relativeLuminance(rgb.r) + 0.7152 * relativeLuminance(rgb.g) + 0.0722 * relativeLuminance(rgb.b)
  return (1.05) / (luminance + 0.05)
}

function relativeLuminance(channel: number): number {
  const normalized = channel / 255
  return normalized <= 0.03928 ? normalized / 12.92 : ((normalized + 0.055) / 1.055) ** 2.4
}

/** Write the ramp for `hex` onto the document root. */
export function applyPrimaryColor(hex: string, isDark: boolean): void {
  const ramp = buildPrimaryRamp(hex, isDark)
  if (Object.keys(ramp).length === 0) {
    return
  }
  for (const [variable, value] of Object.entries(ramp)) {
    document.documentElement.style.setProperty(variable, value)
  }
}

/** Drop the override so the palette falls back to the stylesheet's own values. */
export function resetPrimaryColor(): void {
  const ramp = buildPrimaryRamp(DEFAULT_PRIMARY_COLOR, false)
  for (const variable of Object.keys(ramp)) {
    document.documentElement.style.removeProperty(variable)
  }
}

/**
 * The accent colour actually in effect, resolved to a literal.
 *
 * ECharts and the PDF exporter cannot read CSS variables, so they ask here
 * instead of hardcoding a value that would no longer match the theme.
 */
export function resolvedPrimaryColor(): string {
  return resolvedVariable('--el-color-primary', DEFAULT_PRIMARY_COLOR)
}

/** A resolved shade of the accent, e.g. `-light-3` or `-dark-2`. */
export function resolvedPrimaryShade(shade: string): string {
  return resolvedVariable(`--el-color-primary-${shade}`, DEFAULT_PRIMARY_COLOR)
}

function resolvedVariable(variable: string, fallback: string): string {
  if (typeof window === 'undefined') {
    return fallback
  }
  const value = window.getComputedStyle(document.documentElement).getPropertyValue(variable).trim()
  return value || fallback
}

/**
 * `rgba(r, g, b, alpha)` for a hex colour.
 *
 * Charts hold literal colours rather than CSS variables, so they build their
 * washes from the accent this way — reading the reactive colour, which keeps
 * the chart option computed reactive to a theme change.
 */
export function hexToRgba(hex: string | null | undefined, alpha: number): string {
  const rgb = parseHex(hex) ?? (parseHex(DEFAULT_PRIMARY_COLOR) as Rgb)
  return `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, ${alpha})`
}
