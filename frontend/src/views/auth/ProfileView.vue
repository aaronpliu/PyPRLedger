<template>
  <div class="profile-container">
    <el-card class="profile-card">
      <template #header>
        <div class="card-header">
          <span>{{ t('profile.tabs.title', 'Profile') }}</span>
          <span class="current-tab-label">{{ currentTabLabel }}</span>
        </div>
      </template>

      <!-- Fixed-width nav panel + content panel. The nav is custom-rendered
           (Element Plus' left tabs size their nav from the labels, which made
           the layout shift between languages). -->
      <div class="profile-layout">
        <nav class="profile-nav">
          <button
            v-for="item in navItems"
            :key="item.name"
            type="button"
            class="profile-nav-item"
            :class="{ 'is-active': activeTab === item.name }"
            @click="activeTab = item.name"
          >
            {{ item.label }}
          </button>
        </nav>

        <div class="profile-body">
          <!-- User Info Tab -->
          <div v-show="activeTab === 'info'" class="profile-pane">
          <div class="tab-content">
            <!-- Two-column layout: avatar on the left, profile info on the right -->
            <div class="user-info-layout">
              <div class="avatar-panel">
                <h3>{{ t('profile.user_info.avatar', 'Avatar') }}</h3>
                <AvatarUpload
                  v-if="authStore.user"
                  :username="authStore.user.username"
                  :avatarUrl="authStore.user.avatar_url"
                  :size="120"
                  :showActions="true"
                  @update:avatarUrl="handleAvatarUpdate"
                />
              </div>

              <!-- Compact user info grid -->
              <div class="user-info-panel">
            <el-row :gutter="16" class="info-row">
              <el-col :span="12">
                <div class="info-item">
                  <label>{{ t('profile.user_info.username') }}</label>
                  <span>{{ authStore.user?.username }}</span>
                </div>
              </el-col>
              <el-col :span="12">
                <div class="info-item">
                  <label>{{ t('profile.user_info.email') }}</label>
                  <span>{{ authStore.user?.email || t('profile.user_info.na') }}</span>
                </div>
              </el-col>
            </el-row>
            
            <el-row :gutter="16" class="info-row">
              <el-col :span="12">
                <div class="info-item">
                  <label>{{ t('profile.user_info.status') }}</label>
                  <div class="status-container">
                    <el-tag :type="authStore.user?.is_active ? 'success' : 'danger'" size="small">
                      {{ authStore.user?.is_active ? t('profile.user_info.active') : t('profile.user_info.inactive') }}
                    </el-tag>
                  </div>
                </div>
              </el-col>
              <el-col :span="12">
                <div class="info-item">
                  <label>{{ t('profile.user_info.last_login') }}</label>
                  <span>{{ authStore.user?.last_login_at ? formatDate(authStore.user.last_login_at) : t('profile.user_info.never') }}</span>
                </div>
              </el-col>
            </el-row>
            
            <el-row :gutter="16" class="info-row">
              <el-col :span="12">
                <div class="info-item">
                  <label>{{ t('profile.user_info.member_since') }}</label>
                  <span>{{ authStore.user?.created_at ? formatDate(authStore.user.created_at) : t('profile.user_info.na') }}</span>
                </div>
              </el-col>
              <el-col :span="12">
                <div class="info-item">
                  <label>{{ t('profile.user_info.roles') }}</label>
                  <div class="roles-header">
                    <div v-if="authStore.user?.roles && authStore.user.roles.length > 0" class="roles-container">
                      <el-tag
                        v-for="role in authStore.user.roles"
                        :key="role"
                        :type="getRoleTagType(role)"
                        size="small"
                        style="margin-right: 4px;"
                      >
                        {{ formatRoleName(role) }}
                      </el-tag>
                    </div>
                    <el-tag v-else type="info" size="small">{{ t('profile.user_info.no_roles') }}</el-tag>
                    
                    <!-- Popover for viewer-only users -->
                    <el-popover
                      v-if="isViewerOnly"
                      placement="top"
                      :width="350"
                      trigger="click"
                    >
                      <template #reference>
                        <el-button
                          link
                          type="warning"
                          size="small"
                          style="margin-left: 4px;"
                        >
                          <el-icon><InfoFilled /></el-icon>
                        </el-button>
                      </template>
                      <div class="viewer-tips-content">
                        <h4 style="margin: 0 0 12px 0; color: var(--el-color-warning);">
                          <el-icon style="vertical-align: middle; margin-right: 4px;"><WarningFilled /></el-icon>
                          {{ t('profile.viewer_tips.title') }}
                        </h4>
                        <ul style="margin: 0; padding-left: 20px; line-height: 1.8;">
                          <li>{{ t('profile.viewer_tips.only_view') }}</li>
                          <li>{{ t('profile.viewer_tips.no_score') }}</li>
                          <li>{{ t('profile.viewer_tips.no_comment') }}</li>
                          <li>{{ t('profile.viewer_tips.no_assign') }}</li>
                        </ul>
                        <el-divider style="margin: 12px 0;" />
                        <p style="margin: 0; color: var(--el-text-color-secondary); font-size: 13px;">
                          💡 {{ t('profile.viewer_tips.contact_admin') }}
                        </p>
                      </div>
                    </el-popover>
                  </div>
                </div>
              </el-col>
            </el-row>
              </div>
            </div>

            <!-- Change Password Section -->
            <el-divider />
            <h3>{{ t('profile.password.title', 'Change Password') }}</h3>
            <el-form :model="passwordForm" :rules="passwordRules" ref="passwordFormRef" label-width="140px" class="password-form">
              <el-form-item :label="t('profile.password.current')" prop="old_password">
                <el-input
                  v-model="passwordForm.old_password"
                  type="password"
                  :placeholder="t('profile.password.current_ph')"
                  show-password
                />
              </el-form-item>
              
              <el-form-item :label="t('profile.password.new')" prop="new_password">
                <el-input
                  v-model="passwordForm.new_password"
                  type="password"
                  :placeholder="t('profile.password.new_ph')"
                  show-password
                />
              </el-form-item>
              
              <el-form-item :label="t('profile.password.confirm')" prop="confirm_password">
                <el-input
                  v-model="passwordForm.confirm_password"
                  type="password"
                  :placeholder="t('profile.password.confirm_ph')"
                  show-password
                />
              </el-form-item>
              
              <el-form-item>
                <el-button type="primary" :loading="changingPassword" @click="handleChangePassword">
                  {{ t('profile.password.change') }}
                </el-button>
              </el-form-item>
            </el-form>
          </div>
        </div>

        <!-- Role Delegations Tab -->
        <div v-show="activeTab === 'delegations'" class="profile-pane">
          <div class="tab-content delegation-tab-content">
            <div class="tab-section-header">
              <div class="delegation-header-left">
                <h3>{{ t('profile.delegations.my_title') }}</h3>
                <!-- Replaces the horizontal sub-tabs: the current direction is
                     shown as a label and toggled in place. -->
                <el-radio-group v-model="delegationDirection">
                  <el-radio-button value="received">{{ t('profile.delegations.received') }}</el-radio-button>
                  <el-radio-button value="sent">{{ t('profile.delegations.sent') }}</el-radio-button>
                </el-radio-group>
              </div>
              <el-button
                v-if="canManageDelegations"
                type="primary"
                @click="showCreateDialog = true"
              >
                <el-icon><Plus /></el-icon>
                {{ t('profile.delegations.create') }}
              </el-button>
            </div>

            <div v-show="delegationDirection === 'received'" v-loading="loadingReceived" class="delegation-table-wrapper">
              <el-empty v-if="receivedDelegations.length === 0" :description="t('profile.delegations.no_received')" />
              <el-table v-else :data="receivedDelegations" stripe style="width: 100%">
                    <el-table-column prop="role_name" :label="t('profile.delegations.role')" width="130">
                      <template #default="{ row }">
                        <el-tag :type="getRoleTagType(row.role_name || '')" size="small">
                          {{ row.role_name || t('profile.delegations.role_with_id', { id: row.role_id }) }}
                        </el-tag>
                      </template>
                    </el-table-column>
                    <el-table-column prop="resource_type" :label="t('profile.delegations.resource')" width="110" />
                    <el-table-column :label="t('profile.delegations.delegator')" min-width="160">
                      <template #default="{ row }">
                        <div class="user-info-cell">
                          <div v-if="row.delegator_display_name" class="display-name">{{ row.delegator_display_name }}</div>
                          <div class="username">{{ row.delegator_username || t('profile.delegations.user_with_id', { id: row.delegator_id }) }}</div>
                        </div>
                      </template>
                    </el-table-column>
                    <el-table-column :label="t('profile.delegations.status')" width="100">
                      <template #default="{ row }">
                        <el-tag :type="getStatusType(row.delegation_status)">
                          {{ formatStatus(row.delegation_status) }}
                        </el-tag>
                      </template>
                    </el-table-column>
                    <el-table-column :label="t('profile.delegations.valid_period')" min-width="220">
                      <template #default="{ row }">
                        <div v-if="row.starts_at && row.expires_at">
                          {{ formatDate(row.starts_at) }} → {{ formatDate(row.expires_at) }}
                        </div>
                        <span v-else>-</span>
                      </template>
                    </el-table-column>
                    <el-table-column :label="t('profile.delegations.reason')" min-width="180">
                      <template #default="{ row }">
                        {{ row.delegation_reason || '-' }}
                      </template>
                    </el-table-column>
                  </el-table>
                </div>

                <div v-show="delegationDirection === 'sent'" v-loading="loadingSent" class="delegation-table-wrapper">
                  <el-empty v-if="sentDelegations.length === 0" :description="t('profile.delegations.no_sent')" />
                  <el-table v-else :data="sentDelegations" stripe style="width: 100%">
                    <el-table-column prop="role_name" :label="t('profile.delegations.role')" width="130">
                      <template #default="{ row }">
                        <el-tag :type="getRoleTagType(row.role_name || '')" size="small">
                          {{ row.role_name || t('profile.delegations.role_with_id', { id: row.role_id }) }}
                        </el-tag>
                      </template>
                    </el-table-column>
                    <el-table-column prop="resource_type" :label="t('profile.delegations.resource')" width="110" />
                    <el-table-column :label="t('profile.delegations.delegatee')" min-width="160">
                      <template #default="{ row }">
                        <div class="user-info-cell">
                          <div v-if="row.delegatee_display_name" class="display-name">{{ row.delegatee_display_name }}</div>
                          <div class="username">{{ row.delegatee_username || t('profile.delegations.user_with_id', { id: row.auth_user_id }) }}</div>
                        </div>
                      </template>
                    </el-table-column>
                    <el-table-column :label="t('profile.delegations.status')" width="100">
                      <template #default="{ row }">
                        <el-tag :type="getStatusType(row.delegation_status)">
                          {{ formatStatus(row.delegation_status) }}
                        </el-tag>
                      </template>
                    </el-table-column>
                    <el-table-column :label="t('profile.delegations.valid_period')" min-width="220">
                      <template #default="{ row }">
                        <div v-if="row.starts_at && row.expires_at">
                          {{ formatDate(row.starts_at) }} → {{ formatDate(row.expires_at) }}
                        </div>
                        <span v-else>-</span>
                      </template>
                    </el-table-column>
                    <el-table-column :label="t('profile.delegations.actions')" width="100" fixed="right">
                      <template #default="{ row }">
                        <el-button
                          v-if="row.delegation_status === 'active' || row.delegation_status === 'pending'"
                          size="small"
                          type="danger"
                          @click="handleRevokeDelegation(row.id)"
                        >
                          {{ t('profile.delegations.revoke') }}
                        </el-button>
                        <span v-else style="color: var(--el-text-color-secondary);">-</span>
                      </template>
                    </el-table-column>
                  </el-table>
                </div>
          </div>
        </div>

        <div v-show="activeTab === 'sessions'" class="profile-pane">
          <div class="tab-content sessions-tab-content">
            <div class="tab-section-header">
              <div>
                <h3>{{ t('profile.sessions.title') }}</h3>
                <p class="sessions-subtitle">
                  {{ t('profile.sessions.subtitle') }}
                </p>
              </div>
              <el-button type="primary" :loading="loadingSessions" @click="loadSessions">
                <el-icon><Refresh /></el-icon>
                {{ t('profile.sessions.refresh') }}
              </el-button>
            </div>

            <el-table :data="sessions" v-loading="loadingSessions" stripe style="width: 100%">
              <el-table-column :label="t('profile.sessions.session')" min-width="200">
                <template #default="{ row }">
                  <div class="session-id-cell">
                    <span class="session-id">{{ row.session_id }}</span>
                    <el-tag v-if="row.is_current" size="small" type="success">{{ t('profile.sessions.current') }}</el-tag>
                  </div>
                </template>
              </el-table-column>
              <el-table-column :label="t('profile.sessions.created')" width="170">
                <template #default="{ row }">
                  {{ formatDate(row.created_at) }}
                </template>
              </el-table-column>
              <el-table-column :label="t('profile.sessions.last_activity')" width="170">
                <template #default="{ row }">
                  {{ formatDate(row.last_activity_at) }}
                </template>
              </el-table-column>
              <el-table-column :label="t('profile.sessions.ip')" width="130">
                <template #default="{ row }">
                  {{ row.ip_address || '-' }}
                </template>
              </el-table-column>
              <el-table-column :label="t('profile.sessions.device')" min-width="220">
                <template #default="{ row }">
                  <div class="device-cell" :title="getDeviceDetails(row).rawUserAgent || ''">
                    <div class="device-label-row">
                      <el-icon class="device-icon"><component :is="getDeviceIcon(row)" /></el-icon>
                      <span class="device-label">{{ getDeviceDetails(row).label }}</span>
                      <el-tag v-if="row.is_current" size="small" type="primary">{{ t('profile.sessions.this_device') }}</el-tag>
                      <el-tag
                        v-if="getDeviceDetails(row).precision === 'approximate'"
                        size="small"
                        type="info"
                        effect="plain"
                        :title="t('profile.sessions.approximate_tooltip')"
                      >
                        {{ t('profile.sessions.approximate') }}
                      </el-tag>
                    </div>
                    <div class="device-meta">
                      {{ getDeviceDetails(row).browserLabel }} · {{ getDeviceDetails(row).osLabel }}
                    </div>
                  </div>
                </template>
              </el-table-column>
              <el-table-column :label="t('profile.sessions.idle_timeout')" width="160">
                <template #default="{ row }">
                  <el-tag :type="getSessionExpiryType(row.expires_in_seconds)">
                    {{ formatDuration(row.expires_in_seconds) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column :label="t('profile.sessions.actions')" width="120" fixed="right">
                <template #default="{ row }">
                  <el-button
                    size="small"
                    type="danger"
                    :loading="revokingSessionId === row.session_id"
                    @click="handleRevokeSession(row.session_id, row.is_current)"
                  >
                    {{ t('profile.sessions.revoke') }}
                  </el-button>
                </template>
              </el-table-column>
            </el-table>

            <el-empty v-if="!loadingSessions && sessions.length === 0" :description="t('profile.sessions.no_sessions')" />
          </div>
        </div>

        <!-- Personal Access Tokens Tab -->
        <div v-show="activeTab === 'tokens'" class="profile-pane">
          <div class="tab-content">
            <PATManagement />
          </div>
        </div>

        <!-- My Comment Templates Tab -->
        <div v-show="activeTab === 'comment-templates'" class="profile-pane">
          <div class="tab-content">
            <CommentTemplateManagement />
          </div>
        </div>

        <!-- Appearance Tab -->
        <div v-show="activeTab === 'appearance'" class="profile-pane">
          <div class="tab-content appearance-tab">
            <section class="appearance-section">
              <h3>{{ t('profile.appearance.theme') }}</h3>
              <p class="appearance-hint">{{ t('profile.appearance.theme_hint') }}</p>
              <el-radio-group v-model="themeMode">
                <el-radio-button value="light">{{ t('profile.appearance.light') }}</el-radio-button>
                <el-radio-button value="dark">{{ t('profile.appearance.dark') }}</el-radio-button>
                <el-radio-button value="auto">{{ t('profile.appearance.auto') }}</el-radio-button>
              </el-radio-group>
            </section>

            <section class="appearance-section">
              <h3>{{ t('profile.appearance.accent') }}</h3>
              <p class="appearance-hint">
                {{ t('profile.appearance.accent_hint') }}
              </p>
              <div class="appearance-presets">
                <button
                  v-for="preset in THEME_COLOR_PRESETS"
                  :key="preset.key"
                  type="button"
                  class="appearance-swatch"
                  :class="{ 'is-active': primaryColor === preset.value }"
                  :style="{ backgroundColor: preset.value }"
                  :title="t(`profile.appearance.preset_${preset.key}`)"
                  :aria-label="t(`profile.appearance.preset_${preset.key}`)"
                  :aria-pressed="primaryColor === preset.value"
                  @click="setPrimaryColor(preset.value)"
                />
              </div>

              <div class="appearance-custom">
                <span class="appearance-custom-label">{{ t('profile.appearance.custom') }}</span>
                <el-color-picker
                  :model-value="primaryColor"
                  :predefine="presetValues"
                  @change="onCustomColor"
                />
                <code class="appearance-color-value">{{ primaryColor }}</code>
                <el-button
                  v-if="isCustomPrimaryColor"
                  link
                  type="primary"
                  @click="resetPrimaryColor"
                >
                  {{ t('profile.appearance.reset_to_default') }}
                </el-button>
              </div>

              <el-alert
                v-if="contrastWarning"
                type="warning"
                :closable="false"
                show-icon
                class="appearance-warning"
                :title="contrastWarning"
              />
            </section>
          </div>
        </div>
        </div>
      </div>
    </el-card>

    <!-- Create Delegation Dialog -->
    <el-dialog v-model="showCreateDialog" :title="t('profile.delegations.dialog_title')" width="800px">
      <DelegationForm
        ref="delegationFormRef"
        :current-user-id="authStore.user?.id || 0"
        :current-username="authStore.user?.username || ''"
        @submit="handleSubmitDelegation"
      />
      
      <template #footer>
        <el-button @click="showCreateDialog = false">{{ t('common.cancel', 'Cancel') }}</el-button>
        <el-button type="primary" :loading="creating" @click="handleConfirmCreate">
          {{ t('profile.delegations.create') }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useI18n } from 'vue-i18n'
import { authApi } from '@/api/auth'
import { rbacApi, type DelegationResponse } from '@/api/rbac'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { Cellphone, InfoFilled, Monitor, Plus, Refresh, WarningFilled } from '@element-plus/icons-vue'
import dayjs from 'dayjs'
import DelegationForm from '@/components/delegation/DelegationForm.vue'
import AvatarUpload from '@/components/user/AvatarUpload.vue'
import PATManagement from '@/components/auth/PATManagement.vue'
import CommentTemplateManagement from '@/components/review/CommentTemplateManagement.vue'
import type { AuthSession } from '@/types'
import { describeSession } from '@/utils/device'
import { useTheme } from '@/composables/useTheme'
import { MIN_READABLE_CONTRAST, THEME_COLOR_PRESETS, contrastWithWhite } from '@/utils/themeColor'

const router = useRouter()
const authStore = useAuthStore()
const { t } = useI18n()
const passwordFormRef = ref<FormInstance>()
const changingPassword = ref(false)
const PROFILE_TABS = ['info', 'delegations', 'sessions', 'tokens', 'comment-templates', 'appearance']
const requestedTab =
  typeof router.currentRoute.value.query.tab === 'string' ? router.currentRoute.value.query.tab : ''
const activeTab = ref(PROFILE_TABS.includes(requestedTab) ? requestedTab : 'info')

// Left nav panel entries - labels re-resolve on language change, but the
// panel width stays fixed (see .profile-nav) so nothing shifts on switch.
const navItems = computed(() => [
  { name: 'info', label: t('profile.tabs.user_info', 'User Info') },
  { name: 'delegations', label: t('profile.tabs.delegations', 'Role Delegations') },
  { name: 'sessions', label: t('profile.tabs.sessions', 'My Sessions') },
  { name: 'tokens', label: t('profile.tabs.tokens', 'Personal Access Tokens') },
  { name: 'comment-templates', label: t('profile.tabs.comment_templates', 'My Comment Templates') },
  { name: 'appearance', label: t('profile.tabs.appearance', 'Appearance') },
])
// Shown in the card header so the reader always sees which panel is open.
const currentTabLabel = computed(
  () => navItems.value.find((item) => item.name === activeTab.value)?.label ?? ''
)
const delegationDirection = ref<'received' | 'sent'>('received')
const loadingSessions = ref(false)
const sessions = ref<AuthSession[]>([])
const revokingSessionId = ref<string | null>(null)

// Appearance — the accent is applied by the shared theme composable, so the
// header switcher and this tab drive the same state.
const {
  currentTheme,
  primaryColor,
  isCustomPrimaryColor,
  setTheme,
  setPrimaryColor,
  resetPrimaryColor,
} = useTheme()

const themeMode = computed({
  get: () => currentTheme.value,
  set: (value: 'light' | 'dark' | 'auto') => setTheme(value),
})

const presetValues = THEME_COLOR_PRESETS.map((preset) => preset.value)

const onCustomColor = (value: string | null) => {
  if (value) {
    setPrimaryColor(value)
  }
}

/** Warn rather than refuse: the choice is the user's, but unreadable is worth saying. */
const contrastWarning = computed(() => {
  const ratio = contrastWithWhite(primaryColor.value)
  if (ratio === 0 || ratio >= MIN_READABLE_CONTRAST) {
    return ''
  }
  return t('profile.appearance.contrast_warning', { ratio: ratio.toFixed(1) })
})

// Delegation data
const loadingReceived = ref(false)
const loadingSent = ref(false)
const receivedDelegations = ref<DelegationResponse[]>([])
const sentDelegations = ref<DelegationResponse[]>([])

// Create delegation dialog
const showCreateDialog = ref(false)
const creating = ref(false)
const delegationFormRef = ref<InstanceType<typeof DelegationForm>>()

const passwordForm = reactive({
  old_password: '',
  new_password: '',
  confirm_password: '',
})

const validatePass = (rule: any, value: string, callback: any) => {
  if (value === '') {
    callback(new Error(t('profile.password.input_new')))
  } else {
    if (passwordForm.confirm_password !== '') {
      passwordFormRef.value?.validateField('confirm_password')
    }
    callback()
  }
}

const validatePass2 = (rule: any, value: string, callback: any) => {
  if (value === '') {
    callback(new Error(t('profile.password.input_confirm')))
  } else if (value !== passwordForm.new_password) {
    callback(new Error(t('profile.password.mismatch')))
  } else {
    callback()
  }
}

const passwordRules: FormRules = {
  old_password: [
    { required: true, message: t('profile.password.input_current'), trigger: 'blur' },
  ],
  new_password: [
    { validator: validatePass, trigger: 'blur' },
    { min: 6, message: t('profile.password.min_length'), trigger: 'blur' },
  ],
  confirm_password: [
    { validator: validatePass2, trigger: 'blur' },
  ],
}

const formatDate = (dateStr: string) => {
  return dayjs(dateStr).format('YYYY-MM-DD HH:mm:ss')
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

const getDeviceDetails = (session: AuthSession) => {
  return describeSession(session.device, session.user_agent)
}

const getDeviceIcon = (session: AuthSession) => {
  const category = getDeviceDetails(session).category
  if (category === 'mobile') return Cellphone
  if (category === 'tablet') return Cellphone
  return Monitor
}

const getSessionExpiryType = (seconds: number): 'success' | 'warning' | 'danger' => {
  if (seconds <= 300) return 'danger'
  if (seconds <= 1800) return 'warning'
  return 'success'
}

const formatRoleName = (role: string): string => {
  // Convert role name to display format
  const roleMap: Record<string, string> = {
    viewer: 'Viewer',
    reviewer: 'Reviewer',
    review_admin: 'Review Admin',
    system_admin: 'System Admin',
  }
  return roleMap[role] || role
}

const getRoleTagType = (role: string): 'success' | 'warning' | 'danger' | 'info' => {
  // Assign different colors based on role level
  const roleTypes: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
    viewer: 'info',
    reviewer: 'success',
    review_admin: 'warning',
    system_admin: 'danger',
  }
  return roleTypes[role] || 'info'
}

// Check if user has only viewer role (no other roles)
const isViewerOnly = computed(() => {
  const roles = authStore.user?.roles || []
  return roles.length === 1 && roles[0] === 'viewer'
})

// Check if user can manage delegations
// User must have admin role AND not have any active delegated roles (to prevent delegation chains)
const canManageDelegations = ref(false)

const updateCanManageDelegations = () => {
  const roles = authStore.user?.roles || []
  
  // Check if user has admin role directly assigned
  const hasDirectAdminRole = roles.includes('system_admin') || roles.includes('review_admin')
  
  // Also check if user has any ACTIVE delegated admin roles
  // (revoked delegations should not count)
  const hasActiveDelegatedAdminRole = receivedDelegations.value.some(
    d => d.delegation_status === 'active' && 
         (d.role_name === 'system_admin' || d.role_name === 'review_admin')
  )
  
  // Check if user has any active delegated roles (to prevent delegation chains)
  const hasAnyActiveDelegatedRoles = receivedDelegations.value.some(
    d => d.delegation_status === 'active'
  )
  
  // User can manage delegations if:
  // 1. They have direct admin role OR active delegated admin role
  // 2. AND they don't have any other active delegated roles (prevent chains)
  const hasAdminPermission = hasDirectAdminRole || hasActiveDelegatedAdminRole
  canManageDelegations.value = hasAdminPermission && !hasAnyActiveDelegatedRoles
  
  console.log('canManageDelegations updated:', {
    roles,
    hasDirectAdminRole,
    hasActiveDelegatedAdminRole,
    hasAnyActiveDelegatedRoles,
    canManage: canManageDelegations.value
  })
}

// Load delegations
const loadReceivedDelegations = async () => {
  if (!authStore.user?.id) return
  loadingReceived.value = true
  try {
    receivedDelegations.value = await rbacApi.getUserDelegations(
      authStore.user.id,
      'received',
      true // include expired
    )
  } catch (error) {
    console.error('Failed to load received delegations:', error)
  } finally {
    loadingReceived.value = false
  }
}

const loadSentDelegations = async () => {
  if (!authStore.user?.id) return
  loadingSent.value = true
  try {
    sentDelegations.value = await rbacApi.getUserDelegations(
      authStore.user.id,
      'sent',
      true // include expired
    )
  } catch (error) {
    console.error('Failed to load sent delegations:', error)
  } finally {
    loadingSent.value = false
  }
}

// Watch for tab changes
watch(delegationDirection, (newDir) => {
  if (newDir === 'received') {
    loadReceivedDelegations()
  } else {
    loadSentDelegations()
  }
})

watch(activeTab, (newTab) => {
  if (newTab === 'delegations') {
    loadReceivedDelegations()
    loadSentDelegations()
    // Update permission check after loading delegations
    setTimeout(() => updateCanManageDelegations(), 100)
  } else if (newTab === 'sessions') {
    loadSessions()
  }
})

const loadSessions = async () => {
  loadingSessions.value = true
  try {
    sessions.value = await authApi.getMySessions()
  } catch (error) {
    ElMessage.error(t('profile.sessions.load_failed'))
  } finally {
    loadingSessions.value = false
  }
}

const handleRevokeSession = async (sessionId: string, isCurrent: boolean) => {
  try {
    await ElMessageBox.confirm(
      isCurrent
        ? t('profile.sessions.revoke_current_body')
        : t('profile.sessions.revoke_body'),
      t('profile.sessions.revoke_title'),
      { type: 'warning' }
    )

    revokingSessionId.value = sessionId
    await authApi.revokeMySession(sessionId)

    if (isCurrent) {
      authStore.clearAuth()
      ElMessage.success(t('profile.sessions.revoked_current'))
      await router.replace('/login')
      return
    }

    ElMessage.success(t('profile.sessions.revoked_success'))
    await loadSessions()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(t('profile.sessions.revoke_failed'))
    }
  } finally {
    revokingSessionId.value = null
  }
}

// Format delegation status
const formatStatus = (status?: string | null): string => {
  if (!status) return t('profile.delegations.st_pending', 'Pending')
  const statusMap: Record<string, string> = {
    active: t('profile.delegations.st_active'),
    pending: t('profile.delegations.st_pending'),
    expired: t('profile.delegations.st_expired'),
    revoked: t('profile.delegations.st_revoked'),
  }
  return statusMap[status] || status
}

const getStatusType = (status?: string | null): 'success' | 'warning' | 'info' | 'danger' => {
  if (!status) return 'info'
  const typeMap: Record<string, 'success' | 'warning' | 'info' | 'danger'> = {
    active: 'success',
    pending: 'warning',
    expired: 'info',
    revoked: 'danger',
  }
  return typeMap[status] || 'info'
}

// Revoke delegation
const handleRevokeDelegation = async (assignmentId: number) => {
  try {
    await ElMessageBox.confirm(
      t('profile.delegations.revoke_body'),
      t('profile.delegations.revoke_title'),
      { type: 'warning' }
    )
    
    await rbacApi.revokeDelegation(assignmentId, { reason: t('profile.delegations.revoke_reason') })
    ElMessage.success(t('profile.delegations.revoked_success'))
    
    // Reload delegations
    await loadSentDelegations()
    await loadReceivedDelegations()
    
    // Update permission check
    updateCanManageDelegations()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(t('profile.delegations.revoked_failed'))
    }
  }
}

