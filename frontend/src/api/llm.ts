import request from '@/utils/request'

export interface LlmConfig {
  enabled: boolean
  model: string
  base_url: string
}

export const llmApi = {
  /** Fetch LLM configuration from backend (apiKey excluded) */
  getConfig(): Promise<LlmConfig> {
    return request.get('/llm/config')
  },
}
