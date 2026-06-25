import request from '@/utils/request'
import type { User, PaginatedResponse } from '@/types'

export interface ReviewerUser {
  id: number
  user_id: number
  username: string
  display_name: string
  email_address: string
  active: boolean
  is_reviewer: boolean
  created_date: string
  updated_date: string
}

export interface ReviewerListResponse {
  items: ReviewerUser[]
  total: number
  page: number
  page_size: number
}

export const usersApi = {
  /**
   * Get all Bitbucket/Git users (for task assignment - includes all users, not just reviewers)
   */
  async getAllBitbucketUsers(params?: {
    limit?: number
    username?: string
    active?: boolean
    is_reviewer?: boolean
  }): Promise<ReviewerUser[]> {
    const queryParams: any = {}
    if (params?.limit) queryParams.limit = params.limit
    if (params?.username) queryParams.username = params.username
    if (params?.active !== undefined) queryParams.active = params.active
    if (params?.is_reviewer !== undefined) queryParams.is_reviewer = params.is_reviewer

    const response: any = await request.get('/users/git', { params: queryParams })
    return response.items || []
  },

  /**
   * Get active reviewers
   */
  getReviewers(limit: number = 100): Promise<ReviewerListResponse> {
    return request.get('/users/git/reviewers', { params: { limit } })
  },

  /**
   * Get user by ID
   */
  getUserById(userId: number): Promise<User> {
    return request.get(`/users/git/${userId}`)
  },

  /**
   * Get user by username
   */
  getUserByUsername(username: string): Promise<User> {
    return request.get(`/users/git/username/${username}`)
  },

  /**
   * Update a git user (requires system_admin role)
   */
  updateUser(userId: number, data: Record<string, any>): Promise<any> {
    return request.put(`/users/git/${userId}`, data)
  },

  /**
   * Get all active auth users (for delegation)
   * Returns AuthUser records (system login users), not Bitbucket users
   */
  async getAllUsers(limit: number = 500, active?: boolean, username?: string): Promise<User[]> {
    const params: any = { limit }
    if (active !== undefined) {
      params.active = active
    }
    if (username) {
      params.username = username
    }
    
    const response: any = await request.get('/users/auth', { params })
    // Handle response format
    return response.items || []
  },

  /**
   * Search users by username (for delegation - fallback)
   */
  searchUsers(query: string, limit: number = 10): Promise<User[]> {
    return request.get('/users/git', { params: { search: query, limit } })
  },

  /**
   * Upload user avatar
   */
  uploadAvatar(username: string, formData: FormData): Promise<{ avatar_url: string }> {
    return request.post(`/users/auth/${username}/avatar`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
  },

  /**
   * Delete user avatar
   */
  deleteAvatar(username: string): Promise<{ avatar_url: null }> {
    return request.delete(`/users/auth/${username}/avatar`)
  },

  /**
   * Create a new git user (requires system_admin role)
   */
  createGitUser(data: {
    user_id: number
    username: string
    display_name: string
    email_address: string
    is_reviewer?: boolean
  }): Promise<any> {
    return request.post('/users/git', data)
  },

  /**
   * Delete a git user (requires system_admin role)
   */
  deleteGitUser(gitUserId: number): Promise<void> {
    return request.delete(`/users/git/${gitUserId}`)
  },

  /**
   * Toggle reviewer status for a git user (requires system_admin role)
   */
  toggleReviewerStatus(gitUserId: number): Promise<any> {
    return request.patch(`/users/git/${gitUserId}/toggle-reviewer`)
  },

  /**
   * Delete an auth user (requires system_admin role)
   * Permanently deletes the auth user, cascades roles/audit/PATs.
   * Does NOT delete the linked git user.
   */
  deleteAuthUser(authUserId: number): Promise<void> {
    return request.delete(`/users/auth/${authUserId}`)
  },

  /**
   * Activate a user (requires system_admin role)
   */
  activateUser(userId: number): Promise<User> {
    return request.patch(`/users/auth/${userId}/activate`)
  },

  /**
   * Deactivate a user (requires system_admin role)
   */
  deactivateUser(userId: number): Promise<User> {
    return request.patch(`/users/auth/${userId}/deactivate`)
  },
}
