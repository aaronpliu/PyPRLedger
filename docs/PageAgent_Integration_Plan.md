# PageAgent Integration Plan

## Architecture

```
[Browser] -- POST /api/v1/llm/proxy/* --> [FastAPI Backend] -- POST real-LLM-endpoint/* --> [LLM Provider]
    |                                         |
    |                                         | Reads apiKey from system_settings table
    |                                         | (key stays server-side)
    PageAgent library                         
    baseURL: '/api/v1/llm/proxy'              
    apiKey: 'proxy' (dummy, ignored by backend)
```

The API key is stored ONLY in the server's `system_settings` table and never exposed to the frontend. The backend proxies all LLM requests.

---

## Files to Create/Modify

### 1. Backend: LLM Proxy Endpoint (new file)
**`/Users/aaronliu/Documents/repositories/PyPRLedger/src/api/v1/endpoints/llm_proxy.py`**

- `router = APIRouter(prefix="/llm/proxy")` 
- `@router.post("/{path:path}")` — catch-all proxy route
  - Reads `llm_base_url`, `llm_api_key`, `llm_model` from `system_settings` (with env fallback)
  - Forwards the request body to the configured LLM provider at `{llm_base_url}/{path}`
  - Adds `Authorization: Bearer {apiKey}` header
  - Streams the response back (supports SSE streaming for chat completions)
  - Requires auth (any logged-in user) to prevent abuse
- Include router in `src/api/v1/api.py`

### 2. Backend: System settings keys
**`/Users/aaronliu/Documents/repositories/PyPRLedger/src/core/config.py`**

Add optional env vars as defaults (injectable via `.env`):
```python
LLM_PROXY_ENABLED: bool = Field(default=False)
LLM_DEFAULT_MODEL: str = Field(default="")
LLM_DEFAULT_BASE_URL: str = Field(default="")
LLM_DEFAULT_API_KEY: str = Field(default="")
```

The proxy endpoint will check `system_settings` first, then fall back to these env vars.

### 3. Backend: Register proxy router
**`/Users/aaronliu/Documents/repositories/PyPRLedger/src/api/v1/api.py`**

Add:
```python
from src.api.v1.endpoints import llm_proxy
api_router.include_router(llm_proxy.router, tags=["llm-proxy"])
```

### 4. Frontend: Install page-agent package
```bash
cd /Users/aaronliu/Documents/repositories/PyPRLedger/frontend
npm install page-agent
```

### 5. Frontend: LLM config API
**`/Users/aaronliu/Documents/repositories/PyPRLedger/frontend/src/api/llm.ts`** (new)

```typescript
import request from '@/utils/request'

export const llmApi = {
  getConfig(): Promise<{ enabled: boolean; model: string; base_url: string }> {
    return request.get('/llm/config')
  },
}
```

Add backend endpoint to return LLM config (without apiKey):
- `GET /api/v1/llm/config` — returns `{ enabled, model, base_url }` from settings

### 6. Frontend: PageAgent composable
**`/Users/aaronliu/Documents/repositories/PyPRLedger/frontend/src/composables/usePageAgent.ts`** (new)

```typescript
import { PageAgent } from 'page-agent'
import { ref, watch } from 'vue'
import { llmApi } from '@/api/llm'
import { useI18n } from 'vue-i18n'

export function usePageAgent() {
  const agent = ref<PageAgent | null>(null)
  const mounted = ref(false)

  async function init() {
    // Fetch LLM config from backend (no apiKey exposed)
    const config = await llmApi.getConfig()
    if (!config.enabled) return

    // Initialize PageAgent with backend proxy baseURL
    agent.value = new PageAgent({
      model: config.model,
      baseURL: '/api/v1/llm/proxy',  // Backend proxy handles auth
      apiKey: 'proxy',               // Dummy key, backend adds real key
      language: getCurrentLanguage(),
    })
    agent.value.mount()
    mounted.value = true
  }

  async function destroy() {
    agent.value?.destroy()
    mounted.value = false
    agent.value = null
  }

  return { agent, mounted, init, destroy }
}
```

### 7. Frontend: Initialize in App.vue
**`/Users/aaronliu/Documents/repositories/PyPRLedger/frontend/src/App.vue`**

In the `<script setup>`:
```typescript
import { usePageAgent } from '@/composables/usePageAgent'
import { useAuthStore } from '@/stores/auth'

const pageAgent = usePageAgent()
const authStore = useAuthStore()

// Auto-init when user logs in
watch(() => authStore.isAuthenticated, async (isAuth) => {
  if (isAuth) {
    await pageAgent.init()
  } else {
    pageAgent.destroy()
  }
}, { immediate: true })
```

### 8. Frontend: Environment variables (optional feature flags)
**`/Users/aaronliu/Documents/repositories/PyPRLedger/frontend/.env`**
```
VITE_PAGE_AGENT_ENABLED=true
```

Not strictly required since the backend controls `llm_enabled`, but useful as a build-time toggle.

## Admin Configuration UI (future, optional)
The LLM settings (`llm_enabled`, `llm_model`, `llm_base_url`, `llm_api_key`) can be configured:
- Via `.env` backend env vars (initial setup)
- Via System Settings management page in Admin UI (future enhancement)

For this initial integration, we'll use `.env` backend config and add the system settings + admin UI as a separate task.

## Backend Endpoints Summary
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/llm/config` | Return LLM config (no apiKey) |
| POST | `/api/v1/llm/proxy/{path}` | Proxy LLM requests with server-side apiKey |

## Order of Implementation
1. Backend: Add config env vars to `Settings`
2. Backend: Create `llm_proxy.py` with config + proxy endpoints
3. Backend: Register router in `api.py`
4. Frontend: `npm install page-agent`
5. Frontend: Create `src/api/llm.ts`
6. Frontend: Create `src/composables/usePageAgent.ts`
7. Frontend: Integrate in `App.vue`
8. Verify with `vue-tsc --noEmit` and `ruff check`
