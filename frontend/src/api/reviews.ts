import request from '@/utils/request'

export interface Review {
  id: number
  public_id?: string
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
    git_provider?: string
    created_date: string
    updated_date: string
  } | null
  repository?: Record<string, any> | null
  pull_request_user_info?: Record<string, any> | null
  reviewer_info?: Record<string, any> | null
  
  // Multi-reviewer display fields (for PR owner view)
  total_reviewers?: number
  all_reviewers?: Array<{
    username: string
    display_name: string
  }>
  
  // Score summary
  score_summary?: ReviewScoreSummary | null
  
  // Pin/Flag feature
  is_pinned_by_me?: boolean
  
  // Associated reviews (related/follow-up PRs)
  associated_review_ids?: number[]
  
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

export interface ReviewRawRecord {
  id: number
  public_id?: string
  request_payload: Record<string, any>
  status: 'pending' | 'success' | 'failed'
  error_message?: string | null
  error_details?: Record<string, any> | null
  review_base_id?: number | null
  source_ip?: string | null
  user_agent?: string | null
  created_date: string
  processed_date?: string | null
}

export interface ReviewValidationSummary {
  total_attempted: number
  total_successful: number
  total_failed: number
  success_rate: number
  failed_reviews: ReviewRawRecord[]
  date_range: {
    from: string | null
    to: string | null
  }
}

// Reviews API
// NOTE: Reviews are created by Bitbucket webhook, not from UI
export const reviewsApi = {
  // Get all reviews with pagination (using page/page_size to match backend API)
  getReviews(params: { 
    page?: number
    page_size?: number
    project_key?: string
    repository_slug?: string
    pull_request_id?: string
    pull_request_user?: string
    reviewer?: string
    source_branch?: string
    target_branch?: string
    pull_request_status?: string
    pull_request_commit_id?: string
    date_from?: string
    date_to?: string
    app_names?: string
    search_query?: string
    has_scores?: boolean
    severity?: string
    pinned_only?: boolean
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

  // Get review by ID - uses dedicated endpoint
  async getReviewById(id: number): Promise<Review> {
    const response = await request.get(`/reviews/${id}`, {
      _suppressGlobalError: true,
    } as any)
    return response.data || response
  },

  // Get review by obfuscated public ID
  async getReviewByPublicId(publicId: string): Promise<Review> {
    const response = await request.get(`/reviews/by-public-id/${publicId}`, {
      _suppressGlobalError: true,
    } as any)
    return response.data || response
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
  getStats(params?: { project_key?: string; app_names?: string }): Promise<any> {
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

  /**
   * Get validation summary comparing raw vs successful reviews
   */
  getValidationSummary(params?: {
    date_from?: string
    date_to?: string
    project_key?: string
  }): Promise<ReviewValidationSummary> {
    return request.get('/reviews/validation/summary', { params })
  },

  /**
   * Retry a failed review using stored raw data
   */
  retryFailedReview(rawRecordId: number): Promise<{
    success: boolean
    message: string
    review_id: number
    pull_request_id: string
  }> {
    return request.post(`/reviews/validation/retry/${rawRecordId}`)
  },

  /**
   * Delete a failed or pending raw review record
   */
  deleteFailedReview(rawRecordId: number): Promise<{
    success: boolean
    message: string
  }> {
    return request.delete(`/reviews/validation/raw/${rawRecordId}`)
  },

  /**
   * Get all scores for a specific review (returns array of individual scores)
   */
  getReviewScores(params: {
    project_key: string
    repository_slug: string
    pull_request_id: string
    reviewer?: string
    source_filename?: string
  }): Promise<{ items: ReviewScoreResponse[] }> {
    // Backend returns array directly, request interceptor unwraps response.data
    return request.get('/reviews/scores', { params }).then((scores) => ({
      items: Array.isArray(scores) ? scores : []
    }))
  },

  /**
   * Pin a review (mark as noteworthy for the current user)
   */
  pinReview(reviewId: number): Promise<{ message: string; is_pinned: boolean }> {
    return request.post(`/reviews/${reviewId}/pin`)
  },

  /**
   * Unpin a review (remove personal pin)
   */
  unpinReview(reviewId: number): Promise<{ message: string; is_pinned: boolean }> {
    return request.delete(`/reviews/${reviewId}/pin`)
  },

  /**
   * Associate two reviews together (bidirectional)
   */
  associateReviews(reviewId: number, targetReviewId: number): Promise<{ message: string; associated: boolean }> {
    return request.post(`/reviews/${reviewId}/associate/${targetReviewId}`)
  },

  /**
   * Remove association between two reviews
   */
  disassociateReviews(reviewId: number, targetReviewId: number): Promise<{ message: string; associated: boolean }> {
    return request.delete(`/reviews/${reviewId}/associate/${targetReviewId}`)
  },
}