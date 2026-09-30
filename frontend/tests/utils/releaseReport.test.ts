import { describe, expect, it } from 'vitest'
import enMessages from '@/locales/en.json'
import type {
  ReleaseCommitCheckResponse,
  ReleaseCompareResponse,
} from '@/api/releaseDiff'
import {
  buildCheckSectionHtml,
  buildCompareSectionHtml,
  buildReleaseReportHtml,
  escapeHtml,
  normalizeUrl,
  releaseRefUrl,
  releaseReportFilename,
  repositoryBaseUrl,
  type ReleaseReportContext,
} from '@/utils/export/releaseReport'

const CONTEXT: ReleaseReportContext = {
  project_key: 'AI',
  repository_slug: 'pylang',
  git_provider: 'bitbucket_cloud',
  workspace_slug: 'aaronpliu',
  project_url: 'https://bitbucket.org/aaronpliu',
  repository_url: 'https://bitbucket.org/aaronpliu/pylang.git',
}

const C1 = '1111111111111111111111111111111111111111'
const C2 = '2222222222222222222222222222222222222222'

const COMPARE: ReleaseCompareResponse = {
  project_key: 'AI',
  repository_slug: 'pylang',
  git_provider: 'bitbucket_cloud',
  source_ref: 'v1.0.0',
  target_ref: 'v1.1.0',
  baseline_ref: 'v0.9.0',
  baseline_stored: true,
  narrowed: true,
  verdict: 'missing',
  scan_complete: true,
  scan_limit: 2000,
  filtered_by_baseline_count: 1,
  missing_count: 1,
  missing_commits: [
    {
      id: C1,
      display_id: '1111111',
      author_name: 'Jane <Doe>',
      author_email: 'jane@example.com',
      author_timestamp: 1_690_000_000_000,
      message: 'fix: escape <script>alert(1)</script> & more',
      url: 'https://bitbucket.org/aaronpliu/pylang/commits/1111111',
    },
  ],
  added_count: 1,
  added_commits: [{ id: C2, display_id: '2222222', message: 'feat: dashboard' }],
  added_complete: true,
  rendered_truncated: false,
}

const CHECK: ReleaseCommitCheckResponse = {
  project_key: 'AI',
  repository_slug: 'pylang',
  git_provider: 'bitbucket_cloud',
  target_release_ref: 'v1.1.0',
  target_release_base_ref: 'v1.0.0',
  all_included: false,
  summary: { requested: 2, included_count: 1, missing_count: 1, release_commit_count: 3 },
  results: [
    {
      commit: C1,
      included: true,
      matched_id: C1,
      commit_info: {
        id: C1,
        display_id: '1111111',
        message: 'fix: crash',
        url: 'https://bitbucket.org/aaronpliu/pylang/commits/1111111',
      },
    },
    { commit: 'deadbee', included: false, reason: 'not_found_in_release_scope' },
  ],
  truncated: false,
}

describe('escapeHtml', () => {
  it('escapes every html sensitive character', () => {
    expect(escapeHtml(`<a href="x">'&'</a>`)).toBe(
      '&lt;a href=&quot;x&quot;&gt;&#39;&amp;&#39;&lt;/a&gt;',
    )
    expect(escapeHtml(null)).toBe('')
    expect(escapeHtml(42)).toBe('42')
  })
})

describe('repositoryBaseUrl / releaseRefUrl', () => {
  it('prefers the stored repository url and strips the .git suffix', () => {
    expect(repositoryBaseUrl(CONTEXT)).toBe('https://bitbucket.org/aaronpliu/pylang')
  })

  it('strips clone credentials from the url', () => {
    expect(normalizeUrl('https://alice@bitbucket.org/acme/web-app.git')).toBe(
      'https://bitbucket.org/acme/web-app',
    )
    expect(
      repositoryBaseUrl({ ...CONTEXT, repository_url: 'https://alice@bitbucket.org/aaronpliu/pylang' }),
    ).toBe('https://bitbucket.org/aaronpliu/pylang')
  })

  it('falls back to the project url when no repository url is known', () => {
    expect(repositoryBaseUrl({ ...CONTEXT, repository_url: null })).toBe(
      'https://bitbucket.org/aaronpliu',
    )
  })

  it('derives a Cloud url from the workspace when nothing is stored', () => {
    expect(
      repositoryBaseUrl({
        project_key: 'AI',
        repository_slug: 'pylang',
        git_provider: 'bitbucket_cloud',
        workspace_slug: 'aaronpliu',
      }),
    ).toBe('https://bitbucket.org/aaronpliu/pylang')
  })

  it('does not invent urls for other providers', () => {
    expect(
      repositoryBaseUrl({
        project_key: 'PROJ',
        repository_slug: 'my-repo',
        git_provider: 'bitbucket_server',
      }),
    ).toBeUndefined()
  })

  it('builds ref browse urls for Cloud only', () => {
    expect(releaseRefUrl(CONTEXT, 'release/1.0')).toBe(
      'https://bitbucket.org/aaronpliu/pylang/commits/release%2F1.0',
    )
    expect(releaseRefUrl({ ...CONTEXT, git_provider: 'bitbucket_server' }, 'v1.0.0')).toBeUndefined()
    expect(releaseRefUrl(CONTEXT, null)).toBeUndefined()
  })
})

