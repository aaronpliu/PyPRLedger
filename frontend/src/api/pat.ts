import request from '@/utils/request'

export interface PersonalAccessToken {
  id: number
  name: string
  prefix: string
  created_at: string
  expires_at: string | null
  last_used_at: string | null
  is_active: boolean
}

export interface PATCreationResponse extends PersonalAccessToken {
  token: string
}

export interface PATListResponse {
  total: number
  items: PersonalAccessToken[]
}

export interface PATCreateRequest {
  name: string
  expires_in_days?: number | null
}

export const patApi = {
  /**
   * List all personal access tokens for current user
   */
  listTokens(includeExpired: boolean = false): Promise<PATListResponse> {
    return request.get('/personal-access-tokens/', {
      params: { include_expired: includeExpired },
    })
  },

  /**
   * Create a new personal access token
   */
  createToken(data: PATCreateRequest): Promise<PATCreationResponse> {
    return request.post('/personal-access-tokens/', data)
  },

  /**
   * Get details of a specific token
   */
  getToken(tokenId: number): Promise<PersonalAccessToken> {
    return request.get(`/personal-access-tokens/${tokenId}`)
  },

  /**
   * Revoke a personal access token
   */
  revokeToken(tokenId: number): Promise<{ message: string }> {
    return request.delete(`/personal-access-tokens/${tokenId}`)
  },
}
