import request from '@/utils/request'

export interface Review {
  id: number
  pull_request_id: string
  pull_request_commit_id?: string | null
  
  // Business key fields
  project_key: string
  repository_slug: string
  reviewer: string
  pull_request_user: string
  
  source_branch: string
  target_branch: string
  git_code_diff?: string | null
  source_filename?: string | null  // null for PR-level review
  ai_suggestions?: AIReviewSuggestions | null
  reviewer_comments?: string | null
  pull_request_status: string
  metadata?: Record<string, any> | null
  
  created_date: string
  updated_date: string
  
  // Embedded entity information
  app_name?: string
  project?: Record<string, any> | null
  repository?: Record<string, any> | null
  pull_request_user_info?: Record<string, any> | null
  reviewer_info?: Record<string, any> | null
  
  // Score summary
  score_summary?: ReviewScoreSummary | null
  
  // Legacy fields (for backward compatibility)
  pr_url?: string  // May not be present in new API
  reviewer_username?: string  // Alias for 'reviewer'
  status?: string  // Alias for 'pull_request_status'
  summary?: string | null  // Alias for 'reviewer_comments'
  diff_content?: string | null  // Alias for 'git_code_diff'
  created_at?: string  // Alias for 'created_date'
  updated_at?: string  // Alias for 'updated_date'
}

export interface ReviewScoreSummary {
  pull_request_id: string
  project_key: string
  repository_slug: string
  source_filename?: string | null
  total_scores: number
  average_score?: number
  scores: ReviewScoreResponse[]
}

export interface ReviewScoreResponse {
  id: number
  reviewer: string
  reviewer_info?: Record<string, any> | null
  score: number
  max_score?: number
  weight?: number
  comment?: string | null
  reviewer_comments?: string | null
  source_filename?: string | null
  created_date: string
  updated_date?: string
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

  // Get review by composite key (project_key/repository_slug/pull_request_id)
  getReviewByCompositeKey(
    projectKey: string,
    repositorySlug: string,
    pullRequestId: string
  ): Promise<{ items: Review[]; total: number }> {
    return request.get(`/reviews/${encodeURIComponent(projectKey)}/${encodeURIComponent(repositorySlug)}/${encodeURIComponent(pullRequestId)}`)
  },

  // Get review by ID - fetches from list and finds by ID
  async getReviewById(id: number): Promise<Review> {
    // First try to get all reviews and find by ID
    const response = await request.get('/reviews', { params: { page: 1, page_size: 100 } })
    const data = response.data || response
    const review = data.items?.find((r: Review) => r.id === id)
    if (!review) {
      throw new Error(`Review with ID ${id} not found`)
    }
    return review
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
