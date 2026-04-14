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

function loadStoredItems(): ReviewNavigationItem[] {
  try {
    const stored = sessionStorage.getItem(STORAGE_KEY)
    if (!stored) {
      return []
    }

    const parsed = JSON.parse(stored)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

export const useReviewNavigationStore = defineStore('reviewNavigation', () => {
  const items = ref<ReviewNavigationItem[]>(loadStoredItems())

  const total = computed(() => items.value.length)

  const persist = () => {
    if (items.value.length === 0) {
      sessionStorage.removeItem(STORAGE_KEY)
      return
    }

    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(items.value))
  }

  const setItems = (nextItems: ReviewNavigationItem[]) => {
    items.value = nextItems
    persist()
  }

  const clear = () => {
    items.value = []
    persist()
  }

  return {
    items,
    total,
    setItems,
    clear,
  }
})