describe('buildCompareSectionHtml', () => {
  it('renders the release meta as a table with scope and ref urls', () => {
    const html = buildCompareSectionHtml(COMPARE, CONTEXT)

    expect(html).toContain('<table class="meta">')
    expect(html).toContain('v1.0.0')
    expect(html).toContain('v1.1.0')
    expect(html).toContain('https://bitbucket.org/aaronpliu/pylang/commits/v1.0.0')
    expect(html).toContain('https://bitbucket.org/aaronpliu/pylang/commits/v1.1.0')
    // the effective baseline is part of the report, not the two old scopes
    expect(html).toContain('Stored baseline: v0.9.0')
    // scope row names the compared pair
    expect(html).toContain('v1.0.0 → v1.1.0')
    // commit url column
    expect(html).toContain('https://bitbucket.org/aaronpliu/pylang/commits/1111111')
  })

  it('highlights missing commits in red instead of amber', () => {
    const html = buildCompareSectionHtml(COMPARE, CONTEXT)

    // the verdict banner and the missing stat use the missing (red) variants
    expect(html).toContain('class="status status-missing"')
    expect(html).toContain('class="stat stat-missing"')
    expect(html).toContain('<h3 class="section-missing">')
    expect(html).not.toContain('status-warn')
    expect(html).not.toContain('stat-warn')
    // the cherry-pick caveat is part of the report
    expect(html).toContain('cherry-picked')
  })

  it('renders an inconclusive verdict with the warning colour', () => {
    const html = buildCompareSectionHtml(
      { ...COMPARE, verdict: 'inconclusive', scan_complete: false, scan_limit: 1 },
      CONTEXT,
    )

    expect(html).toContain('class="status status-warn"')
    expect(html).toContain('class="warning"')
    expect(html).not.toContain('class="status status-ok"')
  })

  it('escapes commit messages coming from the git provider', () => {
    const html = buildCompareSectionHtml(COMPARE, CONTEXT)

    expect(html).not.toContain('<script>alert(1)</script>')
    expect(html).toContain('&lt;script&gt;alert(1)&lt;/script&gt;')
    expect(html).toContain('Jane &lt;Doe&gt;')
  })
})

describe('buildCheckSectionHtml', () => {
  it('lists the per commit results with their status and url', () => {
    const html = buildCheckSectionHtml(CHECK, CONTEXT)

    expect(html).toContain('deadbee')
    expect(html).toContain('v1.0.0..v1.1.0')
    expect(html).toContain('https://bitbucket.org/aaronpliu/pylang/commits/v1.1.0')
    expect(html.match(/class="cell-ok"/g)).toHaveLength(1)
    // missing entries are red, not amber
    expect(html.match(/class="cell-missing"/g)).toHaveLength(1)
    expect(html).not.toContain('cell-warn')
    expect(html).toContain('class="status status-missing"')
    expect(html.match(/class="url"/g)).toBeTruthy()
  })

  it('warns in the report when the commit listing was capped', () => {
    const html = buildCheckSectionHtml({ ...CHECK, truncated: true }, CONTEXT)

    // a sentence a reader can act on, not a key nobody can substitute afterwards
    expect(html).toContain(`<p class="warning">${enMessages.releaseDiff.truncated_warning}</p>`)
    expect(html).not.toContain('releaseDiff.')
  })
})

