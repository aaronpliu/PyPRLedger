---
name: unit-test-frontend
description: Auto-generate or update frontend Vitest unit tests when new features are added or code changes in frontend/src/. Use when the user says "add tests", "write tests", "unit test", "test frontend", "vitest", "component test", "store test", or when a frontend store, composable, utility, component, or view needs unit test coverage.
---

# Unit Test Frontend

Auto-generate or update frontend Vitest tests for the PyPRLedger project so every new feature or code change in `frontend/` lands with test coverage.

## When to Use

- A new feature or code change affects `frontend/src/` — stores, composables, utils, components, or views
- The user asks to "add tests", "write tests", "unit test", "test frontend", "vitest", "component test", or "store test"
- An existing test file needs new cases for changed behavior
- Coverage fell below the 60% thresholds in `frontend/vitest.config.ts` and needs to be restored

## Phase 1: Detect Changes

Find which frontend files changed:

```bash
git diff --name-only HEAD~1 -- frontend/src/
```

Map each changed file to its test location (mirror the structure under `frontend/tests/`):

| Changed file | Test file |
|---|---|
| `frontend/src/stores/foo.ts` | `frontend/tests/stores/foo.test.ts` |
| `frontend/src/composables/foo.ts` | `frontend/tests/composables/foo.test.ts` |
| `frontend/src/utils/foo.ts` | `frontend/tests/utils/foo.test.ts` |
| `frontend/src/components/**/*.vue` | `frontend/tests/components/<name>.test.ts` |
| `frontend/src/views/**/*.vue` | `frontend/tests/components/` or a view test file |

## Phase 2: Check for Existing Tests

- If the mapped test file **exists**, read it and ADD new test cases for the new/changed behavior. Keep the existing style.
- If it **does not exist**, CREATE it following the conventions below.

## Phase 3: Write Tests Following Conventions

- Import from `vitest`: `describe`, `it`, `expect`, `beforeEach`, `vi`
- Use `@vue/test-utils` (`mount`, `shallowMount`) for components
- Use `@pinia/testing` (`createTestingPinia`) for stores, or `setActivePinia(createPinia())` in `beforeEach`
- Mock API modules with `vi.mock('@/api/...')`
- Use the `@/` alias for imports (configured in `frontend/vitest.config.ts`)
- Cover: initial state, state transitions, actions/async behavior, error handling, edge cases

### Store test pattern

Mirror `frontend/tests/stores/auth.test.ts`:

```ts
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useAuthStore } from '@/stores/auth'
import { createPinia, setActivePinia } from 'pinia'
import { authApi } from '@/api/auth'

vi.mock('@/api/auth', () => ({
  authApi: {
    login: vi.fn(),
    logout: vi.fn().mockResolvedValue(undefined),
    getCurrentUser: vi.fn(),
  },
}))

describe('Auth Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('should initialize with null user', () => {
    const authStore = useAuthStore()
    expect(authStore.user).toBeNull()
    expect(authStore.isAuthenticated).toBe(false)
  })

  it('should set user and tokens on login', async () => {
    vi.mocked(authApi.login).mockResolvedValue({
      access_token: 'token123',
      refresh_token: 'refresh456',
      token_type: 'bearer',
      expires_in: 3600,
      refresh_expires_in: 86400,
    })
    const authStore = useAuthStore()
    const result = await authStore.login({ username: 'testuser', password: 'password123' })
    expect(result).toBe(true)
    expect(authStore.isAuthenticated).toBe(true)
  })
})
```

### Composable test pattern

Mirror `frontend/tests/composables/usePermission.test.ts`:

```ts
import { describe, it, expect, beforeEach } from 'vitest'
import { usePermission } from '@/composables/usePermission'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from '@/stores/auth'

describe('usePermission Composable', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('should return false when not authenticated', () => {
    const authStore = useAuthStore()
    authStore.user = null

    const { hasPermission } = usePermission()
    expect(hasPermission('read', 'review')).toBe(false)
  })
})
```

### Component test pattern

For `.vue` components, use `@vue/test-utils`:

```ts
import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import MyComponent from '@/components/MyComponent.vue'

describe('MyComponent', () => {
  it('should render the title', () => {
    const wrapper = mount(MyComponent, { props: { title: 'Hello' } })
    expect(wrapper.text()).toContain('Hello')
  })
})
```

## Phase 4: Run and Verify

```bash
cd frontend && npm run test:run
cd frontend && npm run test:coverage   # meet 60% thresholds
```

Fix failures or coverage gaps before finishing.

## Phase 5: Checklist

- [ ] All tests green (`npm run test:run`)
- [ ] Coverage thresholds met (`npm run test:coverage` — 60% lines/functions/branches/statements)
- [ ] No `any` abuse in tests (use `vi.mocked()` and proper types)
- [ ] Meaningful assertions — no trivial `expect(true).toBe(true)`
- [ ] Mirrors existing test patterns (see `frontend/tests/stores/auth.test.ts`, `frontend/tests/composables/usePermission.test.ts`)
