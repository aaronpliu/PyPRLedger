import dayjs from 'dayjs'
import i18n from '@/i18n'
import type {
  AggregatePackageEntry,
  AggregateReleaseNoteResponse,
} from '@/api/aggregateReleaseNote'
import type { JiraSettings } from '@/utils/jira'
import { tExport as t } from './shared'
import {
  buildReportStyle,
  commitTable,
  escapeHtml,
  metaRow,
  metaTable,
  stat,
} from './releaseReport'
import type { ReleaseReportContext } from './releaseReport'

/**
 * Standalone HTML report for the aggregate release note page.
 *
 * Same contract as the app diff report: generated entirely on the client from
 * the API response, savable and archivable without the backend, everything
 * escaped, and every known commit URL emitted as a link. The layout mirrors
 * the page - the application's own section first, then one section per moved
 * package, then what stayed unchanged.
 */

export interface AggregateNoteReportContext {
  project_key: string
  repository_slug: string
  git_provider?: string | null
  workspace_slug?: string | null
  /** JIRA link settings: ticket keys in commit subjects link to the instance. */
  jira?: JiraSettings | null
}

export interface AggregateNoteReportInput {
  result: AggregateReleaseNoteResponse
  context: AggregateNoteReportContext

  generatedAt?: Date
}

/**
 * The combined note as one markdown body, from the rendered sections the
 * backend answers with: the application's own release note first (summary,
 * categorized sections, ticket links, authors), then one section per package
 * the span moved, then the lines that keep the rest legible - a package that
 * could not be compared says why, and the unchanged ones are named.
 *
 * This is what a combined release saves with: the body reads like a release
 * note, not like a commit listing.
 */
export function buildCombinedNoteBody(
  result: AggregateReleaseNoteResponse,
  translate: (key: string) => string = t,
): string {
  const parts: string[] = []

  if (result.application_body) {
    parts.push(result.application_body.trim())
  }

  for (const entry of result.packages) {
    const heading = `## ${entry.name} (${versionSpan(entry)})`
    if (entry.body) {
      parts.push(`${heading}\n\n${entry.body.trim()}`)
    } else {
      // skipped or failed: the section says what happened instead of hiding
      const change = translate(CHANGE_KEY[entry.change])
      const status = translate(`aggregateNote.status_${entry.status}`)
      const reason = entry.reason ? ` - ${entry.reason}` : ''
      parts.push(`${heading}\n\n_${change}, ${status}${reason}_`)
    }
  }

  if (result.unchanged_packages.length) {
    parts.push(
      `_${translate('aggregateNote.unchanged_label')}: ${result.unchanged_packages.join(', ')}_`,
    )
  }

  return parts.join('\n\n')
}

function i18nLocale(): string {
  const locale = i18n.global.locale as unknown
  const value = typeof locale === 'string' ? locale : (locale as { value?: string })?.value
  return (value || 'en').replace('_', '-')
}

const CHANGE_KEY: Record<AggregatePackageEntry['change'], string> = {
  upgraded: 'aggregateNote.change_upgraded',
  added: 'aggregateNote.change_added',
  removed: 'aggregateNote.change_removed',
}

const STATUS_TONE: Record<AggregatePackageEntry['status'], string> = {
  compared: 'ok',
  skipped: 'info',
  failed: 'missing',
}

function versionSpan(entry: AggregatePackageEntry): string {
  const from = entry.from_version || '—'
  const to = entry.to_version || '—'
  return `${from} → ${to}`
}

function packageSection(entry: AggregatePackageEntry, context: AggregateNoteReportContext): string {
  const tone = STATUS_TONE[entry.status]
  const status = t(`aggregateNote.status_${entry.status}`)
  const reason = entry.reason
    ? `<p class="muted">${escapeHtml(t('aggregateNote.report_reason'))}: ${escapeHtml(entry.reason)}</p>`
    : ''

  const verdictLine =
    entry.comparison && entry.status === 'compared'
      ? `<p class="status status-${
          entry.comparison.verdict === 'contained' ? 'ok' : 'missing'
        }">${escapeHtml(t(`appDiff.code_verdict_${entry.comparison.verdict}`))}</p>`
      : ''

  const commits =
    entry.comparison && entry.status === 'compared'
      ? `<h3>${escapeHtml(t('aggregateNote.report_commits'))}</h3>
  ${commitTable(entry.comparison.added_commits, entry.comparison.rendered_truncated, {
    project_key: context.project_key,
    repository_slug: context.repository_slug,
    jira: context.jira,
  })}`
      : ''

  const repo =
    entry.repository && entry.status === 'compared'
      ? `<p class="muted">${escapeHtml(t('aggregateNote.report_from_repository'))}: ${escapeHtml(
          `${entry.repository.project_key}/${entry.repository.repository_slug}`,
        )}</p>`
      : ''

  return `<section class="report-section">
  <h2>${escapeHtml(entry.name)} <span class="muted">${escapeHtml(versionSpan(entry))}</span></h2>
  <p class="status status-${tone}">${escapeHtml(t(CHANGE_KEY[entry.change]))} · ${escapeHtml(status)}</p>
  ${repo}
  ${reason}
  ${verdictLine}
  ${commits}
</section>`
}