// Handle delegation form submit (called by child component)
const handleSubmitDelegation = (formData: any) => {
  // Store form data for confirmation
  pendingDelegationData.value = formData
}

const pendingDelegationData = ref<any>(null)

// Confirm and create delegation
const handleConfirmCreate = async () => {
  // First validate the form
  if (!delegationFormRef.value) return
  
  const isValid = await delegationFormRef.value.validate()
  if (!isValid) {
    ElMessage.warning(t('profile.delegations.fill_required'))
    return
  }
  
  if (!pendingDelegationData.value) {
    ElMessage.warning(t('profile.delegations.complete_form'))
    return
  }
  
  try {
    creating.value = true
    await rbacApi.createDelegation(pendingDelegationData.value)
    
    ElMessage.success(t('profile.delegations.created_success'))
    showCreateDialog.value = false
    pendingDelegationData.value = null
    
    // Reset the form
    if (delegationFormRef.value) {
      delegationFormRef.value.reset()
    }
    
    loadSentDelegations()
  } catch (error: any) {
    // Don't show permission errors
    if (error?.response?.status !== 403) {
      ElMessage.error(error?.response?.data?.detail || t('profile.delegations.create_failed'))
    }
  } finally {
    creating.value = false
  }
}

const handleChangePassword = async () => {
  if (!passwordFormRef.value) return
  
  await passwordFormRef.value.validate(async (valid) => {
    if (valid) {
      changingPassword.value = true
      try {
        await authApi.changePassword({
          old_password: passwordForm.old_password,
          new_password: passwordForm.new_password,
        })
        ElMessage.success(t('profile.password.change_success'))
        
        // Logout and redirect to login page
        setTimeout(async () => {
          await authStore.logout()
          router.push('/login')
        }, 1500)
      } catch (error) {
        ElMessage.error(t('profile.password.change_failed'))
      } finally {
        changingPassword.value = false
      }
    }
  })
}

