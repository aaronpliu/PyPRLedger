import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useAuthStore } from '@/stores/auth'
import { createPinia, setActivePinia } from 'pinia'

describe('Auth Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('should initialize with null user', () => {
    const authStore = useAuthStore()
    expect(authStore.user).toBeNull()
    expect(authStore.isAuthenticated).toBe(false)
  })

  it('should set user on login', () => {
    const authStore = useAuthStore()
    const mockUser = {
      id: 1,
      username: 'testuser',
      email: 'test@example.com',
      roles: ['reviewer'],
    }
    
    authStore.login(mockUser as any, 'token123', 'refresh456')
    
    expect(authStore.user).toEqual(mockUser)
    expect(authStore.isAuthenticated).toBe(true)
    expect(localStorage.getItem('access_token')).toBe('token123')
    expect(localStorage.getItem('refresh_token')).toBe('refresh456')
  })

  it('should clear user on logout', () => {
    const authStore = useAuthStore()
    const mockUser = {
      id: 1,
      username: 'testuser',
      email: 'test@example.com',
      roles: ['reviewer'],
    }
    
    authStore.login(mockUser as any, 'token123', 'refresh456')
    expect(authStore.isAuthenticated).toBe(true)
    
    authStore.logout()
    
    expect(authStore.user).toBeNull()
    expect(authStore.isAuthenticated).toBe(false)
    expect(localStorage.getItem('access_token')).toBeNull()
    expect(localStorage.getItem('refresh_token')).toBeNull()
  })

  it('should restore session from localStorage', () => {
    const authStore = useAuthStore()
    localStorage.setItem('access_token', 'saved_token')
    localStorage.setItem('refresh_token', 'saved_refresh')
    localStorage.setItem('user', JSON.stringify({
      id: 1,
      username: 'saved_user',
      email: 'saved@example.com',
      roles: ['admin'],
    }))
    
    // Create new store instance
    const newStore = useAuthStore()
    expect(newStore.isAuthenticated).toBe(true)
    expect(newStore.user?.username).toBe('saved_user')
  })

  it('should update user profile', () => {
    const authStore = useAuthStore()
    const mockUser = {
      id: 1,
      username: 'testuser',
      email: 'test@example.com',
      roles: ['reviewer'],
    }
    
    authStore.login(mockUser as any, 'token123', 'refresh456')
    
    authStore.updateProfile({
      username: 'newusername',
      email: 'newemail@example.com',
    })
    
    expect(authStore.user?.username).toBe('newusername')
    expect(authStore.user?.email).toBe('newemail@example.com')
  })

  it('should check if user has role', () => {
    const authStore = useAuthStore()
    const mockUser = {
      id: 1,
      username: 'testuser',
      email: 'test@example.com',
      roles: ['reviewer', 'manager'],
    }
    
    authStore.login(mockUser as any, 'token123', 'refresh456')
    
    expect(authStore.hasRole('reviewer')).toBe(true)
    expect(authStore.hasRole('admin')).toBe(false)
  })

  it('should check if user is admin', () => {
    const authStore = useAuthStore()
    const mockUser = {
      id: 1,
      username: 'testuser',
      email: 'test@example.com',
      roles: ['admin'],
    }
    
    authStore.login(mockUser as any, 'token123', 'refresh456')
    expect(authStore.isAdmin()).toBe(true)
    
    authStore.logout()
    expect(authStore.isAdmin()).toBe(false)
  })
})
