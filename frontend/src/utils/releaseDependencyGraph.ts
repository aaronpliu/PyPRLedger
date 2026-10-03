/**
 * Pure logic behind the release dependency graph: the per-release dependency
 * file a monorepo dependency script is expected to emit, plus the questions the
 * view asks of it - which edges close a cycle, what a given depth keeps, which
 * nodes and edges stay in full colour when one node is picked, and how one
 * release's file becomes the graph the canvas draws.
 */

/** One node of the graph: a project, a workspace package or a dependency. */
export interface ReleaseDependencyGraphNode {
  id: string
  /** Display name; defaults to the id when absent. */
  name?: string
  /** 0 = project (package.json at the repo root), 1 = dependency, 2 = workspace package. */
  category: number
  version?: string
}

export interface ReleaseDependencyGraphLink {
  source: string
  target: string
  /** What the source declares for the target: an exact version or a range. */
  constraint?: string
  /** True for an exact version, false for a range - the two read differently. */
  pinned?: boolean
  /** Marks an edge that closes a cycle - a back edge of the depth-first walk. */
  circular?: boolean
}

export interface ReleaseDependencyGraphData {
  nodes: ReleaseDependencyGraphNode[]
  links: ReleaseDependencyGraphLink[]
}

/**
 * One entry of the per-release dependency file: a package.json of the release,
 * its own shipped version and the constraints it declares for its dependencies.
 * An exact version pins; anything else is the range the author wrote.
 */
export interface ReleaseDependencyGraphPackage {
  id: string
  /** Display name; defaults to the id when absent. */
  name?: string
  /** 0 = project, 1 = dependency, 2 = workspace package. */
  category: number
  version: string
  dependencies: Record<string, string>
}

/** The dependency file of one release of the app. */
export interface ReleaseDependencyGraphRelease {
  version: string
  releasedAt: string
  packages: ReleaseDependencyGraphPackage[]
}

/** One release readied for the canvas: its metadata plus the graph it describes. */
export interface ReleaseDependencyGraph {
  version: string
  releasedAt: string
  data: ReleaseDependencyGraphData
}

/** What kind of ref a dependency file was produced at. */
export type DependencyRefType = 'tag' | 'branch' | 'commit'

/** The ref a dependency file was produced at. */
export interface DependencyFileRef {
  /** Ref name as the provider reports it - a tag name or a branch name. */
  name: string
  type: DependencyRefType
  /** Commit the file was produced at; absent when the producer did not record it. */
  commit?: string
}

/**
 * The dependency file of one repository at one ref: the contract between
 * whatever walks the package.json files of a monorepo and this view.
 *
 * Cycles are not part of the file - they are derived from ``packages`` when the
 * file is read, so a producer never has to compute them. A dependency named by
 * ``dependencies`` but absent from ``packages`` still becomes a node, as an
 * external dependency (category 1).
 */
export interface DependencyFile {
  /** Schema version of this file; bumped when the shape changes. */
  schema_version: string
  project_key: string
  repository_slug: string
  ref: DependencyFileRef
  /** When the file was produced; a branch has no release date of its own. */
  generated_at?: string
  packages: ReleaseDependencyGraphPackage[]
}

/** A dependency file readied for the canvas. */
export type DependencyFileGraph = DependencyFile & ReleaseDependencyGraph

/**
 * Read one dependency file for the canvas: its packages become the graph, and
 * the edges that close a cycle are marked here, once.
 */
export function dependencyFileToGraph(file: DependencyFile): DependencyFileGraph {
  const graph = releaseToGraph({
    version: file.ref.name,
    releasedAt: file.generated_at ?? '',
    packages: file.packages,
  })
  return { ...file, ...graph, data: markCircularLinks(graph.data) }
}

/**
 * An exact semver pins the dependency: no range operator, no wildcard, one
 * number the resolved tree has to carry.
 */
export function isExactVersion(constraint: string): boolean {
  return /^\d+\.\d+\.\d+$/.test(constraint.trim())
}

/**
 * Turn the dependency file of one release into the graph the view draws: every
 * package is a node, every declared dependency is an edge that carries what the
 * source asked for. A dependency the file never declares as a package still
 * becomes a node - the walk has to reach it - as a dependency (category 1).
 */
export function releaseToGraph(release: ReleaseDependencyGraphRelease): ReleaseDependencyGraph {
  const nodes: ReleaseDependencyGraphNode[] = release.packages.map((entry) => ({
    id: entry.id,
    category: entry.category,
    version: entry.version,
  }))

  const known = new Set(nodes.map((node) => node.id))
  const links: ReleaseDependencyGraphLink[] = []
  for (const entry of release.packages) {
    for (const [target, constraint] of Object.entries(entry.dependencies)) {
      if (!known.has(target)) {
        nodes.push({ id: target, category: 1 })
      }
      links.push({ source: entry.id, target, constraint, pinned: isExactVersion(constraint) })
    }
  }

  return { version: release.version, releasedAt: release.releasedAt, data: { nodes, links } }
}

/**
 * The versions the graph's edges carry on their lines: an edge answers to "at
 * which version" only when one was asked for. An exact version pins and reads
 * on the line, while a package's own range declares the bare relationship and
 * reads there as noise rather than information.
 */
export function pinnedEdgeLabels(links: ReleaseDependencyGraphLink[]): ReleaseDependencyGraphLink[] {
  return links.filter((link) => link.pinned && link.constraint)
}

