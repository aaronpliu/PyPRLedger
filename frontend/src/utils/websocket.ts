import { io, Socket } from 'socket.io-client'
import { ElNotification } from 'element-plus'

export interface NotificationData {
  id: string
  title: string
  message: string
  type: 'success' | 'warning' | 'error' | 'info'
  data?: any
  created_at: string
}

class WebSocketService {
  private socket: Socket | null = null
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private reconnectDelay = 3000

  connect(userId: number) {
    if (this.socket?.connected) {
      console.log('WebSocket already connected')
      return
    }

    const wsUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:8000'
    
    this.socket = io(wsUrl, {
      query: { user_id: userId },
      reconnection: true,
      reconnectionAttempts: this.maxReconnectAttempts,
      reconnectionDelay: this.reconnectDelay,
    })

    this.socket.on('connect', () => {
      console.log('WebSocket connected:', this.socket?.id)
      this.reconnectAttempts = 0
      ElNotification({
        title: 'Connected',
        message: 'Real-time notifications enabled',
        type: 'success',
        duration: 2000,
      })
    })

    this.socket.on('disconnect', (reason) => {
      console.log('WebSocket disconnected:', reason)
      if (reason === 'io server disconnect') {
        // Server disconnected, try to reconnect
        this.socket?.connect()
      }
    })

    this.socket.on('connect_error', (error) => {
      console.error('WebSocket connection error:', error)
      this.reconnectAttempts++
      
      if (this.reconnectAttempts >= this.maxReconnectAttempts) {
        ElNotification({
          title: 'Connection Failed',
          message: 'Unable to connect to notification service',
          type: 'error',
          duration: 5000,
        })
      }
    })

    // Listen for notifications
    this.socket.on('notification', (data: NotificationData) => {
      this.handleNotification(data)
    })

    // Listen for review updates
    this.socket.on('review_updated', (data: any) => {
      this.handleNotification({
        id: Date.now().toString(),
        title: 'Review Updated',
        message: `Review #${data.review_id} has been updated`,
        type: 'info',
        data,
        created_at: new Date().toISOString(),
      })
    })

    // Listen for score updates
    this.socket.on('score_updated', (data: any) => {
      this.handleNotification({
        id: Date.now().toString(),
        title: 'Score Updated',
        message: `New score added to review #${data.review_id}`,
        type: 'info',
        data,
        created_at: new Date().toISOString(),
      })
    })
  }

  disconnect() {
    if (this.socket) {
      this.socket.disconnect()
      this.socket = null
      console.log('WebSocket disconnected')
    }
  }

  private handleNotification(data: NotificationData) {
    // Show Element Plus notification
    ElNotification({
      title: data.title,
      message: data.message,
      type: data.type,
      duration: 5000,
      onClick: () => {
        // Handle notification click
        console.log('Notification clicked:', data)
      },
    })

    // Dispatch custom event for components to listen
    window.dispatchEvent(new CustomEvent('notification-received', { detail: data }))
  }

  emit(event: string, data: any) {
    if (this.socket?.connected) {
      this.socket.emit(event, data)
    } else {
      console.warn('WebSocket not connected')
    }
  }

  isConnected(): boolean {
    return this.socket?.connected || false
  }
}

export const wsService = new WebSocketService()
