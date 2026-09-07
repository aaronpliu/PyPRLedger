import type { Review } from '@/api/reviews'
import dayjs from 'dayjs'
import { buildReviewExportRow, REVIEW_EXPORT_COLUMNS, tExport } from './shared'

/**
 * Export data to CSV format
 */
export function exportToCSV(
  data: any[],
  filename: string,
  columns?: string[]
) {
  if (!data || data.length === 0) {
    console.warn('No data to export')
    return
  }

  // Determine columns
  const headers = columns || Object.keys(data[0])

  // Create CSV content
  const csvContent = [
    headers.join(','), // Header row
    ...data.map(row => 
      headers.map(header => {
        const value = row[header] ?? ''
        // Escape quotes and wrap in quotes if contains comma, quote, or newline
        const escaped = String(value).replace(/"/g, '""')
        return /[",\n\r]/.test(escaped) ? `"${escaped}"` : escaped
      }).join(',')
    ),
  ].join('\n')

  // Add BOM for Excel compatibility
  const BOM = '\uFEFF'
  const blob = new Blob([BOM + csvContent], { type: 'text/csv;charset=utf-8;' })
  
  // Download
  downloadFile(blob, filename)
}

/**
 * Export reviews to CSV
 */
export function exportReviewsToCSV(reviews: Review[], filename?: string) {
  const finalFilename = filename || `reviews_${dayjs().format('YYYY-MM-DD_HH-mm-ss')}.csv`

  // Localized, human-readable headers instead of raw internal field names.
  // Rows are built by the shared builder, which fills the Reviewer and
  // Comments cells from nested score data when the record was scored.
  const labels = REVIEW_EXPORT_COLUMNS.map((col) => tExport(col.labelKey))

  const data = reviews.map((review, index) => {
    const row = buildReviewExportRow(review, index)
    const record: Record<string, unknown> = {}
    REVIEW_EXPORT_COLUMNS.forEach((col, i) => {
      record[labels[i]] = row[col.key]
    })
    return record
  })

  exportToCSV(data, finalFilename, labels)
}

/**
 * Export data to JSON format
 */
export function exportToJSON(
  data: any[],
  filename: string,
  prettyPrint: boolean = true
) {
  if (!data || data.length === 0) {
    console.warn('No data to export')
    return
  }

  const jsonContent = prettyPrint
    ? JSON.stringify(data, null, 2)
    : JSON.stringify(data)

  const blob = new Blob([jsonContent], { type: 'application/json;charset=utf-8;' })
  
  downloadFile(blob, filename)
}

/**
 * Export reviews to JSON
 */
export function exportReviewsToJSON(reviews: Review[], filename?: string) {
  const finalFilename = filename || `reviews_${dayjs().format('YYYY-MM-DD_HH-mm-ss')}.json`
  exportToJSON(reviews, finalFilename)
}

/**
 * Export scores to JSON with metadata
 */
export function exportScoresToJSON(scores: any[], filename?: string) {
  const finalFilename = filename || `scores_${dayjs().format('YYYY-MM-DD_HH-mm-ss')}.json`
  
  const exportData = {
    metadata: {
      exportedAt: dayjs().toISOString(),
      totalScores: scores.length,
      version: '1.0',
    },
    data: scores,
  }

  // Pass as array to match function signature
  exportToJSON([exportData], finalFilename)
}

/**
 * Generic file download helper
 */
function downloadFile(blob: Blob, filename: string) {
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
 * Export selected reviews based on format
 */
export async function exportSelectedReviews(
  reviews: Review[],
  format: 'csv' | 'json' | 'excel' | 'pdf',
  selectedIds?: number[]
) {
  let dataToExport = reviews
  
  // Filter by selected IDs if provided
  if (selectedIds && selectedIds.length > 0) {
    dataToExport = reviews.filter(r => selectedIds.includes(r.id))
  }

  switch (format) {
    case 'csv':
      exportReviewsToCSV(dataToExport)
      break
    case 'json':
      exportReviewsToJSON(dataToExport)
      break
    case 'excel':
      // Lazy import to avoid bundling issues
      const { exportReviewsToExcel } = await import('./excel')
      await exportReviewsToExcel(dataToExport)
      break
    case 'pdf':
      // Lazy import to avoid bundling issues
      const { exportReviewsToPDF } = await import('./pdf')
      await exportReviewsToPDF(dataToExport)
      break
    default:
      console.error(`Unsupported export format: ${format}`)
  }
}
