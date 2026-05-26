import request from '@/utils/request'

export interface SearchResult {
  id: string | number
  type: 'review' | 'user' | 'project'
  title: string
  description: string
  url: string
  created_at: string
}

export interface SearchResponse {
  reviews: SearchResult[]
  users: SearchResult[]
  projects: SearchResult[]
}

/**
 * Global search across reviews, users, and projects
 */
export const globalSearch = async (
  query: string,
  type?: 'review' | 'user' | 'project',
  limit = 10
): Promise<SearchResponse> => {
  const params: any = { q: query, limit }
  if (type) {
    params.type = type
  }

  return request({
    url: '/search/',
    method: 'get',
    params,
  })
}
