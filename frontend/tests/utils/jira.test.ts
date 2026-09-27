import { describe, it, expect } from 'vitest'
import {
  jiraTicketSegments,
  jiraTicketUrl,
  linkifyJiraMarkdown,
  type JiraSettings,
} from '@/utils/jira'

/** JIRA with every PROJECT-123 key allowed */
const OPEN: JiraSettings = { base_url: 'https://jira.local', project_keys: [] }
/** JIRA restricted to a single project */
const RESTRICTED: JiraSettings = { base_url: 'https://jira.local/', project_keys: ['PRL'] }

describe('jiraTicketUrl', () => {
  it('builds the browse url of a ticket', () => {
    expect(jiraTicketUrl('PRL-123', OPEN)).toBe('https://jira.local/browse/PRL-123')
  })

  it('normalizes a trailing slash of the configured instance', () => {
    expect(jiraTicketUrl('PRL-123', RESTRICTED)).toBe('https://jira.local/browse/PRL-123')
  })

  it('rejects a project outside the allowlist', () => {
    expect(jiraTicketUrl('AI-7', RESTRICTED)).toBeUndefined()
  })

  it('has no url while JIRA is not configured', () => {
    expect(jiraTicketUrl('PRL-123', null)).toBeUndefined()
    expect(jiraTicketUrl('PRL-123', { base_url: '', project_keys: [] })).toBeUndefined()
  })
})

describe('jiraTicketSegments', () => {
  it('keeps the whole message as plain text without a configured instance', () => {
    expect(jiraTicketSegments('fix login PRL-123', null)).toEqual([
      { text: 'fix login PRL-123' },
    ])
  })

  it('splits the subject around the ticket keys', () => {
    const segments = jiraTicketSegments('fix login PRL-123 for good', OPEN)

    expect(segments).toEqual([
      { text: 'fix login ' },
      { text: 'PRL-123', url: 'https://jira.local/browse/PRL-123' },
      { text: ' for good' },
    ])
  })

  it('links every ticket key of the subject', () => {
    const segments = jiraTicketSegments('PRL-1 and PRL-2', OPEN)

    expect(segments.filter((segment) => segment.url)).toHaveLength(2)
  })

  it('keeps a key of another project plain when the allowlist excludes it', () => {
    const segments = jiraTicketSegments('fix PRL-4 and UTF-8 handling', RESTRICTED)

    expect(segments.filter((segment) => segment.url).map((segment) => segment.text)).toEqual([
      'PRL-4',
    ])
    expect(segments.map((segment) => segment.text).join('')).toBe('fix PRL-4 and UTF-8 handling')
  })

  it('returns no segment for an empty message', () => {
    expect(jiraTicketSegments('', OPEN)).toEqual([])
    expect(jiraTicketSegments(null, OPEN)).toEqual([])
  })
})

describe('linkifyJiraMarkdown', () => {
  it('links a ticket key typed by the publisher', () => {
    expect(linkifyJiraMarkdown('## Notes\n\n- ship the login fix PRL-123', OPEN)).toBe(
      '## Notes\n\n- ship the login fix [PRL-123](https://jira.local/browse/PRL-123)',
    )
  })

  it('returns the body unchanged while JIRA is not configured', () => {
    expect(linkifyJiraMarkdown('- ship PRL-123', null)).toBe('- ship PRL-123')
    expect(linkifyJiraMarkdown('- ship PRL-123', { base_url: '', project_keys: [] })).toBe(
      '- ship PRL-123',
    )
  })

  it('leaves code blocks and inline code as typed', () => {
    const body = ['```bash', 'curl PRL-9', '```', '', 'inline `PRL-9` code', '', '- real PRL-9'].join(
      '\n',
    )

    const linked = linkifyJiraMarkdown(body, OPEN)

    expect(linked).toContain('curl PRL-9\n')
    expect(linked).toContain('`PRL-9` code')
    // only the plain mention of the last line is linked
    expect(linked.match(/browse\/PRL-9/g)).toHaveLength(1)
    expect(linked).toContain('- real [PRL-9](https://jira.local/browse/PRL-9)')
  })

  it('does not touch an existing link or a browse url', () => {
    const body = '- [PRL-1](https://jira.local/browse/PRL-1)\n- https://jira.local/browse/PRL-2\n'

    expect(linkifyJiraMarkdown(body, OPEN)).toBe(body)
  })

  it('applies the project key allowlist', () => {
    expect(linkifyJiraMarkdown('PRL-1 and AI-2', RESTRICTED)).toBe(
      '[PRL-1](https://jira.local/browse/PRL-1) and AI-2',
    )
  })
})
