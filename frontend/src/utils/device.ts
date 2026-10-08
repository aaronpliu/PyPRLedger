import { UAParser } from 'ua-parser-js'
import type { DeviceCategory, SessionDeviceInfo } from '@/types'

/**
 * How much a device description can be trusted.
 *
 * `precise` when the device reported itself through User-Agent Client Hints,
 * `approximate` when the user agent string was all we had, and `unknown` when
 * there was nothing to go on at all.
 */
export type DevicePrecision = 'precise' | 'approximate' | 'unknown'

export interface SessionDeviceDetails {
  category: DeviceCategory
  label: string
  browserLabel: string
  osLabel: string
  rawUserAgent: string
  precision: DevicePrecision
}

/**
 * What Chromium substitutes for the device model once the user agent is reduced.
 * Carrying it through would label an Android phone "K".
 */
const REDUCED_UA_MODEL_PLACEHOLDER = 'K'

function compactParts(parts: Array<string | undefined | null>): string[] {
  return parts.filter((part): part is string => Boolean(part && part.trim())).map((part) => part.trim())
}

/**
 * Classify a device from whatever is available.
 *
 * An iPad running iPadOS 13 or later reports itself as a Macintosh and the user
 * agent holds no hint that it is not one — but its touch points give it away, so
 * a caller that is looking at its own device should pass them in. That signal is
 * deliberately optional: on a session belonging to another device the viewer's
 * touch points say nothing about it, and classifying on them would be guessing.
 */
export function resolveDeviceCategory(
  userAgent: string | null | undefined,
  hint: { mobile?: boolean; maxTouchPoints?: number } = {},
): DeviceCategory {
  if ((hint.maxTouchPoints ?? 0) > 1 && /Macintosh/.test(userAgent ?? '')) {
    return 'tablet'
  }
  if (hint.mobile === true) {
    return 'mobile'
  }
  const { type } = new UAParser(userAgent || undefined).getDevice()
  if (type === 'mobile' || type === 'tablet') {
    return type
  }
  return 'desktop'
}

/**
 * Describe a session's device for display.
 *
 * Prefers the record the device reported about itself and falls back to the user
 * agent string field by field, because the two are not equally truthful: the user
 * agent pins Windows 11 to "Windows 10", fixes macOS at 10.15.7, and truncates
 * the browser build to a frozen "140.0.0.0". What the user agent is still good
 * for is the browser's name, which client hints do not carry as a display name.
 */
export function describeSession(
  device: SessionDeviceInfo | null | undefined,
  userAgent: string | null | undefined,
): SessionDeviceDetails {
  if (!device && !userAgent) {
    return {
      category: 'desktop',
      label: 'Unknown device',
      browserLabel: 'Unknown browser',
      osLabel: 'Unknown OS',
      rawUserAgent: '',
      precision: 'unknown',
    }
  }

  const hasHints = device?.source === 'client-hints'
  const parser = new UAParser(userAgent || undefined)
  const parsedDevice = parser.getDevice()
  const browser = parser.getBrowser()
  const os = parser.getOS()

  const category = device?.category ?? resolveDeviceCategory(userAgent)
  const typeLabel = category === 'mobile' ? 'Mobile' : category === 'tablet' ? 'Tablet' : 'Desktop'

  const browserVersion = (hasHints && device?.browser_full_version) || browser.version
  const browserLabel = compactParts([browser.name, browserVersion]).join(' ') || 'Unknown browser'

  const reportedOs = hasHints
    ? compactParts([device?.platform, device?.platform_version]).join(' ')
    : ''
  const osLabel = reportedOs || compactParts([os.name, os.version]).join(' ') || 'Unknown OS'

  const parsedModel = parsedDevice.model === REDUCED_UA_MODEL_PLACEHOLDER ? undefined : parsedDevice.model
  const vendorModel = compactParts([parsedDevice.vendor, parsedModel]).join(' ')
  const label = (hasHints && device?.model) || vendorModel || `${typeLabel} · ${browser.name || 'Browser'}`

  return {
    category,
    label,
    browserLabel,
    osLabel,
    rawUserAgent: userAgent ?? '',
    precision: hasHints ? 'precise' : userAgent ? 'approximate' : 'unknown',
  }
}
