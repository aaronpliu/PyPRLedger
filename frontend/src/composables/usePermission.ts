import { computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { rbacApi } from '@/api/rbac'
import type { RoleAssignment } from '@/types'

export function usePermission() {
  const authStore = useAuthStore()

  // Check if user has specific permission
  const hasPermission = (action: string, resourceType: string, resourceId?: string): boolean => {
    // Not authenticated - no permissions
    if (!authStore.isAuthenticated) {
      return false
    }

    // Admin users have all permissions
    if (authStore.user?.username === 'admin') {
      return true
    }

    // Check if user has review_admin role for review-related actions
    if ((resourceType === 'review' || resourceType === 'reviews') && authStore.user?.roles?.includes('review_admin')) {
      return true
    }

    // Default: deny access
    return false
  }

  // Convenience methods
  const canView = (resourceType: string, resourceId?: string): boolean => {
    return hasPermission('read', resourceType, resourceId)
  }

  const canEdit = (resourceType: string, resourceId?: string): boolean => {
    return hasPermission('update', resourceType, resourceId)
  }

  const canDelete = (resourceType: string, resourceId?: string): boolean => {
    return hasPermission('delete', resourceType, resourceId)
  }

  const canCreate = (resourceType: string): boolean => {
    return hasPermission('create', resourceType)
  }

  const isAdmin = computed(() => {
    // Check if user has admin username or admin role
    return authStore.user?.username === 'admin' || authStore.user?.roles?.includes('admin')
  })

  return {
    hasPermission,
    canView,
    canEdit,
    canDelete,
    canCreate,
    isAdmin,
  }
}
