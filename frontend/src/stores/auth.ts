import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '@/api/auth'
import type { User, LoginRequest, RegisterRequest, TokenResponse } from '@/types'
import router from '@/router'
// TODO: Import WebSocket service when backend implements Socket.IO
// import { wsService } from '@/utils/websocket'

const INVALID_STORED_TOKEN_VALUES = new Set(['', 'undefined', 'null'])

export const useAuthStore = defineStore('auth', () => {
  // State
  const user = ref<User | null>(null)
  const accessToken = ref<string>('')
  const refreshTokenValue = ref<string>('')
  const isInitialized = ref<boolean>(false)
  let initPromise: Promise<void> | null = null

  // Getters
  const isAuthenticated = computed(() => !!accessToken.value)
  const currentUser = computed(() => user.value)

  function normalizeStoredToken(value: string | null): string {
    if (!value || INVALID_STORED_TOKEN_VALUES.has(value)) {
      return ''
    }
    return value
  }

  function applyTokenResponse(response: TokenResponse) {
    accessToken.value = response.access_token
    refreshTokenValue.value = response.refresh_token
    localStorage.setItem('access_token', response.access_token)
    localStorage.setItem('refresh_token', response.refresh_token)
  }

  // Actions
  async function login(credentials: LoginRequest) {
    try {
      const response = await authApi.login(credentials)
      applyTokenResponse(response)

      // Fetch user profile
      await fetchUserProfile()

      // TODO: Connect WebSocket when backend implements Socket.IO
      // if (user.value) {
      //   wsService.connect(user.value.id)
      // }
      console.log('WebSocket disabled - backend not implemented yet')

      return true
    } catch (error) {
      console.error('Login failed:', error)
      throw error
    }
  }

  async function register(data: RegisterRequest) {
    try {
      const response = await authApi.register(data)
      applyTokenResponse(response)

      await fetchUserProfile()
      return true
    } catch (error) {
      console.error('Registration failed:', error)
      throw error
    }
  }

  async function logout() {
    const currentRefreshToken = refreshTokenValue.value

    try {
      await authApi.logout(currentRefreshToken || undefined)
    } catch (error) {
      console.error('Logout error:', error)
    } finally {
      // TODO: Disconnect WebSocket when backend implements Socket.IO
      // wsService.disconnect()
      clearAuth()
      router.push('/login')
    }
  }

  async function refreshSession() {
    const currentRefreshToken = refreshTokenValue.value || normalizeStoredToken(localStorage.getItem('refresh_token'))
    if (!currentRefreshToken) {
      clearAuth()
      throw new Error('Refresh token missing')
    }

    const response = await authApi.refreshToken(currentRefreshToken)
    applyTokenResponse(response)
    return response.access_token
  }

  async function fetchUserProfile() {
    try {
      user.value = await authApi.getCurrentUser()
    } catch (error) {
      console.error('Failed to fetch user profile:', error)
      clearAuth()
      throw error
    }
  }

  function clearAuth() {
    user.value = null
    accessToken.value = ''
    refreshTokenValue.value = ''
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
  }

  // Initialize from localStorage
  async function initAuth() {
    if (initPromise) {
      return initPromise
    }

    initPromise = (async () => {
      const token = normalizeStoredToken(localStorage.getItem('access_token'))
      const refresh = normalizeStoredToken(localStorage.getItem('refresh_token'))

      if (!token || !refresh) {
        clearAuth()
        isInitialized.value = true
        initPromise = null
        return
      }

      accessToken.value = token
      refreshTokenValue.value = refresh

      try {
        await fetchUserProfile()
      } catch {
        clearAuth()
      } finally {
        isInitialized.value = true
        initPromise = null
      }
    })()

    return initPromise
  }

  return {
    user,
    accessToken,
    refreshToken: refreshTokenValue,
    isInitialized,
    isAuthenticated,
    currentUser,
    login,
    register,
    logout,
    refreshSession,
    fetchUserProfile,
    clearAuth,
    initAuth,
  }
})
