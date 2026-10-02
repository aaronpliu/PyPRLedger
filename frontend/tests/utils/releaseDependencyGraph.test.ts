import { describe, it, expect } from 'vitest'
import {
  isExactVersion,
  markCircularLinks,
  releaseToGraph,
  relatedHighlight,
  withinDepth,
} from '@/utils/releaseDependencyGraph'
import type { ReleaseDependencyGraphData } from '@/utils/releaseDependencyGraph'
import { MOCK_RELEASES } from '@/views/releases/releaseDependencyGraphMock'

/**
 * The shape the question asked about: projectA pulls packageA and packageB,
 * packageA pulls packageE and packageF, packageB pulls packageJ - the walk
 * continues for as long as the dependencies have dependencies.
 */
function fixture(): ReleaseDependencyGraphData {
  return {
    nodes: [
      { id: 'projectA', category: 0 },
      { id: 'packageA', category: 2 },
      { id: 'packageB', category: 2 },
      { id: 'packageE', category: 1 },
      { id: 'packageF', category: 1 },
      { id: 'packageJ', category: 1 },
    ],
    links: [
      { source: 'projectA', target: 'packageA' },
      { source: 'projectA', target: 'packageB' },
      { source: 'packageA', target: 'packageE' },
      { source: 'packageA', target: 'packageF' },
      { source: 'packageB', target: 'packageJ' },
    ],
  }
}

/** The dependency file of one mock release, read as the graph the view draws. */
function graphOf(version: string): ReleaseDependencyGraphData {
  const release = MOCK_RELEASES.find((entry) => entry.version === version)
  if (!release) throw new Error(`No mock release ${version}`)
  return releaseToGraph(release).data
}

describe('withinDepth', () => {
  it('keeps the project and its direct dependencies at depth one', () => {
    const view = withinDepth(fixture(), 1)

    expect(view.nodes.map((node) => node.id).sort()).toEqual([
      'packageA',
      'packageB',
      'projectA',
    ])
    expect(view.links).toHaveLength(2)
    // the dependencies of the dependencies stay out until the depth says so
    expect(view.nodes.map((node) => node.id)).not.toContain('packageE')
  })

  it('continues the recursion at depth two', () => {
    const view = withinDepth(fixture(), 2)

    expect(view.nodes.map((node) => node.id).sort()).toEqual([
      'packageA',
      'packageB',
      'packageE',
      'packageF',
      'packageJ',
      'projectA',
    ])
    expect(view.links).toHaveLength(5)
  })

  it('keeps everything when the depth is unlimited', () => {
    const view = withinDepth(fixture(), Infinity)

    expect(view.nodes).toHaveLength(fixture().nodes.length)
    expect(view.links).toHaveLength(fixture().links.length)
  })

  it('does not quote a package without its own dependencies', () => {
    // depth one contains packageA, so packageA's edges to E and F are not
    // shown: showing them would present them as leaves of the project
    const view = withinDepth(fixture(), 1)

    expect(view.links.map((link) => link.target)).not.toContain('packageE')
    expect(view.links.map((link) => link.target)).not.toContain('packageF')
  })

  it('shows only what the app names at depth one, on the mock data', () => {
    const view = withinDepth(graphOf('2.0.0'), 1)

    // the app and the six packages its dependency file names
    expect(view.nodes).toHaveLength(7)
    // six edges, every one of them out of the app: no edge of a package
    // leaks in, not even to a package the app also names
    expect(view.links).toHaveLength(6)
    expect(view.links.every((link) => link.source === 'app')).toBe(true)
    expect(view.nodes.map((node) => node.id)).not.toContain('packageD')
  })

  it('adds what the dependencies name at depth two', () => {
    const view = withinDepth(graphOf('2.0.0'), 2)

    // every package of the release is two hops away at most
    expect(view.nodes).toHaveLength(8)
    // the edges out of the app and out of the packages it names; packageD
    // sits at depth two, so what it names waits for the unlimited depth
    expect(view.links).toHaveLength(15)
    expect(view.links.some((link) => link.source === 'packageA')).toBe(true)
    expect(view.links.map((link) => link.target)).toContain('packageD')
    expect(view.links.some((link) => link.source === 'packageD')).toBe(false)
  })
})

describe('markCircularLinks', () => {
  it('leaves an acyclic graph alone', () => {
    const data = markCircularLinks(fixture())

    expect(data.links.filter((link) => link.circular)).toHaveLength(0)
  })

  it('leaves the release that knows no cycle alone', () => {
    const data = markCircularLinks(graphOf('1.0.0'))

    expect(data.links.filter((link) => link.circular)).toHaveLength(0)
  })

  it('marks the edge that closes a cycle in the release that has one', () => {
    const data = markCircularLinks(graphOf('2.0.0'))

    const circular = data.links.filter((link) => link.circular)
    expect(circular).toHaveLength(1)
    // packageA pulls packageD in, packageD reaches back to packageA
    expect([circular[0].source, circular[0].target].sort()).toEqual([
      'packageA',
      'packageD',
    ])
  })
})

