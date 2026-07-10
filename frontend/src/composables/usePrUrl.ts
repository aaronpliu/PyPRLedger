import type { Review } from '@/api/reviews'
import type { ReviewV2 } from '@/api/taskAssignment'

// Union type for all review types that have project information
type ReviewWithProject = Review | ReviewV2

/**
 * Generate PR URL for external navigation to Bitbucket/GitHub
 * @param review - Review object containing project and PR information
 * @returns Full PR URL or null if required fields are missing
 */
export function usePrUrl() {
  const getPrUrl = (review: ReviewWithProject): string | null => {
    if (!review.project?.project_url || !review.repository_slug || !review.pull_request_id) {
      return null
    }

    const baseUrl = review.project.project_url.replace(/\/$/, '') // Remove trailing slash
    const gitProvider = review.project.git_provider

    if (gitProvider === 'github_enterprise') {
      // GitHub Enterprise: <project_url>/<repo>/pull/<id>
      return `${baseUrl}/${review.repository_slug}/pull/${review.pull_request_id}`
    }

    // Bitbucket Server (default): <project_url>/repos/<slug>/pull-requests/<id>/diff
    return `${baseUrl}/repos/${review.repository_slug}/pull-requests/${review.pull_request_id}/diff`
  }

  return {
    getPrUrl,
  }
}