import axios from 'axios'
import type { AxiosError, AxiosInstance, AxiosResponse, InternalAxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'
import { useAuthStore } from '@/stores/auth'

type RetryableRequestConfig = InternalAxiosRequestConfig & {
  _retry?: boolean
}

const AUTH_EXCLUDED_PATHS = ['/auth/login', '/auth/register', '/auth/refresh', '/auth/logout']
let refreshPromise: Promise<string> | null = null
let lastAuthFailureTimestamp = 0

// Create axios instance
const request: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

function normalizeStoredToken(value: string | null): string {
  if (!value || value === 'undefined' || value === 'null') {
    return ''
  }
  return value
}

function isAuthExcluded(url?: string): boolean {
  return AUTH_EXCLUDED_PATHS.some((path) => url?.includes(path))
}

function decodeBase64Url(value: string): string {
  const normalizedValue = value.replace(/-/g, '+').replace(/_/g, '/')
  const padding = normalizedValue.length % 4
  const paddedValue = padding ? normalizedValue.padEnd(normalizedValue.length + (4 - padding), '=') : normalizedValue
  return atob(paddedValue)
}

function shouldRefreshAccessToken(token: string): boolean {
  try {
    const payload = JSON.parse(decodeBase64Url(token.split('.')[1] || '')) as { exp?: number }
    if (!payload.exp) {
      return false
    }
    const now = Math.floor(Date.now() / 1000)
    return payload.exp - now <= 60
  } catch {
    return false
  }
}

async function redirectToLogin() {
  const authStore = useAuthStore()
  authStore.clearAuth()

  const now = Date.now()
  if (now - lastAuthFailureTimestamp > 5000) {
    ElMessage.closeAll()
    ElMessage.error('Your session expired. Please login again.')
    lastAuthFailureTimestamp = now
  }

  if (router.currentRoute.value.path !== '/login') {
    await router.replace('/login')
  }
}

async function refreshAccessToken(): Promise<string> {
  if (!refreshPromise) {
    const authStore = useAuthStore()
    refreshPromise = authStore.refreshSession().finally(() => {
      refreshPromise = null
    })
  }

  return refreshPromise
}

// Request interceptor - add JWT token
request.interceptors.request.use(
  async (config) => {
    if (isAuthExcluded(config.url)) {
      return config
    }

    let token = normalizeStoredToken(localStorage.getItem('access_token'))
    const refreshToken = normalizeStoredToken(localStorage.getItem('refresh_token'))

    if (token && refreshToken && shouldRefreshAccessToken(token)) {
      try {
        token = await refreshAccessToken()
      } catch (error) {
        await redirectToLogin()
        return Promise.reject(error)
      }
    }

    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor - handle errors
request.interceptors.response.use(
  (response: AxiosResponse) => {
    return response.data
  },
  async (error: AxiosError) => {
    const { response } = error
    const originalRequest = error.config as RetryableRequestConfig | undefined
    const responseData = response?.data as { detail?: string; message?: string; error?: string } | undefined

    if (response) {
      switch (response.status) {
        case 401:
          if (originalRequest && !originalRequest._retry && !isAuthExcluded(originalRequest.url)) {
            originalRequest._retry = true
            try {
              const token = await refreshAccessToken()
              originalRequest.headers.Authorization = `Bearer ${token}`
              return request(originalRequest)
            } catch {
              await redirectToLogin()
            }
          } else if (!isAuthExcluded(originalRequest?.url)) {
            await redirectToLogin()
          }
          // Don't show additional error message for 401 on auth endpoints
          break

        case 403:
          // Only show error if not handled by the calling component
          if (!originalRequest?.url?.includes('/auth/')) {
            ElMessage.error('You do not have permission to perform this action.')
          }
          break

        case 404:
          // Only show error if not handled by the calling component
          if (!originalRequest?.url?.includes('/auth/')) {
            ElMessage.error('Resource not found.')
          }
          break

        case 400:
        case 409:
        case 422:
          // For validation errors on auth endpoints, let the view handle it
          // Don't show duplicate messages
          if (!originalRequest?.url?.includes('/auth/')) {
            const errorMessage = responseData?.detail || responseData?.message || 'Validation error.'
            ElMessage.error(errorMessage)
          }
          break

        case 500:
          // Only show generic server error for non-auth endpoints
          if (!originalRequest?.url?.includes('/auth/')) {
            ElMessage.error('Server error. Please try again later.')
          }
          break

        default:
          // For other errors, only show if not an auth endpoint
          if (!originalRequest?.url?.includes('/auth/')) {
            const errorMessage = responseData?.detail || responseData?.message || 'An error occurred.'
            ElMessage.error(errorMessage)
          }
      }
    } else {
      // Network errors - always show
      ElMessage.error('Network error. Please check your connection.')
    }

    return Promise.reject(error)
  }
)

export default request
