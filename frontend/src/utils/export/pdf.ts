import jsPDF from 'jspdf'
import 'jspdf-autotable'
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
  const headers = includeHeaders ? [['ID', 'PR URL', 'Reviewer', 'Status', 'Summary', 'Created']] : []
  
  const data = reviews.map(review => [
    review.id.toString(),
    truncateText(review.pr_url, 50),
    review.reviewer_username,
    review.status,
    truncateText(review.summary || '-', 40),
    dayjs(review.created_at).format('YYYY-MM-DD HH:mm'),
  ])

  // Add table
  ;(doc as any).autoTable({
    startY: yPos,
    head: headers,
    body: data,
    theme: 'grid',
    styles: {
      fontSize: 8,
      cellPadding: 3,
      overflow: 'linebreak',
    },
    headStyles: {
      fillColor: [64, 158, 255], // #409eff
      textColor: 255,
      fontStyle: 'bold',
      halign: 'center',
    },
    alternateRowStyles: {
      fillColor: [245, 247, 250], // #f5f7fa
    },
    columnStyles: {
      0: { cellWidth: 15, halign: 'center' }, // ID
      1: { cellWidth: 60 }, // PR URL
      2: { cellWidth: 30 }, // Reviewer
      3: { cellWidth: 25, halign: 'center' }, // Status
      4: { cellWidth: 50 }, // Summary
      5: { cellWidth: 35 }, // Created
    },
    didDrawPage: (data: any) => {
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
  const finalY = (doc as any).lastAutoTable.finalY || yPos
  if (finalY < pageHeight - 40) {
    doc.setFontSize(12)
    doc.setTextColor(64, 158, 255)
    doc.text('Summary Statistics', 14, finalY + 10)
    
    doc.setFontSize(10)
    doc.setTextColor(64, 64, 64)
    
    const statusCounts = reviews.reduce((acc, review) => {
      acc[review.status] = (acc[review.status] || 0) + 1
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

  ;(doc as any).autoTable({
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