/** The nodes and edges kept in full colour around a picked node. */
export interface ReleaseDependencyGraphHighlight {
  nodes: Set<string>
  links: Set<ReleaseDependencyGraphLink>
}

const WHITE = 0
const GRAY = 1
const BLACK = 2

/**
 * Keep only what sits within `maxDepth` hops of the project roots (category 0,
 * or every node when the data holds no project). `maxDepth` of `Infinity`
 * keeps the whole graph. A package the depth leaves out is left out whole:
 * quoting a dependency without its own dependencies reads as a leaf and lies.
 */
export function withinDepth(
  data: ReleaseDependencyGraphData,
  maxDepth: number,
): ReleaseDependencyGraphData {
  if (!Number.isFinite(maxDepth)) return { nodes: [...data.nodes], links: [...data.links] }

  const roots = data.nodes.filter((node) => node.category === 0).map((node) => node.id)
  const frontier = roots.length > 0 ? roots : data.nodes.map((node) => node.id)

  const outgoing = new Map<string, string[]>()
  for (const link of data.links) {
    const bucket = outgoing.get(link.source)
    if (bucket) bucket.push(link.target)
    else outgoing.set(link.source, [link.target])
  }

  // Breadth first: the first visit to a node is its shortest hop count.
  const depthById = new Map<string, number>()
  const queue: string[] = []
  for (const root of frontier) {
    if (!depthById.has(root)) {
      depthById.set(root, 0)
      queue.push(root)
    }
  }

  while (queue.length > 0) {
    const current = queue.shift() as string
    const nextDepth = (depthById.get(current) as number) + 1
    if (nextDepth > maxDepth) continue
    for (const target of outgoing.get(current) ?? []) {
      if (!depthById.has(target)) {
        depthById.set(target, nextDepth)
        queue.push(target)
      }
    }
  }

  return {
    nodes: data.nodes.filter((node) => depthById.has(node.id)),
    // An edge is kept when its source still expands at this depth: depth one
    // shows what the projects' package.json files name, depth two adds what
    // those dependencies name. The induced alternative leaks edges between
    // siblings - ui-kit -> vue shows up because a project also names vue.
    links: data.links.filter((link) => {
      const sourceDepth = depthById.get(link.source)
      return sourceDepth !== undefined && sourceDepth < maxDepth
    }),
  }
}

/**
 * Mark the edges that close a cycle: the back edges of a depth-first walk over
 * the whole graph. Only the back edge is marked - one per simple cycle found -
 * which is what the red dash on the canvas reports. Edges already marked stay
 * marked, so the function is safe to run over data that carries the flag.
 */
export function markCircularLinks(data: ReleaseDependencyGraphData): ReleaseDependencyGraphData {
  const outgoing = new Map<string, ReleaseDependencyGraphLink[]>()
  for (const link of data.links) {
    const bucket = outgoing.get(link.source)
    if (bucket) bucket.push(link)
    else outgoing.set(link.source, [link])
  }

  const color = new Map<string, number>()
  for (const node of data.nodes) color.set(node.id, WHITE)

  // Iterative walk: a monorepo closure is deep enough to matter.
  for (const node of data.nodes) {
    if (color.get(node.id) !== WHITE) continue
    const stack: Array<{ id: string; edges: ReleaseDependencyGraphLink[]; next: number }> = [
      { id: node.id, edges: outgoing.get(node.id) ?? [], next: 0 },
    ]
    color.set(node.id, GRAY)

    while (stack.length > 0) {
      const frame = stack[stack.length - 1]
      if (frame.next >= frame.edges.length) {
        color.set(frame.id, BLACK)
        stack.pop()
        continue
      }
      const edge = frame.edges[frame.next]
      frame.next += 1

      const targetColor = color.get(edge.target) ?? BLACK
      if (targetColor === GRAY) {
        // The target is still on the stack: this edge closes a cycle.
        edge.circular = true
      } else if (targetColor === WHITE) {
        color.set(edge.target, GRAY)
        stack.push({
          id: edge.target,
          edges: outgoing.get(edge.target) ?? [],
          next: 0,
        })
      }
    }
  }

  return data
}

/**
 * The relationships worth showing in full colour when `selectedId` is picked:
 * its direct dependencies, the packages that depend on it directly, and - when
 * `transitive` is asked for - the whole closure of what it pulls in. Anything
 * outside the sets reads as context and is dimmed. An empty selection keeps
 * the whole graph lit.
 */
export function relatedHighlight(
  data: ReleaseDependencyGraphData,
  selectedId: string | null,
  transitive: boolean,
): ReleaseDependencyGraphHighlight {
  if (!selectedId) {
    return { nodes: new Set<string>(), links: new Set<ReleaseDependencyGraphLink>() }
  }

  const nodes = new Set<string>([selectedId])
  // Who pulls this package in - a reader asks that as often as the other way.
  for (const link of data.links) {
    if (link.target === selectedId) nodes.add(link.source)
  }

  if (transitive) {
    const queue: string[] = [selectedId]
    while (queue.length > 0) {
      const current = queue.shift() as string
      for (const link of data.links) {
        if (link.source === current && !nodes.has(link.target)) {
          nodes.add(link.target)
          queue.push(link.target)
        }
      }
    }
  } else {
    for (const link of data.links) {
      if (link.source === selectedId) nodes.add(link.target)
    }
  }

  const links = new Set(
    data.links.filter((link) => nodes.has(link.source) && nodes.has(link.target)),
  )
  return { nodes, links }
}
