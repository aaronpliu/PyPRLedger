import { computed, ref } from 'vue'
import dayjs from 'dayjs'
import weekOfYear from 'dayjs/plugin/weekOfYear'
import type { ReviewV2 } from '@/api/taskAssignment'

// Enable weekOfYear plugin for weekly aggregation
dayjs.extend(weekOfYear)

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

export interface ScoringStats {
  totalAssigned: number
  totalCompleted: number
  completionRate: number
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
    period: 'daily' | 'weekly' | 'monthly'
  ): TimePeriodData[] => {
    const grouped: Record<string, TimePeriodData> = {}

    reviews.value.forEach((review) => {
      const date = dayjs(review.created_date)
      let key: string

      switch (period) {
        case 'daily':
          key = date.format('YYYY-MM-DD')
          break
        case 'weekly':
          key = `${date.year()}-W${date.week()}`
          break
        case 'monthly':
          key = date.format('YYYY-MM')
          break
        default:
          key = date.format('YYYY-MM-DD')
      }

      if (!grouped[key]) {
        grouped[key] = {
          date: key,
          count: 0,
          assigned: 0,
          completed: 0,
        }
      }

      grouped[key].count++
      
      // Count assignments
      review.reviewers?.forEach((assignment) => {
        grouped[key].assigned!++
        if (assignment.assignment_status === 'completed') {
          grouped[key].completed!++
        }
      })
    })

    // Sort by date and convert to array
    return Object.values(grouped).sort((a, b) => a.date.localeCompare(b.date))
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
   * Calculate overall scoring statistics
   */
  const calculateScoringStats = (): ScoringStats => {
    let totalAssigned = 0
    let totalCompleted = 0

    reviews.value.forEach((review) => {
      review.reviewers?.forEach((assignment) => {
        totalAssigned++
        if (assignment.assignment_status === 'completed') {
          totalCompleted++
        }
      })
    })

    const completionRate = totalAssigned > 0 
      ? (totalCompleted / totalAssigned) * 100 
      : 0

    return {
      totalAssigned,
      totalCompleted,
      completionRate: Math.round(completionRate * 100) / 100,
    }
  }

  /**
   * Get summary statistics
   */
  const getSummaryStats = computed(() => {
    const totalReviews = reviews.value.length
    const activeReviews = reviews.value.filter(
      (r) => r.pull_request_status === 'open'
    ).length
    
    const scoringStats = calculateScoringStats()
    
    // Calculate average assignments per review
    const totalAssignments = reviews.value.reduce(
      (sum, r) => sum + (r.reviewers?.length || 0),
      0
    )
    const avgAssignments = totalReviews > 0 
      ? Math.round((totalAssignments / totalReviews) * 100) / 100 
      : 0

    return {
      totalReviews,
      activeReviews,
      avgAssignments,
      scoringRate: scoringStats.completionRate,
    }
  })

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
    calculateScoringStats,
    getSummaryStats,
    loadReviews,
    setReviews,
    clearReviews,
  }
}
