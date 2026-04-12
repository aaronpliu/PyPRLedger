import request from '@/utils/request'
import type { User, PaginatedResponse } from '@/types'

export const usersApi = {
  /**
   * Get active reviewers
   */
  getReviewers(limit: number = 100): Promise<PaginatedResponse<User>> {
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
  async getAllUsers(limit: number = 500): Promise<User[]> {
    const response: any = await request.get('/users/auth-users', { 
      params: { 
        active: true,  // Only active users
        limit: limit 
      } 
    })
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
