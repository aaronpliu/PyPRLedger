import { computed, ref } from 'vue'
import dayjs from 'dayjs'
import type { Dayjs } from 'dayjs'
import isoWeek from 'dayjs/plugin/isoWeek'
import type { ReviewV2 } from '@/api/taskAssignment'
import { ANALYTICS_PERIOD_WINDOWS, type AnalyticsPeriod } from '@/config/analytics'

// ISO weeks: a week that straddles new year belongs to its week-year, not to the
// calendar year its days happen to fall in.
dayjs.extend(isoWeek)

export type { AnalyticsPeriod }

const PERIOD_STEPS: Record<AnalyticsPeriod, { unit: 'day' | 'week' | 'month'; startOf: 'day' | 'isoWeek' | 'month' }> = {
  daily: { unit: 'day', startOf: 'day' },
  weekly: { unit: 'week', startOf: 'isoWeek' },
  monthly: { unit: 'month', startOf: 'month' },
}

const pad2 = (value: number) => String(value).padStart(2, '0')

/**
 * The bucket a date falls in.
 *
 * The week number is padded so the keys read in the order they happen: as plain
 * strings `2026-W9` sorts after `2026-W10`, which is how the axis came out of
 * order every January.
 */
function periodKey(date: Dayjs, period: AnalyticsPeriod): string {
  switch (period) {
    case 'weekly':
      return `${date.isoWeekYear()}-W${pad2(date.isoWeek())}`
    case 'monthly':
      return date.format('YYYY-MM')
    default:
      return date.format('YYYY-MM-DD')
  }
}

/**
 * Every bucket in the window, oldest first.
 *
 * Built from the calendar rather than from the reviews, so a period without
 * reviews is a real zero on the axis instead of a gap the line jumps over.
 *
 * The size defaults to `ANALYTICS_PERIOD_WINDOWS`; pass one to widen or narrow
 * this call without touching the configured default.
 */
function periodWindow(period: AnalyticsPeriod, windowSize?: number): string[] {
  const { unit, startOf } = PERIOD_STEPS[period]
  const count = windowSize ?? ANALYTICS_PERIOD_WINDOWS[period]
  const buckets: string[] = []
  for (let ago = count - 1; ago >= 0; ago--) {
    buckets.push(periodKey(dayjs().startOf(startOf).subtract(ago, unit), period))
  }
  return buckets
}

export interface TimePeriodData {
  date: string
  count: number
  assigned?: number
  completed?: number
}

export interface PRUserData {
  username: string
  count: number
}

export interface ProjectData {
  project_key: string
  repository_slug: string
  app_name?: string
  count: number
}

export interface ReviewerData {
  reviewer: string
  display_name?: string
  assigned: number
  completed: number
  in_progress: number
  pending: number
}

export interface SeveritySeriesPoint {
  date: string
  value: number
}

export interface SeveritySeries {
  name: string
  data: SeveritySeriesPoint[]
  color: string
}

type IssueSeverity = 'low' | 'medium' | 'high' | 'critical'

const SEVERITY_ORDER: IssueSeverity[] = ['low', 'medium', 'high', 'critical']

const SEVERITY_COLORS: Record<IssueSeverity, string> = {
  low: '#3b82f6',
  medium: '#eab308',
  high: '#f97316',
  critical: '#ef4444',
}

/**
 * Composable for task assignment analytics data aggregation
 */
