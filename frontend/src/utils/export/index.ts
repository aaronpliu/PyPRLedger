import type { Review } from '@/api/reviews'
import dayjs from 'dayjs'

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
        // Escape quotes and wrap in quotes if contains comma
        const escaped = String(value).replace(/"/g, '""')
        return escaped.includes(',') ? `"${escaped}"` : escaped
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
  
  // Map internal field names to display names
  const columns = [
    'seq#',
    'pull_request_id',
    'project_repo',
    'pr_user',
    'reviewer',
    'pr_status',
    'scores',
    'reviewer_comments',
    'created_date',
    'updated_date',
  ]

  const data = reviews.map((review, index) => ({
    ...review,
    'seq#': index + 1,
    'project_repo': `${review.project_key} / ${review.repository_slug}`,
    'pr_user': review.pull_request_user_info?.display_name || review.pull_request_user,
    'reviewer': review.reviewer_info?.display_name || review.reviewer,
    'pr_status': review.pull_request_status,
    'scores': review.score_summary && review.score_summary.total_scores > 0
      ? `${review.score_summary.max_score?.toFixed(1) || review.score_summary.average_score?.toFixed(1)} (${review.score_summary.total_scores})${review.score_summary.max_score ? ' [max]' : ''}`
      : 'No scores',
    created_date: review.created_date ? dayjs(review.created_date).format('YYYY-MM-DD HH:mm:ss') : '',
    updated_date: review.updated_date ? dayjs(review.updated_date).format('YYYY-MM-DD HH:mm:ss') : '',
  }))

  exportToCSV(data, finalFilename, columns)
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
