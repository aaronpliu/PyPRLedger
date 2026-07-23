import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

const STORAGE_KEY = 'task-assignment-navigation-context'

export interface TaskAssignmentNavigationItem {
  id: number
  projectKey: string
  repositorySlug: string
  pullRequestId: string
}

export interface TaskAssignmentNavigationContext {
  items: TaskAssignmentNavigationItem[]
  currentPage: number
  pageSize: number
  totalItems: number
  hasMorePages: boolean
  filters?: {
    project_key?: string
    reviewer?: string
    status?: string
    app_names?: string
    pull_request_user?: string
    severity?: string
    date_from?: string
    date_to?: string
    hide_archived?: boolean
  }
}

function loadStoredContext(): TaskAssignmentNavigationContext | null {
  try {
    const stored = sessionStorage.getItem(STORAGE_KEY)
    if (!stored) {
      return null
    }

    const parsed = JSON.parse(stored)
    if (!parsed || !Array.isArray(parsed.items)) {
      return null
    }

    return {
      items: parsed.items,
      currentPage: parsed.currentPage || 1,
      pageSize: parsed.pageSize || 20,
      totalItems: parsed.totalItems || 0,
      hasMorePages: parsed.hasMorePages || false,
      filters: parsed.filters || {},
    }
  } catch {
    return null
  }
}

export const useTaskAssignmentNavigationStore = defineStore('taskAssignmentNavigation', () => {
  const context = ref<TaskAssignmentNavigationContext | null>(loadStoredContext())

  const items = computed(() => context.value?.items || [])
  const total = computed(() => context.value?.totalItems || 0)
  const currentPage = computed(() => context.value?.currentPage || 1)
  const pageSize = computed(() => context.value?.pageSize || 20)
  const totalPages = computed(() => Math.ceil(total.value / pageSize.value))
  const hasMorePages = computed(() => context.value?.hasMorePages || false)
  const filters = computed(() => context.value?.filters || {})

  const persist = () => {
    if (!context.value || context.value.items.length === 0) {
      sessionStorage.removeItem(STORAGE_KEY)
      return
    }

    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(context.value))
  }

  const setContext = (nextContext: TaskAssignmentNavigationContext) => {
    context.value = nextContext
    persist()
  }

  const clear = () => {
    context.value = null
    persist()
  }

  return {
    items,
    total,
    currentPage,
    pageSize,
    totalPages,
    hasMorePages,
    filters,
    setContext,
    clear,
  }
})
