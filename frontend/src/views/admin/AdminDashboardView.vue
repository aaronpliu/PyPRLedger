<template>
  <div class="admin-dashboard">
    <header class="dashboard-header">
      <div>
        <h2>{{ t('admin.dashboard.title') }}</h2>
        <p class="dashboard-subtitle">{{ t('admin.dashboard.subtitle') }}</p>
      </div>
      <el-button
        type="primary"
        :loading="refreshing"
        data-test="dashboard-refresh"
        @click="refreshAll"
      >
        <el-icon><Refresh /></el-icon>
        {{ t('common.refresh') }}
      </el-button>
    </header>

    <!-- Headline numbers: a CSS grid rather than a fixed four-column row, so the
         cards keep their shape on narrow screens. -->
    <div class="stats-grid">
      <div
        v-for="card in statCards"
        :key="card.key"
        class="stat-card"
        :class="`stat-card--${card.tone}`"
      >
        <span class="stat-card__accent" />
        <div class="stat-card__body">
          <div class="stat-card__icon">
            <el-icon><component :is="card.icon" /></el-icon>
          </div>
          <div class="stat-card__info">
            <div class="stat-card__label">{{ card.label }}</div>
            <div v-if="loadingStats" class="stat-card__skeleton" />
            <div v-else class="stat-card__value" data-test="stat-value">{{ card.value }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Shortcuts stay neutral; only their icon carries a semantic colour, so
         six actions no longer read as six competing coloured buttons. -->
    <section class="panel">
      <div class="panel__header">
        <h3>{{ t('admin.dashboard.quickActions') }}</h3>
      </div>
      <div class="quick-actions" data-test="quick-action">
        <button
          v-for="action in quickActions"
          :key="action.name"
          type="button"
          class="quick-action"
          :class="`quick-action--${action.tone}`"
          @click="go(action.name)"
        >
          <span class="quick-action__icon">
            <el-icon><component :is="action.icon" /></el-icon>
          </span>
          <span class="quick-action__label">{{ action.label }}</span>
          <el-icon class="quick-action__arrow"><ArrowRight /></el-icon>
        </button>
      </div>
    </section>

    <div class="activity-grid">
      <section class="panel">
        <div class="panel__header">
          <h3>{{ t('admin.dashboard.recentAuditLogs') }}</h3>
          <el-button text type="primary" @click="go('AuditLogs')">
            {{ t('common.viewAll') }}
          </el-button>
        </div>
        <div v-loading="loadingAuditLogs" class="panel__body">
          <el-empty
            v-if="!loadingAuditLogs && recentAuditLogs.length === 0"
            :description="t('common.noData')"
          />
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
      </section>

      <section class="panel">
        <div class="panel__header">
          <h3>{{ t('admin.dashboard.activeSessions') }}</h3>
          <el-button text type="primary" @click="go('SessionManagement')">
            {{ t('common.viewAll') }}
          </el-button>
        </div>
        <div v-loading="loadingSessions" class="panel__body">
          <el-empty
            v-if="!loadingSessions && recentSessions.length === 0"
            :description="t('common.noData')"
          />
          <el-table v-else-if="!loadingSessions" :data="recentSessions" style="width: 100%">
            <el-table-column prop="username" :label="t('admin.dashboard.sessionUser')" width="150" />
            <el-table-column prop="ip_address" :label="t('admin.dashboard.ipAddress')" width="140" />
            <el-table-column prop="created_at" :label="t('admin.dashboard.loginTime')">
              <template #default="{ row }">
                {{ formatDate(row.created_at) }}
              </template>
            </el-table-column>
          </el-table>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  ArrowRight,
  Document,
  Lock,
  Monitor,
  Refresh,
  Setting,
  Share,
  User,
} from '@element-plus/icons-vue'
import dayjs from 'dayjs'
import { usersApi } from '@/api/users'
import { rbacApi } from '@/api/rbac'
import { auditApi } from '@/api/audit'
import { authApi } from '@/api/auth'
import type { AuditLog, AuthSession } from '@/types'

const router = useRouter()
const { t } = useI18n()

const stats = ref({
  totalUsers: 0,
  totalRoles: 0,
  activeDelegations: 0,
  activeSessions: 0,
})

