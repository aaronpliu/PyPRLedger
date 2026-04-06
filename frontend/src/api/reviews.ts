import request from '@/utils/request'

export interface Review {
  id: number
  pr_url: string
  reviewer_username: string
  status: string
  summary: string | null
  created_at: string
  updated_at: string
}

export interface ReviewCreate {
  pr_url: string
  reviewer_username: string
  status?: string
  summary?: string | null
}

export interface ReviewUpdate {
  status?: string
  summary?: string | null
}

// Reviews API
export const reviewsApi = {
  // Get all reviews with pagination
  getReviews(params: { limit?: number; offset?: number }): Promise<{ total: number; items: Review[] }> {
    return request.get('/reviews', { params })
  },

  // Get review by ID
  getReviewById(id: number): Promise<Review> {
    return request.get(`/reviews/${id}`)
  },

  // Create new review
  createReview(data: ReviewCreate): Promise<Review> {
    return request.post('/reviews', data)
  },

  // Update review
  updateReview(id: number, data: ReviewUpdate): Promise<Review> {
    return request.put(`/reviews/${id}`, data)
  },

  // Delete review
  deleteReview(id: number): Promise<void> {
    return request.delete(`/reviews/${id}`)
  },

  // Search reviews
  searchReviews(query: string): Promise<Review[]> {
    return request.get('/reviews/search', { params: { q: query } })
  },
}
