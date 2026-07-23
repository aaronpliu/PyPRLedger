import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useAuthStore } from '@/stores/auth'
import { createPinia, setActivePinia } from 'pinia'
import { authApi } from '@/api/auth'
import type { User } from '@/types'

vi.mock('@/api/auth', () => ({
  authApi: {
    login: vi.fn(),
    logout: vi.fn().mockResolvedValue(undefined),
    getCurrentUser: vi.fn(),
    refreshToken: vi.fn(),
  },
}))

const mockUser: User = {
  id: 1,
  username: 'testuser',
  email: 'test@example.com',
  is_active: true,
  git_user_id: null,
  git_username: null,
  avatar_url: null,
  last_login_at: null,
  created_at: '2026-01-01T00:00:00Z',
  roles: ['reviewer'],
}

const mockTokenResponse = {
  access_token: 'token123',
  refresh_token: 'refresh456',
  token_type: 'bearer',
  expires_in: 3600,
  refresh_expires_in: 86400,
}

describe('Auth Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('should initialize with null user', () => {
    const authStore = useAuthStore()
    expect(authStore.user).toBeNull()
    expect(authStore.isAuthenticated).toBe(false)
  })

  it('should set user and tokens on login', async () => {
    vi.mocked(authApi.login).mockResolvedValue(mockTokenResponse)
    vi.mocked(authApi.getCurrentUser).mockResolvedValue(mockUser)

    const authStore = useAuthStore()
    const result = await authStore.login({ username: 'testuser', password: 'password123' })

    expect(result).toBe(true)
    expect(authStore.user).toEqual(mockUser)
    expect(authStore.isAuthenticated).toBe(true)
    expect(localStorage.getItem('access_token')).toBe('token123')
    expect(localStorage.getItem('refresh_token')).toBe('refresh456')
  })

  it('should clear user and tokens on logout', async () => {
    vi.mocked(authApi.login).mockResolvedValue(mockTokenResponse)
    vi.mocked(authApi.getCurrentUser).mockResolvedValue(mockUser)

    const authStore = useAuthStore()
    await authStore.login({ username: 'testuser', password: 'password123' })
    expect(authStore.isAuthenticated).toBe(true)

    await authStore.logout()

    expect(authStore.user).toBeNull()
    expect(authStore.isAuthenticated).toBe(false)
    expect(localStorage.getItem('access_token')).toBeNull()
    expect(localStorage.getItem('refresh_token')).toBeNull()
  })

  it('should restore session from localStorage via initAuth', async () => {
    vi.mocked(authApi.getCurrentUser).mockResolvedValue(mockUser)

    localStorage.setItem('access_token', 'saved_token')
    localStorage.setItem('refresh_token', 'saved_refresh')
    localStorage.setItem('user_profile', JSON.stringify(mockUser))

    const newStore = useAuthStore()
    await newStore.initAuth()

    expect(newStore.isAuthenticated).toBe(true)
    expect(newStore.user?.username).toBe('testuser')
  })

  it('should expose currentUser computed from user ref', async () => {
    vi.mocked(authApi.login).mockResolvedValue(mockTokenResponse)
    vi.mocked(authApi.getCurrentUser).mockResolvedValue(mockUser)

    const authStore = useAuthStore()
    await authStore.login({ username: 'testuser', password: 'password123' })

    expect(authStore.currentUser?.username).toBe('testuser')
  })

  it('should have roles accessible via user', async () => {
    const adminUser: User = { ...mockUser, roles: ['admin'] }
    vi.mocked(authApi.login).mockResolvedValue(mockTokenResponse)
    vi.mocked(authApi.getCurrentUser).mockResolvedValue(adminUser)

    const authStore = useAuthStore()
    await authStore.login({ username: 'admin', password: 'password123' })

    expect(authStore.user?.roles).toContain('admin')
    expect(authStore.user?.roles).not.toContain('reviewer')
  })
})
