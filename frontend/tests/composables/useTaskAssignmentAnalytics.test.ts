import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import dayjs from 'dayjs'
import isoWeek from 'dayjs/plugin/isoWeek'
import { useTaskAssignmentAnalytics } from '@/composables/useTaskAssignmentAnalytics'
import type { ReviewV2, ReviewerAssignment } from '@/api/taskAssignment'

dayjs.extend(isoWeek)

function reviewer(name: string, status: ReviewerAssignment['assignment_status'] = 'assigned'): ReviewerAssignment {
  return {
    id: 1,
    reviewer: name,
    assignment_status: status,
    created_date: '2026-10-01T00:00:00Z',
    updated_date: '2026-10-01T00:00:00Z',
  }
}

function review(patch: Partial<ReviewV2> = {}): ReviewV2 {
  return {
    id: 1,
    pull_request_id: '1',
    project_key: 'PRJ',
    repository_slug: 'repo',
    source_branch: 'feature/x',
    target_branch: 'develop',
    pull_request_status: 'open',
    created_date: '2026-10-01T00:00:00Z',
    updated_date: '2026-10-01T00:00:00Z',
    reviewers: [],
    total_reviewers: 0,
    completed_reviewers: 0,
    pending_reviewers: 0,
    has_scores: false,
    ...patch,
  }
}

function summaryOf(reviews: ReviewV2[]) {
  const analytics = useTaskAssignmentAnalytics()
  analytics.setReviews(reviews)
  return analytics.getSummaryStats.value
}

describe('useTaskAssignmentAnalytics summary', () => {
  it('counts nothing when there is nothing', () => {
    expect(summaryOf([])).toEqual({
      totalPRs: 0,
      activePRs: 0,
      avgAssignments: 0,
      scoringRate: 0,
    })
  })

  it('counts a pull request once however many review rows it arrived as', () => {
    // One PR reviewed file by file is still one pull request.
    const summary = summaryOf([
      review({ id: 1, pull_request_id: '42' }),
      review({ id: 2, pull_request_id: '42' }),
      review({ id: 3, pull_request_id: '42' }),
    ])

    expect(summary.totalPRs).toBe(1)
  })

  it('keeps pull requests of the same number apart when the repository differs', () => {
    const summary = summaryOf([
      review({ id: 1, repository_slug: 'alpha', pull_request_id: '7' }),
      review({ id: 2, repository_slug: 'beta', pull_request_id: '7' }),
      review({ id: 3, project_key: 'OTHER', repository_slug: 'alpha', pull_request_id: '7' }),
    ])

    // A PR number is only unique within its repository.
    expect(summary.totalPRs).toBe(3)
  })

  describe('active pull requests', () => {
    it('counts one whose reviewer has not finished', () => {
      const summary = summaryOf([
        review({ pull_request_id: '1', reviewers: [reviewer('alice', 'completed')] }),
        review({ pull_request_id: '2', reviewers: [reviewer('bob', 'in_progress')] }),
      ])

      expect(summary.totalPRs).toBe(2)
      expect(summary.activePRs).toBe(1)
    })

    it('leaves out one every reviewer has completed', () => {
      const summary = summaryOf([
        review({
          pull_request_id: '1',
          reviewers: [reviewer('alice', 'completed'), reviewer('bob', 'completed')],
        }),
      ])

      expect(summary.activePRs).toBe(0)
    })

    it('counts one nobody has been assigned to, since nothing about it is done', () => {
      const summary = summaryOf([review({ pull_request_id: '1', reviewers: [] })])

      expect(summary.activePRs).toBe(1)
    })

    it('stays outstanding while any file of it is unfinished', () => {
      const summary = summaryOf([
        // The overall review is done, a file review is not.
        review({ id: 1, pull_request_id: '1', reviewers: [reviewer('alice', 'completed')] }),
        review({ id: 2, pull_request_id: '1', reviewers: [reviewer('alice', 'assigned')] }),
      ])

      expect(summary.totalPRs).toBe(1)
      expect(summary.activePRs).toBe(1)
    })

    it('does not follow the pull request status, which nothing updates', () => {
      // A merged PR with unfinished work is still unfinished work, and a closed
      // one whose reviewers are done is still done.
      const summary = summaryOf([
        review({
          pull_request_id: '1',
          pull_request_status: 'merged',
          reviewers: [reviewer('alice', 'in_progress')],
        }),
        review({
          pull_request_id: '2',
          pull_request_status: 'closed',
          reviewers: [reviewer('bob', 'completed')],
        }),
      ])

      expect(summary.activePRs).toBe(1)
    })

    it('never exceeds the total', () => {
      const summary = summaryOf([
        review({ id: 1, pull_request_id: '1', reviewers: [reviewer('alice', 'pending')] }),
        review({ id: 2, pull_request_id: '1', reviewers: [reviewer('alice', 'pending')] }),
        review({ id: 3, pull_request_id: '2', reviewers: [reviewer('bob', 'completed')] }),
      ])

      expect(summary.activePRs).toBeLessThanOrEqual(summary.totalPRs)
    })
  })

  it('averages assignments per pull request, counting a reviewer once', () => {
    const summary = summaryOf([
      // Same reviewer on both files of the first PR: one reviewer on that PR.
      review({ id: 1, pull_request_id: '1', reviewers: [reviewer('alice')] }),
      review({ id: 2, pull_request_id: '1', reviewers: [reviewer('alice')] }),
      // Two reviewers on the second.
      review({ id: 3, pull_request_id: '2', reviewers: [reviewer('alice'), reviewer('bob')] }),
    ])

    expect(summary.totalPRs).toBe(2)
    expect(summary.avgAssignments).toBe(1.5)
  })

  it('rates scoring per pull request, scoring one if any of its rows has scores', () => {
    const summary = summaryOf([
      review({ id: 1, pull_request_id: '1', has_scores: false }),
      review({ id: 2, pull_request_id: '1', has_scores: true }),
      review({ id: 3, pull_request_id: '2', has_scores: false }),
    ])

    expect(summary.totalPRs).toBe(2)
    expect(summary.scoringRate).toBe(50)
  })

  it('reports a fully scored set as 100 percent', () => {
    const summary = summaryOf([
      review({ pull_request_id: '1', has_scores: true }),
      review({ pull_request_id: '2', has_scores: true }),
    ])

    expect(summary.scoringRate).toBe(100)
  })
})

