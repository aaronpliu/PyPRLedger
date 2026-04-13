import { UAParser } from 'ua-parser-js'

export interface SessionDeviceDetails {
  category: 'desktop' | 'mobile' | 'tablet'
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
      category: 'desktop',
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

  const category = device.type === 'mobile'
    ? 'mobile'
    : device.type === 'tablet'
      ? 'tablet'
      : 'desktop'
  const deviceType = category === 'mobile' ? 'Mobile' : category === 'tablet' ? 'Tablet' : 'Desktop'

  const vendorModel = compactParts([device.vendor, device.model]).join(' ')
  const browserLabel = compactParts([browser.name, browser.version]).join(' ') || 'Unknown browser'
  const osLabel = compactParts([os.name, os.version]).join(' ') || 'Unknown OS'
  const label = vendorModel || `${deviceType} · ${browser.name || 'Browser'}`

  return {
    category,
    label,
    browserLabel,
    osLabel,
    rawUserAgent: userAgent,
  }
}