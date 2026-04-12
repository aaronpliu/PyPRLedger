import request from '@/utils/request'

export interface Score {
  id: number
  reviewer: string
  reviewer_info?: Record<string, any> | null
  score: number
  max_score?: number
  weight?: number
  comment?: string | null
  reviewer_comments?: string | null
  source_filename?: string | null
  pull_request_id: string
  project_key: string
  repository_slug: string
  created_date: string
  updated_date?: string
}

export interface ScoreCreate {
  pull_request_id: string
  pull_request_commit_id: string
  project_key: string
  repository_slug: string
  reviewer: string
  score: number
  reviewer_comments?: string  // Use undefined instead of null for better TypeScript compatibility
  source_filename?: string | null  // null for PR-level score
}

export interface ScoreUpdate {
  score?: number
  comment?: string | null
}

export interface ScoreStats {
  average_score: number
  total_reviews: number
  score_distribution: Record<string, number>
}

// Scores API
// NOTE: Backend uses composite key (project_key/repository_slug/pull_request_id) for score operations
export const scoresApi = {
  // Get all scores for a review target
  getScoresByReview(
    pullRequestId: string,
    projectKey: string,
    repositorySlug: string,
    sourceFilename?: string | null
  ): Promise<Score[]> {
    const params: any = {
      pull_request_id: pullRequestId,
      project_key: projectKey,
      repository_slug: repositorySlug,
    }
    if (sourceFilename !== undefined && sourceFilename !== null) {
      params.source_filename = sourceFilename
    }
    return request.get('/reviews/scores', { params })
  },

  // Create or update score (upsert)
  createScore(data: ScoreCreate): Promise<Score> {
    return request.put('/reviews/score', data)
  },

  // Delete score by reviewer
  deleteScore(
    reviewer: string,
    pullRequestId: string,
    projectKey: string,
    repositorySlug: string,
    sourceFilename?: string | null
  ): Promise<void> {
    const params: any = {
      pull_request_id: pullRequestId,
      project_key: projectKey,
      repository_slug: repositorySlug,
    }
    if (sourceFilename !== undefined && sourceFilename !== null) {
      params.source_filename = sourceFilename
    }
    return request.delete(`/reviews/score/${encodeURIComponent(reviewer)}`, { params })
  },

  // Get score statistics
  getStats(params?: { project_key?: string; repository_slug?: string }): Promise<any> {
    return request.get('/reviews/statistics', { params })
  },
}
