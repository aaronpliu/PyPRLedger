import request from '@/utils/request'

export interface AppVersionDiffRequest {
  project_key: string
  repository_slug: string
  git_provider?: string | null
  /** Bitbucket Cloud only: workspace holding the repository (falls back to project_key). */
  workspace_slug?: string | null
  /** The releases to compare. Two or more; the order supplied is ignored. */
  refs: string[]
  /** Bypass the cache and read every release from the dependency source again. */
  refresh?: boolean
  /** Read the commits between every pair as well. Defaults to true. */
  include_code?: boolean
}

/** One selected release, placed on the timeline by the server. */
export interface AppVersionDiffRelease {
  ref: string
  /** The release datetime, when one could be established. */
  released_at: string | null
  /** Whether the dependency source holds a record for this release. */
  has_record: boolean
}

/** What one package did between two adjacent releases. */
export interface AppVersionDiffMove {
  name: string
  source_version: string | null
  target_version: string | null
  state: 'unchanged' | 'changed' | 'added' | 'removed'
  /** `upgrade` / `downgrade`, or null when the move is not a change or cannot be ordered. */
  direction: 'upgrade' | 'downgrade' | null
  orderable: boolean
}

/** One row of the matrix: a package across every selected release. */
export interface AppVersionDiffPackage {
  name: string
  /** One entry per release, in the order they are presented; null where not declared. */
  versions: (string | null)[]
  /** One entry per boundary; null where the boundary touches a release with no record. */
  moves: (AppVersionDiffMove | null)[]
}

/** One commit of a pair's delta, as the repository comparison reports it. */
export interface AppVersionDiffCommit {
  id: string
  display_id: string | null
  author_name: string | null
  author_username: string | null
  author_email: string | null
  author_timestamp: number | null
  message: string | null
  url: string | null
}

/**
 * The commits between two adjacent releases.
 *
 * `unavailable` carries the reason they could not be read - which is not the
 * same as a pair with no commits, and must never be shown as one.
 */
export interface AppVersionDiffCode {
  verdict: 'contained' | 'missing' | 'inconclusive'
  scan_complete: boolean
  added_count: number
  missing_count: number
  added_commits: AppVersionDiffCommit[]
  missing_commits: AppVersionDiffCommit[]
  truncated: boolean
  unavailable: string | null
}

/** One adjacent pair of releases, compared. */
export interface AppVersionDiffInterval {
  source_ref: string
  target_ref: string
  /** False when a release of the pair has no record: the pair is unknown, not unchanged. */
  complete: boolean
  summary: Record<string, number>
  changes: AppVersionDiffMove[]
  /** Null when the pair is incomplete or the request did not ask for the code axis. */
  code: AppVersionDiffCode | null
}

export interface AppVersionDiffResponse {
  project_key: string
  repository_slug: string
  app_name: string
  git_provider: string
  releases: AppVersionDiffRelease[]
  verdict: 'identical' | 'changed' | 'incomplete'
  summary: Record<string, number>
  packages: AppVersionDiffPackage[]
  intervals: AppVersionDiffInterval[]
}

export const appVersionDiffApi = {
  /**
   * Compare two or more releases of one application. The repository is resolved to
   * an application through the project registry and every release is read from the
   * dependency source, so this is the same reading the dependency graph page does,
   * applied to several releases at once.
   */
  compare(payload: AppVersionDiffRequest): Promise<AppVersionDiffResponse> {
    return request.post('/release/apps/diff', payload)
  },
}
