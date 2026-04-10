// User types
export interface User {
  id: number
  username: string
  email: string
  is_active: boolean
  last_login_at: string | null
  created_at: string
  updated_at: string
}

// Auth types
export interface LoginRequest {
  username: string
  password: string
}

export interface RegisterRequest {
  username: string
  email: string
  password: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export interface PasswordChangeRequest {
  old_password: string
  new_password: string
}

// RBAC types
export interface Role {
  id: number
  name: string
  description: string | null
  permissions: Record<string, string[]>
  created_at: string
}

export interface RoleAssignment {
  id: number
  auth_user_id: number
  role_id: number
  role_name?: string  // Added for display purposes
  resource_type: ResourceType
  resource_id: string | null
  granted_by: number | null
  expires_at: string | null
  created_at: string
}

export interface RoleAssignmentRequest {
  role_id: number
  resource_type: ResourceType
  resource_id?: string | null
  expires_at?: string | null
}

// Define a common type for resource types
export type ResourceType = 'global' | 'project' | 'repository';

// Audit types
export interface AuditLog {
  id: number
  auth_user_id: number | null
  action: string
  resource_type: string | null
  resource_id: string | null
  old_values: Record<string, any> | null
  new_values: Record<string, any> | null
  ip_address: string | null
  user_agent: string | null
  request_method: string | null
  request_path: string | null
  response_status: number | null
  execution_time_ms: number | null
  error_message: string | null
  created_at: string
}

export interface AuditLogQuery {
  auth_user_id?: number | null
  resource_type?: string | null
  resource_id?: string | null
  action?: string | null
  request_method?: string | null
  response_status?: number | null
  start_date?: string | null
  end_date?: string | null
  limit?: number
  offset?: number
}

export interface AuditStats {
  period_days: number
  total_actions: number
  actions_by_method: Record<string, number>
  actions_by_type: Record<string, number>
  actions_by_status: Record<string, number>
  top_actors: Array<{
    user_id: number
    action_count: number
  }>
}

// API Response wrapper
export interface ApiResponse<T = any> {
  data?: T
  message?: string
  error?: string
}

// Pagination
export interface PaginatedResponse<T> {
  total: number
  limit: number
  offset: number
  items: T[]
}
