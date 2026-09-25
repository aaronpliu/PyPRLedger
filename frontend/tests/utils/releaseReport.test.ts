import { describe, expect, it } from 'vitest'
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
  old_release_ref: 'v1.0.0',
  new_release_ref: 'v1.1.0',
  old_release_base_ref: null,
  new_release_base_ref: null,
  old_commits_included: false,
  status: 'missing_commits',
  summary: {
    old_commit_count: 2,
    new_commit_count: 3,
    missing_count: 1,
    added_count: 1,
    common_count: 1,
  },
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
  added_commits: [{ id: C2, display_id: '2222222', message: 'feat: dashboard' }],
  old_release_commits: [],
  new_release_commits: [],
  truncated: true,
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
    // scope row shows both release scopes
    expect(html).toContain('full history of v1.0.0')
    expect(html).toContain('full history of v1.1.0')
    // commit url column
    expect(html).toContain('https://bitbucket.org/aaronpliu/pylang/commits/1111111')
    expect(html.match(/No commits/g)).toHaveLength(2)
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
    expect(html.match(/class="cell-warn"/g)).toHaveLength(1)
    expect(html.match(/class="url"/g)).toBeTruthy()
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
