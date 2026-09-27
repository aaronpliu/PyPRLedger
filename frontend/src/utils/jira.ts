/**
 * JIRA ticket keys inside commit messages.
 *
 * The backend publishes its JIRA configuration (``GET /rbac/settings/jira``); as
 * long as no base URL is configured every message stays plain text, so the same
 * helpers can be used unconditionally by the commit tables and the HTML report.
 */

export interface JiraSettings {
  base_url: string
  /** Optional allowlist of project keys (empty links every PROJECT-123 key) */
  project_keys: string[]
}

/** A commit message split into plain text and JIRA ticket links. */
export interface JiraMessageSegment {
  text: string
  url?: string
}

// A project key starts with a letter, followed by letters / digits / underscores
const JIRA_TICKET_RE = /\b[A-Z][A-Z0-9_]{1,9}-\d+\b/g

// Fenced code block opening / closing line
const CODE_FENCE_RE = /^\s*(```|~~~)/

function normalizedBaseUrl(settings?: JiraSettings | null): string {
  return (settings?.base_url ?? '').trim().replace(/\/+$/, '')
}

/**
 * Browse URL of a ticket key, or ``undefined`` when JIRA is not configured for it
 * (no base URL, or a project the allowlist excludes).
 */
export function jiraTicketUrl(key: string, settings?: JiraSettings | null): string | undefined {
  const baseUrl = normalizedBaseUrl(settings)
  if (!baseUrl || !key) return undefined

  const allowed = settings?.project_keys ?? []
  const project = (key.split('-')[0] ?? '').toUpperCase()
  if (allowed.length > 0 && !allowed.includes(project)) return undefined

  return `${baseUrl}/browse/${key}`
}

/**
 * Split a message into segments so the ticket keys can be rendered as links.
 *
 * Returns a single plain segment when nothing can be linked, so callers never
 * have to special case JIRA being unconfigured.
 */
export function jiraTicketSegments(
  message: string | null | undefined,
  settings?: JiraSettings | null,
): JiraMessageSegment[] {
  const text = message ?? ''
  if (!text) return []

  const segments: JiraMessageSegment[] = []
  let cursor = 0

  for (const match of text.matchAll(JIRA_TICKET_RE)) {
    const key = match[0]
    const index = match.index ?? 0
    const url = jiraTicketUrl(key, settings)
    if (!url) continue

    if (index > cursor) {
      segments.push({ text: text.slice(cursor, index) })
    }
    segments.push({ text: key, url })
    cursor = index + key.length
  }

  if (cursor < text.length) {
    segments.push({ text: text.slice(cursor) })
  }

  return segments
}

/**
 * Whether the key already belongs to a link or to a URL of ``text``.
 *
 * Guards the markdown transformation below: a generated body already holds
 * ``[PRL-123](…)`` and a hand written one often quotes a browse URL.
 */
function isAlreadyLinked(text: string, offset: number, key: string): boolean {
  if (text.slice(offset + key.length).startsWith('](')) {
    return true
  }

  const tokenStart = Math.max(text.lastIndexOf(' ', offset), text.lastIndexOf('\n', offset)) + 1
  const tokenEnd = text.indexOf(' ', offset + key.length)
  const token = text.slice(tokenStart, tokenEnd === -1 ? text.length : tokenEnd)

  return token.includes('://') || token.includes('](')
}

function linkifyJiraText(text: string, settings?: JiraSettings | null): string {
  return text.replace(JIRA_TICKET_RE, (key: string, offset: number, whole: string) => {
    const url = jiraTicketUrl(key, settings)
    if (!url || isAlreadyLinked(whole, offset, key)) return key
    return `[${key}](${url})`
  })
}

/** One markdown line, leaving its inline code spans untouched. */
function linkifyJiraLine(line: string, settings?: JiraSettings | null): string {
  return line
    .split(/(`[^`]*`)/g)
    .map((part) => (part.startsWith('`') ? part : linkifyJiraText(part, settings)))
    .join('')
}

/**
 * Link the JIRA ticket keys of a markdown body.
 *
 * The backend links the notes it generates itself; a body written (or imported)
 * by hand keeps its plain text, so the renderers apply the same transformation
 * on display. Code blocks / inline code, existing markdown links and bare URLs
 * are left as they are; without JIRA the body is returned unchanged.
 */
export function linkifyJiraMarkdown(
  body: string | null | undefined,
  settings?: JiraSettings | null,
): string {
  const text = body ?? ''
  if (!text || !normalizedBaseUrl(settings)) return text

  let inCodeBlock = false
  return text
    .split('\n')
    .map((line) => {
      if (CODE_FENCE_RE.test(line)) {
        inCodeBlock = !inCodeBlock
        return line
      }
      return inCodeBlock ? line : linkifyJiraLine(line, settings)
    })
    .join('\n')
}
