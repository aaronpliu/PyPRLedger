import { describe, expect, it } from 'vitest'
import {
  DEFAULT_PRIMARY_COLOR,
  THEME_COLOR_PRESETS,
  applyPrimaryColor,
  buildPrimaryRamp,
  contrastWithWhite,
  normalizeHex,
  resetPrimaryColor,
  resolvedPrimaryColor,
} from '@/utils/themeColor'

/**
 * The shades Element Plus compiles from SCSS for its own primary, read out of
 * `element-plus/dist/index.css` and `theme-chalk/dark/css-vars.css`. Reproducing
 * them is the whole point of the ramp: setting `--el-color-primary` alone would
 * leave every hover, disabled and selected state on the default blue.
 */
const ELEMENT_PLUS_LIGHT_RAMP = {
  '--el-color-primary': '#409eff',
  '--el-color-primary-light-3': '#79bbff',
  '--el-color-primary-light-5': '#a0cfff',
  '--el-color-primary-light-7': '#c6e2ff',
  '--el-color-primary-light-8': '#d9ecff',
  '--el-color-primary-light-9': '#ecf5ff',
  '--el-color-primary-dark-2': '#337ecc',
}

const ELEMENT_PLUS_DARK_RAMP = {
  '--el-color-primary': '#409eff',
  '--el-color-primary-light-3': '#3375b9',
  '--el-color-primary-light-5': '#2a598a',
  '--el-color-primary-light-7': '#213d5b',
  '--el-color-primary-light-8': '#1d3043',
  '--el-color-primary-light-9': '#18222b',
  '--el-color-primary-dark-2': '#66b1ff',
}

function channels(hex: string): number[] {
  const value = hex.replace('#', '')
  return [0, 2, 4].map((offset) => Number.parseInt(value.slice(offset, offset + 2), 16))
}

describe('buildPrimaryRamp', () => {
  it('reproduces the light-mode palette Element Plus ships', () => {
    const ramp = buildPrimaryRamp(DEFAULT_PRIMARY_COLOR, false)

    for (const [variable, expected] of Object.entries(ELEMENT_PLUS_LIGHT_RAMP)) {
      expect(ramp[variable], variable).toBe(expected)
    }
  })

  it('reproduces the dark-mode palette Element Plus ships', () => {
    const ramp = buildPrimaryRamp(DEFAULT_PRIMARY_COLOR, true)

    for (const [variable, expected] of Object.entries(ELEMENT_PLUS_DARK_RAMP)) {
      // Sass rounds one channel of one shade differently; a single step is
      // indistinguishable and the ramp is replaced wholesale either way.
      const actual = channels(ramp[variable])
      channels(expected).forEach((channel, index) => {
        expect(Math.abs(actual[index] - channel), `${variable} channel ${index}`).toBeLessThanOrEqual(1)
      })
    }
  })

  it('shifts dark-2 the other way in dark mode', () => {
    // On light surfaces dark-2 is darker than the accent; on dark ones, lighter.
    const light = buildPrimaryRamp(DEFAULT_PRIMARY_COLOR, false)
    const dark = buildPrimaryRamp(DEFAULT_PRIMARY_COLOR, true)

    expect(light['--el-color-primary-dark-2']).toBe('#337ecc')
    expect(dark['--el-color-primary-dark-2']).toBe('#66b1ff')
  })

  it('blends light shades towards a different surface per mode', () => {
    const light = buildPrimaryRamp(DEFAULT_PRIMARY_COLOR, false)
    const dark = buildPrimaryRamp(DEFAULT_PRIMARY_COLOR, true)

    // Towards white in light mode, towards the dark surface in dark mode.
    expect(light['--el-color-primary-light-9']).toBe('#ecf5ff')
    expect(dark['--el-color-primary-light-9']).not.toBe(light['--el-color-primary-light-9'])
  })

  it('exposes the rgb triplet the accent shadows are built from', () => {
    expect(buildPrimaryRamp(DEFAULT_PRIMARY_COLOR, false)['--el-color-primary-rgb']).toBe('64, 158, 255')
  })

  it('derives every shade from the accent it was given', () => {
    const ramp = buildPrimaryRamp('#e11d48', false)

    expect(ramp['--el-color-primary']).toBe('#e11d48')
    // Halfway to white, channel by channel.
    expect(ramp['--el-color-primary-light-5']).toBe('#f08ea4')
    expect(ramp['--el-color-primary-dark-2']).toBe('#b4173a')
  })

  it('returns nothing for a value that is not a colour', () => {
    expect(buildPrimaryRamp('not-a-colour', false)).toEqual({})
    expect(buildPrimaryRamp('', false)).toEqual({})
  })
})

describe('parse and normalise', () => {
  it('accepts the shapes a colour input can produce', () => {
    expect(normalizeHex('#409EFF')).toBe('#409eff')
    expect(normalizeHex('409eff')).toBe('#409eff')
    expect(normalizeHex('#abc')).toBe('#aabbcc')
    expect(normalizeHex('  #409eff  ')).toBe('#409eff')
  })

  it('rejects anything else', () => {
    expect(normalizeHex('#12345')).toBeNull()
    expect(normalizeHex('rgba(64, 158, 255, 1)')).toBeNull()
    expect(normalizeHex(null)).toBeNull()
    expect(normalizeHex(undefined)).toBeNull()
  })
})

describe('contrastWithWhite', () => {
  it('scores the extremes', () => {
    expect(contrastWithWhite('#ffffff')).toBeCloseTo(1, 5)
    expect(contrastWithWhite('#000000')).toBeCloseTo(21, 1)
  })

  it('scores the accents in use', () => {
    // Element Plus's own primary is what the palette ships with, so this is the
    // bar a custom colour is measured against.
    expect(contrastWithWhite(DEFAULT_PRIMARY_COLOR)).toBeCloseTo(2.78, 1)
    expect(contrastWithWhite('#e11d48')).toBeGreaterThan(4)
  })

  it('flags a colour that white text cannot sit on', () => {
    expect(contrastWithWhite('#facc15')).toBeLessThan(2)
  })
})

describe('applying and resetting', () => {
  it('writes the ramp onto the document root', () => {
    applyPrimaryColor('#0d9488', false)

    const root = document.documentElement
    expect(root.style.getPropertyValue('--el-color-primary')).toBe('#0d9488')
    expect(root.style.getPropertyValue('--el-color-primary-light-9')).toBe(
      buildPrimaryRamp('#0d9488', false)['--el-color-primary-light-9'],
    )

    resetPrimaryColor()
  })

  it('leaves the resolved accent readable for charts and the PDF export', () => {
    applyPrimaryColor('#0d9488', false)
    expect(resolvedPrimaryColor()).toBe('#0d9488')

    // With no override in place the palette's own value answers.
    resetPrimaryColor()
    expect(resolvedPrimaryColor()).toBe(DEFAULT_PRIMARY_COLOR)
  })
})

describe('presets', () => {
  it('offers a colour that is safe to put white text on', () => {
    THEME_COLOR_PRESETS.forEach((preset) => {
      expect(normalizeHex(preset.value), preset.key).not.toBeNull()
      expect(contrastWithWhite(preset.value), preset.key).toBeGreaterThan(2.5)
    })
  })

  it('includes the palette default so it can be restored', () => {
    expect(THEME_COLOR_PRESETS.map((preset) => preset.value)).toContain(DEFAULT_PRIMARY_COLOR)
  })
})
