import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { describeSession, resolveDeviceCategory } from '@/utils/device'
import {
  CLIENT_DEVICE_HEADER,
  collectDeviceInfo,
  getClientDeviceHeader,
  resetDeviceInfoCache,
} from '@/utils/deviceInfo'
import type { SessionDeviceInfo } from '@/types'

/** Chrome 140 on Windows 11. The user agent says Windows 10 and hides the build. */
const CHROME_WINDOWS_11 =
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36'

/** Chrome 140 on Android, where the reduced user agent replaced the model with "K". */
const CHROME_ANDROID_REDUCED =
  'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Mobile Safari/537.36'

/** Safari on macOS 15 — and, character for character, Safari on an iPad. */
const SAFARI_MACINTOSH =
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Safari/605.1.15'

interface UserAgentDataStub {
  mobile?: boolean
  platform?: string
  getHighEntropyValues?: (hints: string[]) => Promise<Record<string, string>>
}

function installUserAgentData(stub: UserAgentDataStub): void {
  Object.defineProperty(navigator, 'userAgentData', { configurable: true, value: stub })
}

function removeUserAgentData(): void {
  Object.defineProperty(navigator, 'userAgentData', { configurable: true, value: undefined })
}

function installTouchPoints(count: number): void {
  Object.defineProperty(navigator, 'maxTouchPoints', { configurable: true, value: count })
}

function installUserAgent(userAgent: string): void {
  Object.defineProperty(navigator, 'userAgent', { configurable: true, value: userAgent })
}

function decodeHeader(header: string): SessionDeviceInfo {
  const padded = header + '='.repeat(-header.length % 4)
  const binary = atob(padded.replace(/-/g, '+').replace(/_/g, '/'))
  return JSON.parse(binary) as SessionDeviceInfo
}

describe('describeSession', () => {
  it('prefers what the device reported over the user agent it froze', () => {
    const device: SessionDeviceInfo = {
      source: 'client-hints',
      category: 'desktop',
      platform: 'Windows',
      platform_version: '15.0.0',
      browser_full_version: '140.0.7339.80',
    }

    const details = describeSession(device, CHROME_WINDOWS_11)

    expect(details.precision).toBe('precise')
    // The user agent calls this Windows 10 whatever the machine actually runs.
    expect(details.osLabel).toBe('Windows 15.0.0')
    // And it truncates the build, which the hints carry in full.
    expect(details.browserLabel).toBe('Chrome 140.0.7339.80')
    expect(details.category).toBe('desktop')
  })

  it('names an Android phone by the model the client hints carry', () => {
    const details = describeSession(
      {
        source: 'client-hints',
        category: 'mobile',
        platform: 'Android',
        platform_version: '14.0.0',
        model: 'Pixel 8',
      },
      CHROME_ANDROID_REDUCED,
    )

    expect(details.label).toBe('Pixel 8')
    expect(details.category).toBe('mobile')
    expect(details.osLabel).toBe('Android 14.0.0')
  })

  it('never shows the placeholder Chromium leaves where the model was', () => {
    const details = describeSession(null, CHROME_ANDROID_REDUCED)

    expect(details.label).not.toBe('K')
    expect(details.label).toContain('Mobile')
    expect(details.precision).toBe('approximate')
  })

  it('keeps the user agent values for Safari and marks them approximate', () => {
    const details = describeSession(null, SAFARI_MACINTOSH)

    expect(details.precision).toBe('approximate')
    // Safari reports no client hints and pins macOS at 10.15.7 for good.
    expect(details.osLabel).toBe('macOS 10.15.7')
    expect(details.browserLabel).toBe('Safari 18.5')
  })

  it('takes the device class from an approximate record but not its platform', () => {
    const details = describeSession(
      { source: 'user-agent', category: 'tablet', platform: 'iOS' },
      SAFARI_MACINTOSH,
    )

    expect(details.category).toBe('tablet')
    expect(details.precision).toBe('approximate')
    expect(details.osLabel).toBe('macOS 10.15.7')
  })

  it('does not classify another device from this one', () => {
    // An iPad and a Macintosh are the same user agent, and a session list shows
    // other devices — so the touch points of the reader prove nothing here.
    expect(describeSession(null, SAFARI_MACINTOSH).category).toBe('desktop')
  })

  it('says nothing rather than guessing when there is nothing to go on', () => {
    expect(describeSession(null, null)).toMatchObject({
      label: 'Unknown device',
      browserLabel: 'Unknown browser',
      osLabel: 'Unknown OS',
      precision: 'unknown',
    })
  })
})

