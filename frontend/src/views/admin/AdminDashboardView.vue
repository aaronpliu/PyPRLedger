<template>
  <div class="admin-dashboard">
    <el-row :gutter="20" class="stats-row">
      <!-- Total Users -->
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon users">
              <el-icon><User /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.totalUsers }}</div>
              <div class="stat-label">{{ t('admin.dashboard.totalUsers') }}</div>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- Active Roles -->
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon roles">
              <el-icon><Lock /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.totalRoles }}</div>
              <div class="stat-label">{{ t('admin.dashboard.totalRoles') }}</div>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- Active Delegations -->
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon delegations">
              <el-icon><Share /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.activeDelegations }}</div>
              <div class="stat-label">{{ t('admin.dashboard.activeDelegations') }}</div>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- Active Sessions -->
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon sessions">
              <el-icon><Monitor /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.activeSessions }}</div>
              <div class="stat-label">{{ t('admin.dashboard.activeSessions') }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Quick Actions -->
    <el-row :gutter="20" class="quick-actions-row">
      <el-col :span="24">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>{{ t('admin.dashboard.quickActions') }}</span>
            </div>
          </template>
          <div class="action-buttons">
            <el-button type="primary" @click="$router.push({ name: 'UserManagement' })">
              <el-icon><User /></el-icon>
              {{ t('admin.dashboard.manageUsers') }}
            </el-button>
            <el-button type="success" @click="$router.push({ name: 'RoleManagement' })">
              <el-icon><Lock /></el-icon>
              {{ t('admin.dashboard.manageRoles') }}
            </el-button>
            <el-button type="warning" @click="$router.push({ name: 'DelegationManagement' })">
              <el-icon><Share /></el-icon>
              {{ t('admin.dashboard.manageDelegations') }}
            </el-button>
            <el-button type="info" @click="$router.push({ name: 'AuditLogs' })">
              <el-icon><Document /></el-icon>
              {{ t('admin.dashboard.viewAuditLogs') }}
            </el-button>
            <el-button @click="$router.push({ name: 'SessionManagement' })">
              <el-icon><Monitor /></el-icon>
              {{ t('admin.dashboard.manageSessions') }}
            </el-button>
            <el-button type="danger" @click="$router.push({ name: 'SystemSettings' })">
              <el-icon><Setting /></el-icon>
              {{ t('admin.dashboard.systemSettings') }}
            </el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Recent Activity -->
    <el-row :gutter="20">
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>{{ t('admin.dashboard.recentAuditLogs') }}</span>
              <el-button text type="primary" @click="$router.push({ name: 'AuditLogs' })">
                {{ t('common.viewAll') }}
              </el-button>
            </div>
          </template>
          <div v-loading="loadingAuditLogs">
            <el-empty v-if="!loadingAuditLogs && recentAuditLogs.length === 0" :description="t('common.noData')" />
            <el-timeline v-else-if="!loadingAuditLogs">
              <el-timeline-item
                v-for="log in recentAuditLogs"
                :key="log.id"
                :timestamp="formatDate(log.created_at)"
                placement="top"
              >
                <div class="audit-log-item">
                  <el-tag size="small" :type="getActionType(log.action)">{{ log.action }}</el-tag>
                  <span class="log-detail">{{ log.resource_type }}: {{ log.resource_id }}</span>
                </div>
              </el-timeline-item>
            </el-timeline>
          </div>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>{{ t('admin.dashboard.activeSessions') }}</span>
              <el-button text type="primary" @click="$router.push({ name: 'SessionManagement' })">
                {{ t('common.viewAll') }}
              </el-button>
            </div>
          </template>
          <div v-loading="loadingSessions">
            <el-empty v-if="!loadingSessions && recentSessions.length === 0" :description="t('common.noData')" />
            <el-table v-else-if="!loadingSessions" :data="recentSessions" style="width: 100%">
              <el-table-column prop="username" label="User" width="150" />
              <el-table-column prop="ip_address" label="IP Address" width="140" />
              <el-table-column prop="created_at" label="Login Time">
                <template #default="{ row }">
                  {{ formatDate(row.created_at) }}
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { User, Lock, Share, Monitor, Document, Setting } from '@element-plus/icons-vue'
import dayjs from 'dayjs'
import { usersApi } from '@/api/users'
import { rbacApi } from '@/api/rbac'
import { auditApi } from '@/api/audit'
import { authApi } from '@/api/auth'
import type { AuditLog } from '@/types'
import type { AuthSession } from '@/types'

const router = useRouter()
const { t } = useI18n()

// Statistics
const stats = ref({
  totalUsers: 0,
  totalRoles: 0,
  activeDelegations: 0,
  activeSessions: 0,
})

// Recent activity data
const recentAuditLogs = ref<AuditLog[]>([])
const recentSessions = ref<AuthSession[]>([])

// Loading states
const loadingStats = ref(false)
const loadingAuditLogs = ref(false)
const loadingSessions = ref(false)

// Format date
const formatDate = (dateStr: string) => {
  return dayjs(dateStr).format('YYYY-MM-DD HH:mm:ss')
}

// Get action type for tag styling
const getActionType = (action: string): 'success' | 'warning' | 'danger' | 'info' => {
  const actionLower = action.toLowerCase()
  if (actionLower.includes('create') || actionLower.includes('login')) return 'success'
  if (actionLower.includes('update') || actionLower.includes('delegate')) return 'warning'
  if (actionLower.includes('delete') || actionLower.includes('revoke') || actionLower.includes('logout')) return 'danger'
  return 'info'
}

// Load statistics
const loadStats = async () => {
  loadingStats.value = true
  try {
    // Fetch data in parallel for better performance
    const [
      reviewersResponse,
      roles,
      delegations,
      sessions
    ] = await Promise.all([
      usersApi.getReviewers(1).catch(() => ({ total: 0 })),
      rbacApi.getRoles().catch(() => []),
      rbacApi.listDelegations({ status: 'active', include_expired: false }).catch(() => []),
      authApi.getSessions().catch(() => [])
    ])

    stats.value.totalUsers = reviewersResponse.total || 0
    stats.value.totalRoles = Array.isArray(roles) ? roles.length : 0
    stats.value.activeDelegations = Array.isArray(delegations) ? delegations.length : 0
    stats.value.activeSessions = Array.isArray(sessions) ? sessions.length : 0
  } catch (error) {
    console.error('Failed to load statistics:', error)
  } finally {
    loadingStats.value = false
  }
}

// Load recent audit logs
const loadRecentAuditLogs = async () => {
  loadingAuditLogs.value = true
  try {
    const response = await auditApi.getLogs({ limit: 5, offset: 0 })
    recentAuditLogs.value = response.logs || []
  } catch (error) {
    console.error('Failed to load audit logs:', error)
    recentAuditLogs.value = []
  } finally {
    loadingAuditLogs.value = false
  }
}

// Load recent sessions
const loadRecentSessions = async () => {
  loadingSessions.value = true
  try {
    const sessions = await authApi.getSessions()
    // Sort by created_at descending and take top 5
    recentSessions.value = sessions
      .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
      .slice(0, 5)
  } catch (error) {
    console.error('Failed to load sessions:', error)
    recentSessions.value = []
  } finally {
    loadingSessions.value = false
  }
}

onMounted(() => {
  loadStats()
  loadRecentAuditLogs()
  loadRecentSessions()
})
</script>

<style scoped>
.admin-dashboard {
  padding: 0;
}

.stats-row {
  margin-bottom: 20px;
}

.stat-card {
  height: 120px;
}

.stat-content {
  display: flex;
  align-items: center;
  gap: 16px;
  height: 100%;
}

.stat-icon {
  width: 60px;
  height: 60px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  color: white;
}

.stat-icon.users {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.stat-icon.roles {
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
}

.stat-icon.delegations {
  background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
}

.stat-icon.sessions {
  background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 32px;
  font-weight: bold;
  color: var(--el-text-color-primary);
  line-height: 1;
  margin-bottom: 8px;
}

.stat-label {
  font-size: 14px;
  color: var(--el-text-color-secondary);
}

.quick-actions-row {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.action-buttons {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.audit-log-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.log-detail {
  color: var(--el-text-color-regular);
  font-size: 13px;
}
</style>
