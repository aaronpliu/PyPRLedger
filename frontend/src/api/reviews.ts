import request from '@/utils/request'

export interface Review {
  id: number
  pull_request_id: string
  pull_request_commit_id?: string | null
  
  // Business key fields
  project_key: string
  repository_slug: string
  reviewer: string | null  // Can be null for pending assignment
  pull_request_user: string
  
  source_branch: string
  target_branch: string
  git_code_diff?: string | null
  source_filename?: string | null  // null for PR-level review
  ai_suggestions?: AIReviewSuggestions | null
  reviewer_comments?: string | null
  assignment_status?: 'pending' | 'assigned' | 'in_progress' | 'completed' | string
  assigned_by?: string | null
  assigned_date?: string | null
  pull_request_status: string
  metadata?: Record<string, any> | null
  ai_review_id?: string | null
  
  created_date: string
  updated_date: string
  
  // Embedded entity information
  app_name?: string
  project?: {
    id: number
    project_id: number
    project_name: string
    project_key: string
    project_url: string
    created_date: string
    updated_date: string
  } | null
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
  max_score?: number | null
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

export interface AIReviewSummary {
  total_issues: number
  files_reviewed: number
  critical_count: number
}

export interface AIReviewSuggestions {
  summary?: AIReviewSummary
  issues?: AIReviewIssue[]
  positive_feedback?: string[]
  overall_assessment?: string
}

export interface AIReviewIssue {
  category: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  file: string
  line?: number
  description: string
  suggestion?: string
  code_snippet?: string
}

export interface ReviewUpdate {
  status?: string
  summary?: string | null
}

export interface ReviewAssignmentRequest {
  pull_request_id: string
  project_key: string
  repository_slug: string
  assignee_username: string
  pull_request_user: string
  source_branch: string
  target_branch: string
  pull_request_commit_id?: string | null
  git_code_diff: string
  ai_suggestions?: any
  reviewer_comments?: string
}

// Reviews API
// NOTE: Reviews are created by Bitbucket webhook, not from UI
export const reviewsApi = {
  // Get all reviews with pagination (using page/page_size to match backend API)
  getReviews(params: { 
    page?: number
    page_size?: number
    project_key?: string
  }): Promise<{ total: number; items: Review[]; page: number; page_size: number }> {
    return request.get('/reviews', { params })
  },

  // Get review by composite key (project_key/repository_slug/pull_request_id)
  getReviewByCompositeKey(
    projectKey: string,
    repositorySlug: string,
    pullRequestId: string,
    params?: {
      reviewer?: string
      source_filename?: string
    }
  ): Promise<{ items: Review[]; total: number }> {
    return request.get(
      `/reviews/${encodeURIComponent(projectKey)}/${encodeURIComponent(repositorySlug)}/${encodeURIComponent(pullRequestId)}`,
      { params }
    )
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

  // Delete review using composite key
  deleteReview(projectKey: string, repositorySlug: string, pullRequestId: string): Promise<void> {
    return request.delete(`/reviews/${encodeURIComponent(projectKey)}/${encodeURIComponent(repositorySlug)}/${encodeURIComponent(pullRequestId)}`)
  },

  /**
   * Assign a review task to a reviewer (requires review_admin role)
   */
  assignTask(data: ReviewAssignmentRequest): Promise<Review> {
    return request.post('/reviews/assign', data)
  },

  /**
   * Get review statistics
   */
  getStats(params?: { project_key?: string }): Promise<any> {
    return request.get('/reviews/statistics', { params })
  },

  /**
   * Get reviewer activity trends (assigned + self-raised PRs)
   */
  getReviewerActivityTrends(params?: { period?: 'daily' | 'weekly' | 'monthly'; days?: number }): Promise<{
    period: string
    days: number
    username: string
    trends: Array<{
      date: string
      assigned_reviews: number
      self_raised_prs: number
      total: number
    }>
  }> {
    return request.get('/reviews/trends/reviewer-activity', { params })
  },

  /**
   * Get score trends by current reviewer
   */
  getScoreTrends(params?: { period?: 'daily' | 'weekly' | 'monthly'; days?: number }): Promise<{
    period: string
    days: number
    username: string
    trends: Array<{
      date: string
      average_score: number
      score_count: number
      min_score: number
      max_score: number
    }>
  }> {
    return request.get('/reviews/trends/score-trends', { params })
  },

  /**
   * Get project and repository activity trends
   */
  getProjectRepoActivityTrends(params?: { period?: 'daily' | 'weekly' | 'monthly'; days?: number }): Promise<{
    period: string
    days: number
    username: string
    trends: Array<{
      date: string
      unique_projects: number
      unique_repositories: number
    }>
  }> {
    return request.get('/reviews/trends/project-repo-activity', { params })
  },

  /**
   * Get good suggestions trends (high-quality scores)
   */
  getGoodSuggestionsTrends(params?: { 
    period?: 'daily' | 'weekly' | 'monthly'
    days?: number
    threshold?: number
  }): Promise<{
    period: string
    days: number
    threshold: number
    username: string
    trends: Array<{
      date: string
      good_suggestions: number
      total_scores: number
      percentage: number
    }>
  }> {
    return request.get('/reviews/trends/good-suggestions', { params })
  },
}