// Handle avatar update
const handleAvatarUpdate = async (avatarUrl: string | null) => {
  // Update user in auth store
  if (authStore.user) {
    authStore.user.avatar_url = avatarUrl
    // Persist to localStorage to survive page refresh
    localStorage.setItem('user_profile', JSON.stringify(authStore.user))
  }
  
  // Re-fetch user profile to ensure consistency
  try {
    await authStore.fetchUserProfile()
  } catch (error) {
    console.error('Failed to refresh user profile after avatar update:', error)
  }
}

onMounted(() => {
  loadSessions()
})
</script>

<style scoped>
.profile-container {
  width: 1400px;
  max-width: 96vw;
  margin: 20px auto;
}

.profile-card {
  height: 750px;
  display: flex;
  flex-direction: column;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 18px;
  font-weight: bold;
}

/* Label of the currently selected panel, shown at the right of the header */
.current-tab-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-color-primary);
  background-color: var(--el-color-primary-light-9);
  padding: 4px 14px;
  border-radius: 12px;
}

/* User Info tab: avatar panel on the left, profile info on the right */
.user-info-layout {
  display: flex;
  align-items: flex-start;
  gap: 32px;
  flex-wrap: wrap;
}

.avatar-panel {
  flex: 0 0 220px;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 8px 24px 20px 0;
  border-right: 1px solid var(--el-border-color-lighter);
}

