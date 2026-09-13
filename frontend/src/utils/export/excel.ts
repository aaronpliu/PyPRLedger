import ExcelJS from 'exceljs'
import type { Review } from '@/api/reviews'
import dayjs from 'dayjs'
import { buildReviewExportRow, REVIEW_EXPORT_COLUMNS, tExport } from './shared'

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
    sheetName = tExport('export.excel_sheet_reviews'),
    includeHeaders = true,
  } = options

  // Create workbook
  const workbook = new ExcelJS.Workbook()
  workbook.creator = 'PyPRLedger'
  workbook.created = new Date()

  // Add Reviews worksheet
  const reviewWorksheet = workbook.addWorksheet(sheetName)

  // Localized headers. Rows are built by the shared builder, which fills the
  // Reviewer / Comments cells from nested score data for scored records.
  const labels = REVIEW_EXPORT_COLUMNS.map((col) => tExport(col.labelKey))
  const widthByKey: Record<string, number> = {
    seq: 8,
    prId: 35,
    projectRepo: 35,
    prUser: 25,
    reviewer: 25,
    status: 15,
    scores: 18,
    comments: 50,
    created: 20,
    updated: 20,
  }

  reviewWorksheet.columns = REVIEW_EXPORT_COLUMNS.map((col, index) => ({
    header: labels[index],
    key: col.key,
    width: widthByKey[col.key] || 20,
  }))

  // Prepare data
  const data = reviews.map((review, index) => buildReviewExportRow(review, index))

  // Add rows
  data.forEach(item => {
    reviewWorksheet.addRow(item)
  })

  // Style header row if included
  if (includeHeaders && reviewWorksheet.getRow(1)) {
    styleHeaderRow(reviewWorksheet.getRow(1), 'FF409EFF')
  }

  // Add Summary worksheet
  const summaryWorksheet = workbook.addWorksheet(tExport('export.excel_sheet_summary'))
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
    { label: tExport('export.summary_title'), value: '' },
    { label: tExport('export.generated_at'), value: dayjs().format('YYYY-MM-DD HH:mm:ss') },
    { label: tExport('export.total_reviews'), value: reviews.length },
    { label: '', value: '' },
    { label: tExport('export.status_breakdown'), value: '' },
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
