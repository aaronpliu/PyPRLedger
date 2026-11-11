import request from '@/utils/request'

export interface RepositoryCatalogItem {
  project_key: string
  repository_slug: string
  app_name?: string | null
}

export interface RepositoryAccessItem {
  project_key: string
  repository_slug: string
}

export interface RepositoryAccessResponse {
  subject_type: string
  subject_id: number
  subject_username: string | null
  items: Array<Record<string, unknown>>
  total: number
}

export const repositoryAccessApi = {
  getCatalog(): Promise<RepositoryCatalogItem[]> {
    return request.get('/repository-access/catalog')
  },

  getAccess(subjectType: string, subjectId: number): Promise<RepositoryAccessResponse> {
    return request.get(`/repository-access/${subjectType}/${subjectId}`)
  },

  replaceAccess(
    subjectType: string,
    subjectId: number,
    items: RepositoryAccessItem[]
  ): Promise<RepositoryAccessResponse> {
    return request.put(`/repository-access/${subjectType}/${subjectId}`, { items })
  },
}