export function buildAggregateReleaseNoteHtml(input: AggregateNoteReportInput): string {
  const { result, context } = input
  const generatedAt = dayjs(input.generatedAt ?? new Date()).format('YYYY-MM-DD HH:mm:ss')

  const summary = result.summary
  const appVerdict = result.application.verdict

  const applicationSection = `<section class="report-section">
  <h2>${escapeHtml(t('aggregateNote.report_application'))}</h2>
  <p class="status status-${appVerdict === 'contained' ? 'ok' : 'missing'}">${escapeHtml(
    t(`appDiff.code_verdict_${appVerdict}`),
  )}</p>
  <div class="stats">
    ${stat(t('aggregateNote.stat_app_commits'), result.application.added_count)}
    ${stat(t('aggregateNote.stat_missing'), result.application.missing_count, result.application.missing_count ? 'missing' : undefined)}
    ${stat(t('aggregateNote.stat_packages_changed'), summary.packages_changed)}
    ${stat(t('aggregateNote.stat_package_commits'), summary.package_commits)}
  </div>
  ${commitTable(result.application.added_commits, result.application.rendered_truncated, {
    project_key: context.project_key,
    repository_slug: context.repository_slug,
    jira: context.jira,
  })}
</section>`

  const packagesSections = result.packages
    .map((entry) => packageSection(entry, context))
    .join('\n')

  const unchanged =
    result.unchanged_packages.length > 0
      ? `<section class="report-section">
  <h2>${escapeHtml(t('aggregateNote.report_unchanged'))}</h2>
  <p class="muted">${escapeHtml(result.unchanged_packages.join(', '))}</p>
</section>`
      : ''

  const meta = metaTable([
    metaRow(t('aggregateNote.report_application'), result.app_name),
    metaRow(t('releaseDiff.project_key'), context.project_key),
    metaRow(t('releaseDiff.repository_slug'), context.repository_slug),
    metaRow(t('releaseDiff.git_provider'), context.git_provider || result.git_provider),
    metaRow(t('appDiff.releases_label'), `${result.source_ref} → ${result.target_ref}`),
    metaRow(t('releaseDiff.report_generated_at'), generatedAt),
  ])

  const title = t('aggregateNote.title')

  return `<!DOCTYPE html>
<html lang="${escapeHtml(i18nLocale())}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${escapeHtml(title)} - ${escapeHtml(result.app_name || context.repository_slug)}</title>
<style>${buildReportStyle()}</style>
</head>
<body>
<div class="report">
  <h1>${escapeHtml(title)}</h1>
  <p class="subtitle">${escapeHtml(
    t('aggregateNote.report_subtitle', {
      app: result.app_name,
      from: result.source_ref,
      to: result.target_ref,
    }),
  )}</p>
  ${meta}
  ${applicationSection}
  ${packagesSections}
  ${unchanged}
  <footer>PR Ledger</footer>
</div>
</body>
</html>`
}

export function aggregateNoteFilename(context: AggregateNoteReportContext): string {
  const scope = `${context.project_key || 'project'}-${context.repository_slug || 'repository'}`
  const safeScope = scope.replace(/[^A-Za-z0-9._-]+/g, '_')
  return `release-notes-${safeScope}-${dayjs().format('YYYYMMDD-HHmmss')}.html`
}

export function downloadAggregateReleaseNote(html: string, filename: string): void {
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

/**
 * The same note as markdown, for saving it as a version release.
 *
 * A stored release body is markdown by contract (`release_note.body`), so the
 * combined note lands on the Release Notes page - and from there on the git
 * provider and in Confluence - through the flows that already exist. Ticket
 * keys stay plain text here: markdown has no ticket linking, and the subject
 * itself still reads.
 */
export function buildAggregateReleaseNoteMarkdown(result: AggregateReleaseNoteResponse): string {
  const lines: string[] = []

  lines.push(`## ${t('aggregateNote.report_application')} (${result.source_ref} → ${result.target_ref})`)
  lines.push('')
  lines.push(t(`appDiff.code_verdict_${result.application.verdict}`))
  lines.push('')
  for (const commit of result.application.added_commits ?? []) {
    lines.push(commitLine(commit))
  }

  const compared = result.packages.filter((entry) => entry.status === 'compared' && entry.comparison)
  const skipped = result.packages.filter((entry) => entry.status !== 'compared')

  if (compared.length > 0) {
    lines.push('')
    lines.push(`## ${t('aggregateNote.packages_heading')}`)
    lines.push('')
    for (const entry of compared) {
      lines.push(
        `### ${entry.name} ${versionSpanText(entry)} — ${t(CHANGE_KEY[entry.change])}, ${t(
          `appDiff.code_verdict_${entry.comparison!.verdict}`,
        )}`,
      )
      lines.push('')
      for (const commit of entry.comparison!.added_commits ?? []) {
        lines.push(commitLine(commit))
      }
    }
  }

  if (skipped.length > 0) {
    lines.push('')
    lines.push(`### ${t('aggregateNote.report_not_compared')}`)
    lines.push('')
    for (const entry of skipped) {
      const reason = entry.reason ? ` — ${entry.reason}` : ''
      lines.push(`- **${entry.name}** ${versionSpanText(entry)}: ${t(CHANGE_KEY[entry.change])}${reason}`)
    }
  }

  if (result.unchanged_packages.length > 0) {
    lines.push('')
    lines.push(`**${t('aggregateNote.unchanged_label')}** ${result.unchanged_packages.join(', ')}`)
  }

  return lines.join('\n')
}

function commitLine(commit: { display_id?: string | null; id: string; message?: string | null; author_name?: string | null }): string {
  const sha = commit.display_id || commit.id
  const author = commit.author_name ? ` _(${commit.author_name})_` : ''
  const message = (commit.message ?? '').split('\n')[0]
  return `- \`${sha}\` ${message}${author}`
}

function versionSpanText(entry: AggregatePackageEntry): string {
  const from = entry.from_version || '—'
  const to = entry.to_version || '—'
  return `${from} → ${to}`
}
