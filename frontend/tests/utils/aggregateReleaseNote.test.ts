import { describe, expect, it } from 'vitest'
import { buildCombinedNoteBody } from '@/utils/export/aggregateReleaseNote'
import type {
  AggregatePackageEntry,
  AggregateReleaseNoteResponse,
} from '@/api/aggregateReleaseNote'

// The combined body reads the response the backend answers with; the tests
// below pin the contract the release depends on - the rendered sections in
// order, legibility for what cannot be compared, and nothing that did not
// move.

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