describe('resolveDeviceCategory', () => {
  it('takes touch points as proof that a Macintosh is an iPad', () => {
    expect(resolveDeviceCategory(SAFARI_MACINTOSH, { maxTouchPoints: 5 })).toBe('tablet')
  })

  it('leaves a real Mac a desktop', () => {
    expect(resolveDeviceCategory(SAFARI_MACINTOSH, { maxTouchPoints: 0 })).toBe('desktop')
  })

  it('believes a device that reports itself mobile', () => {
    expect(resolveDeviceCategory(CHROME_ANDROID_REDUCED, { mobile: true })).toBe('mobile')
  })

  it('does not turn a touchscreen laptop into an iPad', () => {
    expect(resolveDeviceCategory(CHROME_WINDOWS_11, { maxTouchPoints: 10 })).toBe('desktop')
  })
})

describe('device reporting', () => {
  beforeEach(() => {
    resetDeviceInfoCache()
    removeUserAgentData()
    installTouchPoints(0)
    installUserAgent(CHROME_WINDOWS_11)
  })

  afterEach(() => {
    removeUserAgentData()
    resetDeviceInfoCache()
  })

  it('uses the header name the server reads', () => {
    expect(CLIENT_DEVICE_HEADER).toBe('X-Client-Device')
  })

  it('reports the client hints when the browser has them', async () => {
    installUserAgentData({
      mobile: false,
      platform: 'Windows',
      getHighEntropyValues: async () => ({
        platform: 'Windows',
        platformVersion: '15.0.0',
        model: '',
        uaFullVersion: '140.0.7339.80',
      }),
    })

    await expect(collectDeviceInfo()).resolves.toEqual({
      source: 'client-hints',
      category: 'desktop',
      platform: 'Windows',
      platform_version: '15.0.0',
      browser_full_version: '140.0.7339.80',
    })
  })

  it('falls back to the user agent when the browser has no client hints', async () => {
    await expect(collectDeviceInfo()).resolves.toEqual({
      source: 'user-agent',
      category: 'desktop',
    })
  })

  it('falls back rather than failing when the hints are refused', async () => {
    installUserAgentData({
      platform: 'Windows',
      getHighEntropyValues: async () => {
        throw new Error('hints not permitted')
      },
    })

    await expect(collectDeviceInfo()).resolves.toEqual({
      source: 'user-agent',
      category: 'desktop',
      platform: 'Windows',
    })
  })

  it('hands an iPad the class the user agent hides', async () => {
    installUserAgent(SAFARI_MACINTOSH)
    installTouchPoints(5)

    await expect(collectDeviceInfo()).resolves.toMatchObject({
      source: 'user-agent',
      category: 'tablet',
    })
  })

  it('sends the record as base64url JSON the server can decode', async () => {
    installUserAgent(SAFARI_MACINTOSH)
    installUserAgentData({
      mobile: true,
      platform: 'Android',
      getHighEntropyValues: async () => ({
        platform: 'Android',
        platformVersion: '14.0.0',
        model: 'Pixel 8',
        uaFullVersion: '140.0.7339.80',
      }),
    })

    const header = await getClientDeviceHeader()

    expect(header).toMatch(/^[A-Za-z0-9_-]+=*$/)
    expect(decodeHeader(header)).toEqual({
      source: 'client-hints',
      category: 'mobile',
      platform: 'Android',
      platform_version: '14.0.0',
      model: 'Pixel 8',
      browser_full_version: '140.0.7339.80',
    })
  })

  it('detects once and reuses the answer for every request', async () => {
    const getHighEntropyValues = vi.fn(async () => ({ platformVersion: '15.0.0' }))
    installUserAgentData({ mobile: false, platform: 'Windows', getHighEntropyValues })

    await getClientDeviceHeader()
    await getClientDeviceHeader()
    await collectDeviceInfo()

    expect(getHighEntropyValues).toHaveBeenCalledTimes(1)
  })
})
