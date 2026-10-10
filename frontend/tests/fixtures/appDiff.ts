import type {
  AppVersionDiffCode,
  AppVersionDiffCommit,
  AppVersionDiffMove,
  AppVersionDiffPackageComparison,
  AppVersionDiffResponse,
} from '@/api/appVersionDiff'

/**
 * The answers the App Diff endpoint hands the view.
 *
 * One fixture per case the page has to read: an ordinary comparison across two
 * releases, and a third release the dependency source holds no record for.
 */

export const APP_NAME = 'mylang'
export const RELEASE_EARLIER = 'v1.1.0'
export const RELEASE_LATER = 'v2.0.0'
export const RELEASE_MISSING = 'v9.9.9'
export const RELEASE_REBUILT = 'v3.0.0'
export const RELEASE_UNAVAILABLE = 'v4.0.0'
export const RELEASE_DEFERRED = 'v5.0.0'

function commit(id: string, subject: string): AppVersionDiffCommit {
  return {
    id,
    display_id: id.slice(0, 7),
    author_name: 'Tester',
    author_username: 'tester',
    author_email: 'tester@example.com',
    author_timestamp: 1780000000000,
    message: subject,
    url: `https://example.com/commits/${id}`,
  }
}

/** The commits one pair of releases carries. */
function code(added: number, missing = 0) {
  return {
    verdict: 'contained' as const,
    scan_complete: true,
    added_count: added,
    missing_count: missing,
    added_commits: [commit('a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2', 'Add the new module')],
    missing_commits: [],
    truncated: false,
    unavailable: null,
    deferred: false,
  }
}

function unchanged(name: string, version: string): AppVersionDiffMove {
  return {
    name,
    kind: 'dependency',
    source_version: version,
    target_version: version,
    state: 'unchanged',
    direction: null,
    orderable: true,
  }
}

/** The same comparison, with the later version missing something of the earlier one. */
function codeMissing(missing: number): AppVersionDiffCode {
  return { ...code(0, missing), verdict: 'missing' }
}

/** A comparison that could not be run, and why. */
function notCompared(reason: string): AppVersionDiffCode {
  return {
    verdict: 'inconclusive',
    scan_complete: false,
    added_count: 0,
    missing_count: 0,
    added_commits: [],
    missing_commits: [],
    truncated: false,
    unavailable: reason,
    deferred: false,
  }
}

/**
 * A comparison the first response left for the batches that follow.
 *
 * There is a pair of versions and a repository, so this is a comparison waiting
 * its turn - not one that cannot be made, and not one that was made and found
 * empty.
 */
function deferredCode(): AppVersionDiffCode {
  return {
    verdict: 'inconclusive',
    scan_complete: false,
    added_count: 0,
    missing_count: 0,
    added_commits: [],
    missing_commits: [],
    truncated: false,
    unavailable: null,
    deferred: true,
  }
}

/** One moved package, and how its two versions were compared. */
function packageComparison(
  name: string,
  state: 'changed' | 'added' | 'removed',
  versions: [string | null, string | null],
  comparison: AppVersionDiffCode,
  repository: string | null = null,
): AppVersionDiffPackageComparison {
  const [project, slug] = repository ? repository.split('/') : [null, null]
  return {
    name,
    state,
    source_version: versions[0],
    target_version: versions[1],
    project_key: project,
    repository_slug: slug,
    git_provider: repository ? 'bitbucket_server' : null,
    code: comparison,
  }
}

