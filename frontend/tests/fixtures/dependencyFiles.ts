import type { DependencyFile } from '@/utils/releaseDependencyGraph'

/**
 * The dependency files the tests read, in the shape the API serves: one per
 * ref, mirroring the package.json files a monorepo walk produces - the project
 * naming its modules by exact version, the packages naming theirs by range.
 *
 * The three tags tell the story of the graph changing over time: 1.0.0 knew
 * seven packages, 1.1.0 added G, and 2.0.0 wired the full shape - including the
 * cycle where D reaches back to A, which A also pulls in. The branch is what a
 * walk outside a release produces: the same shape, at whatever main points at.
 */
export const DEPENDENCY_FILES: DependencyFile[] = [
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

/** The file the given ref names, falling back to the newest one. */
export function dependencyFileOf(ref: string): DependencyFile {
  return DEPENDENCY_FILES.find((entry) => entry.ref.name === ref) ?? DEPENDENCY_FILES[0]
}
