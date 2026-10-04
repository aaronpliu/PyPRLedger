import type {
  AppVersionDiffMove,
  AppVersionDiffResponse,
} from '@/api/appVersionDiff'

/**
 * The answers the App Diff endpoint hands the view.
 *
 * One fixture per case the page has to read: an ordinary comparison across two
 * releases, and a third release the dependency source holds no record for.
 */

export const RELEASE_EARLIER = 'v1.1.0'
export const RELEASE_LATER = 'v2.0.0'
export const RELEASE_MISSING = 'v9.9.9'

function unchanged(name: string, version: string): AppVersionDiffMove {
  return {
    name,
    source_version: version,
    target_version: version,
    state: 'unchanged',
    direction: null,
    orderable: true,
  }
}

/** The comparison of the two newest releases: every state, one of them unorderable. */
function compared(): AppVersionDiffResponse {
  const moves: AppVersionDiffMove[] = [
    {
      name: 'packageA',
      source_version: '1.0.0',
      target_version: '1.0.1',
      state: 'changed',
      direction: 'upgrade',
      orderable: true,
    },
    unchanged('packageB', '1.1.0'),
    {
      name: 'packageC',
      source_version: '1.0.0',
      target_version: null,
      state: 'removed',
      direction: null,
      orderable: true,
    },
    {
      name: 'packageD',
      source_version: null,
      target_version: '0.9.0',
      state: 'added',
      direction: null,
      orderable: true,
    },
    {
      name: 'packageE',
      source_version: '2.1.0',
      target_version: '2.0.0',
      state: 'changed',
      direction: 'downgrade',
      orderable: true,
    },
    {
      // a declared range the version reader cannot order: a change with no direction
      name: 'packageF',
      source_version: '1.0.0',
      target_version: '^2.0.0',
      state: 'changed',
      direction: null,
      orderable: false,
    },
  ]

  return {
    project_key: 'CORE',
    repository_slug: 'app',
    app_name: 'mylang',
    git_provider: 'bitbucket_server',
    releases: [
      { ref: RELEASE_EARLIER, released_at: '2026-09-01', has_record: true },
      { ref: RELEASE_LATER, released_at: '2026-10-01', has_record: true },
    ],
    verdict: 'changed',
    summary: {
      unchanged: 1,
      changed: 3,
      upgrade: 1,
      downgrade: 1,
      added: 1,
      removed: 1,
    },
    packages: [
      {
        name: 'packageA',
        versions: ['1.0.0', '1.0.1'],
        moves: [moves[0]],
      },
      { name: 'packageB', versions: ['1.1.0', '1.1.0'], moves: [moves[1]] },
      { name: 'packageC', versions: ['1.0.0', null], moves: [moves[2]] },
      { name: 'packageD', versions: [null, '0.9.0'], moves: [moves[3]] },
      { name: 'packageE', versions: ['2.1.0', '2.0.0'], moves: [moves[4]] },
      { name: 'packageF', versions: ['1.0.0', '^2.0.0'], moves: [moves[5]] },
    ],
    intervals: [
      {
        source_ref: RELEASE_EARLIER,
        target_ref: RELEASE_LATER,
        complete: true,
        summary: {
          unchanged: 1,
          changed: 3,
          upgrade: 1,
          downgrade: 1,
          added: 1,
          removed: 1,
        },
        changes: moves.filter((move) => move.state !== 'unchanged'),
      },
    ],
  }
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
    packages: base.packages.map((pkg) => ({
      ...pkg,
      versions: [...pkg.versions, null],
      moves: [...pkg.moves, null],
    })),
    intervals: [
      ...base.intervals,
      {
        source_ref: RELEASE_LATER,
        target_ref: RELEASE_MISSING,
        complete: false,
        summary: { unchanged: 0, changed: 0, upgrade: 0, downgrade: 0, added: 0, removed: 0 },
        changes: [],
      },
    ],
  }
}

/** The answer for a request: the missing-record case once that release is asked for. */
export function diffOf(payload: { refs: string[] }): AppVersionDiffResponse {
  return payload.refs.includes(RELEASE_MISSING) ? withMissing() : compared()
}