/** The comparison of the two newest releases: every state, one of them unorderable. */
function compared(): AppVersionDiffResponse {
  const moves: AppVersionDiffMove[] = [
    {
      name: 'packageA',
      kind: 'dependency',
      source_version: '1.0.0',
      target_version: '1.0.1',
      state: 'changed',
      direction: 'upgrade',
      orderable: true,
    },
    unchanged('packageB', '1.1.0'),
    {
      name: 'packageC',
      kind: 'dependency',
      source_version: '1.0.0',
      target_version: null,
      state: 'removed',
      direction: null,
      orderable: true,
    },
    {
      name: 'packageD',
      kind: 'dependency',
      source_version: null,
      target_version: '0.9.0',
      state: 'added',
      direction: null,
      orderable: true,
    },
    {
      name: 'packageE',
      kind: 'dependency',
      source_version: '2.1.0',
      target_version: '2.0.0',
      state: 'changed',
      direction: 'downgrade',
      orderable: true,
    },
    {
      // a declared range the version reader cannot order: a change with no direction
      name: 'packageF',
      kind: 'dependency',
      source_version: '1.0.0',
      target_version: '^2.0.0',
      state: 'changed',
      direction: null,
      orderable: false,
    },
  ]

  // the application's own version is a row like the others, and it moved too
  const appMove: AppVersionDiffMove = {
    name: APP_NAME,
    kind: 'application',
    source_version: '1.0.0_10000',
    target_version: '1.1.0_10000',
    state: 'changed',
    direction: 'upgrade',
    orderable: true,
  }
  const summary = {
    unchanged: 1,
    changed: 4,
    upgrade: 2,
    downgrade: 1,
    added: 1,
    removed: 1,
  }

  return {
    project_key: 'CORE',
    repository_slug: 'app',
    app_name: APP_NAME,
    git_provider: 'bitbucket_server',
    releases: [
      { ref: RELEASE_EARLIER, released_at: '2026-09-01', has_record: true },
      { ref: RELEASE_LATER, released_at: '2026-10-01', has_record: true },
    ],
    verdict: 'changed',
    summary,
    rows: [
      {
        kind: 'application',
        name: APP_NAME,
        versions: ['1.0.0_10000', '1.1.0_10000'],
        moves: [appMove],
      },
      { kind: 'dependency', name: 'packageA', versions: ['1.0.0', '1.0.1'], moves: [moves[0]] },
      { kind: 'dependency', name: 'packageB', versions: ['1.1.0', '1.1.0'], moves: [moves[1]] },
      { kind: 'dependency', name: 'packageC', versions: ['1.0.0', null], moves: [moves[2]] },
      { kind: 'dependency', name: 'packageD', versions: [null, '0.9.0'], moves: [moves[3]] },
      { kind: 'dependency', name: 'packageE', versions: ['2.1.0', '2.0.0'], moves: [moves[4]] },
      { kind: 'dependency', name: 'packageF', versions: ['1.0.0', '^2.0.0'], moves: [moves[5]] },
    ],
    intervals: [
      {
        source_ref: RELEASE_EARLIER,
        target_ref: RELEASE_LATER,
        complete: true,
        summary,
        dependencies_moved: true,
        changes: [appMove, ...moves.filter((move) => move.state !== 'unchanged')],
        code: code(5),
        packages: [
          // compared in its own repository, at its two versions used as the refs
          packageComparison('packageA', 'changed', ['1.0.0', '1.0.1'], code(4), 'CORE/pkg-a'),
          // the later version does not hold everything of the earlier one
          packageComparison('packageF', 'changed', ['1.0.0', '^2.0.0'], codeMissing(1), 'CORE/pkg-f'),
          // a package no repository is registered as: reported, not dropped
          packageComparison(
            'packageE',
            'changed',
            ['2.1.0', '2.0.0'],
            notCompared("no repository is registered as 'packageE'"),
          ),
          // one version only, so there is no pair of refs to compare
          packageComparison(
            'packageC',
            'removed',
            ['1.0.0', null],
            notCompared('only one version is recorded, so there is no pair to compare'),
            'CORE/pkg-c',
          ),
        ],
      },
    ],
    // nothing was left for later: this page has nothing more to read
    auto_compare_remaining: 90,
  }
}

/**
 * A pair that moved more packages than one response reads.
 *
 * The first response carries one package's comparison and leaves two for the
 * batches that follow, with an allowance of one - so a page reading on its own
 * reaches the end of what it may read and has to say so.
 */
function deferred(): AppVersionDiffResponse {
  const base = compared()

  return {
    ...base,
    releases: [
      { ref: RELEASE_EARLIER, released_at: '2026-09-01', has_record: true },
      { ref: RELEASE_DEFERRED, released_at: '2026-10-01', has_record: true },
    ],
    // one comparison may still be read without being asked for
    auto_compare_remaining: 1,
    intervals: [
      {
        ...base.intervals[0],
        target_ref: RELEASE_DEFERRED,
        packages: [
          packageComparison('packageA', 'changed', ['1.0.0', '1.0.1'], code(4), 'CORE/pkg-a'),
          // these two moved and have a repository, so they are comparisons waiting
          // their turn - each carrying where it lives, which is what lets the page
          // ask for it on its own
          packageComparison(
            'packageE',
            'changed',
            ['2.1.0', '2.0.0'],
            deferredCode(),
            'CORE/pkg-e',
          ),
          packageComparison(
            'packageF',
            'changed',
            ['1.0.0', '^2.0.0'],
            deferredCode(),
            'CORE/pkg-f',
          ),
        ],
      },
    ],
  }
}

