import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '@/api/auth'
import type { User, LoginRequest, RegisterRequest } from '@/types'
import router from '@/router'

export const useAuthStore = defineStore('auth', () => {
  // State
  const user = ref<User | null>(null)
  const accessToken = ref<string>('')
  const refreshTokenValue = ref<string>('')

  // Getters
  const isAuthenticated = computed(() => !!accessToken.value)
  const currentUser = computed(() => user.value)

  // Actions
  async function login(credentials: LoginRequest) {
    try {
      const response = await authApi.login(credentials)
      accessToken.value = response.access_token
      refreshTokenValue.value = response.refresh_token

      // Store tokens
      localStorage.setItem('access_token', response.access_token)
      localStorage.setItem('refresh_token', response.refresh_token)

      // Fetch user profile
      await fetchUserProfile()

      return true
    } catch (error) {
      console.error('Login failed:', error)
      throw error
    }
  }

  async function register(data: RegisterRequest) {
    try {
      const response = await authApi.register(data)
      accessToken.value = response.access_token
      refreshTokenValue.value = response.refresh_token

      localStorage.setItem('access_token', response.access_token)
      localStorage.setItem('refresh_token', response.refresh_token)

      await fetchUserProfile()
      return true
    } catch (error) {
      console.error('Registration failed:', error)
      throw error
    }
  }

  async function logout() {
    try {
      await authApi.logout()
    } catch (error) {
      console.error('Logout error:', error)
    } finally {
      clearAuth()
      router.push('/login')
    }
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
  function initAuth() {
    const token = localStorage.getItem('access_token')
    const refresh = localStorage.getItem('refresh_token')

    if (token && refresh) {
      accessToken.value = token
      refreshTokenValue.value = refresh
      fetchUserProfile().catch(() => {
        // If fetch fails, tokens are invalid
        clearAuth()
      })
    }
  }

  return {
    user,
    accessToken,
    refreshToken: refreshTokenValue,
    isAuthenticated,
    currentUser,
    login,
    register,
    logout,
    fetchUserProfile,
    clearAuth,
    initAuth,
  }
})
