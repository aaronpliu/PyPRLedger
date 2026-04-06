import request from '@/utils/request'

export interface Score {
  id: number
  review_id: number
  category: string
  score: number
  max_score: number
  weight: number
  comment: string | null
  created_at: string
  updated_at: string
}

export interface ScoreCreate {
  review_id: number
  category: string
  score: number
  max_score?: number
  weight?: number
  comment?: string | null
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
export const scoresApi = {
  // Get scores for a review
  getScoresByReview(reviewId: number): Promise<Score[]> {
    return request.get(`/reviews/${reviewId}/scores`)
  },

  // Create score
  createScore(data: ScoreCreate): Promise<Score> {
    return request.post('/scores', data)
  },

  // Update score
  updateScore(id: number, data: ScoreUpdate): Promise<Score> {
    return request.put(`/scores/${id}`, data)
  },

  // Delete score
  deleteScore(id: number): Promise<void> {
    return request.delete(`/scores/${id}`)
  },

  // Get score statistics
  getStats(params?: { project_id?: string; repository_id?: string }): Promise<ScoreStats> {
    return request.get('/scores/stats', { params })
  },

  // Get scores by project
  getScoresByProject(projectId: string): Promise<Score[]> {
    return request.get(`/projects/${projectId}/scores`)
  },
}
