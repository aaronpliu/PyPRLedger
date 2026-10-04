import { describe, expect, it } from 'vitest'
import {
  buildRows,
  codeTone,
  commitSubject,
  commitTotal,
  defaultSelection,
  downgradeCount,
  isMarked,
  isRisk,
  moveLabelKey,
  moveSymbol,
  moveTone,
  rebuiltWithUnchangedDependencies,
  shortCommitId,
  summaryEntries,
} from '@/utils/appVersionDiff'
import type { AppVersionDiffMove } from '@/api/appVersionDiff'
import { APP_NAME, diffOf } from '../fixtures/appDiff'

const TWO = ['v1.1.0', 'v2.0.0']
const THREE = ['v1.1.0', 'v2.0.0', 'v9.9.9']
const REBUILT = ['v1.1.0', 'v3.0.0']

/** The code axis of the ordinary comparison. */
function codeOf(refs: string[] = TWO) {
  return diffOf({ refs }).intervals[0].code
}

function move(overrides: Partial<AppVersionDiffMove> = {}): AppVersionDiffMove {
  return {
    name: 'packageA',
    source_version: '1.0.0',
    target_version: '1.0.1',
    state: 'changed',
    direction: 'upgrade',
    orderable: true,
    ...overrides,
  }
}

describe('buildRows', () => {
  it('gives every row one cell per release, in column order', () => {
    const rows = buildRows(diffOf({ refs: TWO }))

    expect(rows.map((row) => row.name)).toEqual([
      APP_NAME,
      'packageA',
      'packageB',
      'packageC',
      'packageD',
      'packageE',
      'packageF',
    ])
    expect(rows[1].cells.map((cell) => cell.ref)).toEqual(TWO)
    expect(rows[1].cells.map((cell) => cell.version)).toEqual(['1.0.0', '1.0.1'])
  })

  it("puts the application's own version first, and marks it as the application", () => {
    const rows = buildRows(diffOf({ refs: TWO }))

    expect(rows[0].kind).toBe('application')
    expect(rows[0].name).toBe(APP_NAME)
    expect(rows[0].cells.map((cell) => cell.version)).toEqual([
      '1.0.0_10000',
      '1.1.0_10000',
    ])
    // and it is classified like any other row
    expect(rows[0].cells[1].move?.state).toBe('changed')
    expect(rows[0].cells[1].move?.direction).toBe('upgrade')
    // every row after it is a dependency
    expect(rows.slice(1).every((row) => row.kind === 'dependency')).toBe(true)
  })

  it('keeps an absent version as an empty cell rather than a zero', () => {
    const rows = buildRows(diffOf({ refs: TWO }))
    const packageC = rows.find((row) => row.name === 'packageC')
    const packageD = rows.find((row) => row.name === 'packageD')

    expect(packageC?.cells.map((cell) => cell.version)).toEqual(['1.0.0', null])
    expect(packageD?.cells.map((cell) => cell.version)).toEqual([null, '0.9.0'])
  })

  it('leaves the first column without a boundary and an unknown boundary without a move', () => {
    const rows = buildRows(diffOf({ refs: THREE }))

    // no boundary before the first column
    expect(rows[0].cells[0].move).toBeUndefined()
    // a boundary into a release with no record is unknown, not unchanged
    expect(rows[0].cells[2].move).toBeNull()
    expect(rows[0].cells[2].hasRecord).toBe(false)
  })
})

describe('moveTone', () => {
  it('reads a direction when there is one', () => {
    expect(moveTone(move({ direction: 'upgrade' }))).toBe('upgrade')
    expect(moveTone(move({ direction: 'downgrade' }))).toBe('downgrade')
  })

  it('separates a plain change from an upgrade', () => {
    const unorderable = move({ direction: null, orderable: false })

    expect(moveTone(unorderable)).toBe('changed')
    // the tone is what drives the colour and the arrow, so it must not read as one
    expect(moveTone(unorderable)).not.toBe('upgrade')
  })

  it('reads added, removed and unchanged', () => {
    expect(moveTone(move({ state: 'added', direction: null }))).toBe('added')
    expect(moveTone(move({ state: 'removed', direction: null }))).toBe('removed')
    expect(moveTone(move({ state: 'unchanged', direction: null }))).toBe('none')
  })

  it('tells "no boundary" apart from "unknown boundary"', () => {
    expect(moveTone(undefined)).toBe('none')
    expect(moveTone(null)).toBe('unknown')
  })
})

describe('isMarked / isRisk', () => {
  it('marks everything except an unchanged or absent move', () => {
    expect(isMarked(move({ direction: 'upgrade' }))).toBe(true)
    expect(isMarked(move({ direction: null, orderable: false }))).toBe(true)
    expect(isMarked(move({ state: 'unchanged', direction: null }))).toBe(false)
    expect(isMarked(undefined)).toBe(false)
  })

  it('calls a downgrade a risk and nothing else one', () => {
    expect(isRisk(move({ direction: 'downgrade' }))).toBe(true)
    expect(isRisk(move({ direction: 'upgrade' }))).toBe(false)
    // a change with no direction is not a risk, it is simply unknown
    expect(isRisk(move({ direction: null, orderable: false }))).toBe(false)
  })
})

