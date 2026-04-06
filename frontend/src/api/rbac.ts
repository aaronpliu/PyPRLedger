import request from '@/utils/request'
import type { Role, RoleAssignment, RoleAssignmentRequest } from '@/types'

// RBAC API
export const rbacApi = {
  // Get all roles
  getRoles(): Promise<Role[]> {
    return request.get('/rbac/roles')
  },

  // Get role by ID
  getRoleById(roleId: number): Promise<Role> {
    return request.get(`/rbac/roles/${roleId}`)
  },

  // Create role
  createRole(data: Omit<Role, 'id' | 'created_at'>): Promise<Role> {
    return request.post('/rbac/roles', data)
  },

  // Update role
  updateRole(roleId: number, data: Partial<Role>): Promise<Role> {
    return request.put(`/rbac/roles/${roleId}`, data)
  },

  // Get user roles
  getUserRoles(userId: number): Promise<RoleAssignment[]> {
    return request.get(`/rbac/users/${userId}/roles`)
  },

  // Assign role to user
  assignRole(userId: number, data: RoleAssignmentRequest): Promise<RoleAssignment> {
    return request.post(`/rbac/users/${userId}/roles`, data)
  },

  // Revoke role from user
  revokeRole(
    userId: number,
    roleId: number,
    resourceType: string,
    resourceId?: string | null
  ): Promise<void> {
    return request.delete(`/rbac/users/${userId}/roles/${roleId}`, {
      params: { resource_type: resourceType, resource_id: resourceId },
    })
  },
}
