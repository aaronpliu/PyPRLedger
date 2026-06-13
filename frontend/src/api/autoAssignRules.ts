import request from '@/utils/request'

export interface AutoAssignRule {
  id: number
  name: string
  description?: string | null
  priority: number
  conditions: Record<string, any>
  assign_to: string[]
  max_assignments: number
  starts_at?: string | null
  expires_at?: string | null
  is_active: boolean
  created_by: string
  created_at: string
  updated_at: string
}

export interface AutoAssignRuleCreate {
  name: string
  description?: string | null
  priority: number
  conditions: Record<string, any>
  assign_to: string[]
  max_assignments: number
  starts_at?: string | null
  expires_at?: string | null
  is_active: boolean
}

export interface AutoAssignRuleUpdate {
  name?: string
  description?: string | null
  priority?: number
  conditions?: Record<string, any>
  assign_to?: string[]
  max_assignments?: number
  starts_at?: string | null
  expires_at?: string | null
  is_active?: boolean
}

export interface AutoAssignRuleListResponse {
  items: AutoAssignRule[]
  total: number
  page: number
  page_size: number
}

export interface AutoAssignRuleToggleResponse {
  id: number
  name: string
  is_active: boolean
  message: string
}

export const autoAssignRulesApi = {
  /**
   * List all auto-assignment rules ordered by priority
   */
  listRules(params?: {
    page?: number
    page_size?: number
  }): Promise<AutoAssignRuleListResponse> {
    return request.get('/auto-task-assignment/rules', { params })
  },

  /**
   * Get a single auto-assignment rule by ID
   */
  getRule(ruleId: number): Promise<AutoAssignRule> {
    return request.get(`/auto-task-assignment/rules/${ruleId}`)
  },

  /**
   * Create a new auto-assignment rule
   */
  createRule(data: AutoAssignRuleCreate): Promise<AutoAssignRule> {
    return request.post('/auto-task-assignment/rules', data)
  },

  /**
   * Update an existing auto-assignment rule
   */
  updateRule(ruleId: number, data: AutoAssignRuleUpdate): Promise<AutoAssignRule> {
    return request.put(`/auto-task-assignment/rules/${ruleId}`, data)
  },

  /**
   * Delete an auto-assignment rule
   */
  deleteRule(ruleId: number): Promise<void> {
    return request.delete(`/auto-task-assignment/rules/${ruleId}`)
  },

  /**
   * Toggle the active status of a rule
   */
  toggleRule(ruleId: number): Promise<AutoAssignRuleToggleResponse> {
    return request.patch(`/auto-task-assignment/rules/${ruleId}/toggle`)
  },
}
