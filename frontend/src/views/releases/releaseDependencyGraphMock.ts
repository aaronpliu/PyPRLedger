import { dependencyFileToGraph } from '@/utils/releaseDependencyGraph'
import type {
  DependencyFile,
  DependencyFileGraph,
} from '@/utils/releaseDependencyGraph'

/**
 * Stand-in for the dependency files a monorepo dependency script is expected to
 * emit: one per repository ref, in the shape of the package.json files it
 * walked - the app naming its direct dependencies by exact version, the
 * packages it pulls in naming theirs by range. So the graph reads the way the
 * repository works: the app's edges carry the version it ships against, the
 * edges among the packages carry the bare relationship.
 *
 * The three tags tell the story of the graph changing over time: 1.0.0 knew
 * seven packages, 1.1.0 added G, and 2.0.0 wired the full shape - including
 * the cycle where D reaches back to A, which A also pulls in. The branch is
 * what the script produces outside a release: the same walk, at whatever main
 * points at now.
 */
export const MOCK_DEPENDENCY_FILES: DependencyFile[] = [
  {
    schema_version: '1.0',
    project_key: 'CORE',
    repository_slug: 'app',
    ref: { name: 'v2.0.0', type: 'tag', commit: '9f3c1ab' },
    generated_at: '2026-09-30',
    packages: [
      {
        id: 'app',
        category: 0,
        version: '2.0.0',
        dependencies: {
          packageA: '2.0.0',
          packageB: '2.0.0',
          packageC: '1.4.2',
          packageE: '3.1.0',
          packageF: '1.9.4',
          packageG: '0.8.7',
        },
      },
      {
        id: 'packageA',
        category: 2,
        version: '2.0.0',
        dependencies: {
          packageD: '>=2.2610.0 <=2.2610.100',
          packageE: '>=3.0.0 <4.0.0',
          packageC: '>=1.4.0 <2.0.0',
        },
      },
      {
        id: 'packageB',
        category: 2,
        version: '2.0.0',
        dependencies: {
          packageC: '>=1.4.0 <2.0.0',
          packageF: '>=1.9.0 <2.0.0',
          packageA: '>=2.0.0 <3.0.0',
        },
      },
      {
        id: 'packageC',
        category: 2,
        version: '1.4.2',
        dependencies: {
          packageE: '>=3.0.0 <4.0.0',
          packageF: '>=1.9.0 <2.0.0',
          packageG: '>=0.8.0 <1.0.0',
        },
      },
      {
        id: 'packageD',
        category: 2,
        version: '2.2610.44',
        dependencies: {
          packageE: '>=3.0.0 <4.0.0',
          // The cycle: A pulls D in, D reaches back to A.
          packageA: '>=2.0.0 <3.0.0',
        },
      },
      { id: 'packageE', category: 1, version: '3.1.0', dependencies: {} },
      { id: 'packageF', category: 1, version: '1.9.4', dependencies: {} },
      { id: 'packageG', category: 1, version: '0.8.7', dependencies: {} },
    ],
  },
  {
    schema_version: '1.0',
    project_key: 'CORE',
    repository_slug: 'app',
    ref: { name: 'v1.1.0', type: 'tag', commit: '2d71e05' },
    generated_at: '2026-08-02',
    packages: [
      {
        id: 'app',
        category: 0,
        version: '1.1.0',
        dependencies: {
          packageA: '1.1.0',
          packageB: '1.1.0',
          packageC: '1.2.0',
          packageE: '2.9.0',
          packageF: '1.8.1',
          packageG: '0.8.2',
        },
      },
      {
        id: 'packageA',
        category: 2,
        version: '1.1.0',
        dependencies: {
          packageD: '>=1.2610.0 <=1.2610.50',
          packageE: '>=2.8.0 <3.0.0',
        },
      },
      {
        id: 'packageB',
        category: 2,
        version: '1.1.0',
        dependencies: {
          packageC: '>=1.1.0 <2.0.0',
          packageF: '>=1.8.0 <2.0.0',
        },
      },
      {
        id: 'packageC',
        category: 2,
        version: '1.2.0',
        dependencies: {
          packageE: '>=2.8.0 <3.0.0',
          packageF: '>=1.8.0 <2.0.0',
          packageG: '>=0.7.0 <1.0.0',
        },
      },
      {
        id: 'packageD',
        category: 2,
        version: '1.2610.12',
        dependencies: {
          packageE: '>=2.8.0 <3.0.0',
        },
      },
      { id: 'packageE', category: 1, version: '2.9.0', dependencies: {} },
      { id: 'packageF', category: 1, version: '1.8.1', dependencies: {} },
      { id: 'packageG', category: 1, version: '0.8.2', dependencies: {} },
    ],
  },
  {
    schema_version: '1.0',
    project_key: 'CORE',
    repository_slug: 'app',
    ref: { name: 'v1.0.0', type: 'tag', commit: 'b04c7f9' },
    generated_at: '2026-06-15',
    packages: [
      {
        id: 'app',
        category: 0,
        version: '1.0.0',
        dependencies: {
          packageA: '1.0.0',
          packageB: '1.0.0',
          packageE: '2.7.3',
          packageF: '1.7.0',
        },
      },
      {
        id: 'packageA',
        category: 2,
        version: '1.0.0',
        dependencies: {
          packageD: '>=0.9.0 <1.0.0',
          packageE: '>=2.7.0 <3.0.0',
        },
      },
      {
        id: 'packageB',
        category: 2,
        version: '1.0.0',
        dependencies: {
          packageC: '>=1.0.0 <2.0.0',
          packageF: '>=1.7.0 <2.0.0',
        },
      },
      {
        id: 'packageC',
        category: 2,
        version: '1.0.0',
        dependencies: {
          packageE: '>=2.7.0 <3.0.0',
        },
      },
      {
        id: 'packageD',
        category: 2,
        version: '0.9.5',
        dependencies: {
          packageE: '>=2.7.0 <3.0.0',
        },
      },
      { id: 'packageE', category: 1, version: '2.7.3', dependencies: {} },
      { id: 'packageF', category: 1, version: '1.7.0', dependencies: {} },
    ],
  },
  {
    schema_version: '1.0',
    project_key: 'CORE',
    repository_slug: 'app',
    ref: { name: 'main', type: 'branch', commit: 'c58a3d1' },
    generated_at: '2026-10-01',
    packages: [
      {
        id: 'app',
        category: 0,
        version: '2.1.0-SNAPSHOT',
        dependencies: {
          packageA: '2.0.0',
          packageB: '2.0.0',
          packageC: '1.4.2',
          packageE: '3.1.0',
          packageF: '1.9.4',
          packageG: '0.8.7',
          packageH: '0.1.0',
        },
      },
      {
        id: 'packageA',
        category: 2,
        version: '2.0.0',
        dependencies: {
          packageD: '>=2.2610.0 <=2.2610.100',
          packageE: '>=3.0.0 <4.0.0',
          packageC: '>=1.4.0 <2.0.0',
        },
      },
      {
        id: 'packageB',
        category: 2,
        version: '2.0.0',
        dependencies: {
          packageC: '>=1.4.0 <2.0.0',
          packageF: '>=1.9.0 <2.0.0',
          packageA: '>=2.0.0 <3.0.0',
        },
      },
      {
        id: 'packageC',
        category: 2,
        version: '1.4.2',
        dependencies: {
          packageE: '>=3.0.0 <4.0.0',
          packageF: '>=1.9.0 <2.0.0',
          packageG: '>=0.8.0 <1.0.0',
        },
      },
      {
        id: 'packageD',
        category: 2,
        version: '2.2610.44',
        dependencies: {
          packageE: '>=3.0.0 <4.0.0',
          packageA: '>=2.0.0 <3.0.0',
        },
      },
      { id: 'packageE', category: 1, version: '3.1.0', dependencies: {} },
      { id: 'packageF', category: 1, version: '1.9.4', dependencies: {} },
      { id: 'packageG', category: 1, version: '0.8.7', dependencies: {} },
      { id: 'packageH', category: 1, version: '0.1.0', dependencies: {} },
    ],
  },
]

/**
 * Stands in for the endpoint that serves one ref's dependency file. A ref the
 * stand-in has nothing for falls back to the newest file it holds, so the
 * canvas still shows the shape of the repository instead of an empty page.
 */
export function loadMockDependencyFile(
  projectKey: string,
  repositorySlug: string,
  ref: string,
): Promise<DependencyFileGraph> {
  const file =
    MOCK_DEPENDENCY_FILES.find((entry) => entry.ref.name === ref) ?? MOCK_DEPENDENCY_FILES[0]
  return Promise.resolve(
    dependencyFileToGraph({
      ...file,
      project_key: projectKey,
      repository_slug: repositorySlug,
    }),
  )
}
