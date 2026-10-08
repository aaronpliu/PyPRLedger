// Version configuration
import packageJson from '../../package.json'

// UI version from package.json (build-time)
export const UI_VERSION = packageJson.version

// The first year the notice covers. The range it is printed as ends at the year
// it is read in, so nobody has to edit this when the year turns.
const COPYRIGHT_START_YEAR = 2026

/**
 * The copyright notice for the year it is read in.
 *
 * `© 2026 Mobile, All rights reserved` while the first year is still the current
 * one, and `© 2026-2027 Mobile, All rights reserved` from the first of January
 * after that: the range widens on its own.
 *
 * Read it at render instead of into a module constant. Frozen in a constant it
 * becomes the year the build was made in, so a deployment that outlives its year
 * keeps claiming the old one.
 */
export function copyrightNotice(now: Date = new Date()): string {
  const year = now.getFullYear()
  const years =
    year > COPYRIGHT_START_YEAR ? `${COPYRIGHT_START_YEAR}-${year}` : `${COPYRIGHT_START_YEAR}`

  return `© ${years} Mobile, All rights reserved`
}

// API version will be fetched from backend at runtime
let apiVersion: string | null = null

/**
 * Fetch API version from backend
 */
export async function fetchApiVersion(): Promise<string> {
  if (apiVersion) {
    return apiVersion as string
  }

  try {
    // Use /api/v1/info endpoint
    const baseUrl = import.meta.env.VITE_API_BASE_URL || '/api/v1'
    const response = await fetch(`${baseUrl}/info`)
    if (response.ok) {
      const data = await response.json()
      apiVersion = data.version || 'unknown'
      return apiVersion as string
    }
  } catch (error) {
    console.warn('Failed to fetch API version:', error)
  }

  apiVersion = 'unknown'
  return apiVersion as string
}

/**
 * Get current API version (cached)
 */
export function getApiVersion(): string {
  return apiVersion || 'loading...'
}
