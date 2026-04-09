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
}
