import type {
  AggregatePackageEntry,
  AggregateReleaseNoteResponse,
} from '@/api/aggregateReleaseNote'
import { tExport as t } from './shared'

/**
 * The combined note as one markdown body, from the rendered sections the
 * backend answers with: the application's own release note first (summary,
 * categorized sections, ticket links, authors), then one section per package
 * the span moved, then the lines that keep the rest legible - a package that
 * could not be compared says why. The unchanged packages stay out: what the
 * release says is what moved, not a list of what did not.
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

  // the unchanged packages are the release's quiet half: the answer carries
  // them, but a note that names what did not happen buries what did
  return parts.join('\n\n')
}

const CHANGE_KEY: Record<AggregatePackageEntry['change'], string> = {
  upgraded: 'aggregateNote.change_upgraded',
  added: 'aggregateNote.change_added',
  removed: 'aggregateNote.change_removed',
}

function versionSpan(entry: AggregatePackageEntry): string {
  const from = entry.from_version || '—'
  const to = entry.to_version || '—'
  return `${from} → ${to}`
}
