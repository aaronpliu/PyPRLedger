import request from '@/utils/request'

/** What the reading below was scoped to. */
export interface InsightsScope {
  project_key: string | null
  repository_slug: string | null
  days: number
  period: string
  generated_at: string
}

export interface InsightsKpis {
  reviews_total: number
  reviews_open: number
  reviews_today: number
  avg_score: number
  good_suggestion_rate: number
  assigned_pending: number
  assigned_in_progress: number
  unassigned_count: number
  active_reviewers: number
}

export interface InsightsTrendPoint {
  period_start: string
  reviews: number
  avg_score: number
  high_scores: number
  assigned: number
  completed: number
}

export interface InsightsCount {
  key: string
  count: number
}

export interface InsightsReviewerStat {
  reviewer: string
  assigned: number
  completed: number
}

export interface InsightsRecentReview {
  project_key: string
  repository_slug: string
  pull_request_id: string
  pull_request_commit_id: string | null
  status: string
  avg_score: number
  created_date: string
}

export interface InsightsBreakdown {
  by_status: InsightsCount[]
  by_reviewer: InsightsReviewerStat[]
  by_project: InsightsCount[]
}

export interface RepositoryInsights {
  scope: InsightsScope
  kpis: InsightsKpis
  trends: InsightsTrendPoint[]
  breakdown: InsightsBreakdown
  recent: InsightsRecentReview[]
}

export interface RepositoryInsightsParams {
  project_key?: string
  repository_slug?: string
  days?: number
  period?: 'daily' | 'weekly' | 'monthly'
}

export const insightsApi = {
  /**
   * One aggregated reading of a repository (or of every repository of a project).
   * The server caches it for a minute, so a polling page is cheap.
   */
  getRepositoryInsights(params: RepositoryInsightsParams): Promise<RepositoryInsights> {
    return request.get('/insights/repository', { params })
  },
}