.avatar-panel h3 {
  margin: 0 0 16px;
}

.user-info-panel {
  flex: 1;
  min-width: 320px;
}

.profile-layout {
  flex: 1;
  display: flex;
  align-items: stretch;
  min-height: 0;
}

/* Fixed-width nav panel - the width is sized for the longest English label
   ("Personal Access Tokens") and never re-measured from the DOM, so the
   splitter holds still in every language. */
.profile-nav {
  width: 220px;
  min-width: 220px;
  max-width: 220px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px 10px;
  background-color: var(--el-fill-color-light);
  border-right: 1px solid var(--el-border-color-lighter);
}

.profile-nav-item {
  display: flex;
  align-items: center;
  width: 100%;
  padding: 12px 16px;
  border: none;
  border-radius: 8px;
  background: transparent;
  cursor: pointer;
  font: inherit;
  font-size: 14px;
  line-height: 1.4;
  text-align: left;
  white-space: nowrap;
  color: var(--el-text-color-regular);
  transition: color 0.2s ease, background-color 0.2s ease;
}

.profile-nav-item:hover {
  color: var(--el-color-primary);
  background-color: var(--el-fill-color);
}

.profile-nav-item.is-active {
  position: relative;
  font-weight: 600;
  color: var(--el-color-primary);
  background-color: var(--el-color-primary-light-9);
}

