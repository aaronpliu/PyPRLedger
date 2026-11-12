import { describe, expect, it } from 'vitest'
import type { AppVersionDiffResponse } from '@/api/appVersionDiff'
import {
  appDiffReportFilename,
  buildAppDiffReportHtml,
  type AppDiffReportContext,
} from '@/utils/export/appDiffReport'

const context: AppDiffReportContext = {
  project_key: 'CORE',
  repository_slug: 'app',
  app_name: 'Ledger App',
  git_provider: 'bitbucket_server',
}

const result: AppVersionDiffResponse = {
  project_key: 'CORE',
  repository_slug: 'app',
  app_name: 'Ledger App',
  git_provider: 'bitbucket_server',
  verdict: 'changed',
  summary: { changed: 1, added: 0, removed: 0 },
  releases: [
    { ref: 'v1.0.0', released_at: '2026-01-01T00:00:00Z', has_record: true },
    { ref: 'v1.1.0', released_at: null, has_record: true },
  ],
  rows: [
    {
      kind: 'application',
      name: 'ledger-app',
      versions: ['1.0.0', '1.1.0'],
      moves: [null, null],
    },
    {
      kind: 'dependency',
      name: 'pylang',
      versions: ['0.9.0', '1.0.0'],
      moves: [null, null],
    },
  ],
  intervals: [
    {
      source_ref: 'v1.0.0',
      target_ref: 'v1.1.0',
      complete: true,
      summary: { changed: 1 },
      dependencies_moved: true,
      changes: [],
      code: {
        verdict: 'contained',
        scan_complete: true,
        added_count: 1,
        missing_count: 0,
        added_commits: [
          {
            id: 'abcdef1234567890',
            display_id: 'abcdef1',
            author_name: 'Alice',
            author_username: 'alice',
            author_email: null,
            author_timestamp: 1760000000000,
            message: 'Add the new module',
            url: 'https://git.example.com/commits/abcdef1',
          },
        ],
        missing_commits: [],
        truncated: false,
        unavailable: null,
        deferred: false,
      },
      packages: [
        {
          name: 'pylang',
          state: 'changed',
          source_version: '0.9.0',
          target_version: '1.0.0',
          project_key: 'AI',
          repository_slug: 'pylang',
          git_provider: 'bitbucket_server',
          code: {
            verdict: 'missing',
            scan_complete: true,
            added_count: 0,
            missing_count: 1,
            added_commits: [],
            missing_commits: [
              {
                id: 'beef1234567890ab',
                display_id: 'beef123',
                author_name: 'Bob',
                author_username: null,
                author_email: null,
                author_timestamp: null,
                message: 'Fix the parser bug\n\nLong body that stays out of the table cell.',
                url: null,
              },
            ],
            truncated: false,
            unavailable: null,
            deferred: false,
          },
        },
      ],
    },
  ],
  package_comparisons: { per_pair: 5, page_total: 10, batch: 3, remaining: 5 },
}

describe('appDiffReport', () => {
  it('names the report after the repository pair and the current time', () => {
    expect(appDiffReportFilename(context)).toMatch(/^app-diff-CORE-app-\d{8}-\d{6}\.html$/)
  })

  it('renders the version matrix, the pair sections and the commit links', () => {
    const html = buildAppDiffReportHtml({ result, context })

    // the matrix carries every row and every release
    expect(html).toContain('Ledger App')
    expect(html).toContain('v1.0.0')
    expect(html).toContain('v1.1.0')
    expect(html).toContain('>pylang<')

    // one section per adjacent pair, headed by its refs
    expect(html).toContain('v1.0.0 → v1.1.0')

    // the application's added commits appear with their provider links
    expect(html).toContain('abcdef1')
    expect(html).toContain('https://git.example.com/commits/abcdef1')

    // the package's own comparison reports its missing commit
    expect(html).toContain('beef123')
    expect(html).toContain('Fix the parser bug')
    // the message body is escaped into the hover title, never rendered raw
    expect(html).toContain('title="Fix the parser bug')
    expect(html).not.toContain('<Long body')
  })

  it('escapes a hostile commit message and repository name', () => {
    const hostile = {
      ...result,
      app_name: '<script>alert(1)</script>',
      intervals: result.intervals.map((interval) => ({
        ...interval,
        code: {
          ...interval.code!,
          added_commits: [
            {
              ...interval.code!.added_commits[0],
              message: '<img src=x onerror=alert(2)>',
              url: null,
            },
          ],
        },
      })),
    }

    const html = buildAppDiffReportHtml({ result: hostile, context })
    expect(html).not.toContain('<script>alert')
    expect(html).not.toContain('<img src=x')
    expect(html).toContain('&lt;script&gt;')
  })
})
