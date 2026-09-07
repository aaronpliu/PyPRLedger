import jsPDF from 'jspdf'
import autoTable, { UserOptions } from 'jspdf-autotable'
import type { Review } from '@/api/reviews'
import dayjs from 'dayjs'
import { buildReviewExportRow, REVIEW_EXPORT_COLUMNS, tExport } from './shared'

// ---------------------------------------------------------------------------
// CJK font support
//
// jsPDF only ships Latin (Standard 14) fonts, so Chinese text renders as
// missing-glyph boxes ("□□□"). To fix that we embed a TrueType CJK font that
// is served from the app's /fonts directory. The font file is fetched lazily
// on the first PDF export and its base64 payload is cached for later exports.
// The font (Droid Sans Fallback) is Apache-2.0 licensed, see
// frontend/public/fonts/README.md for the source and license details.
// ---------------------------------------------------------------------------

const CJK_FONT_SOURCE = `${import.meta.env.BASE_URL}fonts/DroidSansFallbackFull.ttf`
const CJK_FONT_VFS_NAME = 'DroidSansFallbackFull.ttf'
const CJK_FONT_FAMILY = 'DroidSansFallback'

let fontBase64Promise: Promise<string> | null = null

function arrayBufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer)
  let binary = ''
  // Convert in chunks to avoid call-stack overflow on large fonts.
  const chunkSize = 0x8000
  for (let i = 0; i < bytes.length; i += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunkSize))
  }
  return btoa(binary)
}

async function getCJKFontBase64(): Promise<string> {
  const response = await fetch(CJK_FONT_SOURCE)
  if (!response.ok) {
    throw new Error(`Failed to load CJK font (HTTP ${response.status})`)
  }
  return arrayBufferToBase64(await response.arrayBuffer())
}

/**
 * Register the CJK font on a document so its text calls can render Chinese.
 * Returns false when the font cannot be loaded (export still works, but CJK
 * glyphs will fall back to missing-glyph boxes).
 */
async function registerCJKFont(doc: jsPDF): Promise<boolean> {
  try {
    fontBase64Promise ??= getCJKFontBase64()
    const fontBase64 = await fontBase64Promise
    doc.addFileToVFS(CJK_FONT_VFS_NAME, fontBase64)
    doc.addFont(CJK_FONT_VFS_NAME, CJK_FONT_FAMILY, 'normal')
    return true
  } catch (error) {
    console.warn('[export] CJK font unavailable; Chinese text may not render in the PDF', error)
    return false
  }
}

function useCJKFont(doc: jsPDF, enabled: boolean) {
  if (enabled) {
    doc.setFont(CJK_FONT_FAMILY, 'normal')
  }
}

export interface ExportOptions {
  title?: string
  filename?: string
  includeHeaders?: boolean
  pageSize?: 'a4' | 'letter'
  orientation?: 'portrait' | 'landscape'
}

export async function exportReviewsToPDF(
  reviews: Review[],
  options: ExportOptions = {}
) {
  const {
    title = tExport('export.report_title'),
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

  // jsPDF has no built-in CJK glyphs; embed the bundled Chinese font so
  // localized headers, reviewers and comments render correctly.
  const hasCJKFont = await registerCJKFont(doc)

  const pageWidth = doc.internal.pageSize.getWidth()
  const pageHeight = doc.internal.pageSize.getHeight()
  let yPos = 20

  // Add header
  useCJKFont(doc, hasCJKFont)
  doc.setFontSize(20)
  doc.setTextColor(64, 158, 255) // #409eff
  doc.text(title, pageWidth / 2, yPos, { align: 'center' })
  
  yPos += 10
  
  // Add metadata
  doc.setFontSize(10)
  doc.setTextColor(128, 128, 128)
  doc.text(`${tExport('export.generated')}: ${dayjs().format('YYYY-MM-DD HH:mm:ss')}`, pageWidth / 2, yPos, { align: 'center' })
  doc.text(`${tExport('export.total_reviews')}: ${reviews.length}`, pageWidth / 2, yPos + 5, { align: 'center' })
  
  yPos += 15

  // Prepare table data
  const headers = includeHeaders
    ? [REVIEW_EXPORT_COLUMNS.map((col) => tExport(col.labelKey))]
    : []

  const data = reviews.map((review, index) => {
    const row = buildReviewExportRow(review, index)
    return REVIEW_EXPORT_COLUMNS.map((col) => {
      const value = row[col.key]
      return value || (col.key === 'comments' ? '-' : '')
    })
  })

  // Add table
  autoTable(doc, {
    startY: yPos,
    head: headers,
    body: data,
    theme: 'grid',
    styles: {
      // Only use the CJK family when the font was successfully embedded;
      // otherwise let autoTable fall back to the built-in Latin font.
      ...(hasCJKFont ? { font: CJK_FONT_FAMILY } : {}),
      fontStyle: 'normal',
      fontSize: 7,
      cellPadding: 2,
      overflow: 'linebreak',
      cellWidth: 'wrap',
    },
    headStyles: {
      fillColor: [64, 158, 255], // #409eff
      textColor: 255,
      fontStyle: 'normal',
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
      useCJKFont(doc, hasCJKFont)
      doc.setFontSize(8)
      doc.setTextColor(128, 128, 128)
      doc.text(
        tExport('export.page_footer', { page: data.pageNumber }),
        pageWidth / 2,
        pageHeight - 10,
        { align: 'center' }
      )
    },
  })

  // Add summary section on last page
  const finalY = (doc as any).lastAutoTable?.finalY || yPos
  if (finalY < pageHeight - 40) {
    useCJKFont(doc, hasCJKFont)
    doc.setFontSize(12)
    doc.setTextColor(64, 158, 255)
    doc.text(tExport('export.summary_statistics'), 14, finalY + 10)
    
    doc.setFontSize(10)
    doc.setTextColor(64, 64, 64)
    
    const statusCounts = reviews.reduce((acc, review) => {
      const status = review.pull_request_status || 'unknown'
      acc[status] = (acc[status] || 0) + 1
      return acc
    }, {} as Record<string, number>)
    
    let statY = finalY + 18
    Object.entries(statusCounts).forEach(([status, count]) => {
      doc.text(tExport('export.status_count', { status, count }), 14, statY)
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

export async function exportScoresToPDF(
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

  // Embed the CJK font so Chinese comments / categories render correctly.
  const hasCJKFont = await registerCJKFont(doc)

  const pageWidth = doc.internal.pageSize.getWidth()

  // Header
  useCJKFont(doc, hasCJKFont)
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
    styles: {
      ...(hasCJKFont ? { font: CJK_FONT_FAMILY } : {}),
      fontStyle: 'normal',
      fontSize: 8,
      cellPadding: 3,
    },
    headStyles: {
      fillColor: [103, 194, 58],
      textColor: 255,
      fontStyle: 'normal',
    },
  })

  doc.save(filename)
}
