import { describe, expect, it } from 'vitest'
import { useTaskAssignmentAnalytics } from '@/composables/useTaskAssignmentAnalytics'
import type { ReviewV2, ReviewerAssignment } from '@/api/taskAssignment'

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
