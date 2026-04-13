<template>
  <div class="session-management">
    <el-card>
      <template #header>
        <div class="card-header">
          <div>
            <h2>Session Management</h2>
            <p class="card-subtitle">Inspect active login sessions and revoke them immediately.</p>
          </div>
          <el-button type="primary" :loading="loading" @click="loadSessions">
            Refresh
          </el-button>
        </div>
      </template>

      <el-form :inline="true" class="filter-form" @submit.prevent>
        <el-form-item label="User ID">
          <el-input
            v-model="userIdFilter"
            clearable
            placeholder="Filter by auth user ID"
            style="width: 220px"
            @keyup.enter="loadSessions"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadSessions">Search</el-button>
          <el-button @click="resetFilters">Reset</el-button>
        </el-form-item>
      </el-form>

      <el-alert
        title="Revoking a session invalidates its refresh token immediately."
        type="info"
        :closable="false"
        show-icon
        class="session-alert"
      />

      <el-table :data="sessions" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="auth_user_id" label="User ID" width="100" />
        <el-table-column prop="username" label="Username" width="180" />
        <el-table-column label="Session" min-width="240">
          <template #default="{ row }">
            <div class="session-id-cell">
              <span class="session-id">{{ row.session_id }}</span>
              <el-tag v-if="row.is_current" size="small" type="success">Current</el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="Created" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="Last Activity" width="180">
          <template #default="{ row }">
            {{ formatDate(row.last_activity_at) }}
          </template>
        </el-table-column>
        <el-table-column label="IP Address" width="150">
          <template #default="{ row }">
            {{ row.ip_address || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="User Agent" min-width="260">
          <template #default="{ row }">
            <div class="device-cell" :title="getDeviceDetails(row.user_agent).rawUserAgent || ''">
              <div class="device-label-row">
                <el-icon class="device-icon"><component :is="getDeviceIcon(row.user_agent)" /></el-icon>
                <span class="device-label">{{ getDeviceDetails(row.user_agent).label }}</span>
                <el-tag v-if="row.is_current" size="small" type="primary">This device</el-tag>
              </div>
              <div class="device-meta">
                {{ getDeviceDetails(row.user_agent).browserLabel }} · {{ getDeviceDetails(row.user_agent).osLabel }}
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="Idle Timeout Remaining" width="190">
          <template #default="{ row }">
            <el-tag :type="getExpiryTagType(row.expires_in_seconds)">
              {{ formatDuration(row.expires_in_seconds) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="Actions" width="140" fixed="right">
          <template #default="{ row }">
            <el-button
              size="small"
              type="danger"
              :disabled="revokingSessionId === row.session_id"
              @click="handleRevoke(row)"
            >
              {{ revokingSessionId === row.session_id ? 'Revoking...' : 'Revoke' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty
        v-if="!loading && sessions.length === 0"
        description="No active sessions found for the current filter."
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Cellphone, Monitor } from '@element-plus/icons-vue'
import dayjs from 'dayjs'
import { authApi } from '@/api/auth'
import type { AuthSession } from '@/types'
import { getSessionDeviceDetails } from '@/utils/device'

const loading = ref(false)
const sessions = ref<AuthSession[]>([])
const userIdFilter = ref('')
const revokingSessionId = ref<string | null>(null)

const formatDate = (dateStr: string) => {
  return dayjs(dateStr).format('YYYY-MM-DD HH:mm:ss')
}

const getDeviceDetails = (userAgent: string | null | undefined) => {
  return getSessionDeviceDetails(userAgent)
}

const getDeviceIcon = (userAgent: string | null | undefined) => {
  const category = getDeviceDetails(userAgent).category
  if (category === 'mobile') return Cellphone
  if (category === 'tablet') return Cellphone
  return Monitor
}

const formatDuration = (seconds: number) => {
  const totalSeconds = Math.max(seconds, 0)
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const remainingSeconds = totalSeconds % 60

  if (hours > 0) {
    return `${hours}h ${minutes}m`
  }

  if (minutes > 0) {
    return `${minutes}m ${remainingSeconds}s`
  }

  return `${remainingSeconds}s`
}

const getExpiryTagType = (seconds: number) => {
  if (seconds <= 300) {
    return 'danger'
  }
  if (seconds <= 1800) {
    return 'warning'
  }
  return 'success'
}

const parseUserIdFilter = () => {
  const trimmedValue = userIdFilter.value.trim()
  if (!trimmedValue) {
    return undefined
  }

  const parsedValue = Number(trimmedValue)
  if (!Number.isInteger(parsedValue) || parsedValue <= 0) {
    throw new Error('User ID must be a positive integer')
  }

  return parsedValue
}

const loadSessions = async () => {
  loading.value = true
  try {
    const authUserId = parseUserIdFilter()
    sessions.value = await authApi.getSessions(authUserId)
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Failed to load sessions'
    ElMessage.error(message)
    sessions.value = []
  } finally {
    loading.value = false
  }
}

const resetFilters = () => {
  userIdFilter.value = ''
  loadSessions()
}

const handleRevoke = async (session: AuthSession) => {
  try {
    await ElMessageBox.confirm(
      `Revoke the session for ${session.username} (${session.session_id})?`,
      'Confirm Session Revocation',
      { type: 'warning' }
    )

    revokingSessionId.value = session.session_id
    await authApi.revokeSession(session.session_id)
    ElMessage.success('Session revoked successfully')
    await loadSessions()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('Failed to revoke session')
    }
  } finally {
    revokingSessionId.value = null
  }
}

onMounted(() => {
  loadSessions()
})
</script>

<style scoped>
.session-management {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.card-header h2 {
  margin: 0;
  font-size: 20px;
}

.card-subtitle {
  margin: 6px 0 0;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.filter-form {
  margin-bottom: 16px;
}

.session-alert {
  margin-bottom: 16px;
}

.session-id-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.session-id {
  font-family: 'Consolas', 'Courier New', monospace;
  font-size: 12px;
  word-break: break-all;
}

.device-cell {
  min-width: 0;
}

.device-label-row {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.device-icon {
  color: var(--el-color-primary);
  flex-shrink: 0;
}

.device-label {
  min-width: 0;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.device-meta {
  color: var(--el-text-color-secondary);
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>