.profile-nav-item.is-active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 8px;
  bottom: 8px;
  width: 3px;
  border-radius: 0 3px 3px 0;
  background-color: var(--el-color-primary);
  transform-origin: center;
  animation: tabAccentIn 0.25s ease;
}

@keyframes tabAccentIn {
  from { transform: scaleY(0); }
  to { transform: scaleY(1); }
}

/* Content owns exactly what the fixed 220px nav leaves over, so the
   splitter between them holds still regardless of the active language. */
.profile-body {
  flex: 1;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  background-color: var(--el-bg-color);
}

.profile-pane {
  height: 100%;
  overflow: hidden;
}

.tab-content {
  height: 100%;
  overflow-y: auto;
  padding: 20px;
}

/* Compact info item layout */
.info-row {
  margin-bottom: 6px;
}

.info-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 3px 0;
  font-size: 14px;
}

.info-item label {
  font-weight: 600;
  color: var(--el-text-color-secondary);
  min-width: 110px;
  flex-shrink: 0;
}

.info-item span {
  color: var(--el-text-color-primary);
  word-break: break-word;
  overflow-wrap: break-word;
  flex: 1;
  line-height: 1.4;
}

/* Compact status tag styling */
.status-container {
  display: inline-flex;
  align-items: center;
}

.status-container .el-tag--small {
  padding: 2px 8px;
  height: 22px;
  line-height: 18px;
  font-size: 12px;
  border-radius: 3px;
}

