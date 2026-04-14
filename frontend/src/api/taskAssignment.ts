import request from '@/utils/request'

export interface ReviewerAssignment {
  id: number
  reviewer: string
  reviewer_info?: {
    username: string
    display_name: string
  } | null
  assigned_by_info?: {
    username: string
    display_name: string
  } | null
  assigned_by?: string | null
  assigned_date?: string | null
  assignment_status: 'pending' | 'assigned' | 'in_progress' | 'completed'
  reviewer_comments?: string | null
  created_date: string
  updated_date: string
}

export interface ReviewV2 {
  id: number
  pull_request_id: string
  pull_request_commit_id?: string | null
  project_key: string
  repository_slug: string
  pull_request_user?: string | null
  pull_request_user_info?: {
    username: string
    display_name: string
  } | null
  source_filename?: string | null
  source_branch: string
  target_branch: string
  git_code_diff?: string | null
  ai_suggestions?: any | null
  pull_request_status: string
  metadata?: Record<string, any> | null
  created_date: string
  updated_date: string
  
  // Multi-reviewer fields
  reviewers: ReviewerAssignment[]
  total_reviewers: number
  completed_reviewers: number
  pending_reviewers: number
}

export interface ReviewListResponse {
  items: ReviewV2[]
  total: number
  page: number
  page_size: number
}

export interface AssignReviewerRequest {
  reviewer: string
  comments?: string | null
}

export interface UpdateAssignmentStatusRequest {
  assignment_status: 'pending' | 'assigned' | 'in_progress' | 'completed'
  reviewer_comments?: string | null
}

// Task Assignment API (for review_admin)
export const taskAssignmentApi = {
  /**
   * Get list of reviews with their assignments
   */
  getReviews(params: {
    page?: number
    page_size?: number
    project_key?: string
    reviewer?: string
    status?: string
  }): Promise<ReviewListResponse> {
    return request.get('/task-assignment/', { params })
  },

  /**
   * Get a single review with all assignments
   */
  getReviewById(id: number): Promise<ReviewV2> {
    return request.get(`/task-assignment/${id}`)
  },

  /**
   * Assign a reviewer to a review
   */
  assignReviewer(
    reviewId: number,
    data: AssignReviewerRequest
  ): Promise<{ message: string; assignment: any }> {
    return request.post(`/task-assignment/${reviewId}/assign`, data)
  },

  /**
   * Remove a reviewer assignment
   */
  removeReviewer(reviewId: number, reviewer: string): Promise<{ message: string }> {
    return request.delete(`/task-assignment/${reviewId}/assign/${encodeURIComponent(reviewer)}`)
  },

  /**
   * Update assignment status
   */
  updateAssignmentStatus(
    assignmentId: number,
    data: UpdateAssignmentStatusRequest
  ): Promise<{ message: string; assignment: any }> {
    return request.patch(`/task-assignment/assignments/${assignmentId}/status`, data)
  },

  /**
   * Delete a review and all assignments
   */
  deleteReview(reviewId: number): Promise<{ message: string }> {
    return request.delete(`/task-assignment/${reviewId}`)
  },

  /**
   * Get reviews assigned to current user
   */
  getMyTasks(params: {
    page?: number
    page_size?: number
  }): Promise<ReviewListResponse> {
    return request.get('/task-assignment/my-tasks', { params })
  },
}
