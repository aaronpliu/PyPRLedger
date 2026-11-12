import dayjs from 'dayjs'
import type {
  AppVersionDiffCode,
  AppVersionDiffInterval,
  AppVersionDiffResponse,
} from '@/api/appVersionDiff'
import i18n from '@/i18n'
import { tExport as t } from './shared'
import {
  buildReportStyle,
  commitTable,
  escapeHtml,
  metaRow,
  metaTable,
  stat,
} from './releaseReport'

/**
 * Standalone HTML report for the App Diff page.
 *
 * Same contract as the release comparison report: generated entirely on the
 * client from the API response, savable and archivable without the backend,
 * everything escaped, and every known commit URL emitted as a link. The layout
 * mirrors the page - one version matrix, then one section per adjacent release
 * pair with the application's own commits and each moved package's commits.
 */

export interface AppDiffReportContext {
  project_key: string
  repository_slug: string
  app_name?: string | null
  git_provider?: string | null
  workspace_slug?: string | null
}

export interface AppDiffReportInput {
  result: AppVersionDiffResponse
  context: AppDiffReportContext
  generatedAt?: Date
}

export function appDiffReportFilename(context: AppDiffReportContext): string {
  const scope = `${context.project_key || 'project'}-${context.repository_slug || 'repository'}`
  const safeScope = scope.replace(/[^A-Za-z0-9._-]+/g, '_')
  return `app-diff-${safeScope}-${dayjs().format('YYYYMMDD-HHmmss')}.html`
}

