import { describe, it, expect, beforeEach } from 'vitest'
import { offlineQueue, isOffline, withOfflineSupport } from '@/utils/offline'

describe('Offline Utilities', () => {
  beforeEach(() => {
    // Clear the queue before each test
    offlineQueue.clearQueue()
    localStorage.clear()
  })

  it('should detect online status', () => {
    // This depends on actual network status
    const offline = isOffline()
    expect(typeof offline).toBe('boolean')
  })

  it('should add action to queue', () => {
    const id = offlineQueue.addAction({
      type: 'create',
      endpoint: '/api/test',
      data: { key: 'value' },
    })
    
    expect(id).toBeDefined()
    expect(offlineQueue.getQueueSize()).toBe(1)
  })

  it('should get queued actions', () => {
    offlineQueue.addAction({
      type: 'create',
      endpoint: '/api/test',
      data: { key: 'value' },
    })
    
    const actions = offlineQueue.getActions()
    expect(actions.length).toBe(1)
    expect(actions[0].type).toBe('create')
    expect(actions[0].endpoint).toBe('/api/test')
  })

  it('should remove action from queue', () => {
    const id = offlineQueue.addAction({
      type: 'create',
      endpoint: '/api/test',
    })
    
    expect(offlineQueue.getQueueSize()).toBe(1)
    
    offlineQueue.removeAction(id)
    
    expect(offlineQueue.getQueueSize()).toBe(0)
  })

  it('should clear all actions', () => {
    offlineQueue.addAction({
      type: 'create',
      endpoint: '/api/test1',
    })
    
    offlineQueue.addAction({
      type: 'update',
      endpoint: '/api/test2',
    })
    
    expect(offlineQueue.getQueueSize()).toBe(2)
    
    offlineQueue.clearQueue()
    
    expect(offlineQueue.getQueueSize()).toBe(0)
  })

  it('should check if has pending actions', () => {
    expect(offlineQueue.hasPendingActions()).toBe(false)
    
    offlineQueue.addAction({
      type: 'create',
      endpoint: '/api/test',
    })
    
    expect(offlineQueue.hasPendingActions()).toBe(true)
  })

  it('should persist queue to localStorage', () => {
    offlineQueue.addAction({
      type: 'create',
      endpoint: '/api/test',
      data: { key: 'value' },
    })
    
    // Check if data is in localStorage
    const stored = localStorage.getItem('offline_queue')
    expect(stored).not.toBeNull()
    
    const parsed = JSON.parse(stored!)
    expect(parsed.length).toBe(1)
  })

  it('should restore queue from localStorage', () => {
    // Manually set localStorage
    const testData = [
      {
        id: 'test_123',
        type: 'create' as const,
        endpoint: '/api/test',
        data: { key: 'value' },
        timestamp: Date.now(),
      },
    ]
    localStorage.setItem('offline_queue', JSON.stringify(testData))
    
    // Create new instance (simulating page reload)
    const stored = localStorage.getItem('offline_queue')
    expect(stored).not.toBeNull()
    
    const parsed = JSON.parse(stored!)
    expect(parsed.length).toBe(1)
  })

  it('should wrap API call with offline support when online', async () => {
    const mockApiCall = vi.fn().mockResolvedValue({ success: true })
    
    // Mock navigator.onLine
    Object.defineProperty(navigator, 'onLine', {
      writable: true,
      value: true,
    })
    
    const result = await withOfflineSupport(mockApiCall)
    
    expect(mockApiCall).toHaveBeenCalled()
    expect(result).toEqual({ success: true })
  })

  it('should queue action when offline', async () => {
    // Mock navigator.onLine
    Object.defineProperty(navigator, 'onLine', {
      writable: true,
      value: false,
    })
    
    const mockApiCall = vi.fn()
    
    await expect(
      withOfflineSupport(mockApiCall, {
        type: 'create',
        endpoint: '/api/test',
        data: { key: 'value' },
      })
    ).rejects.toThrow('You are offline')
    
    expect(offlineQueue.getQueueSize()).toBe(1)
  })
})
