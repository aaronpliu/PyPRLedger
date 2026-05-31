import request from '@/utils/request'

export interface Notification {
  id: number
  user_id: string
  type: string
  title: string
  message: string
  related_id?: string
  related_type?: string
  is_read: boolean
  priority: 'low' | 'normal' | 'high' | 'urgent'
  channel: 'in_app' | 'email' | 'slack'
  created_at: string
  read_at?: string
  expires_at?: string
}

export interface NotificationListResponse {
  items: Notification[]
  total: number
  page: number
  page_size: number
}

export interface NotificationStats {
  unread_count: number
  total_count: number
  by_priority: Record<string, number>
  by_type: Record<string, number>
}

export interface NotificationPreference {
  id: number
  user_id: string
  notification_type: string
  channel_enabled: boolean
  email_enabled: boolean
  in_app_enabled: boolean
  slack_enabled: boolean
  updated_at: string
}

export interface NotificationPreferenceUpdate {
  channel_enabled?: boolean
  email_enabled?: boolean
  in_app_enabled?: boolean
  slack_enabled?: boolean
}

export const notificationsApi = {
  /**
   * Get list of notifications with pagination and filters
   */
  getNotifications(params: {
    page?: number
    page_size?: number
    is_read?: boolean
    notification_type?: string
    priority?: string
  }, config?: Record<string, any>): Promise<NotificationListResponse> {
    return request.get('/notifications/', { params, ...config, _suppressGlobalError: true } as any)
  },

  /**
   * Get count of unread notifications
   */
  getUnreadCount(config?: Record<string, any>): Promise<{ unread_count: number }> {
    return request.get('/notifications/unread-count', { ...config, _suppressGlobalError: true } as any)
  },

  /**
   * Get notification statistics
   */
  getStats(): Promise<NotificationStats> {
    return request.get('/notifications/stats')
  },

  /**
   * Get a single notification by ID
   */
  getNotificationById(id: number): Promise<Notification> {
    return request.get(`/notifications/${id}`)
  },

  /**
   * Mark a notification as read
   */
  markAsRead(id: number): Promise<Notification> {
    return request.post(`/notifications/${id}/read`)
  },

  /**
   * Mark all notifications as read
   */
  markAllAsRead(): Promise<{ marked_count: number; message: string }> {
    return request.post('/notifications/read-all')
  },

  /**
   * Delete a notification
   */
  deleteNotification(id: number): Promise<{ message: string }> {
    return request.delete(`/notifications/${id}`)
  },

  /**
   * Get user's notification preferences
   */
  getPreferences(): Promise<NotificationPreference[]> {
    return request.get('/notifications/preferences')
  },

  /**
   * Update notification preferences for a specific type
   */
  updatePreference(
    notificationType: string,
    updates: NotificationPreferenceUpdate
  ): Promise<NotificationPreference> {
    return request.put(`/notifications/preferences/${notificationType}`, updates)
  },

  /**
   * Send a test notification
   */
  sendTestNotification(data: {
    type?: string
    title?: string
    message?: string
    priority?: string
  }): Promise<Notification> {
    return request.post('/notifications/test', data)
  },
}
