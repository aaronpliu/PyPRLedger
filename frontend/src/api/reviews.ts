import request from '@/utils/request'

export interface Review {
  id: number
  pr_url: string
  reviewer_username: string
  status: string
  summary: string | null
  diff_content?: string | null  // Unified diff from Bitbucket webhook (alias for git_code_diff)
  git_code_diff?: string | null  // Git code diff content
  ai_suggestions?: AIReviewSuggestions | null  // AI review results
  created_at: string
  updated_at: string
}

export interface AIReviewSuggestions {
  Reviewed_files?: number
  Critical_issues?: number
  Total_issues?: number
  issues?: AIReviewIssue[]
  overall_assessment?: string
}

export interface AIReviewIssue {
  issue_type: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  file_name: string
  line_number?: number
  description: string
  suggestion?: string
  code_snippet?: string
}

export interface ReviewUpdate {
  status?: string
  summary?: string | null
}

// Reviews API
// NOTE: Reviews are created by Bitbucket webhook, not from UI
export const reviewsApi = {
  // Get all reviews with pagination (using page/page_size to match backend API)
  getReviews(params: { page?: number; page_size?: number }): Promise<{ total: number; items: Review[]; page: number; page_size: number }> {
    return request.get('/reviews', { params })
  },

  // Get review by ID
  getReviewById(id: number): Promise<Review> {
    return request.get(`/reviews/${id}`)
  },

  // Update review (status only - reviews are read-only except for status)
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
