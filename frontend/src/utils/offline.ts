/**
 * Offline Support Utilities
 * Handles queued actions when offline and syncs when back online
 */

export interface QueuedAction {
  id: string
  type: 'create' | 'update' | 'delete'
  endpoint: string
  data?: any
  timestamp: number
}

class OfflineQueue {
  private queue: QueuedAction[] = []
  private readonly STORAGE_KEY = 'offline_queue'

  constructor() {
    this.loadFromStorage()
    this.setupSyncListener()
  }

  /**
   * Add action to queue when offline
   */
  addAction(action: Omit<QueuedAction, 'id' | 'timestamp'>): string {
    const queuedAction: QueuedAction = {
      ...action,
      id: `${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      timestamp: Date.now(),
    }

    this.queue.push(queuedAction)
    this.saveToStorage()

    console.log('Action queued:', queuedAction)
    return queuedAction.id
  }

  /**
   * Get all queued actions
   */
  getActions(): QueuedAction[] {
    return [...this.queue]
  }

  /**
   * Remove action from queue
   */
  removeAction(id: string): void {
    this.queue = this.queue.filter(action => action.id !== id)
    this.saveToStorage()
  }

  /**
   * Clear all queued actions
   */
  clearQueue(): void {
    this.queue = []
    this.saveToStorage()
  }

  /**
   * Check if there are pending actions
   */
  hasPendingActions(): boolean {
    return this.queue.length > 0
  }

  /**
   * Get queue size
   */
  getQueueSize(): number {
    return this.queue.length
  }

  /**
   * Sync queued actions when back online
   */
  async syncQueue(): Promise<void> {
    if (!navigator.onLine || this.queue.length === 0) {
      return
    }

    console.log(`Syncing ${this.queue.length} queued actions...`)

    const failedActions: QueuedAction[] = []

    for (const action of this.queue) {
      try {
        await this.executeAction(action)
        console.log('Synced action:', action.id)
      } catch (error) {
        console.error('Failed to sync action:', action.id, error)
        failedActions.push(action)
      }
    }

    // Keep only failed actions in queue
    this.queue = failedActions
    this.saveToStorage()

    if (failedActions.length === 0) {
      console.log('All actions synced successfully')
    } else {
      console.warn(`${failedActions.length} actions failed to sync`)
    }
  }

  /**
   * Execute a single queued action
   */
  private async executeAction(action: QueuedAction): Promise<void> {
    // This would make actual API calls
    // For now, just simulate
    await new Promise(resolve => setTimeout(resolve, 500))

    // In production, you would do:
    // switch (action.type) {
    //   case 'create':
    //     await api.post(action.endpoint, action.data)
    //     break
    //   case 'update':
    //     await api.put(action.endpoint, action.data)
    //     break
    //   case 'delete':
    //     await api.delete(action.endpoint)
    //     break
    // }
  }

  /**
   * Save queue to localStorage
   */
  private saveToStorage(): void {
    try {
      localStorage.setItem(this.STORAGE_KEY, JSON.stringify(this.queue))
    } catch (error) {
      console.error('Failed to save offline queue:', error)
    }
  }

  /**
   * Load queue from localStorage
   */
  private loadFromStorage(): void {
    try {
      const stored = localStorage.getItem(this.STORAGE_KEY)
      if (stored) {
        this.queue = JSON.parse(stored)
      }
    } catch (error) {
      console.error('Failed to load offline queue:', error)
    }
  }

  /**
   * Setup listener for online/offline events
   */
  private setupSyncListener(): void {
    window.addEventListener('online', () => {
      console.log('Back online, syncing queued actions...')
      this.syncQueue()
    })
  }
}

// Singleton instance
export const offlineQueue = new OfflineQueue()

/**
 * Check if user is offline
 */
export function isOffline(): boolean {
  return !navigator.onLine
}

/**
 * Wrap API call with offline support
 */
export async function withOfflineSupport<T>(
  apiCall: () => Promise<T>,
  fallbackAction?: Omit<QueuedAction, 'id' | 'timestamp'>
): Promise<T> {
  // If online, execute normally
  if (navigator.onLine) {
    try {
      return await apiCall()
    } catch (error) {
      // If request failed and we have a fallback, queue it
      if (fallbackAction) {
        offlineQueue.addAction(fallbackAction)
        throw new Error('Request failed, added to offline queue')
      }
      throw error
    }
  }

  // If offline, queue the action
  if (fallbackAction) {
    offlineQueue.addAction(fallbackAction)
    throw new Error('You are offline. Action queued for later sync.')
  }

  throw new Error('You are offline')
}