const recentAuditLogs = ref<AuditLog[]>([])
// One request feeds both the session count and the recent-session list.
const allSessions = ref<AuthSession[]>([])
const recentSessions = computed(() =>
  [...allSessions.value]
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 5)
)

const loadingStats = ref(false)
const loadingAuditLogs = ref(false)
const loadingSessions = ref(false)
const refreshing = ref(false)

const statCards = computed(() => [
  {
    key: 'users',
    label: t('admin.dashboard.totalUsers'),
    value: stats.value.totalUsers,
    icon: User,
    tone: 'primary',
  },
  {
    key: 'roles',
    label: t('admin.dashboard.totalRoles'),
    value: stats.value.totalRoles,
    icon: Lock,
    tone: 'danger',
  },
  {
    key: 'delegations',
    label: t('admin.dashboard.activeDelegations'),
    value: stats.value.activeDelegations,
    icon: Share,
    tone: 'warning',
  },
  {
    key: 'sessions',
    label: t('admin.dashboard.activeSessions'),
    value: stats.value.activeSessions,
    icon: Monitor,
    tone: 'success',
  },
])

const quickActions = computed(() => [
  { name: 'UserManagement', label: t('admin.dashboard.manageUsers'), icon: User, tone: 'primary' },
  { name: 'RoleManagement', label: t('admin.dashboard.manageRoles'), icon: Lock, tone: 'danger' },
  {
    name: 'DelegationManagement',
    label: t('admin.dashboard.manageDelegations'),
    icon: Share,
    tone: 'warning',
  },
  { name: 'AuditLogs', label: t('admin.dashboard.viewAuditLogs'), icon: Document, tone: 'info' },
  { name: 'SessionManagement', label: t('admin.dashboard.manageSessions'), icon: Monitor, tone: 'success' },
  { name: 'SystemSettings', label: t('admin.dashboard.systemSettings'), icon: Setting, tone: 'info' },
])

const go = (name: string) => router.push({ name })

const formatDate = (dateStr: string) => dayjs(dateStr).format('YYYY-MM-DD HH:mm:ss')

const getActionType = (action: string): 'success' | 'warning' | 'danger' | 'info' => {
  const actionLower = action.toLowerCase()
  if (actionLower.includes('create') || actionLower.includes('login')) return 'success'
  if (actionLower.includes('update') || actionLower.includes('delegate')) return 'warning'
  if (actionLower.includes('delete') || actionLower.includes('revoke') || actionLower.includes('logout')) return 'danger'
  return 'info'
}

const loadSessions = async () => {
  loadingSessions.value = true
  try {
    allSessions.value = await authApi.getSessions()
  } catch (error) {
    console.error('Failed to load sessions:', error)
    allSessions.value = []
  } finally {
    loadingSessions.value = false
  }
}

const loadStats = async () => {
  loadingStats.value = true
  try {
    const [reviewersResponse, roles, delegations] = await Promise.all([
      usersApi.getReviewers(1).catch(() => ({ total: 0 })),
      rbacApi.getRoles().catch(() => []),
      rbacApi.listDelegations({ status: 'active', include_expired: false }).catch(() => []),
    ])

    stats.value.totalUsers = reviewersResponse.total || 0
    stats.value.totalRoles = Array.isArray(roles) ? roles.length : 0
    stats.value.activeDelegations = Array.isArray(delegations) ? delegations.length : 0
    stats.value.activeSessions = allSessions.value.length
  } catch (error) {
    console.error('Failed to load statistics:', error)
  } finally {
    loadingStats.value = false
  }
}

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

const refreshAll = async () => {
  refreshing.value = true
  try {
    // Sessions first: the count and the list both read from that one answer.
    await loadSessions()
    await Promise.all([loadStats(), loadRecentAuditLogs()])
  } finally {
    refreshing.value = false
  }
}

onMounted(refreshAll)
</script>