h3 {
  margin: 20px 0 16px 0;
  color: var(--el-text-color-primary);
  font-size: 16px;
  font-weight: 600;
}

/* Fix el-descriptions theme compatibility */
:deep(.el-descriptions__label) {
  color: var(--el-text-color-regular);
  background-color: var(--el-fill-color-light);
}

:deep(.el-descriptions__content) {
  color: var(--el-text-color-primary);
  background-color: var(--el-bg-color);
}

:deep(.el-descriptions__body) {
  background-color: transparent;
}

/* Ensure form label alignment */
.password-form :deep(.el-form-item__label) {
  text-align: right;
  padding-right: 12px;
}

/* Ensure consistent label width for all password fields */
.password-form :deep(.el-form-item) {
  margin-bottom: 20px;
}

.roles-container {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.roles-header {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
}

.viewer-tips-content h4 {
  display: flex;
  align-items: center;
}

.viewer-tips-content ul li {
  margin-bottom: 4px;
}

/* Shared section header: title on the left, action button on the right -
   used by both "My Delegations" and "My Sessions" so they line up. */
.tab-section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
}

.tab-section-header h3 {
  margin: 0;
}

.sessions-subtitle {
  margin: 8px 0 0;
  color: var(--el-text-color-secondary);
  font-size: 14px;
  line-height: 1.5;
}

