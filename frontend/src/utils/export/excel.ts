import * as XLSX from 'xlsx'
import type { Review } from '@/api/reviews'
import dayjs from 'dayjs'

export interface ExcelExportOptions {
  filename?: string
  sheetName?: string
  includeHeaders?: boolean
}

export function exportReviewsToExcel(
  reviews: Review[],
  options: ExcelExportOptions = {}
) {
  const {
    filename = `reviews_${dayjs().format('YYYY-MM-DD_HH-mm-ss')}.xlsx`,
    sheetName = 'Reviews',
    includeHeaders = true,
  } = options

  // Prepare data
  const headers = includeHeaders ? [
    'Seq#',
    'PR ID',
    'Project/Repo',
    'PR User',
    'Reviewer',
    'PR Status',
    'Scores',
    'Comments',
    'Created',
    'Updated',
  ] : []

  const data = reviews.map((review, index) => [
    index + 1,
    review.pull_request_id,
    `${review.project_key} / ${review.repository_slug}`,
    review.pull_request_user_info?.display_name || review.pull_request_user,
    review.reviewer_info?.display_name || review.reviewer,
    review.pull_request_status,
    review.score_summary && review.score_summary.total_scores > 0
      ? `${review.score_summary.average_score?.toFixed(1)} (${review.score_summary.total_scores})`
      : 'No scores',
    review.reviewer_comments || '',
    dayjs(review.created_date).format('YYYY-MM-DD HH:mm:ss'),
    dayjs(review.updated_date).format('YYYY-MM-DD HH:mm:ss'),
  ])

  // Combine headers and data
  const worksheetData = includeHeaders ? [headers, ...data] : data

  // Create worksheet
  const worksheet = XLSX.utils.aoa_to_sheet(worksheetData)

  // Set column widths
  worksheet['!cols'] = [
    { wch: 8 },   // Seq#
    { wch: 35 },  // PR ID
    { wch: 35 },  // Project/Repo
    { wch: 25 },  // PR User
    { wch: 25 },  // Reviewer
    { wch: 15 },  // Status
    { wch: 18 },  // Scores
    { wch: 50 },  // Comments
    { wch: 20 },  // Created
    { wch: 20 },  // Updated
  ]

  // Style header row
  if (includeHeaders) {
    const range = XLSX.utils.decode_range(worksheet['!ref'] || 'A1')
    for (let C = range.s.c; C <= range.e.c; ++C) {
      const address = XLSX.utils.encode_col(C) + '1'
      if (!worksheet[address]) continue
      worksheet[address].s = {
        font: { bold: true, color: { rgb: 'FFFFFF' } },
        fill: { fgColor: { rgb: '409EFF' } },
        alignment: { horizontal: 'center' },
      }
    }
  }

  // Create workbook
  const workbook = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(workbook, worksheet, sheetName)

  // Add summary sheet
  const summaryData = [
    ['Review Export Summary'],
    ['Generated At', dayjs().format('YYYY-MM-DD HH:mm:ss')],
    ['Total Reviews', reviews.length],
    ['', ''],
    ['Status Breakdown'],
  ]

  const statusCounts = reviews.reduce((acc, review) => {
    const status = review.pull_request_status || 'unknown'
    acc[status] = (acc[status] || 0) + 1
    return acc
  }, {} as Record<string, number>)

  Object.entries(statusCounts).forEach(([status, count]) => {
    summaryData.push([status, count])
  })

  const summaryWorksheet = XLSX.utils.aoa_to_sheet(summaryData)
  summaryWorksheet['!cols'] = [{ wch: 25 }, { wch: 15 }]
  XLSX.utils.book_append_sheet(workbook, summaryWorksheet, 'Summary')

  // Save file
  XLSX.writeFile(workbook, filename)
}

export function exportScoresToExcel(
  scores: any[],
  options: ExcelExportOptions = {}
) {
  const {
    filename = `scores_${dayjs().format('YYYY-MM-DD_HH-mm-ss')}.xlsx`,
    sheetName = 'Scores',
  } = options

  // Prepare data
  const headers = [
    'ID',
    'Review ID',
    'Category',
    'Score',
    'Max Score',
    'Weight',
    'Comment',
    'Created By',
    'Created At',
  ]

  const data = scores.map(score => [
    score.id,
    score.review_id,
    score.category || 'N/A',
    score.score ?? 'N/A',
    score.max_score ?? 100,
    score.weight ?? 1.0,
    score.comment || '',
    score.created_by || 'N/A',
    dayjs(score.created_at).format('YYYY-MM-DD HH:mm:ss'),
  ])

  const worksheetData = [headers, ...data]

  // Create worksheet
  const worksheet = XLSX.utils.aoa_to_sheet(worksheetData)

  // Set column widths
  worksheet['!cols'] = [
    { wch: 8 },   // ID
    { wch: 12 },  // Review ID
    { wch: 20 },  // Category
    { wch: 10 },  // Score
    { wch: 12 },  // Max Score
    { wch: 10 },  // Weight
    { wch: 40 },  // Comment
    { wch: 20 },  // Created By
    { wch: 20 },  // Created At
  ]

  // Style header row
  const range = XLSX.utils.decode_range(worksheet['!ref'] || 'A1')
  for (let C = range.s.c; C <= range.e.c; ++C) {
    const address = XLSX.utils.encode_col(C) + '1'
    if (!worksheet[address]) continue
    worksheet[address].s = {
      font: { bold: true, color: { rgb: 'FFFFFF' } },
      fill: { fgColor: { rgb: '67C23A' } },
      alignment: { horizontal: 'center' },
    }
  }

  // Create workbook
  const workbook = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(workbook, worksheet, sheetName)

  // Add statistics sheet
  const statsData = [
    ['Score Statistics'],
    ['Generated At', dayjs().format('YYYY-MM-DD HH:mm:ss')],
    ['Total Scores', scores.length],
    ['', ''],
    ['Average Score', calculateAverageScore(scores)],
    ['Min Score', calculateMinScore(scores)],
    ['Max Score', calculateMaxScore(scores)],
  ]

  const statsWorksheet = XLSX.utils.aoa_to_sheet(statsData)
  statsWorksheet['!cols'] = [{ wch: 25 }, { wch: 15 }]
  XLSX.utils.book_append_sheet(workbook, statsWorksheet, 'Statistics')

  // Save file
  XLSX.writeFile(workbook, filename)
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
