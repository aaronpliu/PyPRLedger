import { beforeAll, describe, expect, it } from 'vitest'
import {
  buildAggregateReleaseNoteHtml,
  buildAggregateReleaseNoteMarkdown,
  buildCombinedNoteBody,
} from '@/utils/export/aggregateReleaseNote'
import type {
  AggregatePackageEntry,
  AggregateReleaseNoteResponse,
} from '@/api/aggregateReleaseNote'
import enMessages from '@/locales/en.json'
import i18n from '@/i18n'

// The report and the markdown body read the same response; the tests below pin
// the contract the readers depend on - legibility for what cannot be compared,
// links where a URL exists, nothing unescaped.

function comparedEntry(): AggregatePackageEntry {
  return {
    name: 'pkgA',
    change: 'upgraded',
    from_version: '1.2.0',
    to_version: '1.4.0',
    status: 'compared',
    repository: { project_key: 'PKGA', repository_slug: 'pkgA-repo', git_provider: null },
    comparison: {
      project_key: 'PKGA',
      repository_slug: 'pkgA-repo',
      git_provider: 'bitbucket_server',
      source_ref: '1.2.0',
      target_ref: '1.4.0',
      narrowed: false,
      verdict: 'missing',
      scan_complete: true,
      scan_limit: 500,
      filtered_by_baseline_count: 0,
      missing_count: 0,
      missing_commits: [],
      added_count: 1,
      added_commits: [
        {
          id: 'a1',
          display_id: 'aaa1111',
          message: 'PRL-10: pkgA work\n\nlong body ignored',
          author_name: 'alice',
          url: 'https://git.example.com/commits/a1',
        },
      ],
      added_complete: true,
      rendered_truncated: false,
    },
    body: '### ✨ Added\n\n- PRL-10: pkgA work',
  }
}

function skippedEntry(): AggregatePackageEntry {
  return {
    name: 'pkgY',
    change: 'upgraded',
    from_version: '0.9.0',
    to_version: '1.0.0',
    status: 'skipped',
    reason: "no repository is registered as 'pkgY'",
  }
}

function noteFixture(packages: AggregatePackageEntry[], overrides: Partial<AggregateReleaseNoteResponse> = {}): AggregateReleaseNoteResponse {
  return {
    app_name: 'MyApp',
    project_key: 'CORE',
    repository_slug: 'app',
    git_provider: 'bitbucket_server',
    source_ref: 'v1.0.0',
    target_ref: 'v2.0.0',
    application: {
      project_key: 'CORE',
      repository_slug: 'app',
      git_provider: 'bitbucket_server',
      source_ref: 'v1.0.0',
      target_ref: 'v2.0.0',
      narrowed: false,
      verdict: 'contained',
      scan_complete: true,
      scan_limit: 500,
      filtered_by_baseline_count: 0,
      missing_count: 0,
      missing_commits: [],
      added_count: 1,
      added_commits: [
        {
          id: 'c1',
          display_id: 'abc1234',
          message: 'PRL-9: ship the feature',
          url: 'https://git.example.com/commits/c1',
        },
      ],
      added_complete: true,
      rendered_truncated: false,
    },
    packages,
    dependency_source: 'database',
    unchanged_packages: ['pkgC@3.2.0'],
    summary: {
      packages_changed: packages.length,
      packages_compared: 1,
      packages_skipped: packages.length - 1,
      packages_failed: 0,
      unchanged_packages: 1,
      app_commits: 1,
      package_commits: 1,
    },
    ...overrides,
  }
}

describe('buildAggregateReleaseNoteMarkdown', () => {
  it('opens with the application section and its commits', () => {
    const markdown = buildAggregateReleaseNoteMarkdown(noteFixture([comparedEntry()]))

    expect(markdown).toContain('## Application (v1.0.0 → v2.0.0)')
    expect(markdown).toContain('- `abc1234` PRL-9: ship the feature')
  })

  it('keeps a compared package readable between its two versions', () => {
    const markdown = buildAggregateReleaseNoteMarkdown(noteFixture([comparedEntry()]))

    expect(markdown).toContain('### pkgA 1.2.0 → 1.4.0')
    // only the subject line survives: a commit body would bury the release
    expect(markdown).toContain('- `aaa1111` PRL-10: pkgA work _(alice)_')
    expect(markdown).not.toContain('long body ignored')
  })

  it('keeps a package without a comparison legible, with its reason', () => {
    const markdown = buildAggregateReleaseNoteMarkdown(noteFixture([skippedEntry()]))

    expect(markdown).toContain("**pkgY** 0.9.0 → 1.0.0: Upgraded — no repository is registered as 'pkgY'")
    expect(markdown).not.toContain('### pkgY')
  })

  it('leaves the unchanged packages out of the markdown', () => {
    const markdown = buildAggregateReleaseNoteMarkdown(noteFixture([comparedEntry()]))

    // what a version release says is what moved, not a list of what did not
    expect(markdown).not.toContain('pkgC@3.2.0')
    expect(markdown).not.toContain('Unchanged')
  })
})

describe('buildCombinedNoteBody', () => {
  it('composes the rendered sections into one release-note body', () => {
    const result = noteFixture([comparedEntry(), skippedEntry()], {
      application_body: '## MyApp v2.0.0\n\nSummary of the release.\n\n### ✨ Added\n\n- the thing',
    })
    const body = buildCombinedNoteBody(result)

    // the application's own notes open the body, rendered by the backend
    expect(body).toContain('## MyApp v2.0.0')
    expect(body).toContain('Summary of the release.')
    expect(body).toContain('### ✨ Added')
    // one section per moved package, headed by its version span, its body the
    // rendered release note the backend answered with
    expect(body).toContain('## pkgA (1.2.0 → 1.4.0)')
    expect(body).toContain('PRL-10')
  })

  it('keeps a package without a body legible instead of hiding it', () => {
    const result = noteFixture([skippedEntry()], { application_body: '## MyApp v2.0.0' })
    const body = buildCombinedNoteBody(result)

    // the skipped section says what happened - change, status, reason - so the
    // note never reads as if the closure had not moved
    expect(body).toContain('## pkgY (0.9.0 → 1.0.0)')
    expect(body).toContain("registered as 'pkgY'")
    expect(body).not.toContain('PRL-10')
  })

  it('leaves the unchanged packages out of the body', () => {
    const result = noteFixture([comparedEntry(), skippedEntry()], {
      application_body: '',
      unchanged_packages: ['pkgC@3.2.0'],
    })
    const body = buildCombinedNoteBody(result)

    // what the release says is what moved; the unchanged list is for the page,
    // not for the note
    expect(body).not.toContain('pkgC@3.2.0')
    expect(body).not.toContain('unchanged')
  })
})

describe('buildAggregateReleaseNoteHtml', () => {
  beforeAll(() => {
    // the report reads the same dictionary through tExport
    void i18n.global.setLocaleMessage('en', enMessages)
  })

  it('renders one section per package and the unchanged line', () => {
    const html = buildAggregateReleaseNoteHtml({
      result: noteFixture([comparedEntry(), skippedEntry()]),
      context: { project_key: 'CORE', repository_slug: 'app' },
    })

    expect(html).toContain('pkgA')
    expect(html).toContain('1.2.0 → 1.4.0')
    expect(html).toContain("no repository is registered as &#39;pkgY&#39;")
    expect(html).toContain('pkgC@3.2.0')
    // commit URLs become links, and the JIRA ticket reads as plain text here
    // (the markdown body is where providers can link them)
    expect(html).toContain('href="https://git.example.com/commits/c1"')
    expect(html).toContain('PRL-9: ship the feature')
  })
})