.session-id-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.session-id {
  font-family: 'Consolas', 'Courier New', monospace;
  font-size: 13px;
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

.user-info-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.display-name {
  font-weight: 500;
  color: var(--el-text-color-primary);
  font-size: 14px;
  line-height: 1.4;
}

.username {
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.4;
}

/* Ensure tables have proper spacing */
:deep(.el-table) {
  font-size: 14px;
}

:deep(.el-table th) {
  padding: 12px 0;
  font-weight: 600;
}

:deep(.el-table td) {
  padding: 12px 0;
}

.delegation-tab-content {
  display: flex;
  flex-direction: column;
}

/* Delegations: direction label (radio) sits next to the title; the two
   table panels are toggled with v-show and fill the remaining height. */
.delegation-header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.delegation-header-left h3 {
  margin: 0;
}

/* Wrapper for delegation tables with flex layout */
.delegation-table-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Tables in delegation panels with flexible height */
:deep(.delegation-tab-content .el-table) {
  flex: 1;
  min-height: 350px;
}

/* Sessions tab content with flex layout */
.sessions-tab-content {
  display: flex;
  flex-direction: column;
}

.sessions-subtitle {
  margin: 8px 0 0;
  color: var(--el-text-color-secondary);
  font-size: 14px;
  line-height: 1.5;
}

/* Table in sessions tab with flexible height */
:deep(.sessions-tab-content .el-table) {
  flex: 1;
  min-height: 450px;
}

/* Empty state container styling */
:deep(.el-empty) {
  margin: 30px auto;
}

/* Appearance tab - sections are spaced by gap only, so the top gap to the
   nav splitter matches the other tabs */
.appearance-tab {
  display: flex;
  flex-direction: column;
  gap: 28px;
  max-width: 560px;
}

.appearance-tab h3 {
  margin: 0 0 12px;
}

.appearance-section h3 {
  margin: 0 0 4px;
  font-size: 15px;
  font-weight: 600;
}

.appearance-hint {
  margin: 0 0 12px;
  font-size: 13px;
  line-height: 1.5;
  color: var(--el-text-color-secondary);
}

.appearance-presets {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 16px;
}

.appearance-swatch {
  width: 30px;
  height: 30px;
  padding: 0;
  border: none;
  border-radius: 50%;
  cursor: pointer;
  /* A ring rather than a border, so the swatch keeps its exact colour. */
  box-shadow: 0 0 0 3px var(--el-bg-color-overlay);
  outline: 1px solid var(--el-border-color);
  outline-offset: 1px;
  transition: transform 0.15s ease;
}

.appearance-swatch:hover {
  transform: scale(1.08);
}

.appearance-swatch.is-active {
  outline: 2px solid var(--el-text-color-primary);
  outline-offset: 3px;
}

.appearance-custom {
  display: flex;
  align-items: center;
  gap: 12px;
}

.appearance-custom-label {
  font-size: 13px;
  color: var(--el-text-color-regular);
}

.appearance-color-value {
  font-family: var(--el-font-family-mono, monospace);
  font-size: 13px;
  padding: 2px 6px;
  border-radius: 4px;
  background: var(--el-fill-color-light);
  color: var(--el-text-color-regular);
}

.appearance-warning {
  margin-top: 16px;
}
</style>