describe('summaryEntries', () => {
  it('reports the counts that moved, in a fixed order', () => {
    const entries = summaryEntries(diffOf({ refs: TWO }).intervals[0].summary)

    // four changed: three dependencies and the application's own version
    expect(entries).toEqual([
      { state: 'changed', count: 4 },
      { state: 'added', count: 1 },
      { state: 'removed', count: 1 },
    ])
  })

  it('reports nothing for an interval in which nothing moved', () => {
    expect(summaryEntries({ changed: 0, added: 0, removed: 0, unchanged: 4 })).toEqual([])
    expect(summaryEntries(undefined)).toEqual([])
  })

  it('counts the downgrades separately, as a risk', () => {
    expect(downgradeCount(diffOf({ refs: TWO }).intervals[0].summary)).toBe(1)
    expect(downgradeCount(undefined)).toBe(0)
  })
})

describe('move symbols and labels', () => {
  it('draws a different glyph per tone', () => {
    expect(moveSymbol('upgrade')).toBe('↑')
    expect(moveSymbol('downgrade')).toBe('↓')
    expect(moveSymbol('added')).toBe('+')
    expect(moveSymbol('removed')).toBe('−')
    expect(moveSymbol('changed')).toBe('•')
    expect(moveSymbol('unknown')).toBe('?')
  })

  it('names the tone by its translation key', () => {
    expect(moveLabelKey('downgrade')).toBe('appDiff.move_downgrade')
    expect(moveLabelKey('unknown')).toBe('appDiff.move_unknown')
  })
})

describe('defaultSelection', () => {
  it('opens on the two most recent releases', () => {
    expect(defaultSelection(['v2.0.0', 'v1.1.0', 'v1.0.0'], ['main'])).toEqual([
      'v2.0.0',
      'v1.1.0',
    ])
  })

  it('falls back to the branches when there are not two tags', () => {
    expect(defaultSelection(['v2.0.0'], ['main', 'develop'])).toEqual(['v2.0.0', 'main'])
    expect(defaultSelection([], ['main'])).toEqual(['main'])
  })
})

describe('codeTone', () => {
  it('tells a pair with commits from one without', () => {
    expect(codeTone(codeOf())).toBe('commits')
    expect(codeTone({ ...codeOf()!, added_count: 0, missing_count: 0 })).toBe('none')
  })

  it('separates "could not be read" from "no commits"', () => {
    expect(codeTone(codeOf(['v1.1.0', 'v4.0.0']))).toBe('unavailable')
    expect(codeTone(null)).toBe('unavailable')
    expect(codeTone(undefined)).toBe('unavailable')
    // and the two must not collapse into one another
    expect(codeTone(null)).not.toBe(codeTone({ ...codeOf()!, added_count: 0 }))
  })
})

describe('commitTotal', () => {
  it('counts both directions', () => {
    expect(commitTotal(codeOf())).toBe(5)
    expect(commitTotal({ ...codeOf()!, added_count: 2, missing_count: 3 })).toBe(5)
  })

  it('counts nothing for an axis that could not be read', () => {
    expect(commitTotal(codeOf(['v1.1.0', 'v4.0.0']))).toBe(0)
    expect(commitTotal(null)).toBe(0)
  })
})

describe('rebuiltWithUnchangedDependencies', () => {
  it('spots a release rebuilt under the same versions', () => {
    const interval = diffOf({ refs: REBUILT }).intervals[0]

    expect(interval.summary.changed).toBe(0)
    expect(interval.summary.added).toBe(0)
    expect(interval.summary.removed).toBe(0)
    expect(interval.dependencies_moved).toBe(false)
    expect(rebuiltWithUnchangedDependencies(interval, interval.code)).toBe(true)
  })

  it('does not say it of a pair whose dependencies moved', () => {
    const interval = diffOf({ refs: TWO }).intervals[0]

    expect(rebuiltWithUnchangedDependencies(interval, interval.code)).toBe(false)
  })

  it('does not say it of a pair whose commits could not be read', () => {
    const interval = diffOf({ refs: ['v1.1.0', 'v4.0.0'] }).intervals[0]

    expect(rebuiltWithUnchangedDependencies(interval, interval.code)).toBe(false)
    expect(rebuiltWithUnchangedDependencies(interval, null)).toBe(false)
  })

  it('does not say it of a pair that really did not change', () => {
    const interval = diffOf({ refs: TWO }).intervals[0]

    expect(
      rebuiltWithUnchangedDependencies(interval, {
        ...interval.code!,
        added_count: 0,
        missing_count: 0,
      }),
    ).toBe(false)
  })

  it('is not fooled by the application moving its own version alone', () => {
    const base = diffOf({ refs: TWO }).intervals[0]
    // the application's own row moved; no dependency did
    const interval = { ...base, dependencies_moved: false }

    // the pair's summary still counts the application's own move ...
    expect(interval.summary.changed).toBeGreaterThan(0)
    // ... while the rebuild reading answers about the dependencies, which did not
    expect(rebuiltWithUnchangedDependencies(interval, interval.code)).toBe(true)
  })
})

describe('commit rendering helpers', () => {
  it('shortens a commit to its display id', () => {
    const commit = codeOf()!.added_commits[0]

    expect(shortCommitId(commit)).toBe('a1b2c3d')
    expect(shortCommitId({ ...commit, display_id: null })).toBe('a1b2c3d')
  })

  it('takes the first line of what a commit says', () => {
    const commit = codeOf()!.added_commits[0]

    expect(commitSubject(commit)).toBe('Add the new module')
    expect(commitSubject({ ...commit, message: 'Subject\n\nBody line' })).toBe('Subject')
    expect(commitSubject({ ...commit, message: null })).toBe('')
  })
})