export function downloadAppDiffReport(html: string, filename: string): void {
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

function i18nLocale(): string {
  const locale = i18n.global.locale as unknown
  const value = typeof locale === 'string' ? locale : (locale as { value?: string })?.value
  return (value || 'en').replace('_', '-')
}

const VERDICT_CLASS: Record<AppVersionDiffCode['verdict'], string> = {
  contained: 'ok',
  missing: 'missing',
  inconclusive: 'warn',
}

const APP_DIFF_STYLE_OVERRIDES = `
  .matrix td { white-space: nowrap; }
  .matrix td.pkg { font-weight: 600; }
  .matrix tr:first-child td.pkg { background: #f0f7ff; }
  .pkg-heading { margin: 20px 0 6px; font-size: 13px; }
  .code-status { display: flex; align-items: center; gap: 8px; margin: 0 0 10px; }
`

/** Verdict badge plus the added/missing counts, as one compact line. */
function codeStatus(code: AppVersionDiffCode | null): string {
  if (!code) return ''
  if (code.deferred) {
    return `<p class="warning">${escapeHtml(t('appDiff.code_deferred'))}</p>`
  }
  if (code.unavailable) {
    return `<p class="warning">${escapeHtml(
      t('appDiff.code_unavailable', { reason: code.unavailable }),
    )}</p>`
  }
  const badge = `<span class="status status-${VERDICT_CLASS[code.verdict]}">${escapeHtml(
    t(`appDiff.code_verdict_${code.verdict}`),
  )}</span>`
  const added = `<span class="cell-ok">${escapeHtml(
    t('appDiff.code_added', { count: code.added_count }),
  )}</span>`
  const missing = code.missing_count
    ? `<span class="cell-missing">${escapeHtml(
        t('appDiff.code_missing', { count: code.missing_count }),
      )}</span>`
    : ''
  return `<p class="code-status">${badge} ${added}${missing ? ` · ${missing}` : ''}</p>`
}

function versionCell(value: string | null): string {
  return value
    ? escapeHtml(value)
    : `<span class="muted">${escapeHtml(t('appDiff.no_record'))}</span>`
}

/** The whole matrix: every row across every selected release, in one table. */
function matrixSection(result: AppVersionDiffResponse): string {
  const head = result.releases
    .map((release) => {
      const when = release.released_at
        ? `<br><span class="muted">${escapeHtml(
            dayjs(release.released_at).format('YYYY-MM-DD'),
          )}</span>`
        : ''
      return `<th>${escapeHtml(release.ref)}${when}</th>`
    })
    .join('')

  const body = result.rows
    .map((row) => {
      const cells = row.versions
        .map((version) => `<td class="matrix">${versionCell(version)}</td>`)
        .join('')
      const selfClass = row.kind === 'application' ? ' self' : ''
      return `<tr><td class="pkg${selfClass}">${escapeHtml(row.name)}</td>${cells}</tr>`
    })
    .join('')

  return `<section class="report-section">
  <h2>1. ${escapeHtml(t('appDiff.report_version_matrix'))}</h2>
  <table class="data matrix">
    <thead><tr><th>${escapeHtml(t('appDiff.package'))}</th>${head}</tr></thead>
    <tbody>${body}</tbody>
  </table>
</section>`
}

/** The commits of one pair's code axis: application-level added and missing. */
function intervalCodeSection(
  interval: AppVersionDiffInterval,
  context: AppDiffReportContext,
): string {
  if (!interval.code) return ''
  return `<h3>${escapeHtml(t('appDiff.application'))}</h3>
  ${codeStatus(interval.code)}
  ${
    interval.code.missing_commits.length
      ? `<h3 class="section-missing">${escapeHtml(t('appDiff.code_missing_heading'))} (${interval.code.missing_commits.length})</h3>
  ${commitTable(interval.code.missing_commits, interval.code.truncated)}`
      : ''
  }
  ${
    interval.code.added_commits.length
      ? `<h3>${escapeHtml(t('appDiff.code_added_heading'))} (${interval.code.added_commits.length})</h3>
  ${commitTable(interval.code.added_commits, false, context)}`
      : ''
  }`
}

/** One package's own commit delta, only for the packages that moved commits. */
function packageCommitSection(
  pkg: AppVersionDiffInterval['packages'][number],
  context: AppDiffReportContext,
): string {
  if (!pkg.code || pkg.code.deferred || pkg.code.unavailable) return ''
  if (pkg.code.added_count + pkg.code.missing_count === 0) return ''

  const move = `${pkg.source_version ?? '—'} → ${pkg.target_version ?? '—'}`
  return `<h4 class="pkg-heading">${escapeHtml(pkg.name)} <span class="muted">${escapeHtml(
    move,
  )}</span></h4>
  ${codeStatus(pkg.code)}
  ${
    pkg.code.missing_commits.length
      ? `<h3 class="section-missing">${escapeHtml(t('appDiff.code_missing_heading'))} (${pkg.code.missing_commits.length})</h3>
  ${commitTable(pkg.code.missing_commits, pkg.code.truncated, context)}`
      : ''
  }
  ${
    pkg.code.added_commits.length
      ? `<h3>${escapeHtml(t('appDiff.code_added_heading'))} (${pkg.code.added_commits.length})</h3>
  ${commitTable(pkg.code.added_commits, false, context)}`
      : ''
  }`
}

function packageOverviewTable(interval: AppVersionDiffInterval): string {
  const rows = interval.packages
  if (rows.length === 0) {
    return `<p class="muted">${escapeHtml(t('appDiff.no_changes'))}</p>`
  }

  const body = rows
    .map((pkg) => {
      const state = escapeHtml(t(`appDiff.state_${pkg.state}`))
      const move =
        pkg.state === 'added'
          ? `— → ${escapeHtml(pkg.target_version ?? '—')}`
          : pkg.state === 'removed'
            ? `${escapeHtml(pkg.source_version ?? '—')} → —`
            : `${escapeHtml(pkg.source_version ?? '—')} → ${escapeHtml(pkg.target_version ?? '—')}`
      const code = pkg.code
      const commits = !code
        ? ''
        : code.deferred
          ? escapeHtml(t('appDiff.code_deferred'))
          : code.unavailable
            ? escapeHtml(t('appDiff.code_unavailable', { reason: code.unavailable }))
            : `${escapeHtml(t(`appDiff.code_verdict_${code.verdict}`))} · ${code.added_count}↑ / ${code.missing_count}✗`
      return `<tr>
        <td class="pkg">${escapeHtml(pkg.name)}</td>
        <td>${state}</td>
        <td class="mono">${move}</td>
        <td>${commits}</td>
      </tr>`
    })
    .join('')

  return `<table class="data">
    <thead><tr>
      <th>${escapeHtml(t('appDiff.package'))}</th>
      <th>${escapeHtml(t('appDiff.report_col_state'))}</th>
      <th>${escapeHtml(t('appDiff.report_col_versions'))}</th>
      <th>${escapeHtml(t('appDiff.report_col_commits'))}</th>
    </tr></thead>
    <tbody>${body}</tbody>
  </table>`
}

function intervalSection(
  interval: AppVersionDiffInterval,
  index: number,
  context: AppDiffReportContext,
): string {
  const summary = interval.summary ?? {}
  const heading = `${index + 2}. ${interval.source_ref} → ${interval.target_ref}`
  const completeness = interval.complete
    ? ''
    : ` · ${escapeHtml(t('appDiff.interval_incomplete'))}`

  return `<section class="report-section">
  <h2>${escapeHtml(heading)}</h2>
  <p class="status status-${interval.dependencies_moved ? 'info' : 'ok'}">${escapeHtml(
    interval.dependencies_moved ? t('appDiff.verdict_changed') : t('appDiff.verdict_identical'),
  )}${completeness}</p>
  <div class="stats">
    ${stat(t('appDiff.state_changed'), summary.changed ?? 0)}
    ${stat(t('appDiff.state_added'), summary.added ?? 0, 'ok')}
    ${stat(t('appDiff.state_removed'), summary.removed ?? 0, 'warn')}
    ${stat(t('appDiff.risk'), summary.downgrade ?? 0, summary.downgrade ? 'missing' : undefined)}
  </div>

  ${packageOverviewTable(interval)}

  <h3>${escapeHtml(t('appDiff.report_commit_detail'))}</h3>
  ${intervalCodeSection(interval, context)}
  ${interval.packages.map((pkg) => packageCommitSection(pkg, context)).join('\n')}
</section>`
}

export function buildAppDiffReportHtml(input: AppDiffReportInput): string {
  const { result, context } = input
  const generatedAt = dayjs(input.generatedAt ?? new Date()).format('YYYY-MM-DD HH:mm:ss')

  const releases = result.releases
    .map((release) => {
      const when = release.released_at
        ? ` (${dayjs(release.released_at).format('YYYY-MM-DD HH:mm')})`
        : ''
      return `${release.ref}${when}`
    })
    .join(', ')

  const sections = [
    matrixSection(result),
    ...result.intervals.map((interval, index) => intervalSection(interval, index, context)),
  ].join('\n')

  const meta = metaTable([
    metaRow(t('appDiff.application'), context.app_name || result.app_name),
    metaRow(t('releaseDiff.project_key'), context.project_key),
    metaRow(t('releaseDiff.repository_slug'), context.repository_slug),
    metaRow(t('releaseDiff.git_provider'), context.git_provider || result.git_provider),
    metaRow(t('appDiff.releases_label'), releases),
    metaRow(t('releaseDiff.report_generated_at'), generatedAt),
  ])

  return `<!DOCTYPE html>
<html lang="${escapeHtml(i18nLocale())}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${escapeHtml(t('appDiff.title'))} - ${escapeHtml(result.app_name || context.repository_slug)}</title>
<style>${buildReportStyle()}${APP_DIFF_STYLE_OVERRIDES}</style>
</head>
<body>
<div class="report">
  <h1>${escapeHtml(t('appDiff.title'))}</h1>
  <p class="subtitle">${escapeHtml(
    t('appDiff.subtitle', { app: result.app_name, count: result.releases.length }),
  )}</p>
  ${meta}
  ${sections}
  <footer>PR Ledger</footer>
</div>
</body>
</html>`
}
