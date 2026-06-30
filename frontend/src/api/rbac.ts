import request from '@/utils/request'
import type { Role, RoleAssignment, RoleAssignmentRequest } from '@/types'

// Delegation types
export interface DelegationCreate {
  delegatee_id: number
  role_id: number
  resource_type: string
  resource_id?: string | null
  delegation_scope: Record<string, string[]>
  starts_at: string
  expires_at: string
  reason?: string | null
}

export interface DelegationResponse {
  id: number
  auth_user_id: number
  delegatee_username?: string | null
  delegatee_display_name?: string | null
  role_id: number
  role_name?: string | null
  resource_type: string
  resource_id?: string | null
  granted_by?: number | null
  delegator_id?: number | null
  delegator_username?: string | null
  delegator_display_name?: string | null
  is_delegated: boolean
  delegation_status?: string | null
  delegation_scope?: Record<string, string[]> | null
  delegation_reason?: string | null
  starts_at?: string | null
  expires_at?: string | null
  revoked_by?: number | null
  revoked_at?: string | null
  created_at: string
}

export interface DelegationRevoke {
  reason?: string | null
}

export interface DelegationListQuery {
  delegator_id?: number | null
  delegator_username?: string | null
  delegatee_id?: number | null
  delegatee_username?: string | null
  status?: string | null
  include_expired?: boolean
}

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

  // ===== Delegation APIs =====

  // Create delegation
  createDelegation(data: DelegationCreate): Promise<DelegationResponse> {
    return request.post('/rbac/delegations', data)
  },

  // List delegations
  listDelegations(params?: DelegationListQuery): Promise<DelegationResponse[]> {
    return request.get('/rbac/delegations', { params })
  },

  // Revoke delegation
  revokeDelegation(assignmentId: number, data?: DelegationRevoke): Promise<void> {
    return request.delete(`/rbac/delegations/${assignmentId}`, { data })
  },

  // Get user's delegations (sent or received)
  getUserDelegations(
    userId: number,
    direction: 'sent' | 'received' = 'received',
    includeExpired: boolean = false
  ): Promise<DelegationResponse[]> {
    return request.get(`/rbac/delegations/users/${userId}`, {
      params: { direction, include_expired: includeExpired },
    })
  },

  // Cleanup expired delegations (admin only)
  cleanupExpiredDelegations(): Promise<{ message: string; updated_count: number }> {
    return request.post('/rbac/delegations/cleanup-expired')
  },

  // ===== System Settings APIs =====

  // Get registration enabled setting
  getRegistrationEnabled(): Promise<{ registration_enabled: boolean }> {
    return request.get('/rbac/settings/registration-enabled')
  },

  // Update registration enabled setting
  updateRegistrationEnabled(enabled: boolean): Promise<{ message: string; registration_enabled: boolean }> {
    return request.put('/rbac/settings/registration-enabled', { registration_enabled: enabled })
  },

  // ===== LLM Settings APIs =====

  /** Get LLM proxy settings (apiKey excluded from response) */
  getLlmConfig(): Promise<{
    enabled: boolean
    model: string
    base_url: string
    has_api_key: boolean
  }> {
    return request.get('/rbac/settings/llm')
  },

  /** Update LLM proxy settings */
  updateLlmConfig(data: {
    enabled?: boolean
    model?: string
    base_url?: string
    api_key?: string
  }): Promise<{ message: string }> {
    return request.put('/rbac/settings/llm', data)
  },

  // ===== Banner Settings APIs =====

  /** Get reviews page banner config */
  getBanner(): Promise<BannerConfig> {
    return request.get('/rbac/settings/banner')
  },

  /** Update reviews page banner config */
  updateBanner(data: BannerConfig): Promise<{ message: string }> {
    return request.put('/rbac/settings/banner', data)
  },
}

export interface BannerConfig {
  enabled: boolean
  content: string
  start_date: string
  end_date: string
}
