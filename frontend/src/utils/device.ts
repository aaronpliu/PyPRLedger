import { UAParser } from 'ua-parser-js'

export interface SessionDeviceDetails {
  label: string
  browserLabel: string
  osLabel: string
  rawUserAgent: string
}

function compactParts(parts: Array<string | undefined | null>): string[] {
  return parts.filter((part): part is string => Boolean(part && part.trim())).map((part) => part.trim())
}

export function getSessionDeviceDetails(userAgent: string | null | undefined): SessionDeviceDetails {
  if (!userAgent) {
    return {
      label: 'Unknown device',
      browserLabel: 'Unknown browser',
      osLabel: 'Unknown OS',
      rawUserAgent: '',
    }
  }

  const parser = new UAParser(userAgent)
  const device = parser.getDevice()
  const browser = parser.getBrowser()
  const os = parser.getOS()

  const deviceType = device.type === 'mobile'
    ? 'Mobile'
    : device.type === 'tablet'
      ? 'Tablet'
      : device.type === 'smarttv'
        ? 'TV'
        : device.type === 'wearable'
          ? 'Wearable'
          : 'Desktop'

  const vendorModel = compactParts([device.vendor, device.model]).join(' ')
  const browserLabel = compactParts([browser.name, browser.version]).join(' ') || 'Unknown browser'
  const osLabel = compactParts([os.name, os.version]).join(' ') || 'Unknown OS'
  const label = vendorModel || `${deviceType} · ${browser.name || 'Browser'}`

  return {
    label,
    browserLabel,
    osLabel,
    rawUserAgent: userAgent,
  }
}