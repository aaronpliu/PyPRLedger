import request from '@/utils/request'

export interface ProjectSummary {
  id: number
  project_id: number
  project_name: string
  project_key: string
  project_url: string
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
  created_date: string
  updated_date: string
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

  // Get repositories for a specific project
  async getProjectRepositories(projectKey: string): Promise<RepositorySummary[]> {
    const response = await request.get(`/projects/key/${projectKey}/repositories`)
    return response.data || response
  },
}