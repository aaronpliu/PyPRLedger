import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

const STORAGE_KEY = 'review-navigation-context'

export interface ReviewNavigationItem {
  id: number
  projectKey: string
  repositorySlug: string
  pullRequestId: string
  reviewer: string
  sourceFilename: string
}

export interface ReviewNavigationContext {
  items: ReviewNavigationItem[]
  currentPage: number
  pageSize: number
  totalItems: number
  hasMorePages: boolean
}

function loadStoredContext(): ReviewNavigationContext | null {
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
    }
  } catch {
    return null
  }
}

export const useReviewNavigationStore = defineStore('reviewNavigation', () => {
  const context = ref<ReviewNavigationContext | null>(loadStoredContext())

  const items = computed(() => context.value?.items || [])
  const total = computed(() => context.value?.totalItems || 0)
  const currentPage = computed(() => context.value?.currentPage || 1)
  const pageSize = computed(() => context.value?.pageSize || 20)
  const totalPages = computed(() => Math.ceil(total.value / pageSize.value))
  const hasMorePages = computed(() => context.value?.hasMorePages || false)

  const persist = () => {
    if (!context.value || context.value.items.length === 0) {
      sessionStorage.removeItem(STORAGE_KEY)
      return
    }

    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(context.value))
  }

  const setContext = (nextContext: ReviewNavigationContext) => {
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
    setContext,
    clear,
  }
})
