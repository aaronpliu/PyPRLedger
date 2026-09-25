import dayjs from 'dayjs'
import type {
  CommitInfo,
  ReleaseCommitCheckResponse,
  ReleaseCompareResponse,
} from '@/api/releaseDiff'
import i18n from '@/i18n'
import { tExport as t } from './shared'

/**
 * Standalone HTML report for the Releases page.
 *
 * The report is generated entirely on the client from the API responses, so it
 * can be saved, mailed or archived without the backend. Everything coming from
 * the git provider is escaped before it reaches the markup, and every known URL
 * (project, repository, release ref, commit) is emitted as a link.
 */

export interface ReleaseReportContext {
  project_key: string
  repository_slug: string
  git_provider?: string | null
  workspace_slug?: string | null
  project_url?: string | null
  repository_url?: string | null
}

export interface ReleaseReportInput {
  context: ReleaseReportContext
  compare?: ReleaseCompareResponse | null
  check?: ReleaseCommitCheckResponse | null
  generatedAt?: Date
}

export type ReleaseReportKind = 'compare' | 'check' | 'both'

const STATUS_CLASS: Record<string, string> = {
  included: 'ok',
  missing_commits: 'warn',
  identical: 'info',
}

export function escapeHtml(value: unknown): string {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

export function releaseReportFilename(
  kind: ReleaseReportKind,
  context: ReleaseReportContext,
): string {
  const scope = `${context.project_key || 'project'}-${context.repository_slug || 'repository'}`
  const safeScope = scope.replace(/[^A-Za-z0-9._-]+/g, '_')
  return `release-${kind}-${safeScope}-${dayjs().format('YYYYMMDD-HHmmss')}.html`
}

function formatTimestamp(value?: number | null): string {
  if (!value) return '-'
  return dayjs(value).format('YYYY-MM-DD HH:mm')
}

function firstLine(message?: string | null): string {
  if (!message) return '-'
  return message.split('\n')[0]
}

function link(url: string, label?: string): string {
  return `<a href="${escapeHtml(url)}" target="_blank" rel="noopener">${escapeHtml(label || url)}</a>`
}

/** Drop the ``.git`` suffix and any ``user:password@`` userinfo from a clone URL. */
export function normalizeUrl(url: string): string {
  const trimmed = url.trim().replace(/\.git$/, '')
  try {
    const parsed = new URL(trimmed)
    if (parsed.username || parsed.password) {
      parsed.username = ''
      parsed.password = ''
      return parsed.toString().replace(/\/$/, '')
    }
    return trimmed
  } catch {
    return trimmed
  }
}

/**
 * Repository web URL used to build browse / commit links.
 *
 * The stored repository URL is authoritative. When it is missing (manually typed
 * coordinates) a Bitbucket Cloud URL can be derived from the workspace, which is
 * the only provider whose web URL scheme is unambiguous.
 */
export function repositoryBaseUrl(context: ReleaseReportContext): string | undefined {
  if (context.repository_url) {
    return normalizeUrl(context.repository_url)
  }
  if (context.project_url) {
    return normalizeUrl(context.project_url)
  }
  if (context.git_provider === 'bitbucket_cloud' && context.repository_slug) {
    const workspace = (context.workspace_slug || context.project_key || '').trim()
    if (workspace) {
      return `https://bitbucket.org/${workspace}/${context.repository_slug}`
    }
  }
  return undefined
}

/** Browse URL of a release ref (only the Bitbucket Cloud scheme is well defined). */
export function releaseRefUrl(context: ReleaseReportContext, ref?: string | null): string | undefined {
  const base = repositoryBaseUrl(context)
  const trimmed = (ref ?? '').trim()
  if (!base || !trimmed || context.git_provider !== 'bitbucket_cloud') {
    return undefined
  }
  return `${base}/commits/${encodeURIComponent(trimmed)}`
}

function stat(label: string, value: number | string, tone?: string): string {
  const toneClass = tone ? ` stat-${tone}` : ''
  return `<div class="stat${toneClass}"><span class="stat-value">${escapeHtml(
    value,
  )}</span><span class="stat-label">${escapeHtml(label)}</span></div>`
}

/** One ``<tr>`` of a meta table: label / value / optional link. */
function metaRow(label: string, value?: string | null, url?: string | null): string {
  if (!value) return ''
  const cell = url ? link(url, value) : escapeHtml(value)
  return `<tr><th>${escapeHtml(label)}</th><td>${cell}</td></tr>`
}

function metaTable(rows: string[]): string {
  const body = rows.filter(Boolean).join('\n      ')
  if (!body) return ''
  return `<table class="meta">\n      ${body}\n    </table>`
}

function commitUrlCell(url?: string | null): string {
  if (!url) return '-'
  return link(url)
}

function commitTable(commits: CommitInfo[] | undefined): string {
  const rows = commits ?? []
  if (rows.length === 0) {
    return `<p class="muted">${escapeHtml(t('releaseDiff.report_no_commits'))}</p>`
  }

  const body = rows
    .map((commit) => {
      const sha = escapeHtml(commit.display_id || commit.id)
      const shaCell = commit.url
        ? `<a href="${escapeHtml(commit.url)}" target="_blank" rel="noopener">${sha}</a>`
        : sha
      const message = escapeHtml(firstLine(commit.message))
      const fullMessage = escapeHtml(commit.message ?? '')
      return `<tr>
        <td class="mono">${shaCell}</td>
        <td>${escapeHtml(commit.author_name || '-')}</td>
        <td class="nowrap">${escapeHtml(formatTimestamp(commit.author_timestamp))}</td>
        <td title="${fullMessage}">${message}</td>
        <td class="url">${commitUrlCell(commit.url)}</td>
      </tr>`
    })
    .join('')

  return `<table class="data">
    <thead><tr>
      <th>${escapeHtml(t('releaseDiff.col_commit'))}</th>
      <th>${escapeHtml(t('releaseDiff.col_author'))}</th>
      <th>${escapeHtml(t('releaseDiff.col_date'))}</th>
      <th>${escapeHtml(t('releaseDiff.col_message'))}</th>
      <th>${escapeHtml(t('releaseDiff.col_url'))}</th>
    </tr></thead>
    <tbody>${body}</tbody>
  </table>`
}

function scopeText(baseRef: string | null | undefined, releaseRef: string): string {
  const base = (baseRef ?? '').trim()
  const release = (releaseRef ?? '').trim() || '?'
  return base ? `${base}..${release}` : t('releaseDiff.scope_full_history', { ref: release })
}

function compareStatusText(result: ReleaseCompareResponse): string {
  if (result.status === 'identical') return t('releaseDiff.status_identical')
  return result.old_commits_included
    ? t('releaseDiff.status_included')
    : t('releaseDiff.status_missing')
}

export function buildCompareSectionHtml(
  result: ReleaseCompareResponse,
  context: ReleaseReportContext,
): string {
  const summary = result.summary ?? {}
  const statusClass = STATUS_CLASS[result.status] ?? 'info'

  const meta = metaTable([
    metaRow(
      t('releaseDiff.old_release_ref'),
      result.old_release_ref,
      releaseRefUrl(context, result.old_release_ref),
    ),
    metaRow(
      t('releaseDiff.old_release_base_ref'),
      result.old_release_base_ref || t('releaseDiff.scope_full_history', { ref: result.old_release_ref }),
    ),
    metaRow(
      t('releaseDiff.new_release_ref'),
      result.new_release_ref,
      releaseRefUrl(context, result.new_release_ref),
    ),
    metaRow(
      t('releaseDiff.new_release_base_ref'),
      result.new_release_base_ref || t('releaseDiff.scope_full_history', { ref: result.new_release_ref }),
    ),
    metaRow(
      t('releaseDiff.report_scope'),
      `${scopeText(result.old_release_base_ref, result.old_release_ref)} → ${scopeText(
        result.new_release_base_ref,
        result.new_release_ref,
      )}`,
    ),
  ])

  return `<section class="report-section">
  <h2>1. ${escapeHtml(t('releaseDiff.tab_compare'))}</h2>
  <p class="status status-${statusClass}">${escapeHtml(compareStatusText(result))}</p>
  ${
    result.truncated
      ? `<p class="warning">${escapeHtml(t('releaseDiff.truncated_warning'))}</p>`
      : ''
  }
  ${meta}

  <div class="stats">
    ${stat(t('releaseDiff.old_commit_count'), summary.old_commit_count ?? 0)}
    ${stat(t('releaseDiff.new_commit_count'), summary.new_commit_count ?? 0)}
    ${stat(t('releaseDiff.missing_count'), summary.missing_count ?? 0, 'warn')}
    ${stat(t('releaseDiff.added_count'), summary.added_count ?? 0, 'ok')}
    ${stat(t('releaseDiff.common_count'), summary.common_count ?? 0)}
  </div>

  <h3>${escapeHtml(t('releaseDiff.missing_commits_title'))} (${result.missing_commits?.length ?? 0})</h3>
  ${commitTable(result.missing_commits)}

  <h3>${escapeHtml(t('releaseDiff.added_commits_title'))} (${result.added_commits?.length ?? 0})</h3>
  ${commitTable(result.added_commits)}

  <h3>${escapeHtml(t('releaseDiff.old_release_commits_title'))} (${result.old_release_commits?.length ?? 0})</h3>
  ${commitTable(result.old_release_commits)}

  <h3>${escapeHtml(t('releaseDiff.new_release_commits_title'))} (${result.new_release_commits?.length ?? 0})</h3>
  ${commitTable(result.new_release_commits)}
</section>`
}

export function buildCheckSectionHtml(
  result: ReleaseCommitCheckResponse,
  context: ReleaseReportContext,
): string {
  const summary = result.summary ?? {}
  const rows = result.results ?? []

  const body = rows
    .map((row) => {
      const sha = escapeHtml(row.matched_id || row.commit)
      const commitUrl = row.commit_info?.url
      const shaCell = commitUrl
        ? `<a href="${escapeHtml(commitUrl)}" target="_blank" rel="noopener">${sha}</a>`
        : sha
      return `<tr>
        <td class="mono">${shaCell}</td>
        <td class="${row.included ? 'cell-ok' : 'cell-warn'}">${escapeHtml(
          row.included ? t('releaseDiff.result_included') : t('releaseDiff.result_missing'),
        )}</td>
        <td>${escapeHtml(row.commit_info?.author_name || '-')}</td>
        <td class="nowrap">${escapeHtml(formatTimestamp(row.commit_info?.author_timestamp))}</td>
        <td title="${escapeHtml(row.commit_info?.message ?? '')}">${escapeHtml(
          firstLine(row.commit_info?.message),
        )}</td>
        <td class="url">${commitUrlCell(commitUrl)}</td>
      </tr>`
    })
    .join('')

  const resultsTable =
    rows.length === 0
      ? `<p class="muted">${escapeHtml(t('releaseDiff.report_no_commits'))}</p>`
      : `<table class="data">
    <thead><tr>
      <th>${escapeHtml(t('releaseDiff.col_commit'))}</th>
      <th>${escapeHtml(t('releaseDiff.col_status'))}</th>
      <th>${escapeHtml(t('releaseDiff.col_author'))}</th>
      <th>${escapeHtml(t('releaseDiff.col_date'))}</th>
      <th>${escapeHtml(t('releaseDiff.col_message'))}</th>
      <th>${escapeHtml(t('releaseDiff.col_url'))}</th>
    </tr></thead>
    <tbody>${body}</tbody>
  </table>`

  const meta = metaTable([
    metaRow(
      t('releaseDiff.target_release_ref'),
      result.target_release_ref,
      releaseRefUrl(context, result.target_release_ref),
    ),
    metaRow(
      t('releaseDiff.target_release_base_ref'),
      result.target_release_base_ref ||
        t('releaseDiff.scope_full_history', { ref: result.target_release_ref }),
    ),
    metaRow(
      t('releaseDiff.report_scope'),
      scopeText(result.target_release_base_ref, result.target_release_ref),
    ),
  ])

  return `<section class="report-section">
  <h2>2. ${escapeHtml(t('releaseDiff.tab_check'))}</h2>
  <p class="status status-${result.all_included ? 'ok' : 'warn'}">${escapeHtml(
    result.all_included ? t('releaseDiff.status_included') : t('releaseDiff.status_missing'),
  )}</p>
  ${
    result.truncated
      ? `<p class="warning">${escapeHtml(t('releaseDiff.truncated_warning'))}</p>`
      : ''
  }
  ${meta}

  <div class="stats">
    ${stat(t('releaseDiff.requested'), summary.requested ?? 0)}
    ${stat(t('releaseDiff.included_count'), summary.included_count ?? 0, 'ok')}
    ${stat(t('releaseDiff.missing_count'), summary.missing_count ?? 0, 'warn')}
    ${stat(t('releaseDiff.release_commit_count'), summary.release_commit_count ?? 0)}
  </div>

  ${resultsTable}
</section>`
}

const REPORT_STYLE = `
  :root { color-scheme: light; }
  * { box-sizing: border-box; }
  body { margin: 0; padding: 32px; background: #f5f7fa; color: #1f2937;
         font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; }
  .report { max-width: 1100px; margin: 0 auto; background: #fff; border-radius: 12px; padding: 32px;
            box-shadow: 0 1px 3px rgba(15, 23, 42, 0.12); }
  h1 { margin: 0 0 4px; font-size: 24px; }
  h2 { margin: 32px 0 12px; font-size: 18px; border-bottom: 2px solid #e5e7eb; padding-bottom: 8px; }
  h3 { margin: 24px 0 8px; font-size: 14px; color: #374151; }
  .subtitle { margin: 0 0 20px; color: #6b7280; font-size: 13px; }
  table { border-collapse: collapse; width: 100%; }
  table.meta { margin: 0 0 16px; font-size: 13px; border: 1px solid #e5e7eb; border-radius: 6px; overflow: hidden; }
  table.meta th { width: 200px; text-align: left; vertical-align: top; background: #f3f4f6;
                  color: #374151; font-weight: 600; padding: 8px 12px; border: 1px solid #e5e7eb; white-space: nowrap; }
  table.meta td { padding: 8px 12px; border: 1px solid #e5e7eb; word-break: break-word; }
  table.meta tr:nth-child(even) td { background: #fafafa; }
  table.meta tr:nth-child(even) th { background: #eef0f3; }
  table.data { font-size: 13px; margin-bottom: 8px; border: 1px solid #e5e7eb; }
  table.data th { background: #f3f4f6; text-align: left; font-weight: 600; padding: 8px 10px;
                  border-bottom: 1px solid #e5e7eb; white-space: nowrap; }
  table.data td { padding: 8px 10px; border-bottom: 1px solid #f1f5f9; vertical-align: top; }
  table.data tr:nth-child(even) td { background: #fafafa; }
  a { color: #2563eb; text-decoration: none; }
  a:hover { text-decoration: underline; }
  .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
  .nowrap { white-space: nowrap; }
  .url { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
         font-size: 12px; color: #475569; word-break: break-all; }
  .muted { color: #9ca3af; font-size: 13px; }
  .status { display: inline-block; margin: 0 0 12px; padding: 6px 14px; border-radius: 999px; font-size: 13px; font-weight: 600; }
  .status-ok { background: #dcfce7; color: #166534; }
  .status-warn { background: #fef3c7; color: #92400e; }
  .status-info { background: #e0e7ff; color: #3730a3; }
  .warning { margin: 0 0 12px; color: #92400e; font-size: 13px; }
  .stats { display: flex; flex-wrap: wrap; gap: 10px; margin: 12px 0 4px; }
  .stat { flex: 1 1 120px; border: 1px solid #e5e7eb; border-radius: 8px; padding: 10px; text-align: center; background: #fafafa; }
  .stat-value { display: block; font-size: 20px; font-weight: 700; }
  .stat-label { display: block; font-size: 11px; color: #6b7280; }
  .stat-ok { border-color: #bbf7d0; background: #f0fdf4; }
  .stat-warn { border-color: #fde68a; background: #fffbeb; }
  .cell-ok { color: #15803d; font-weight: 600; }
  .cell-warn { color: #b45309; font-weight: 600; }
  footer { margin-top: 32px; color: #9ca3af; font-size: 12px; text-align: center; }
  @media print { body { background: #fff; padding: 0; } .report { box-shadow: none; border-radius: 0; } }
`

export function buildReleaseReportHtml(input: ReleaseReportInput): string {
  const { context, compare, check } = input
  const generatedAt = dayjs(input.generatedAt ?? new Date()).format('YYYY-MM-DD HH:mm:ss')
  const repositoryUrl = repositoryBaseUrl(context)

  const sections = [
    compare ? buildCompareSectionHtml(compare, context) : '',
    check ? buildCheckSectionHtml(check, context) : '',
  ]
    .filter(Boolean)
    .join('\n')

  const meta = metaTable([
    metaRow(t('releaseDiff.project_key'), context.project_key, context.project_url),
    metaRow(t('releaseDiff.workspace_slug'), context.workspace_slug),
    metaRow(t('releaseDiff.repository_slug'), context.repository_slug, repositoryUrl),
    metaRow(t('releaseDiff.git_provider'), context.git_provider),
    metaRow(t('releaseDiff.report_project_url'), context.project_url, context.project_url),
    metaRow(t('releaseDiff.report_repository_url'), repositoryUrl, repositoryUrl),
    metaRow(t('releaseDiff.report_generated_at'), generatedAt),
  ])

  return `<!DOCTYPE html>
<html lang="${escapeHtml(i18nLocale())}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${escapeHtml(t('releaseDiff.title'))} - ${escapeHtml(context.project_key)}/${escapeHtml(context.repository_slug)}</title>
<style>${REPORT_STYLE}</style>
</head>
<body>
<div class="report">
  <h1>${escapeHtml(t('releaseDiff.title'))}</h1>
  <p class="subtitle">${escapeHtml(t('releaseDiff.subtitle'))}</p>
  ${meta}
  ${sections}
  <footer>PR Ledger</footer>
</div>
</body>
</html>`
}

function i18nLocale(): string {
  const locale = i18n.global.locale as unknown
  const value = typeof locale === 'string' ? locale : (locale as { value?: string })?.value
  return (value || 'en').replace('_', '-')
}

/** Trigger a browser download for a generated report. */
export function downloadReleaseReport(html: string, filename: string): void {
  const blob = new Blob([html], { type: 'text/html;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.style.display = 'none'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}