describe('relatedHighlight', () => {
  it('lights the whole graph when nothing is picked', () => {
    const { nodes, links } = relatedHighlight(fixture(), null, false)

    expect(nodes.size).toBe(0)
    expect(links.size).toBe(0)
  })

  it('keeps the direct dependencies and the direct dependents', () => {
    const data = fixture()
    const { nodes, links } = relatedHighlight(data, 'packageA', false)

    expect(nodes).toEqual(
      new Set(['packageA', 'packageE', 'packageF', 'projectA']),
    )
    expect(links).toEqual(
      new Set([
        data.links[0], // projectA -> packageA
        data.links[2], // packageA -> packageE
        data.links[3], // packageA -> packageF
      ]),
    )
    // packageB depends on neither side of the pick
    expect(nodes.has('packageB')).toBe(false)
  })

  it('walks the whole closure when asked to be transitive', () => {
    const data = fixture()
    const { nodes } = relatedHighlight(data, 'projectA', true)

    expect(nodes).toEqual(new Set(['projectA', 'packageA', 'packageB', 'packageE', 'packageF', 'packageJ']))
  })

  it('terminates on a cycle instead of spinning between two packages', () => {
    const { nodes } = relatedHighlight(graphOf('2.0.0'), 'app', true)

    // the closure crosses the packageA <-> packageD cycle once
    expect(nodes.has('packageA')).toBe(true)
    expect(nodes.has('packageD')).toBe(true)
    // every package of the release is reachable from the app
    expect(nodes.size).toBe(8)
  })

  it('shows a leaf with nothing but its dependents', () => {
    const { nodes } = relatedHighlight(graphOf('2.0.0'), 'packageG', false)

    // only the app and packageC name packageG
    expect(nodes).toEqual(new Set(['packageG', 'app', 'packageC']))
  })
})

describe('isExactVersion', () => {
  it('takes an exact version for pinned', () => {
    expect(isExactVersion('2.0.0')).toBe(true)
    expect(isExactVersion('2.2610.44')).toBe(true)
  })

  it('refuses anything that declares a range', () => {
    expect(isExactVersion('>=2.2610.0 <=2.2610.100')).toBe(false)
    expect(isExactVersion('>=1.4.0 <2.0.0')).toBe(false)
    expect(isExactVersion('^1.2.3')).toBe(false)
    expect(isExactVersion('1.2.3-beta.1')).toBe(false)
  })
})

describe('releaseToGraph', () => {
  const latest = MOCK_RELEASES[0]

  it('pins the app to exact versions and lets the packages declare ranges', () => {
    const { data } = releaseToGraph(latest)

    const fromApp = data.links.filter((link) => link.source === 'app')
    expect(fromApp).toHaveLength(6)
    expect(fromApp.every((link) => link.pinned)).toBe(true)
    // the app names packageC by the version the release ships
    expect(fromApp.find((link) => link.target === 'packageC')?.constraint).toBe('1.4.2')

    const fromA = data.links.filter((link) => link.source === 'packageA')
    expect(fromA.every((link) => !link.pinned)).toBe(true)
    expect(fromA.find((link) => link.target === 'packageD')?.constraint).toBe(
      '>=2.2610.0 <=2.2610.100',
    )
  })

  it('carries the version each package ships, not the constraints it declares', () => {
    const { data } = releaseToGraph(latest)

    expect(data.nodes.find((node) => node.id === 'app')?.version).toBe('2.0.0')
    expect(data.nodes.find((node) => node.id === 'packageD')?.version).toBe('2.2610.44')
    expect(data.nodes.find((node) => node.id === 'packageE')?.version).toBe('3.1.0')
  })

  it('reads the release metadata along with the graph', () => {
    const graph = releaseToGraph(latest)

    expect(graph.version).toBe('2.0.0')
    expect(graph.releasedAt).toBe('2026-09-30')
  })

  it('draws a different graph for every release', () => {
    const first = releaseToGraph(MOCK_RELEASES[2]).data
    const latestGraph = releaseToGraph(latest).data

    // 1.0.0 never named packageG, 2.0.0 does
    expect(first.nodes.map((node) => node.id)).not.toContain('packageG')
    expect(latestGraph.nodes.map((node) => node.id)).toContain('packageG')
    // and the cycle between A and D is a later arrival: 1.0.0 lets D point at
    // E only, 2.0.0 has it reach back to A
    expect(first.links.some((link) => link.source === 'packageD' && link.target === 'packageA')).toBe(
      false,
    )
    expect(
      latestGraph.links.some((link) => link.source === 'packageD' && link.target === 'packageA'),
    ).toBe(true)
  })

  it('adds a node for a dependency the file never declares as a package', () => {
    const { data } = releaseToGraph({
      version: '1.0.0',
      releasedAt: '2026-01-01',
      packages: [
        {
          id: 'app',
          category: 0,
          version: '1.0.0',
          dependencies: { ghost: '2.0.0' },
        },
      ],
    })

    expect(data.nodes).toHaveLength(2)
    const ghost = data.nodes.find((node) => node.id === 'ghost')
    expect(ghost?.category).toBe(1)
    expect(ghost?.version).toBeUndefined()
    expect(data.links[0]).toMatchObject({ source: 'app', target: 'ghost', pinned: true })
  })
})
