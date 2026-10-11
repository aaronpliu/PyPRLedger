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

/** What to offer out of a project's repositories. */
export interface RepositoryFilters {
  /**
   * Offer the repositories the registry marks as applications, falling back to
   * everything not marked as a package when the project has no application yet.
   *
   * This is what the pages that read an application's releases want: an
   * administrator naming an application is what decides their picker, and a project
   * nobody has classified keeps offering every repository it has.
   */
  preferApplications?: boolean
}

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
   * The pages that read an application's releases pass `preferApplications`, which
   * leaves out what is marked as a package - the dependency database holds no release
   * records for one - and narrows the list to the applications once an administrator
   * has named any.
   */
  async getProjectRepositories(
    projectKey: string,
    filters: RepositoryFilters = {},
  ): Promise<RepositorySummary[]> {
    const response = await request.get(`/projects/key/${projectKey}/repositories`, {
      params: filters.preferApplications ? { prefer_applications: true } : undefined,
    })
    return response.data || response
  },
}