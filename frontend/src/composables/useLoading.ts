import { ref } from 'vue'
import { ElLoading } from 'element-plus'

interface LoadingOptions {
  text?: string
  fullscreen?: boolean
  background?: string
  lock?: boolean
}

class LoadingService {
  private loadingInstance: any = null
  private loadingCount = 0

  /**
   * Show loading
   */
  show(options: LoadingOptions = {}) {
    if (this.loadingCount === 0) {
      this.loadingInstance = ElLoading.service({
        text: options.text || 'Loading...',
        fullscreen: options.fullscreen ?? true,
        background: options.background || 'rgba(0, 0, 0, 0.7)',
        lock: options.lock ?? true,
      })
    }
    this.loadingCount++
  }

  /**
   * Hide loading
   */
  hide() {
    this.loadingCount--
    if (this.loadingCount <= 0) {
      if (this.loadingInstance) {
        this.loadingInstance.close()
        this.loadingInstance = null
      }
      this.loadingCount = 0
    }
  }

  /**
   * Execute async function with loading
   */
  async withLoading<T>(
    fn: () => Promise<T>,
    options: LoadingOptions = {}
  ): Promise<T> {
    this.show(options)
    try {
      return await fn()
    } finally {
      this.hide()
    }
  }

  /**
   * Force hide all loading instances
   */
  forceHide() {
    if (this.loadingInstance) {
      this.loadingInstance.close()
      this.loadingInstance = null
    }
    this.loadingCount = 0
  }
}

export const loadingService = new LoadingService()

/**
 * Composable for loading state
 */
export function useLoading() {
  const isLoading = ref(false)

  const startLoading = () => {
    isLoading.value = true
    loadingService.show()
  }

  const stopLoading = () => {
    isLoading.value = false
    loadingService.hide()
  }

  const withLoading = async <T>(fn: () => Promise<T>): Promise<T> => {
    startLoading()
    try {
      return await fn()
    } finally {
      stopLoading()
    }
  }

  return {
    isLoading,
    startLoading,
    stopLoading,
    withLoading,
  }
}
