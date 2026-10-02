import { markCircularLinks, releaseToGraph } from '@/utils/releaseDependencyGraph'
import type {
  ReleaseDependencyGraph,
  ReleaseDependencyGraphRelease,
} from '@/utils/releaseDependencyGraph'

/**
 * Stand-in for the dependency files a monorepo dependency script is expected to
 * emit: one per release, in the shape of the package.json files it walked -
 * the app naming its direct dependencies by exact version, the packages it
 * pulls in naming theirs by range. So the graph reads the way the repository
 * works: the app's edges carry the version it ships against, the edges among
 * the packages carry the bare relationship. Newest release first, so the view
 * can open on the latest.
 *
 * The three releases tell the story of the graph changing over time: 1.0.0 knew
 * seven packages, 1.1.0 added G, and 2.0.0 wired the full shape - including
 * the cycle where D reaches back to A, which A also pulls in.
 */
export const MOCK_RELEASES: ReleaseDependencyGraphRelease[] = [
  {
    version: '2.0.0',
    releasedAt: '2026-09-30',
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
    version: '1.1.0',
    releasedAt: '2026-08-02',
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
    version: '1.0.0',
    releasedAt: '2026-06-15',
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
]

/**
 * Stands in for fetching one release's dependency file; the real page swaps
 * this for the endpoint that serves it. The circular edges are marked here,
 * once, the way the script is expected to hand them over.
 */
export function loadMockReleaseDependencyGraph(version: string): Promise<ReleaseDependencyGraph> {
  const release = MOCK_RELEASES.find((entry) => entry.version === version)
  if (!release) {
    return Promise.reject(new Error(`No dependency file for release ${version}`))
  }
  const graph = releaseToGraph(release)
  return Promise.resolve({ ...graph, data: markCircularLinks(graph.data) })
}
