import request from '@/utils/request'
import type { ReleaseCompareResponse } from '@/api/releaseDiff'

export interface AggregateReleaseNoteRequest {
  project_key: string
  repository_slug: string
  git_provider?: string | null
  /** Bitbucket Cloud only: workspace holding the repository (falls back to project_key). */
  workspace_slug?: string | null
  /** Resolved from the project registry when left out. */
  app_name?: string | null
  /** The version the release starts from */
  source_ref: string
  /** The version being released */
  target_ref: string
  /** Render the commit lists; the verdicts stand either way */
  include_commits?: boolean
  /** Bypass the caches of the graph and the per-package comparisons */
  refresh?: boolean
}

export interface AggregatePackageRepository {
  project_key: string
  repository_slug: string
  git_provider?: string | null
}

/** Why a package carries no comparison: `compared` | `skipped` | `failed`. */
export type AggregatePackageStatus = 'compared' | 'skipped' | 'failed'

/** How the release span moved the package: `upgraded` | `added` | `removed`. */
export type AggregatePackageChange = 'upgraded' | 'added' | 'removed'

export interface AggregatePackageEntry {
  name: string
  change: AggregatePackageChange
  /** Empty when the package was added in this span */
  from_version: string
  /** Empty when the package was removed in this span */
  to_version: string
  status: AggregatePackageStatus
  /** Why there is no comparison, when status is skipped or failed */
  reason?: string | null
  /** Where the commits are read from, when the registry settles the name */
  repository?: AggregatePackageRepository | null
  comparison?: ReleaseCompareResponse | null
}

export interface AggregateReleaseNoteSummary {
  packages_changed: number
  packages_compared: number
  packages_skipped: number
  packages_failed: number
  app_commits: number
  package_commits: number
}

export interface AggregateReleaseNoteResponse {
  app_name: string
  project_key: string
  repository_slug: string
  git_provider: string | null
  source_ref: string
  target_ref: string
  /** The application's own half of the note */
  application: ReleaseCompareResponse
  packages: AggregatePackageEntry[]
  /** `name@version` of every package both versions hold unchanged */
  unchanged_packages: string[]
  summary: AggregateReleaseNoteSummary
}

export const aggregateReleaseNoteApi = {
  /**
   * The combined release note for one application version span: the app's own
   * commits, plus every pinned package the span moved, compared between its
   * two versions. Packages that cannot be compared come back with the reason,
   * never silently missing.
   */
  build(payload: AggregateReleaseNoteRequest): Promise<AggregateReleaseNoteResponse> {
    return request.post('/release/aggregate-note/build', payload)
  },
}
