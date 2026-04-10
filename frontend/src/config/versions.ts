// Version configuration
import packageJson from '../../package.json'

// UI version from package.json (build-time)
export const UI_VERSION = packageJson.version

// Copyright
export const COPYRIGHT = '© 2026 Mobile, All rights reserved' as const

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
