import { resolveDeviceCategory } from '@/utils/device'
import type { SessionDeviceInfo } from '@/types'

/**
 * Collect what this browser can honestly say about its own device, and report it
 * to the server so a session list can describe a device accurately.
 *
 * The user agent string can no longer answer that question on its own: Chromium
 * freezes the browser build, replaces the Android device model with "K", and
 * reports Windows 11 as Windows 10, while Safari pins macOS to 10.15.7 and
 * reports an iPad as a Mac. User-Agent Client Hints carry the real values, but
 * only Chromium exposes them — so the record this returns is tagged with which
 * of the two it came from, and a session list can show the difference.
 *
 * The values are display metadata. They are reported by the client, so they are
 * only ever rendered, never used to authenticate or authorize.
 */

/** The server reads this header in `src/api/v1/endpoints/auth.py`. */
export const CLIENT_DEVICE_HEADER = 'X-Client-Device'

interface UserAgentDataValues {
  platform?: string
  platformVersion?: string
  model?: string
  uaFullVersion?: string
}

interface UserAgentData {
  mobile?: boolean
  platform?: string
  getHighEntropyValues?: (hints: string[]) => Promise<UserAgentDataValues>
}

// Absent from Safari and Firefox, which support neither client hints nor any
// other way to learn their own platform version.
const HIGH_ENTROPY_HINTS = ['platform', 'platformVersion', 'model', 'uaFullVersion']

function readUserAgentData(): UserAgentData | undefined {
  if (typeof navigator === 'undefined') {
    return undefined
  }
  return (navigator as Navigator & { userAgentData?: UserAgentData }).userAgentData
}

/** Chrome reports an empty model for a desktop; leave those fields out instead. */
function orUndefined(value: string | undefined): string | undefined {
  return value ? value : undefined
}

/** Base64url, which keeps the JSON header value to plain ASCII. */
function base64UrlEncode(value: string): string {
  const bytes = new TextEncoder().encode(value)
  let binary = ''
  bytes.forEach((byte) => {
    binary += String.fromCharCode(byte)
  })
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_')
}

async function detectDeviceInfo(): Promise<SessionDeviceInfo> {
  const userAgent = typeof navigator === 'undefined' ? '' : navigator.userAgent
  const maxTouchPoints = typeof navigator === 'undefined' ? 0 : navigator.maxTouchPoints
  const userAgentData = readUserAgentData()

  // This device is the one being described, so its own touch points are the
  // right ones to hand over — that is what catches an iPad reporting as a Mac.
  const category = resolveDeviceCategory(userAgent, {
    mobile: userAgentData?.mobile,
    maxTouchPoints,
  })

  if (!userAgentData?.getHighEntropyValues) {
    return { source: 'user-agent', category }
  }

  try {
    const hints = await userAgentData.getHighEntropyValues(HIGH_ENTROPY_HINTS)
    return {
      source: 'client-hints',
      category,
      platform: orUndefined(hints.platform || userAgentData.platform),
      platform_version: orUndefined(hints.platformVersion),
      model: orUndefined(hints.model),
      browser_full_version: orUndefined(hints.uaFullVersion),
    }
  } catch {
    // The hints may be refused outright; the platform and category still stand.
    return { source: 'user-agent', category, platform: orUndefined(userAgentData.platform) }
  }
}

let pendingDeviceInfo: Promise<SessionDeviceInfo> | undefined
let pendingHeader: Promise<string> | undefined

/** The device record for this browser, detected once and reused. */
export function collectDeviceInfo(): Promise<SessionDeviceInfo> {
  if (!pendingDeviceInfo) {
    // Detection is best effort: a browser that answers none of this still has a
    // session, and an uninformative record is better than a failed login.
    pendingDeviceInfo = detectDeviceInfo().catch(() => ({ source: 'user-agent', category: 'desktop' }))
  }
  return pendingDeviceInfo
}

/** The encoded device record, ready to send as `CLIENT_DEVICE_HEADER`. */
export function getClientDeviceHeader(): Promise<string> {
  if (!pendingHeader) {
    pendingHeader = collectDeviceInfo().then((info) => base64UrlEncode(JSON.stringify(info)))
  }
  return pendingHeader
}

/** Forget the memoised record so a test can detect from a clean slate. */
export function resetDeviceInfoCache(): void {
  pendingDeviceInfo = undefined
  pendingHeader = undefined
}
