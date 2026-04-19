import type { Review } from '@/api/reviews'

/**
 * Generate PR URL for external navigation to Bitbucket/GitHub
 * @param review - Review object containing project and PR information
 * @returns Full PR URL or null if required fields are missing
 */
export function usePrUrl() {
  const getPrUrl = (review: Review): string | null => {
    if (!review.project?.project_url || !review.repository_slug || !review.pull_request_commit_id) {
      return null
    }
    
    // Construct URL: <project_url>/repos/<repository_slug>/commits/<commit_id>
    const baseUrl = review.project.project_url.replace(/\/$/, '') // Remove trailing slash
    return `${baseUrl}/repos/${review.repository_slug}/commits/${review.pull_request_commit_id}`
  }

  return {
    getPrUrl,
  }
}