export function useTaskAssignmentAnalytics() {
  const reviews = ref<ReviewV2[]>([])

  /**
   * Aggregate reviews by time period (daily/weekly/monthly)
   */
  const aggregateByTimePeriod = (
    period: AnalyticsPeriod,
    windowSize?: number
  ): TimePeriodData[] => {
    const buckets = periodWindow(period, windowSize)
    const grouped: Record<string, TimePeriodData> = {}
    // The window is the axis, in the order the calendar puts it in: no sorting,
    // and no leap over a period that happens to have no reviews.
    buckets.forEach((key) => {
      grouped[key] = { date: key, count: 0, assigned: 0, completed: 0 }
    })

    let inWindow = 0
    reviews.value.forEach((review) => {
      const bucket = grouped[periodKey(dayjs(review.created_date), period)]
      if (!bucket) return // Older than the window, so it belongs to no point.
      inWindow++

      bucket.count++
      review.reviewers?.forEach((assignment) => {
        bucket.assigned!++
        if (assignment.assignment_status === 'completed') {
          bucket.completed!++
        }
      })
    })

    // Nothing in the window: the chart says so rather than drawing a flat line
    // and looking like a measurement.
    return inWindow === 0 ? [] : buckets.map((key) => grouped[key])
  }

  /**
   * Aggregate reviews by PR user
   */
  const aggregateByPRUser = (): PRUserData[] => {
    const grouped: Record<string, number> = {}

    reviews.value.forEach((review) => {
      const username = review.pull_request_user || 'Unknown'
      grouped[username] = (grouped[username] || 0) + 1
    })

    // Convert to array and sort by count (descending)
    return Object.entries(grouped)
      .map(([username, count]) => ({ username, count }))
      .sort((a, b) => b.count - a.count)
  }

  /**
   * Aggregate reviews by project/repository
   */
  const aggregateByProject = (): ProjectData[] => {
    const grouped: Record<string, ProjectData> = {}

    reviews.value.forEach((review) => {
      const key = `${review.project_key}/${review.repository_slug}`
      
      if (!grouped[key]) {
        grouped[key] = {
          project_key: review.project_key,
          repository_slug: review.repository_slug,
          app_name: review.app_name,
          count: 0,
        }
      }

      grouped[key].count++
    })

    // Convert to array and sort by count (descending)
    return Object.values(grouped).sort((a, b) => b.count - a.count)
  }

  /**
   * Aggregate assignments by reviewer
   */
  const aggregateByReviewer = (): ReviewerData[] => {
    const grouped: Record<string, ReviewerData> = {}

    reviews.value.forEach((review) => {
      review.reviewers?.forEach((assignment) => {
        const reviewer = assignment.reviewer
        const displayName = assignment.reviewer_info?.display_name || reviewer

        if (!grouped[reviewer]) {
          grouped[reviewer] = {
            reviewer,
            display_name: displayName,
            assigned: 0,
            completed: 0,
            in_progress: 0,
            pending: 0,
          }
        }

        grouped[reviewer].assigned++

        switch (assignment.assignment_status) {
          case 'completed':
            grouped[reviewer].completed++
            break
          case 'in_progress':
            grouped[reviewer].in_progress++
            break
          case 'assigned':
          case 'pending':
          default:
            grouped[reviewer].pending++
            break
        }
      })
    })

    // Convert to array and sort by assigned count (descending)
    return Object.values(grouped).sort((a, b) => b.assigned - a.assigned)
  }

  /**
   * Reviews grouped by the pull request they belong to.
   *
   * A review row is stored per source file, so one PR can arrive as several; the
   * repository is part of the key because a PR number is only unique within one.
   */
  const groupByPullRequest = (): Map<string, ReviewV2[]> => {
    const grouped = new Map<string, ReviewV2[]>()
    reviews.value.forEach((review) => {
      const key = `${review.project_key}/${review.repository_slug}/${review.pull_request_id}`
      const rows = grouped.get(key)
      if (rows) {
        rows.push(review)
      } else {
        grouped.set(key, [review])
      }
    })
    return grouped
  }

  /**
   * Whether a pull request still has work outstanding.
   *
   * It is finished only once every reviewer on it has completed; a PR that is
   * still waiting for a reviewer counts as outstanding too, since nothing about
   * it is done.
   */
  const isInFlight = (rows: ReviewV2[]): boolean => {
    const statuses = rows.flatMap((row) =>
      (row.reviewers ?? []).map((assignment) => assignment.assignment_status)
    )
    return !(statuses.length > 0 && statuses.every((status) => status === 'completed'))
  }

  /**
   * Summary statistics, every one of them counted per pull request.
   *
   * Pull request status is not the basis here: reviews are ingested when a PR is
   * opened and nothing updates that status afterwards, so counting "open" rows
   * only ever reproduced the total. Reviewer assignment status does move, so it
   * is what tells work apart from finished work.
   */
  const getSummaryStats = computed(() => {
    const byPullRequest = groupByPullRequest()

    let activePRs = 0
    let assignments = 0
    let scoredPRs = 0

    byPullRequest.forEach((rows) => {
      if (isInFlight(rows)) {
        activePRs++
      }

      // Reviewers are stored per row, so the same reviewer on several files of
      // one PR is still one reviewer on that PR.
      assignments += new Set(
        rows.flatMap((row) => (row.reviewers ?? []).map((assignment) => assignment.reviewer))
      ).size

      if (rows.some((row) => row.has_scores)) {
        scoredPRs++
      }
    })

    const totalPRs = byPullRequest.size

    return {
      totalPRs,
      activePRs,
      avgAssignments: totalPRs > 0 ? Math.round((assignments / totalPRs) * 100) / 100 : 0,
      scoringRate: totalPRs > 0 ? Math.round((scoredPRs / totalPRs) * 10000) / 100 : 0,
    }
  })

  /**
   * Aggregate issue counts by severity over time periods
   */
  const aggregateIssuesBySeverity = (
    period: AnalyticsPeriod,
    windowSize?: number
  ): SeveritySeries[] => {
    // Same window and same keys as the trend chart, so the two line up on the axis.
    const buckets = periodWindow(period, windowSize)
    const grouped: Record<string, Record<IssueSeverity, number>> = {}
    buckets.forEach((key) => {
      grouped[key] = { low: 0, medium: 0, high: 0, critical: 0 }
    })

    let inWindow = 0
    reviews.value.forEach((review) => {
      // Prefer the lightweight pre-extracted severities; fall back to parsing
      // the full ai_suggestions payload when present (legacy data shape).
      const severities: string[] = review.issue_severities && review.issue_severities.length > 0
        ? review.issue_severities
        : (review.ai_suggestions?.issues as Array<{ severity: string }> | undefined)
            ?.map((issue) => issue.severity) || []

      if (severities.length === 0) return

      const bucket = grouped[periodKey(dayjs(review.created_date), period)]
      if (!bucket) return // Older than the window, so it belongs to no point.
      inWindow++

      severities.forEach((severity) => {
        const sev = (severity || '').toLowerCase() as IssueSeverity
        if (bucket[sev] !== undefined) {
          bucket[sev]++
        }
      })
    })

    if (inWindow === 0) return []

    return SEVERITY_ORDER.map((severity) => ({
      name: severity.charAt(0).toUpperCase() + severity.slice(1),
      color: SEVERITY_COLORS[severity],
      data: buckets.map((key) => ({
        date: key,
        value: grouped[key][severity],
      })),
    }))
  }

  /**
   * Load reviews data
   */
  const loadReviews = async (params?: {
    page?: number
    page_size?: number
    project_key?: string
    reviewer?: string
    pull_request_user?: string
    date_from?: string
    date_to?: string
  }) => {
    // This will be called from the component with actual API call
    // The composable focuses on data transformation
  }

  /**
   * Set reviews data
   */
  const setReviews = (data: ReviewV2[]) => {
    reviews.value = data
  }

  /**
   * Clear reviews data
   */
  const clearReviews = () => {
    reviews.value = []
  }

  return {
    reviews,
    aggregateByTimePeriod,
    aggregateByPRUser,
    aggregateByProject,
    aggregateByReviewer,
    aggregateIssuesBySeverity,
    getSummaryStats,
    loadReviews,
    setReviews,
    clearReviews,
  }
}