describe('useTaskAssignmentAnalytics period windows', () => {
  // Noon UTC keeps the instant inside the same day (and week) in every zone.
  const NOW = '2026-10-07T12:00:00Z'

  function analyticsWith(reviews: ReviewV2[]) {
    const analytics = useTaskAssignmentAnalytics()
    analytics.setReviews(reviews)
    return analytics
  }

  /** The key the composable builds for an instant, written out independently. */
  function weekKeyOf(instant: string): string {
    const date = dayjs(instant)
    return `${date.isoWeekYear()}-W${String(date.isoWeek()).padStart(2, '0')}`
  }

  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(NOW))
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('shows the last 180 days, 26 weeks and 6 months', () => {
    const analytics = analyticsWith([review({ created_date: NOW })])

    expect(analytics.aggregateByTimePeriod('daily')).toHaveLength(180)
    expect(analytics.aggregateByTimePeriod('weekly')).toHaveLength(26)
    expect(analytics.aggregateByTimePeriod('monthly')).toHaveLength(6)
  })

  it('puts a period with no reviews on the axis as a zero', () => {
    const analytics = analyticsWith([
      review({ id: 1, created_date: NOW }),
      review({ id: 2, created_date: dayjs(NOW).subtract(3, 'week').toISOString() }),
    ])

    const counts = analytics.aggregateByTimePeriod('weekly').map((point) => point.count)

    expect(counts).toHaveLength(26)
    expect(counts.reduce((sum, count) => sum + count, 0)).toBe(2)
    // The current week is the last point, three weeks back the fourth from the
    // end, and the two weeks between them are on the axis with nothing in them.
    expect(counts[counts.length - 1]).toBe(1)
    expect(counts[counts.length - 4]).toBe(1)
    expect(counts[counts.length - 2]).toBe(0)
    expect(counts[counts.length - 3]).toBe(0)
  })

  it('runs oldest to newest, which the padded week number is what keeps', () => {
    // Anchored in March so the window spans weeks 9 and 10 of the year, where
    // unpadded keys sort as strings the wrong way round.
    vi.setSystemTime(new Date('2026-03-04T12:00:00Z'))
    const analytics = analyticsWith([review({ created_date: '2026-03-02T12:00:00Z' })])

    const dates = analytics.aggregateByTimePeriod('weekly').map((point) => point.date)

    expect(dates).toContain('2026-W09')
    expect(dates).toContain('2026-W10')
    expect([...dates].sort()).toEqual(dates)
  })

  it('leaves out what falls before the window', () => {
    const analytics = analyticsWith([
      review({ id: 1, created_date: dayjs(NOW).subtract(30, 'week').toISOString() }),
    ])

    // Nothing left in the window, so there is nothing to draw.
    expect(analytics.aggregateByTimePeriod('weekly')).toEqual([])
    expect(analytics.aggregateByTimePeriod('daily')).toEqual([])
    expect(analytics.aggregateByTimePeriod('monthly')).toEqual([])
  })

  it('keys a new year week by its ISO week-year, not the calendar year', () => {
    // 2025-12-29 opens ISO week 1 of 2026; the calendar year of that Monday is
    // 2025, which is how it used to collide with the first week of 2025.
    const instant = '2025-12-29T12:00:00Z'
    vi.setSystemTime(new Date('2026-01-05T12:00:00Z'))
    const analytics = analyticsWith([review({ created_date: instant })])

    const points = analytics.aggregateByTimePeriod('weekly')

    expect(weekKeyOf(instant)).toBe('2026-W01')
    expect(points.map((point) => point.date)).toContain('2026-W01')
    expect(points.filter((point) => point.count > 0)).toHaveLength(1)
  })

  it('gives the severity chart the same axis as the trend chart', () => {
    const analytics = analyticsWith([
      review({ id: 1, created_date: NOW, issue_severities: ['high', 'low'] }),
      review({ id: 2, created_date: dayjs(NOW).subtract(2, 'month').toISOString(), issue_severities: ['critical'] }),
    ])

    const series = analytics.aggregateIssuesBySeverity('weekly')
    const trend = analytics.aggregateByTimePeriod('weekly')

    expect(series).toHaveLength(4)
    series.forEach((severity) => {
      expect(severity.data.map((point) => point.date)).toEqual(trend.map((point) => point.date))
    })

    const high = series.find((severity) => severity.name === 'High')
    expect(high?.data.reduce((sum, point) => sum + point.value, 0)).toBe(1)
    expect(series.find((severity) => severity.name === 'Critical')?.data.reduce((sum, p) => sum + p.value, 0)).toBe(1)
  })

  it('has nothing to draw when no review in the window carries an issue', () => {
    const analytics = analyticsWith([review({ created_date: NOW })])

    expect(analytics.aggregateIssuesBySeverity('weekly')).toEqual([])
  })
})
