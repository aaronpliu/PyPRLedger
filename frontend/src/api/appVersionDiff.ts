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
  /**
   * What the name is: the application's own version, or one of the packages it
   * declares. A comparison reports both, and a reader has to tell them apart.
   */
  kind: 'application' | 'dependency'
  source_version: string | null
  target_version: string | null
  state: 'unchanged' | 'changed' | 'added' | 'removed'
  /** `upgrade` / `downgrade`, or null when the move is not a change or cannot be ordered. */
  direction: 'upgrade' | 'downgrade' | null
  orderable: boolean
}

/**
 * One row of the matrix: an entry across every selected release.
 *
 * The first row is the application itself - its own version is one of the things
 * a release comparison is about - and the rest are the dependencies it declares.
 */
export interface AppVersionDiffRow {
  kind: 'application' | 'dependency'
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
  /**
   * Whether this comparison was left for later rather than found impossible: the
   * two versions and the repository are known, but the pair moved more packages
   * than one response reads. The page asks for these in batches; until then there
   * is no verdict, which is not the same as an inconclusive one.
   */
  deferred: boolean
}

/**
 * One dependency's own comparison between the two releases of a pair.
 *
 * Which repository a package lives in is not in the dependency record, so it is
 * resolved through the project registry by the name the record uses; a package
 * that resolves to no repository, to several, or whose versions cannot be compared
 * says so in `code.unavailable` rather than being left out.
 */
export interface AppVersionDiffPackageComparison {
  name: string
  /** The move this package made: `changed` has two versions, `added`/`removed` one. */
  state: 'changed' | 'added' | 'removed'
  source_version: string | null
  target_version: string | null
  project_key: string | null
  repository_slug: string | null
  git_provider: string | null
  code: AppVersionDiffCode
}

/** One adjacent pair of releases, compared. */
export interface AppVersionDiffInterval {
  source_ref: string
  target_ref: string
  /** False when a release of the pair has no record: the pair is unknown, not unchanged. */
  complete: boolean
  /** Counts over every row, the application's own included. */
  summary: Record<string, number>
  /**
   * Whether any dependency row moved. Decided over the dependency rows alone, so
   * the application moving its own version does not turn it true.
   */
  dependencies_moved: boolean
  changes: AppVersionDiffMove[]
  /**
   * Every dependency that moved in this pair, with the commits between the two
   * versions it moved between. The application's own version is not among them -
   * it is the pair's code axis, read above.
   */
  packages: AppVersionDiffPackageComparison[]
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
  /** The matrix: the application's own version first, then its direct dependencies. */
  rows: AppVersionDiffRow[]
  intervals: AppVersionDiffInterval[]
  /**
   * How many more dependency comparisons this page may run on its own. The page
   * asks for its deferred packages in batches until this runs out, then leaves what
   * is left for the reader to ask for.
   */
  auto_compare_remaining: number
}

/** One package of a pair to compare, as the page read it off the matrix. */
export interface AppVersionDiffPackageRequest {
  name: string
  source_version: string
  target_version: string
}

/** A pair of releases, and the packages of it to compare now. */
export interface AppVersionDiffPackagesRequest {
  project_key: string
  repository_slug: string
  git_provider?: string | null
  workspace_slug?: string | null
  refresh?: boolean
  source_ref: string
  target_ref: string
  /** A few at a time: the server refuses more than a batch. */
  packages: AppVersionDiffPackageRequest[]
}

/** The packages of one pair that were asked for, compared. */
export interface AppVersionDiffPackagesResponse {
  project_key: string
  repository_slug: string
  source_ref: string
  target_ref: string
  /** One entry per package asked for, in the shape the first response uses. */
  packages: AppVersionDiffPackageComparison[]
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

  /**
   * Compare the packages a pair of releases moved, in batches. The comparison
   * reports the packages past its own first-read ceiling as deferred; this is how
   * they are read, so a release that moved dozens of packages is drawn from the
   * first few and filled in as the rest arrive.
   */
  comparePackages(
    payload: AppVersionDiffPackagesRequest,
  ): Promise<AppVersionDiffPackagesResponse> {
    return request.post('/release/apps/diff/packages', payload)
  },
}
