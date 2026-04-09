import request from '@/utils/request'
import type { AuditLog, AuditLogQuery, AuditStats } from '@/types'

// Audit API
export const auditApi = {
  // Get audit logs with filters
  getLogs(params: AuditLogQuery): Promise<{ total: number; logs: AuditLog[] }> {
    return request.get('/audit/logs', { params })
  },

  // Get specific audit log
  getLogById(logId: number): Promise<AuditLog> {
    return request.get(`/audit/logs/${logId}`)
  },

  // Export audit logs
  exportLogs(params: AuditLogQuery & { format?: 'csv' | 'json' }): Promise<Blob> {
    return request.get('/audit/export', {
      params,
      responseType: 'blob',
    })
  },

  // Get audit statistics
  getStats(days: number = 30): Promise<AuditStats> {
    return request.get('/audit/stats', { params: { days } })
  },
}
