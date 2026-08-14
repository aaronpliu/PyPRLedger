import { describe, it, expect, beforeEach } from 'vitest'
import { usePermission } from '@/composables/usePermission'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from '@/stores/auth'

describe('usePermission Composable', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('should return false when not authenticated', () => {
    const authStore = useAuthStore()
    authStore.user = null

    const { hasPermission } = usePermission()
    expect(hasPermission('read', 'review')).toBe(false)
  })

  it('should return true for admin user', () => {
    const authStore = useAuthStore()
    authStore.user = {
      id: 1,
      username: 'admin',
      email: 'admin@example.com',
      roles: ['admin'],
    } as any
    ;(authStore as any).accessToken = 'test-token'

    const { hasPermission } = usePermission()
    expect(hasPermission('read', 'review')).toBe(true)
    expect(hasPermission('delete', 'user')).toBe(true)
  })

  it('should check review_admin role for review resources', () => {
    const authStore = useAuthStore()
    authStore.user = {
      id: 2,
      username: 'reviewer',
      email: 'reviewer@example.com',
      roles: ['review_admin'],
    } as any
    ;(authStore as any).accessToken = 'test-token'

    const { hasPermission } = usePermission()
    expect(hasPermission('read', 'review')).toBe(true)
    expect(hasPermission('read', 'reviews')).toBe(true)
    expect(hasPermission('read', 'user')).toBe(false)
  })

  it('should return false for regular user without special roles', () => {
    const authStore = useAuthStore()
    authStore.user = {
      id: 3,
      username: 'regular',
      email: 'regular@example.com',
      roles: ['reviewer'],
    } as any
    ;(authStore as any).accessToken = 'test-token'

    const { hasPermission } = usePermission()
    expect(hasPermission('read', 'review')).toBe(false)
  })

  it('should check isAdmin computed property', () => {
    const authStore = useAuthStore()
    authStore.user = {
      id: 1,
      username: 'admin',
      email: 'admin@example.com',
      roles: ['admin'],
    } as any
    ;(authStore as any).accessToken = 'test-token'

    const { isAdmin } = usePermission()
    expect(isAdmin.value).toBe(true)
  })

  it('should return false for isAdmin when user is not admin', () => {
    const authStore = useAuthStore()
    authStore.user = {
      id: 2,
      username: 'reviewer',
      email: 'reviewer@example.com',
      roles: ['reviewer'],
    } as any
    ;(authStore as any).accessToken = 'test-token'

    const { isAdmin } = usePermission()
    expect(isAdmin.value).toBe(false)
  })

  it('should provide convenience methods', () => {
    const authStore = useAuthStore()
    authStore.user = {
      id: 1,
      username: 'admin',
      email: 'admin@example.com',
      roles: ['admin'],
    } as any
    ;(authStore as any).accessToken = 'test-token'

    const { canView, canEdit, canDelete, canCreate } = usePermission()
    expect(canView('review')).toBe(true)
    expect(canEdit('review')).toBe(true)
    expect(canDelete('review')).toBe(true)
    expect(canCreate('review')).toBe(true)
  })
})
