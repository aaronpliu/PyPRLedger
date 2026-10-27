import { describe, expect, it } from 'vitest'
import { appsForTargets, targetsForApps } from '@/utils/ruleConditions'

// the registry listing the rule dialog reads: app name -> the repositories it covers
const REGISTRY = {
  'Frontend Store': ['PROJ-A/frontend', 'PROJ-A/web'],
  'Backend API': ['PROJ-B/api'],
  'Shared Lib': ['PROJ-B/shared'],
}

describe('targetsForApps', () => {
  it('lists the project keys and repository slugs one app covers', () => {
    expect(targetsForApps(REGISTRY, ['Frontend Store'])).toEqual({
      projectKeys: ['PROJ-A'],
      repositorySlugs: ['frontend', 'web'],
    })
  })

  it('unions several apps without repeating a key or a slug', () => {
    expect(targetsForApps(REGISTRY, ['Frontend Store', 'Backend API'])).toEqual({
      projectKeys: ['PROJ-A', 'PROJ-B'],
      repositorySlugs: ['frontend', 'web', 'api'],
    })
  })

  it('reads an app the registry does not hold as covering nothing', () => {
    expect(targetsForApps(REGISTRY, ['Unknown'])).toEqual({
      projectKeys: [],
      repositorySlugs: [],
    })
  })
})

describe('appsForTargets', () => {
  it('reads one app back from its two lists', () => {
    expect(appsForTargets(REGISTRY, ['PROJ-A'], ['frontend', 'web'])).toEqual(['Frontend Store'])
  })

  it('reads several apps back from the lists they were picked as', () => {
    // what a two-app rule is stored as: the lists, with no memory of the selection
    expect(appsForTargets(REGISTRY, ['PROJ-A', 'PROJ-B'], ['frontend', 'web', 'api'])).toEqual([
      'Frontend Store',
      'Backend API',
    ])
  })

  it('does not offer an app the rule only partly covers', () => {
    // Frontend Store also ships PROJ-A/web, which this rule leaves out
    expect(appsForTargets(REGISTRY, ['PROJ-A'], ['frontend'])).toEqual([])
  })

  it('leaves the field empty when part of the rule comes from no app', () => {
    // PROJ-Z is in no registry entry, so no selection reproduces the rule
    expect(appsForTargets(REGISTRY, ['PROJ-A', 'PROJ-Z'], ['frontend', 'web'])).toEqual([])
  })

  it('leaves a project-only rule empty rather than narrowing it', () => {
    // offering the app back would add its slugs, and the rule would stop matching the
    // project's other repositories
    expect(appsForTargets(REGISTRY, ['PROJ-A'], [])).toEqual([])
  })

  it('reads a rule with no project conditions as no app at all', () => {
    expect(appsForTargets(REGISTRY, [], [])).toEqual([])
  })
})
