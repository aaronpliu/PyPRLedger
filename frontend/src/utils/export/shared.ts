import type { Review, ReviewScoreResponse } from '@/api/reviews'
import dayjs from 'dayjs'
import i18n from '@/i18n'

/**
 * Shared helpers for code review export (CSV / Excel / PDF).
 *
 * Review list rows are PR-centric: the top-level `reviewer` and
 * `reviewer_comments` fields are often empty even when the PR has been scored
 * with comments — the real per-reviewer data lives on the assignment list
 * (`all_reviewers`) and inside `score_summary.scores[]`. These helpers resolve
 * those nested values so exported rows keep the Reviewer / Comments columns
 * populated. All user-facing text is localized through the active i18n locale.
 */

export function tExport(key: string, params?: Record<string, unknown>): string {
  return i18n.global.t(key, params ?? {})
}

export interface ReviewExportRow {
  seq: string
  prId: string
  projectRepo: string
  prUser: string
  reviewer: string
  status: string
  scores: string
  comments: string
  created: string
  updated: string
}

export interface ReviewExportColumn {
  key: keyof ReviewExportRow
  labelKey: string
}

export const REVIEW_EXPORT_COLUMNS: ReviewExportColumn[] = [
  { key: 'seq', labelKey: 'export.col_seq' },
  { key: 'prId', labelKey: 'export.col_pr_id' },
  { key: 'projectRepo', labelKey: 'export.col_project_repo' },
  { key: 'prUser', labelKey: 'export.col_pr_user' },
  { key: 'reviewer', labelKey: 'export.col_reviewer' },
  { key: 'status', labelKey: 'export.col_pr_status' },
  { key: 'scores', labelKey: 'export.col_scores' },
  { key: 'comments', labelKey: 'export.col_comments' },
  { key: 'created', labelKey: 'export.col_created' },
  { key: 'updated', labelKey: 'export.col_updated' },
]

interface ReviewerEntry {
  reviewer?: string | null
  reviewer_info?: Record<string, any> | null
}

function reviewerDisplayName(entry?: ReviewerEntry | null): string {
  if (!entry) return ''
  const info = entry.reviewer_info as Record<string, any> | undefined
  return info?.display_name || entry.reviewer || ''
}

function resolveReviewers(review: Review): string {
  const names: string[] = []
  const push = (name: string) => {
    const trimmed = name?.trim()
    if (trimmed && !names.includes(trimmed)) {
      names.push(trimmed)
    }
  }

  const allReviewers = review.all_reviewers || []
  allReviewers.forEach((r) => push(r.display_name || r.username))
  if (names.length) {
    return names.join(', ')
  }

  push(reviewerDisplayName(review))
  if (names.length) {
    return names.join(', ')
  }

  const scores = review.score_summary?.scores || []
  scores.forEach((score) => push(reviewerDisplayName(score)))
  return names.join(', ')
}

function resolveComments(review: Review): string {
  const scores = review.score_summary?.scores || []

  const distinctReviewers = new Set(scores.map((s) => reviewerDisplayName(s) || '')).size
  const multipleSources = distinctReviewers > 1 || scores.length > 1

  const lines: string[] = []
  scores.forEach((score: ReviewScoreResponse) => {
    const comment = String(score.reviewer_comments ?? score.comment ?? '').trim()
    if (!comment) {
      return
    }
    const who = reviewerDisplayName(score)
    const where = score.source_filename ? ` (${score.source_filename})` : ''
    const needsLabel = Boolean(who) && (Boolean(score.source_filename) || multipleSources)
    lines.push(needsLabel ? `${who}${where}: ${comment}` : comment)
  })

  if (lines.length) {
    return lines.join('\n')
  }
  return String(review.reviewer_comments ?? '').trim()
}

export function buildReviewExportRow(review: Review, index: number): ReviewExportRow {
  const summary = review.score_summary
  const totalScores = summary?.total_scores ?? 0

  let scoresText = ''
  if (summary && totalScores > 0) {
    const display = summary.max_score ?? summary.average_score
    scoresText = display != null ? `${display.toFixed(1)} (${totalScores})` : ''
  }
  if (!scoresText) {
    scoresText = tExport('export.no_scores')
  }

  const prUserInfo = review.pull_request_user_info as Record<string, any> | undefined

  return {
    seq: String(index + 1),
    prId: review.pull_request_id,
    projectRepo: `${review.project_key} / ${review.repository_slug}`,
    prUser: prUserInfo?.display_name || review.pull_request_user || '',
    reviewer: resolveReviewers(review),
    status: review.pull_request_status,
    scores: scoresText,
    comments: resolveComments(review),
    created: review.created_date ? dayjs(review.created_date).format('YYYY-MM-DD HH:mm:ss') : '',
    updated: review.updated_date ? dayjs(review.updated_date).format('YYYY-MM-DD HH:mm:ss') : '',
  }
}
