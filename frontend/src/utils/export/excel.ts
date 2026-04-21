import ExcelJS from 'exceljs'
import type { Review } from '@/api/reviews'
import dayjs from 'dayjs'

export interface ExcelExportOptions {
  filename?: string
  sheetName?: string
  includeHeaders?: boolean
}

/**
 * Helper function to trigger file download in browser
 */
async function downloadWorkbook(workbook: ExcelJS.Workbook, filename: string) {
  const buffer = await workbook.xlsx.writeBuffer()
  const blob = new Blob([buffer], { 
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' 
  })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.style.display = 'none'
  
  document.body.appendChild(link)
  link.click()
  
  // Cleanup
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

/**
 * Helper function to apply header styling
 */
function styleHeaderRow(row: ExcelJS.Row, color: string) {
  row.eachCell((cell) => {
    cell.font = { bold: true, color: { argb: 'FFFFFFFF' } }
    cell.fill = {
      type: 'pattern',
      pattern: 'solid',
      fgColor: { argb: color },
    }
    cell.alignment = { horizontal: 'center', vertical: 'middle' }
  })
}

export async function exportReviewsToExcel(
  reviews: Review[],
  options: ExcelExportOptions = {}
) {
  const {
    filename = `reviews_${dayjs().format('YYYY-MM-DD_HH-mm-ss')}.xlsx`,
    sheetName = 'Reviews',
    includeHeaders = true,
  } = options

  // Create workbook
  const workbook = new ExcelJS.Workbook()
  workbook.creator = 'PyPRLedger'
  workbook.created = new Date()

  // Add Reviews worksheet
  const reviewWorksheet = workbook.addWorksheet(sheetName)

  // Define columns
  const columns = [
    { header: 'Seq#', key: 'seq', width: 8 },
    { header: 'PR ID', key: 'prId', width: 35 },
    { header: 'Project/Repo', key: 'projectRepo', width: 35 },
    { header: 'PR User', key: 'prUser', width: 25 },
    { header: 'Reviewer', key: 'reviewer', width: 25 },
    { header: 'PR Status', key: 'status', width: 15 },
    { header: 'Scores', key: 'scores', width: 18 },
    { header: 'Comments', key: 'comments', width: 50 },
    { header: 'Created', key: 'created', width: 20 },
    { header: 'Updated', key: 'updated', width: 20 },
  ]

  reviewWorksheet.columns = columns

  // Prepare data
  const data = reviews.map((review, index) => ({
    seq: index + 1,
    prId: review.pull_request_id,
    projectRepo: `${review.project_key} / ${review.repository_slug}`,
    prUser: review.pull_request_user_info?.display_name || review.pull_request_user,
    reviewer: review.reviewer_info?.display_name || review.reviewer,
    status: review.pull_request_status,
    scores: review.score_summary && review.score_summary.total_scores > 0
      ? `${review.score_summary.average_score?.toFixed(1)} (${review.score_summary.total_scores})`
      : 'No scores',
    comments: review.reviewer_comments || '',
    created: dayjs(review.created_date).format('YYYY-MM-DD HH:mm:ss'),
    updated: dayjs(review.updated_date).format('YYYY-MM-DD HH:mm:ss'),
  }))

  // Add rows
  data.forEach(item => {
    reviewWorksheet.addRow(item)
  })

  // Style header row if included
  if (includeHeaders && reviewWorksheet.getRow(1)) {
    styleHeaderRow(reviewWorksheet.getRow(1), 'FF409EFF')
  }

  // Add Summary worksheet
  const summaryWorksheet = workbook.addWorksheet('Summary')
  summaryWorksheet.columns = [
    { header: '', key: 'label', width: 25 },
    { header: '', key: 'value', width: 15 },
  ]

  const statusCounts = reviews.reduce((acc, review) => {
    const status = review.pull_request_status || 'unknown'
    acc[status] = (acc[status] || 0) + 1
    return acc
  }, {} as Record<string, number>)

  summaryWorksheet.addRows([
    { label: 'Review Export Summary', value: '' },
    { label: 'Generated At', value: dayjs().format('YYYY-MM-DD HH:mm:ss') },
    { label: 'Total Reviews', value: reviews.length },
    { label: '', value: '' },
    { label: 'Status Breakdown', value: '' },
  ])

  Object.entries(statusCounts).forEach(([status, count]) => {
    summaryWorksheet.addRow({ label: status, value: count })
  })

  // Download the file
  await downloadWorkbook(workbook, filename)
}

export async function exportScoresToExcel(
  scores: any[],
  options: ExcelExportOptions = {}
) {
  const {
    filename = `scores_${dayjs().format('YYYY-MM-DD_HH-mm-ss')}.xlsx`,
    sheetName = 'Scores',
  } = options

  // Create workbook
  const workbook = new ExcelJS.Workbook()
  workbook.creator = 'PyPRLedger'
  workbook.created = new Date()

  // Add Scores worksheet
  const scoresWorksheet = workbook.addWorksheet(sheetName)

  // Define columns
  scoresWorksheet.columns = [
    { header: 'ID', key: 'id', width: 8 },
    { header: 'Review ID', key: 'reviewId', width: 12 },
    { header: 'Category', key: 'category', width: 20 },
    { header: 'Score', key: 'score', width: 10 },
    { header: 'Max Score', key: 'maxScore', width: 12 },
    { header: 'Weight', key: 'weight', width: 10 },
    { header: 'Comment', key: 'comment', width: 40 },
    { header: 'Created By', key: 'createdBy', width: 20 },
    { header: 'Created At', key: 'createdAt', width: 20 },
  ]

  // Prepare data
  const data = scores.map(score => ({
    id: score.id,
    reviewId: score.review_id,
    category: score.category || 'N/A',
    score: score.score ?? 'N/A',
    maxScore: score.max_score ?? 100,
    weight: score.weight ?? 1.0,
    comment: score.comment || '',
    createdBy: score.created_by || 'N/A',
    createdAt: dayjs(score.created_at).format('YYYY-MM-DD HH:mm:ss'),
  }))

  // Add rows
  data.forEach(item => {
    scoresWorksheet.addRow(item)
  })

  // Style header row
  if (scoresWorksheet.getRow(1)) {
    styleHeaderRow(scoresWorksheet.getRow(1), 'FF67C23A')
  }

  // Add Statistics worksheet
  const statsWorksheet = workbook.addWorksheet('Statistics')
  statsWorksheet.columns = [
    { header: '', key: 'label', width: 25 },
    { header: '', key: 'value', width: 15 },
  ]

  statsWorksheet.addRows([
    { label: 'Score Statistics', value: '' },
    { label: 'Generated At', value: dayjs().format('YYYY-MM-DD HH:mm:ss') },
    { label: 'Total Scores', value: scores.length },
    { label: '', value: '' },
    { label: 'Average Score', value: calculateAverageScore(scores) },
    { label: 'Min Score', value: calculateMinScore(scores) },
    { label: 'Max Score', value: calculateMaxScore(scores) },
  ])

  // Download the file
  await downloadWorkbook(workbook, filename)
}

function calculateAverageScore(scores: any[]): number {
  const validScores = scores.filter(s => s.score != null).map(s => s.score)
  if (validScores.length === 0) return 0
  return validScores.reduce((sum, score) => sum + score, 0) / validScores.length
}

function calculateMinScore(scores: any[]): number {
  const validScores = scores.filter(s => s.score != null).map(s => s.score)
  if (validScores.length === 0) return 0
  return Math.min(...validScores)
}

function calculateMaxScore(scores: any[]): number {
  const validScores = scores.filter(s => s.score != null).map(s => s.score)
  if (validScores.length === 0) return 0
  return Math.max(...validScores)
}
