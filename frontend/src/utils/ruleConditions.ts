/**
 * The registry's `app_name -> ['project_key/repository_slug', ...]` listing, read in
 * both directions.
 *
 * The rule dialog picks applications, and a rule stores `project_key` and
 * `repository_slug` lists - the registry is what stands between the two. A rule keeps
 * only the flattened lists, so opening one for editing has to find the applications
 * they came from, and it has to find them exactly: the applications offered back must
 * reproduce the same two lists, or saving an untouched rule would quietly widen or
 * narrow what it matches.
 */

export type AppRegistry = Record<string, string[]>

export interface ConditionTargets {
  projectKeys: string[]
  repositorySlugs: string[]
}

function splitEntry(entry: string): [string, string] {
  const [projectKey, repositorySlug] = entry.split('/')
  return [projectKey ?? '', repositorySlug ?? '']
}

function unique(values: string[]): string[] {
  return [...new Set(values)]
}

/** The two lists a selection of applications stands for. */
export function targetsForApps(registry: AppRegistry, apps: string[]): ConditionTargets {
  const projectKeys: string[] = []
  const repositorySlugs: string[] = []
  for (const app of apps) {
    for (const entry of registry[app] ?? []) {
      const [projectKey, repositorySlug] = splitEntry(entry)
      if (projectKey) projectKeys.push(projectKey)
      if (repositorySlug) repositorySlugs.push(repositorySlug)
    }
  }
  return {
    projectKeys: unique(projectKeys),
    repositorySlugs: unique(repositorySlugs),
  }
}

/**
 * The applications a rule's two lists came from.
 *
 * A candidate application is one whose every registered repository is covered by the
 * rule - its project key is listed, and so is its repository slug - so choosing it
 * again adds nothing the rule did not already match. The candidates are only offered
 * when together they cover the rule exactly; a rule that no set of applications
 * explains (one typed as JSON, or one naming a project the registry does not hold)
 * reads as no application chosen, and the JSON preview beside it says what it matches.
 */
export function appsForTargets(
  registry: AppRegistry,
  projectKeys: string[],
  repositorySlugs: string[],
): string[] {
  const keys = unique(projectKeys)
  const slugs = unique(repositorySlugs)
  if (keys.length === 0 && slugs.length === 0) return []

  const candidates = Object.entries(registry).filter(([, entries]) =>
    entries.every((entry) => {
      const [projectKey, repositorySlug] = splitEntry(entry)
      const keyFits = keys.length === 0 || keys.includes(projectKey)
      const slugFits = slugs.length === 0 || slugs.includes(repositorySlug)
      return keyFits && slugFits
    }),
  )
  if (candidates.length === 0) return []

  const names = candidates.map(([app]) => app)
  const covered = targetsForApps(registry, names)
  const sameList = (found: string[], wanted: string[]) =>
    found.length === wanted.length && wanted.every((value) => found.includes(value))

  if (!sameList(covered.projectKeys, keys) || !sameList(covered.repositorySlugs, slugs)) {
    // Part of the rule comes from somewhere other than these applications: offering
    // them back would rewrite that part on the next save.
    return []
  }
  return names
}
