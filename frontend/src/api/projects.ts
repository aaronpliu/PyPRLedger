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

export const projectsApi = {
  listProjects(params?: {
    page?: number
    page_size?: number
    is_active?: boolean
  }): Promise<ProjectListResponse> {
    return request.get('/projects', { params })
  },
}