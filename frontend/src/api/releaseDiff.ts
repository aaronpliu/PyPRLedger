import request from '@/utils/request'

export interface CommitInfo {
  id: string
  display_id?: string | null
  author_name?: string | null
  author_email?: string | null
  author_timestamp?: number | null
  message?: string | null
  url?: string | null
}

export interface ReleaseRefsRequest {
  project_key: string
  repository_slug: string
  git_provider?: string | null
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
  old_release_ref: string
  new_release_ref: string
  old_release_base_ref?: string | null
  new_release_base_ref?: string | null
  include_commits?: boolean
  max_commits?: number
}

export interface ReleaseCompareResponse {
  project_key: string
  repository_slug: string
  git_provider: string
  old_release_ref: string
  new_release_ref: string
  old_release_base_ref?: string | null
  new_release_base_ref?: string | null
  old_commits_included: boolean
  status: 'included' | 'missing_commits' | 'identical'
  summary: {
    old_commit_count?: number
    new_commit_count?: number
    missing_count?: number
    added_count?: number
    common_count?: number
  }
  missing_commits: CommitInfo[]
  added_commits: CommitInfo[]
  old_release_commits: CommitInfo[]
  new_release_commits: CommitInfo[]
  truncated: boolean
}

export interface ReleaseCommitCheckRequest {
  project_key: string
  repository_slug: string
  git_provider?: string | null
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

  /** Compare two releases and report whether the old release is contained in the new one. */
  compare(payload: ReleaseCompareRequest): Promise<ReleaseCompareResponse> {
    return request.post('/release/diff/compare', payload)
  },

  /** Check whether the given commits belong to the target release. */
  check(payload: ReleaseCommitCheckRequest): Promise<ReleaseCommitCheckResponse> {
    return request.post('/release/diff/check', payload)
  },
}
