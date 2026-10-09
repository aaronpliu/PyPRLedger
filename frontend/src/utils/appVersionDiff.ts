import type {
  AppVersionDiffCode,
  AppVersionDiffCommit,
  AppVersionDiffInterval,
  AppVersionDiffMove,
  AppVersionDiffResponse,
} from '@/api/appVersionDiff'

/**
 * What a cell is: the version this release pinned, and how it moved into it.
 *
 * ``move`` is ``undefined`` on the first column (there is no boundary before it),
 * ``null`` where the boundary touches a release with no record - which is
 * unknown rather than unchanged - and the move itself everywhere else.
 */
export interface AppDiffCell {
  ref: string
  version: string | null
  hasRecord: boolean
  move: AppVersionDiffMove | null | undefined
}

export interface AppDiffRow {
  /** `application` for the application's own version, `dependency` for a package. */
  kind: 'application' | 'dependency'
  name: string
  cells: AppDiffCell[]
}

/** How a cell's move reads. `unknown` and `none` are deliberately different. */
export type MoveTone =
  | 'none'
  | 'unknown'
  | 'upgrade'
  | 'downgrade'
  | 'changed'
  | 'added'
  | 'removed'

/** The states an interval summary reports, in the order they are shown. */
export const SUMMARY_ORDER = ['changed', 'added', 'removed'] as const

/**
 * The rows the table draws, in the order the server returned them - the
 * application's own version first: cells follow the release columns, and each
 * cell carries the move into it.
 */
export function buildRows(response: AppVersionDiffResponse): AppDiffRow[] {
  return response.rows.map((row) => ({
    kind: row.kind,
    name: row.name,
    cells: response.releases.map((release, index) => ({
      ref: release.ref,
      version: row.versions[index] ?? null,
      hasRecord: release.has_record,
      move: index === 0 ? undefined : (row.moves[index - 1] ?? null),
    })),
  }))
}

/**
 * How a move should read.
 *
 * A change with no direction stays `changed`: it must never be dressed up as an
 * upgrade, which is exactly what a tone of `upgrade` would say.
 */
export function moveTone(move: AppVersionDiffMove | null | undefined): MoveTone {
  if (move === undefined) return 'none'
  if (move === null) return 'unknown'
  if (move.state === 'unchanged') return 'none'
  if (move.state === 'added') return 'added'
  if (move.state === 'removed') return 'removed'
  if (move.direction === 'upgrade') return 'upgrade'
  if (move.direction === 'downgrade') return 'downgrade'
  return 'changed'
}

/** Whether a move is a risk worth calling out: a downgrade, and nothing else. */
export function isRisk(move: AppVersionDiffMove | null | undefined): boolean {
  return moveTone(move) === 'downgrade'
}

/** Whether a move should be marked at all. */
export function isMarked(move: AppVersionDiffMove | null | undefined): boolean {
  return moveTone(move) !== 'none'
}

/** The counts worth showing for one interval, in the order they are shown. */
export function summaryEntries(
  summary: Record<string, number> | undefined,
): { state: string; count: number }[] {
  return SUMMARY_ORDER.filter((state) => (summary?.[state] ?? 0) > 0).map((state) => ({
    state,
    count: summary![state],
  }))
}

/** The downgrades in a summary, which are reported as a risk rather than a count. */
export function downgradeCount(summary: Record<string, number> | undefined): number {
  return summary?.downgrade ?? 0
}

/** The i18n key for a move's tone. */
export function moveLabelKey(tone: MoveTone): string {
  return `appDiff.move_${tone}`
}

const MOVE_SYMBOLS: Record<MoveTone, string> = {
  none: '·',
  unknown: '?',
  upgrade: '↑',
  downgrade: '↓',
  changed: '•',
  added: '+',
  removed: '−',
}

/** The glyph a marked move is drawn with. */
export function moveSymbol(tone: MoveTone): string {
  return MOVE_SYMBOLS[tone]
}

/**
 * What a move is about, as it is read: the version it was, and the one it became.
 *
 * A side the move does not have is drawn as a dash rather than left blank, so an
 * added or removed package reads as a change of state and not as a missing value.
 */
export function moveVersions(move: AppVersionDiffMove): string {
  return `${move.source_version ?? '—'} → ${move.target_version ?? '—'}`
}

/** How a pair's code axis reads. `unavailable` and `none` are deliberately different. */
export type CodeTone = 'unavailable' | 'none' | 'commits'

export function codeTone(code: AppVersionDiffCode | null | undefined): CodeTone {
  if (!code || code.unavailable) return 'unavailable'
  return commitTotal(code) > 0 ? 'commits' : 'none'
}

/** How many commits a pair reports, in both directions. Zero when it could not be read. */
export function commitTotal(code: AppVersionDiffCode | null | undefined): number {
  if (!code || code.unavailable) return 0
  return code.added_count + code.missing_count
}

/**
 * Whether a pair's dependencies did not move while its commits did.
 *
 * The case the code axis exists for: a tag was moved to a new commit and what it
 * pins stayed identical, so the dependency axis alone would report that nothing
 * happened about a release that shipped different code.
 *
 * The reading comes from `dependencies_moved` rather than the pair's summary,
 * because the summary also counts the application's own version - which can move
 * on its own without a single dependency moving.
 */
export function rebuiltWithUnchangedDependencies(
  interval: AppVersionDiffInterval,
  code: AppVersionDiffCode | null | undefined,
): boolean {
  if (!code || code.unavailable) return false
  return !interval.dependencies_moved && commitTotal(code) > 0
}

/** A commit's short form, and the first line of what it says. */
export function shortCommitId(commit: AppVersionDiffCommit): string {
  return commit.display_id || commit.id.slice(0, 7)
}

export function commitSubject(commit: AppVersionDiffCommit): string {
  return (commit.message ?? '').split('\n')[0]
}