<style scoped>
.admin-dashboard {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.dashboard-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.dashboard-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.dashboard-subtitle {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

/* Headline numbers ------------------------------------------------------- */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.stat-card {
  --stat-color: var(--el-color-primary);
  --stat-soft: var(--el-color-primary-light-9);
  position: relative;
  overflow: hidden;
  padding: 20px 22px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 16px;
  background: var(--el-bg-color);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
}

.stat-card:hover {
  transform: translateY(-4px);
  border-color: var(--stat-color);
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.1);
}

.stat-card--danger {
  --stat-color: var(--el-color-danger);
  --stat-soft: var(--el-color-danger-light-9);
}

.stat-card--warning {
  --stat-color: var(--el-color-warning);
  --stat-soft: var(--el-color-warning-light-9);
}

.stat-card--success {
  --stat-color: var(--el-color-success);
  --stat-soft: var(--el-color-success-light-9);
}

.stat-card--info {
  --stat-color: var(--el-color-info);
  --stat-soft: var(--el-color-info-light-9);
}

.stat-card__accent {
  position: absolute;
  inset: 0 auto 0 0;
  width: 4px;
  background: var(--stat-color);
}

.stat-card__body {
  display: flex;
  align-items: center;
  gap: 16px;
}

.stat-card__icon {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: none;
  width: 48px;
  height: 48px;
  border-radius: 14px;
  font-size: 22px;
  color: var(--stat-color);
  background: var(--stat-soft);
}

.stat-card__info {
  min-width: 0;
}

.stat-card__label {
  margin-bottom: 6px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.stat-card__value {
  font-size: 32px;
  font-weight: 700;
  line-height: 1.1;
  font-variant-numeric: tabular-nums;
  color: var(--el-text-color-primary);
}

.stat-card__skeleton {
  width: 64px;
  height: 34px;
  border-radius: 6px;
  background: linear-gradient(
    90deg,
    var(--el-fill-color) 25%,
    var(--el-fill-color-light) 50%,
    var(--el-fill-color) 75%
  );
  background-size: 200% 100%;
  animation: stat-shimmer 1.4s ease infinite;
}

@keyframes stat-shimmer {
  from { background-position: 200% 0; }
  to { background-position: -200% 0; }
}

/* Panels ----------------------------------------------------------------- */
.panel {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 16px;
  background: var(--el-bg-color);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  overflow: hidden;
}

.panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 16px 20px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.panel__header h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.panel__body {
  padding: 8px 20px 16px;
  min-height: 120px;
}

/* Quick actions ---------------------------------------------------------- */
.quick-actions {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  padding: 16px 20px 20px;
}

.quick-action {
  --stat-color: var(--el-color-primary);
  --stat-soft: var(--el-color-primary-light-9);
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 12px 14px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 12px;
  background: var(--el-bg-color);
  color: var(--el-text-color-primary);
  font: inherit;
  text-align: left;
  cursor: pointer;
  transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
}

.quick-action:hover {
  transform: translateY(-2px);
  border-color: var(--stat-color);
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.08);
}

.quick-action--danger {
  --stat-color: var(--el-color-danger);
  --stat-soft: var(--el-color-danger-light-9);
}

.quick-action--warning {
  --stat-color: var(--el-color-warning);
  --stat-soft: var(--el-color-warning-light-9);
}

.quick-action--success {
  --stat-color: var(--el-color-success);
  --stat-soft: var(--el-color-success-light-9);
}

.quick-action--info {
  --stat-color: var(--el-color-info);
  --stat-soft: var(--el-color-info-light-9);
}

.quick-action__icon {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: none;
  width: 34px;
  height: 34px;
  border-radius: 10px;
  font-size: 17px;
  color: var(--stat-color);
  background: var(--stat-soft);
}

.quick-action__label {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.quick-action__arrow {
  flex: none;
  font-size: 14px;
  color: var(--el-text-color-secondary);
}

/* Recent activity -------------------------------------------------------- */
.activity-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.audit-log-item {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.log-detail {
  color: var(--el-text-color-regular);
  font-size: 13px;
}

/* Dark theme: neutral shadows need more contrast against a dark surface */
[data-theme='dark'] .stat-card,
[data-theme='dark'] .panel {
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.25);
}

[data-theme='dark'] .stat-card:hover {
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.45);
}

[data-theme='dark'] .quick-action:hover {
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.35);
}

@media (max-width: 1100px) {
  .stats-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .quick-actions {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .activity-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 640px) {
  .stats-grid,
  .quick-actions {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
