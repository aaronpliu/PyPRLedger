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
  async getAllBitbucketUsers(limit: number = 500, username?: string): Promise<ReviewerUser[]> {
    const params: any = { limit }
    if (username) {
      params.username = username
    }
    
    const response: any = await request.get('/users', { params })
    return response.items || []
  },

  /**
   * Get active reviewers
   */
  getReviewers(limit: number = 100): Promise<ReviewerListResponse> {
    return request.get('/users/reviewers', { params: { limit } })
  },

  /**
   * Get user by ID
   */
  getUserById(userId: number): Promise<User> {
    return request.get(`/users/${userId}`)
  },

  /**
   * Get user by username
   */
  getUserByUsername(username: string): Promise<User> {
    return request.get(`/users/username/${username}`)
  },

  /**
   * Update user
   */
  updateUser(userId: number, data: Partial<User>): Promise<User> {
    return request.put(`/users/${userId}`, data)
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
    
    const response: any = await request.get('/users/auth-users', { params })
    // Handle response format
    return response.items || []
  },

  /**
   * Search users by username (for delegation - fallback)
   */
  searchUsers(query: string, limit: number = 10): Promise<User[]> {
    return request.get('/users', { params: { search: query, limit } })
  },
}
