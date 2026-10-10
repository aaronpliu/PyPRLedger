import request from '@/utils/request'

export interface ProjectSummary {
  id: number
  project_id: number
  project_name: string
  project_key: string
  project_url: string
  git_provider?: string | null
  created_date: string
  updated_date: string
}

export interface ProjectListResponse {
  items: ProjectSummary[]
  total: number
  page: number
  page_size: number
}

export interface RepositorySummary {
  id: number
  repository_id: number
  repository_name: string
  repository_slug: string
  repository_url: string
  project_id: number
  /**
   * What the project registry says this repository is, where it is registered at
   * all: `application` for one whose releases the dependency database holds,
   * `package` for one that is only a dependency of another. Null where nobody has
   * classified it - including where nothing is registered for it at all.
   */
  registry_kind?: string | null
  created_date: string
  updated_date: string
}

/**
 * What a repository can be, as a filter asks for it.
 *
 * `unclassified` is what a filter names a registration nobody has classified; it is
 * not a stored value, and it covers a repository with no registration at all.
 */
export type RegistryKind = 'application' | 'package' | 'unclassified'

export interface CloudWorkspaceOption {
  slug: string
  name: string
  /** Where the suggestion comes from: config | api | database */
  source: string
}

export interface CloudWorkspaceListResponse {
  workspaces: CloudWorkspaceOption[]
}

export const projectsApi = {
  listProjects(params?: {
    page?: number
    page_size?: number
    is_active?: boolean
  }): Promise<ProjectListResponse> {
    return request.get('/projects', { params })
  },

  // Get all projects (for dropdown)
  async getAllProjects(): Promise<ProjectSummary[]> {
    const response = await request.get('/projects/all')
    return response.data || response
  },

  // Bitbucket Cloud workspaces offered for the repository / release diff forms
  async getCloudWorkspaces(): Promise<CloudWorkspaceOption[]> {
    const response = await request.get('/projects/cloud-workspaces')
    const payload = response.data || response
    return payload?.workspaces ?? []
  },

  /**
   * Get repositories for a specific project.
   *
   * Passing `registryKinds` asks for the repositories the registry has marked with
   * any of them. The pages that read an application's releases ask for
   * `['application', 'unclassified']`: what is marked as a package is left out,
   * because the dependency database holds no release records for it, and everything
   * else keeps behaving as it always did - which is what makes the classification an
   * administrator can make an opt-in rather than a migration nobody can finish.
   */
  async getProjectRepositories(
    projectKey: string,
    registryKinds?: RegistryKind[],
  ): Promise<RepositorySummary[]> {
    const response = await request.get(`/projects/key/${projectKey}/repositories`, {
      params: registryKinds?.length ? { registry_kind: registryKinds.join(',') } : undefined,
    })
    return response.data || response
  },
}