describe('buildReleaseReportHtml', () => {
  it('renders the repository meta as a table including the urls', () => {
    const html = buildReleaseReportHtml({ context: CONTEXT, compare: COMPARE, check: CHECK })

    expect(html.startsWith('<!DOCTYPE html>')).toBe(true)
    expect(html).toContain('<style>')
    expect(html).toContain('<table class="meta">')
    expect(html).toContain('AI')
    expect(html).toContain('aaronpliu')
    expect(html).toContain('pylang')
    expect(html).toContain('bitbucket_cloud')
    // project + repository urls are emitted as links
    expect(html).toContain('href="https://bitbucket.org/aaronpliu"')
    expect(html).toContain('href="https://bitbucket.org/aaronpliu/pylang"')
    // both sections rendered
    expect(html.match(/class="report-section"/g)).toHaveLength(2)
    expect(html).toContain('1. ')
    expect(html).toContain('2. ')
  })

  it('renders only the sections that have a result', () => {
    const compareOnly = buildReleaseReportHtml({ context: CONTEXT, compare: COMPARE })
    expect(compareOnly.match(/class="report-section"/g)).toHaveLength(1)
    expect(compareOnly).toContain('1. ')
    expect(compareOnly).not.toContain('2. ')

    const checkOnly = buildReleaseReportHtml({ context: CONTEXT, check: CHECK })
    expect(checkOnly.match(/class="report-section"/g)).toHaveLength(1)
    expect(checkOnly).not.toContain('1. ')
    expect(checkOnly).toContain('2. ')
  })

  it('omits url rows when no url can be determined', () => {
    const html = buildReleaseReportHtml({
      context: { project_key: 'PROJ', repository_slug: 'my-repo', git_provider: 'bitbucket_server' },
      compare: COMPARE,
    })

    const metaBlock = html.split('<table class="meta">')[1].split('</table>')[0]
    expect(metaBlock).toBeDefined()
    expect(metaBlock).not.toContain('href=')
    expect(html).toContain('<table class="meta">')
  })
})

describe('release report — commit message and author cells', () => {
  const JIRA_CONTEXT: ReleaseReportContext = {
    ...CONTEXT,
    jira: { base_url: 'https://jira.local', project_keys: [] },
  }

  const COMMIT = {
    id: C1,
    display_id: '1111111',
    author_name: 'Aaron Liu',
    author_username: 'aaronpliu',
    author_url: 'https://bitbucket.org/aaronpliu/',
    message: 'fix: crash on logout PRL-123',
    url: 'https://bitbucket.org/aaronpliu/pylang/commits/1111111',
  }

  it('links the JIRA ticket keys and the author profile', () => {
    const html = buildCompareSectionHtml(
      { ...COMPARE, missing_commits: [COMMIT] },
      JIRA_CONTEXT,
    )

    expect(html).toContain(
      '<a href="https://jira.local/browse/PRL-123" target="_blank" rel="noopener">PRL-123</a>',
    )
    expect(html).toContain(
      '<a href="https://bitbucket.org/aaronpliu/" target="_blank" rel="noopener">@aaronpliu</a>',
    )
    // the display name stays available as the tooltip of the account
    expect(html).toContain('fix: crash on logout')
  })

  it('links the ticket keys of the commit check as well', () => {
    const html = buildCheckSectionHtml(
      {
        ...CHECK,
        results: [
          { commit: C1, included: true, matched_id: C1, commit_info: COMMIT },
        ],
      },
      JIRA_CONTEXT,
    )

    expect(html).toContain('href="https://jira.local/browse/PRL-123"')
    expect(html).toContain('>@aaronpliu</a>')
  })

  it('keeps the cells plain while JIRA is not configured', () => {
    const html = buildCompareSectionHtml({ ...COMPARE, missing_commits: [COMMIT] }, CONTEXT)

    expect(html).not.toContain('jira.local')
    expect(html).toContain('fix: crash on logout PRL-123')
  })

  it('falls back to the display name when the provider reports no account', () => {
    const html = buildCompareSectionHtml(
      {
        ...COMPARE,
        missing_commits: [{ ...COMMIT, author_username: null, author_url: null }],
      },
      JIRA_CONTEXT,
    )

    expect(html).toContain('<td>Aaron Liu</td>')
    expect(html).not.toContain('@aaronpliu</a>')
  })
})

describe('releaseReportFilename', () => {
  it('builds a filesystem safe name per report kind', () => {
    const filename = releaseReportFilename('both', { ...CONTEXT, project_key: 'my project/x' })

    expect(filename).toMatch(/^release-both-my_project_x-pylang-\d{8}-\d{6}\.html$/)
  })

  it('falls back to generic placeholders when coordinates are missing', () => {
    const filename = releaseReportFilename('compare', { project_key: '', repository_slug: '' })

    expect(filename).toMatch(/^release-compare-project-repository-\d{8}-\d{6}\.html$/)
  })
})
