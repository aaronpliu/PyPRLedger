import request from '@/utils/request'
import type { DependencyFile } from '@/utils/releaseDependencyGraph'

export interface DependencyGraphReadRequest {
  project_key: string
  repository_slug: string
  ref: string
  git_provider?: string | null
  /** Bitbucket Cloud only: workspace holding the repository (falls back to project_key). */
  workspace_slug?: string | null
}

export const releaseDependencyGraphApi = {
  /**
   * Consolidate the dependency database into the graph of one ref. The
   * repository is resolved to an application through the project registry,
   * since the database holds what an application shipped.
   */
  read(payload: DependencyGraphReadRequest): Promise<DependencyFile> {
    return request.post('/release/dependency-graph/read', payload)
  },
}
