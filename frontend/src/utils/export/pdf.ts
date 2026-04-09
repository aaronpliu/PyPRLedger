import jsPDF from 'jspdf'
import autoTable, { UserOptions } from 'jspdf-autotable'
import type { Review } from '@/api/reviews'
import dayjs from 'dayjs'

export interface ExportOptions {
  title?: string
  filename?: string
  includeHeaders?: boolean
  pageSize?: 'a4' | 'letter'
  orientation?: 'portrait' | 'landscape'
}

export function exportReviewsToPDF(
  reviews: Review[],
  options: ExportOptions = {}
) {
  const {
    title = 'Code Review Report',
    filename = `reviews_${dayjs().format('YYYY-MM-DD_HH-mm-ss')}.pdf`,
    includeHeaders = true,
    pageSize = 'a4',
    orientation = 'landscape',
  } = options

  // Create PDF document
  const doc = new jsPDF({
    orientation,
    unit: 'mm',
    format: pageSize,
  })

  const pageWidth = doc.internal.pageSize.getWidth()
  const pageHeight = doc.internal.pageSize.getHeight()
  let yPos = 20

  // Add header
  doc.setFontSize(20)
  doc.setTextColor(64, 158, 255) // #409eff
  doc.text(title, pageWidth / 2, yPos, { align: 'center' })
  
  yPos += 10
  
  // Add metadata
  doc.setFontSize(10)
  doc.setTextColor(128, 128, 128)
  doc.text(`Generated: ${dayjs().format('YYYY-MM-DD HH:mm:ss')}`, pageWidth / 2, yPos, { align: 'center' })
  doc.text(`Total Reviews: ${reviews.length}`, pageWidth / 2, yPos + 5, { align: 'center' })
  
  yPos += 15

  // Prepare table data
  const headers = includeHeaders ? [['Seq#', 'PR ID', 'Project/Repo', 'PR User', 'Reviewer', 'Status', 'Scores', 'Comments', 'Created', 'Updated']] : []
  
  const data = reviews.map((review, index) => [
    (index + 1).toString(),
    review.pull_request_id,
    `${review.project_key} / ${review.repository_slug}`,
    review.pull_request_user_info?.display_name || review.pull_request_user,
    review.reviewer_info?.display_name || review.reviewer,
    review.pull_request_status,
    review.score_summary && review.score_summary.total_scores > 0
      ? `${review.score_summary.average_score?.toFixed(1)} (${review.score_summary.total_scores})`
      : 'No scores',
    review.reviewer_comments || '-',
    dayjs(review.created_date).format('YYYY-MM-DD HH:mm'),
    dayjs(review.updated_date).format('YYYY-MM-DD HH:mm'),
  ])

  // Add table
  autoTable(doc, {
    startY: yPos,
    head: headers,
    body: data,
    theme: 'grid',
    styles: {
      fontSize: 7,
      cellPadding: 2,
      overflow: 'linebreak',
      cellWidth: 'wrap',
    },
    headStyles: {
      fillColor: [64, 158, 255], // #409eff
      textColor: 255,
      fontStyle: 'bold',
      halign: 'center',
      fontSize: 7,
    },
    alternateRowStyles: {
      fillColor: [245, 247, 250], // #f5f7fa
    },
    columnStyles: {
      0: { cellWidth: 12, halign: 'center' }, // Seq#
      1: { cellWidth: 35 }, // PR ID
      2: { cellWidth: 35 }, // Project/Repo
      3: { cellWidth: 25 }, // PR User
      4: { cellWidth: 25 }, // Reviewer
      5: { cellWidth: 18, halign: 'center' }, // Status
      6: { cellWidth: 20, halign: 'center' }, // Scores
      7: { cellWidth: 'auto' }, // Comments - auto width for full content
      8: { cellWidth: 28 }, // Created
      9: { cellWidth: 28 }, // Updated
    },
    didDrawPage: (data) => {
      // Add footer
      doc.setFontSize(8)
      doc.setTextColor(128, 128, 128)
      doc.text(
        `Page ${data.pageNumber}`,
        pageWidth / 2,
        pageHeight - 10,
        { align: 'center' }
      )
    },
  })

  // Add summary section on last page
  const finalY = (doc as any).lastAutoTable?.finalY || yPos
  if (finalY < pageHeight - 40) {
    doc.setFontSize(12)
    doc.setTextColor(64, 158, 255)
    doc.text('Summary Statistics', 14, finalY + 10)
    
    doc.setFontSize(10)
    doc.setTextColor(64, 64, 64)
    
    const statusCounts = reviews.reduce((acc, review) => {
      const status = review.pull_request_status || 'unknown'
      acc[status] = (acc[status] || 0) + 1
      return acc
    }, {} as Record<string, number>)
    
    let statY = finalY + 18
    Object.entries(statusCounts).forEach(([status, count]) => {
      doc.text(`${status}: ${count} reviews`, 14, statY)
      statY += 6
    })
  }

  // Save PDF
  doc.save(filename)
}

function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text
  return text.substring(0, maxLength - 3) + '...'
}

export function exportScoresToPDF(
  scores: any[],
  options: ExportOptions = {}
) {
  const {
    title = 'Score Analysis Report',
    filename = `scores_${dayjs().format('YYYY-MM-DD_HH-mm-ss')}.pdf`,
  } = options

  const doc = new jsPDF({
    orientation: 'landscape',
    unit: 'mm',
    format: 'a4',
  })

  const pageWidth = doc.internal.pageSize.getWidth()

  // Header
  doc.setFontSize(20)
  doc.setTextColor(103, 194, 58) // #67c23a
  doc.text(title, pageWidth / 2, 20, { align: 'center' })
  
  doc.setFontSize(10)
  doc.setTextColor(128, 128, 128)
  doc.text(`Generated: ${dayjs().format('YYYY-MM-DD HH:mm:ss')}`, pageWidth / 2, 28, { align: 'center' })

  // Table
  const headers = [['ID', 'Review ID', 'Category', 'Score', 'Comment', 'Created']]
  
  const data = scores.map(score => [
    score.id.toString(),
    score.review_id.toString(),
    score.category || 'N/A',
    score.score?.toString() || 'N/A',
    truncateText(score.comment || '-', 40),
    dayjs(score.created_at).format('YYYY-MM-DD'),
  ])

  autoTable(doc, {
    startY: 35,
    head: headers,
    body: data,
    theme: 'grid',
    styles: { fontSize: 8, cellPadding: 3 },
    headStyles: {
      fillColor: [103, 194, 58],
      textColor: 255,
      fontStyle: 'bold',
    },
  })

  doc.save(filename)
}
