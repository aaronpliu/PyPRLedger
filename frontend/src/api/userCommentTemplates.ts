import request from '@/utils/request'

export interface UserCommentTemplate {
  id: number
  name: string
  content: string
  created_at: string
  updated_at: string
}

export interface UserCommentTemplateListResponse {
  total: number
  items: UserCommentTemplate[]
}

export interface UserCommentTemplateCreateRequest {
  name: string
  content: string
}

export interface UserCommentTemplateUpdateRequest {
  name?: string
  content?: string
}

export const userCommentTemplatesApi = {
  /**
   * List all comment templates saved by the current user
   */
  listTemplates(): Promise<UserCommentTemplateListResponse> {
    return request.get('/user-comment-templates/')
  },

  /**
   * Create a new personal comment template
   */
  createTemplate(data: UserCommentTemplateCreateRequest): Promise<UserCommentTemplate> {
    return request.post('/user-comment-templates/', data)
  },

  /**
   * Update an existing personal comment template
   */
  updateTemplate(
    templateId: number,
    data: UserCommentTemplateUpdateRequest,
  ): Promise<UserCommentTemplate> {
    return request.put(`/user-comment-templates/${templateId}`, data)
  },

  /**
   * Delete a personal comment template
   */
  deleteTemplate(templateId: number): Promise<{ message: string }> {
    return request.delete(`/user-comment-templates/${templateId}`)
  },
}
