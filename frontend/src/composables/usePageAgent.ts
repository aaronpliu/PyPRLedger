import { PageAgent } from 'page-agent'
import type { SupportedLanguage } from 'page-agent'
import { ref } from 'vue'
import { llmApi } from '@/api/llm'

export function usePageAgent() {
  const agent = ref<PageAgent | null>(null)
  const initialized = ref(false)

  async function init() {
    // Don't re-initialize if already active
    if (initialized.value) return

    // Fetch LLM config from backend (no apiKey exposed to frontend)
    const config = await llmApi.getConfig()
    if (!config.enabled) return

    // Initialize PageAgent with backend proxy baseURL
    // Panel auto-shows on construction
    agent.value = new PageAgent({
      model: config.model,
      baseURL: '/api/v1/llm/proxy', // Backend proxy handles auth
      apiKey: 'proxy',               // Dummy key, backend adds real key
      language: getSupportedLanguage(),
    })
    initialized.value = true
  }

  /** Dispose agent and clean up */
  function destroy() {
    agent.value?.dispose()
    initialized.value = false
    agent.value = null
  }

  return { agent, initialized, init, destroy }
}

/** Map app locale to PageAgent-supported language */
function getSupportedLanguage(): SupportedLanguage {
  const lang = localStorage.getItem('language') || 'en'
  if (lang === 'zh-CN' || lang === 'zh-TW') return 'zh-CN'
  return 'en-US'
}
