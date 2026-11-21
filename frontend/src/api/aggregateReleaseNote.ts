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
  /** Run the one optional AI pass over the application's own scope */
  summarize?: boolean
  /** Language the rendered bodies are written in (en / zh-CN / zh-TW) */
  language?: string
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
  /**
   * The package's rendered release note body (categorized sections, ticket
   * links, authors), set for compared entries
   */
  body?: string | null
}

export interface AggregateReleaseNoteSummary {
  packages_changed: number
  packages_compared: number
  packages_skipped: number
  packages_failed: number
  unchanged_packages: number
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
  /**
   * Where the package relationship came from: `database` when the dependency
   * database held a record for both refs of the span, `none` when the
   * application is monolithic - no packages, none guessed
   */
  dependency_source: 'database' | 'none'
  /** The application's own half of the note */
  application: ReleaseCompareResponse
  /** The application's rendered release note body (categorized sections, ticket links, authors) */
  application_body?: string | null
  /** `llm` when the optional AI pass answered, `deterministic` when it ran and degraded */
  summary_source?: 'llm' | 'deterministic' | null
  /** Why there is no AI summary, when the pass was asked for and could not be made */
  summary_notice?: string | null
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

  /**
   * What the dependency database says the span carries - versions only, no
   * comparisons: the declared pins of each ref and one entry per package the
   * span moved. Cheap enough to preview while the release is being typed.
   */
  plan(payload: AggregateReleaseNoteRequest): Promise<AggregateNotePlanResponse> {
    return request.post('/release/aggregate-note/plan', payload)
  },
}

/** One package the span moved, as the dependency database places it. */
export interface AggregateNotePlanEntry {
  name: string
  change: 'upgraded' | 'added' | 'removed'
  from_version: string
  to_version: string
  /** Whether the application declares the package */
  pinned: boolean
  /** Why the package will not get a commit comparison, when it will not */
  reason?: string | null
}

/** The dependency versions a span carries, before any note is built. */
export interface AggregateNotePlanResponse {
  app_name: string
  source_ref: string
  target_ref: string
  /** 'database' when both refs have records, 'none' when the application is monolithic */
  dependency_source: 'database' | 'none'
  /** What the application's source version declares: '{package: version}' */
  source_pins: Record<string, string>
  /** What the application's target version declares: '{package: version}' */
  target_pins: Record<string, string>
  packages: AggregateNotePlanEntry[]
  unchanged_packages: string[]
}