/** The answer the batch endpoint gives for the packages a page asked about. */
export function packageAnswers(
  packages: { name: string; source_version: string; target_version: string }[],
): AppVersionDiffPackageComparison[] {
  return packages.map((item) =>
    packageComparison(
      item.name,
      'changed',
      [item.source_version, item.target_version],
      code(2),
      `CORE/${item.name.toLowerCase()}`,
    ),
  )
}

/** The same comparison with a third release the source holds no record for. */
function withMissing(): AppVersionDiffResponse {
  const base = compared()

  return {
    ...base,
    releases: [
      ...base.releases,
      { ref: RELEASE_MISSING, released_at: null, has_record: false },
    ],
    verdict: 'incomplete',
    rows: base.rows.map((row) => ({
      ...row,
      versions: [...row.versions, null],
      moves: [...row.moves, null],
    })),
    intervals: [
      ...base.intervals,
      {
        source_ref: RELEASE_LATER,
        target_ref: RELEASE_MISSING,
        complete: false,
        summary: { unchanged: 0, changed: 0, upgrade: 0, downgrade: 0, added: 0, removed: 0 },
        dependencies_moved: false,
        changes: [],
        packages: [],
        // a pair that could not be compared has no code axis, which is not the
        // same as a pair with no commits
        code: null,
      },
    ],
  }
}

/**
 * A release rebuilt under the same versions: no dependency moved, and the
 * commits did. This is the case the code axis exists for.
 */
function rebuilt(): AppVersionDiffResponse {
  const base = compared()

  return {
    ...base,
    releases: [
      { ref: RELEASE_EARLIER, released_at: '2026-09-01', has_record: true },
      { ref: RELEASE_REBUILT, released_at: '2026-10-01', has_record: true },
    ],
    verdict: 'identical',
    // the application's own version stays put as well: nothing but the commits moved
    rows: base.rows.map((row) => ({
      ...row,
      versions: [row.versions[0], row.versions[0]],
      moves: [unchanged(row.name, row.versions[0] as string)],
    })),
    intervals: [
      {
        source_ref: RELEASE_EARLIER,
        target_ref: RELEASE_REBUILT,
        complete: true,
        summary: { unchanged: 7, changed: 0, upgrade: 0, downgrade: 0, added: 0, removed: 0 },
        dependencies_moved: false,
        changes: [],
        packages: [],
        code: code(3),
      },
    ],
  }
}

/**
 * A pair whose commits could not be read: the reason is carried, which is the
 * only reading that is not a lie about there being no commits.
 */
function unreadable(): AppVersionDiffResponse {
  const base = compared()

  return {
    ...base,
    releases: [
      { ref: RELEASE_EARLIER, released_at: '2026-09-01', has_record: true },
      { ref: RELEASE_UNAVAILABLE, released_at: '2026-10-01', has_record: true },
    ],
    intervals: [
      {
        ...base.intervals[0],
        target_ref: RELEASE_UNAVAILABLE,
        code: {
          verdict: 'inconclusive',
          scan_complete: false,
          added_count: 0,
          missing_count: 0,
          added_commits: [],
          missing_commits: [],
          truncated: false,
          unavailable: 'provider unreachable',
          deferred: false,
        },
      },
    ],
  }
}

/** The answer for a request: which case depends on the releases that were asked for. */
export function diffOf(payload: { refs: string[] }): AppVersionDiffResponse {
  if (payload.refs.includes(RELEASE_MISSING)) return withMissing()
  if (payload.refs.includes(RELEASE_REBUILT)) return rebuilt()
  if (payload.refs.includes(RELEASE_UNAVAILABLE)) return unreadable()
  if (payload.refs.includes(RELEASE_DEFERRED)) return deferred()
  return compared()
}
