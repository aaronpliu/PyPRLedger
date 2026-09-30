import request from '@/utils/request'

export interface CommitInfo {
  id: string
  display_id?: string | null
  author_name?: string | null
  /** Provider login / account slug of the author (when the provider reports one) */
  author_username?: string | null
  /** Web URL of the author profile */
  author_url?: string | null
  author_email?: string | null
  author_timestamp?: number | null
  message?: string | null
  url?: string | null
}

export interface ReleaseRefsRequest {
  project_key: string
  repository_slug: string
  git_provider?: string | null
  /** Bitbucket Cloud only: workspace holding the repository (falls back to project_key). */
  workspace_slug?: string | null
  /** Bypass the backend cache - used by the Refresh action to pick up new tags. */
  refresh?: boolean
  limit?: number
}

export interface ReleaseRefsResponse {
  project_key: string
  repository_slug: string
  git_provider: string
  tags: string[]
  branches: string[]
}

export interface ReleaseCompareRequest {
  project_key: string
  repository_slug: string
  git_provider?: string | null
  /** Bitbucket Cloud only: workspace holding the repository (falls back to project_key). */
  workspace_slug?: string | null
  /** Bypass the backend cache; used by the Refresh action. */
  refresh?: boolean
  /** Release whose commits must be contained in the target */
  source_ref: string
  /** Release that should contain them and whose additions are reported */
  target_ref: string
  /**
   * Optional baseline narrowing **both** directions: difference commits that already
   * existed at it are ignored (the work a line did since the fork point). It belongs
   * to this comparison alone, since a repository holds several release lines.
   */
  baseline_ref?: string | null
  /** Difference commits enumerated per direction before the verdict turns inconclusive */
  scan_limit?: number
  /** Maximum number of difference commits returned with details per direction */
  render_limit?: number
  include_commits?: boolean
}

/** Verdict of a containment check. `inconclusive` is never a pass. */
export type ReleaseVerdict = 'contained' | 'missing' | 'inconclusive'

export interface ReleaseCompareResponse {
  project_key: string
  repository_slug: string
  git_provider: string
  source_ref: string
  target_ref: string
  /** Effective baseline both directions were narrowed against */
  baseline_ref?: string | null
  narrowed: boolean
  /**
   * Containment verdict, derived from the provider difference alone: rendered (and
   * capped) commit lists can never turn it into a pass.
   */
  verdict: ReleaseVerdict
  /** True when the whole missing direction was enumerated (false ⇒ inconclusive) */
  scan_complete: boolean
  scan_limit: number
  /** Difference commits (both directions) ignored because they existed at the baseline */
  filtered_by_baseline_count: number
  missing_count: number
  missing_commits: CommitInfo[]
  added_count: number
  added_commits: CommitInfo[]
  /** True when the whole added direction was enumerated */
  added_complete: boolean
  /** True when more difference commits exist than the rendered lists carry */
  rendered_truncated: boolean
}

export interface ReleaseCommitCheckRequest {
  project_key: string
  repository_slug: string
  git_provider?: string | null
  /** Bitbucket Cloud only: workspace holding the repository (falls back to project_key). */
  workspace_slug?: string | null
  target_release_ref: string
  target_release_base_ref?: string | null
  commits: string[]
  max_commits?: number
}

export interface CommitCheckResult {
  commit: string
  included: boolean
  matched_id?: string | null
  commit_info?: CommitInfo | null
  reason?: string
}

export interface ReleaseCommitCheckResponse {
  project_key: string
  repository_slug: string
  git_provider: string
  target_release_ref: string
  target_release_base_ref?: string | null
  all_included: boolean
  summary: {
    requested?: number
    included_count?: number
    missing_count?: number
    release_commit_count?: number
  }
  results: CommitCheckResult[]
  truncated: boolean
}

export const releaseDiffApi = {
  /** List tags / branches of a repository - used as ref suggestions (any ref stays typeable). */
  listRefs(payload: ReleaseRefsRequest): Promise<ReleaseRefsResponse> {
    return request.post('/release/diff/refs', payload)
  },

  /**
   * The single comparison: is everything from the source release contained in the
   * target release (the verdict), and what does the target add on top of it?
   */
  compare(payload: ReleaseCompareRequest): Promise<ReleaseCompareResponse> {
    return request.post('/release/diff/compare', payload)
  },

  /** Check whether the given commits belong to the target release. */
  check(payload: ReleaseCommitCheckRequest): Promise<ReleaseCommitCheckResponse> {
    return request.post('/release/diff/check', payload)
  },

}
