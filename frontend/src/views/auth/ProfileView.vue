<template>
  <div class="profile-container">
    <el-card class="profile-card">
      <template #header>
        <div class="card-header">
          <span>Profile</span>
        </div>
      </template>

      <el-tabs v-model="activeTab" type="border-card">
        <!-- User Info Tab -->
        <el-tab-pane label="User Info" name="info">
          <el-descriptions :column="1" border>
            <el-descriptions-item label="Username">
              {{ authStore.user?.username }}
            </el-descriptions-item>
            <el-descriptions-item label="Email">
              {{ authStore.user?.email }}
            </el-descriptions-item>
            <el-descriptions-item label="Roles">
              <div class="roles-header">
                <div v-if="authStore.user?.roles && authStore.user.roles.length > 0" class="roles-container">
                  <el-tag
                    v-for="role in authStore.user.roles"
                    :key="role"
                    :type="getRoleTagType(role)"
                    size="small"
                    style="margin-right: 8px; margin-bottom: 4px;"
                  >
                    {{ formatRoleName(role) }}
                  </el-tag>
                </div>
                <el-tag v-else type="info" size="small">No roles assigned</el-tag>
                
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
                      style="margin-left: 8px;"
                    >
                      <el-icon><InfoFilled /></el-icon>
                    </el-button>
                  </template>
                  <div class="viewer-tips-content">
                    <h4 style="margin: 0 0 12px 0; color: var(--el-color-warning);">
                      <el-icon style="vertical-align: middle; margin-right: 4px;"><WarningFilled /></el-icon>
                      Viewer Role Limitations
                    </h4>
                    <ul style="margin: 0; padding-left: 20px; line-height: 1.8;">
                      <li>You can only <strong>view</strong> code reviews and scores</li>
                      <li>You <strong>cannot</strong> add or update scores</li>
                      <li>You <strong>cannot</strong> add comments to reviews</li>
                      <li>You <strong>cannot</strong> be assigned review tasks</li>
                    </ul>
                    <el-divider style="margin: 12px 0;" />
                    <p style="margin: 0; color: var(--el-text-color-secondary); font-size: 13px;">
                      💡 To gain full reviewer permissions, please contact a system administrator to upgrade your role.
                    </p>
                  </div>
                </el-popover>
              </div>
            </el-descriptions-item>
            <el-descriptions-item label="Status">
              <el-tag :type="authStore.user?.is_active ? 'success' : 'danger'">
                {{ authStore.user?.is_active ? 'Active' : 'Inactive' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="Last Login">
              {{ authStore.user?.last_login_at ? formatDate(authStore.user.last_login_at) : 'Never' }}
            </el-descriptions-item>
            <el-descriptions-item label="Member Since">
              {{ authStore.user?.created_at ? formatDate(authStore.user.created_at) : 'N/A' }}
            </el-descriptions-item>
          </el-descriptions>

          <!-- Change Password Section -->
          <el-divider />
          <h3>Change Password</h3>
          <el-form :model="passwordForm" :rules="passwordRules" ref="passwordFormRef" label-width="140px" class="password-form">
            <el-form-item label="Current Password" prop="old_password">
              <el-input
                v-model="passwordForm.old_password"
                type="password"
                placeholder="Enter current password"
                show-password
              />
            </el-form-item>
            
            <el-form-item label="New Password" prop="new_password">
              <el-input
                v-model="passwordForm.new_password"
                type="password"
                placeholder="Enter new password"
                show-password
              />
            </el-form-item>
            
            <el-form-item label="Confirm Password" prop="confirm_password">
              <el-input
                v-model="passwordForm.confirm_password"
                type="password"
                placeholder="Confirm new password"
                show-password
              />
            </el-form-item>
            
            <el-form-item>
              <el-button type="primary" :loading="changingPassword" @click="handleChangePassword">
                Change Password
              </el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <!-- Role Delegations Tab -->
        <el-tab-pane label="Role Delegations" name="delegations">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
            <h3 style="margin: 0;">My Delegations</h3>
            <el-button 
              v-if="canManageDelegations"
              type="primary" 
              size="small"
              @click="showCreateDialog = true"
            >
              <el-icon><Plus /></el-icon>
              Create Delegation
            </el-button>
          </div>
          
          <el-tabs v-model="delegationDirection" type="card" style="margin-bottom: 20px;">
            <el-tab-pane label="Received" name="received">
              <div v-loading="loadingReceived">
                <el-empty v-if="receivedDelegations.length === 0" description="No delegations received" />
                <el-table v-else :data="receivedDelegations" stripe style="width: 100%">
                  <el-table-column prop="role_name" label="Role" width="150">
                    <template #default="{ row }">
                      <el-tag :type="getRoleTagType(row.role_name || '')" size="small">
                        {{ row.role_name || `Role ${row.role_id}` }}
                      </el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column prop="resource_type" label="Resource Type" width="120" />
                  <el-table-column label="Delegator" width="150">
                    <template #default="{ row }">
                      User #{{ row.delegator_id }}
                    </template>
                  </el-table-column>
                  <el-table-column label="Status" width="120">
                    <template #default="{ row }">
                      <el-tag :type="getStatusType(row.delegation_status)">
                        {{ formatStatus(row.delegation_status) }}
                      </el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column label="Valid Period" min-width="200">
                    <template #default="{ row }">
                      <div v-if="row.starts_at && row.expires_at">
                        {{ formatDate(row.starts_at) }} → {{ formatDate(row.expires_at) }}
                      </div>
                      <span v-else>-</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="Reason" min-width="200">
                    <template #default="{ row }">
                      {{ row.delegation_reason || '-' }}
                    </template>
                  </el-table-column>
                </el-table>
              </div>
            </el-tab-pane>

            <el-tab-pane label="Sent" name="sent">
              <div v-loading="loadingSent">
                <el-empty v-if="sentDelegations.length === 0" description="No delegations sent" />
                <el-table v-else :data="sentDelegations" stripe style="width: 100%">
                  <el-table-column prop="role_name" label="Role" width="150">
                    <template #default="{ row }">
                      <el-tag :type="getRoleTagType(row.role_name || '')" size="small">
                        {{ row.role_name || `Role ${row.role_id}` }}
                      </el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column prop="resource_type" label="Resource Type" width="120" />
                  <el-table-column label="Delegatee" width="150">
                    <template #default="{ row }">
                      User #{{ row.auth_user_id }}
                    </template>
                  </el-table-column>
                  <el-table-column label="Status" width="120">
                    <template #default="{ row }">
                      <el-tag :type="getStatusType(row.delegation_status)">
                        {{ formatStatus(row.delegation_status) }}
                      </el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column label="Valid Period" min-width="200">
                    <template #default="{ row }">
                      <div v-if="row.starts_at && row.expires_at">
                        {{ formatDate(row.starts_at) }} → {{ formatDate(row.expires_at) }}
                      </div>
                      <span v-else>-</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="Actions" width="120" fixed="right">
                    <template #default="{ row }">
                      <el-button
                        v-if="row.delegation_status === 'active' || row.delegation_status === 'pending'"
                        size="small"
                        type="danger"
                        @click="handleRevokeDelegation(row.id)"
                      >
                        Revoke
                      </el-button>
                      <span v-else style="color: var(--el-text-color-secondary);">-</span>
                    </template>
                  </el-table-column>
                </el-table>
              </div>
            </el-tab-pane>
          </el-tabs>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- Create Delegation Dialog -->
    <el-dialog v-model="showCreateDialog" title="Create Role Delegation" width="800px">
      <DelegationForm
        ref="delegationFormRef"
        :current-user-id="authStore.user?.id || 0"
        :current-username="authStore.user?.username || ''"
        @submit="handleSubmitDelegation"
      />
      
      <template #footer>
        <el-button @click="showCreateDialog = false">Cancel</el-button>
        <el-button type="primary" :loading="creating" @click="handleConfirmCreate">
          Create Delegation
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { authApi } from '@/api/auth'
import { rbacApi, type DelegationResponse } from '@/api/rbac'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { InfoFilled, WarningFilled, Plus } from '@element-plus/icons-vue'
import dayjs from 'dayjs'
import DelegationForm from '@/components/delegation/DelegationForm.vue'

const router = useRouter()
const authStore = useAuthStore()
const passwordFormRef = ref<FormInstance>()
const changingPassword = ref(false)
const activeTab = ref('info')
const delegationDirection = ref<'received' | 'sent'>('received')

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
    callback(new Error('Please input password'))
  } else {
    if (passwordForm.confirm_password !== '') {
      passwordFormRef.value?.validateField('confirm_password')
    }
    callback()
  }
}

const validatePass2 = (rule: any, value: string, callback: any) => {
  if (value === '') {
    callback(new Error('Please input password again'))
  } else if (value !== passwordForm.new_password) {
    callback(new Error("Two inputs don't match!"))
  } else {
    callback()
  }
}

const passwordRules: FormRules = {
  old_password: [
    { required: true, message: 'Please input current password', trigger: 'blur' },
  ],
  new_password: [
    { validator: validatePass, trigger: 'blur' },
    { min: 6, message: 'Password must be at least 6 characters', trigger: 'blur' },
  ],
  confirm_password: [
    { validator: validatePass2, trigger: 'blur' },
  ],
}

const formatDate = (dateStr: string) => {
  return dayjs(dateStr).format('YYYY-MM-DD HH:mm:ss')
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
const canManageDelegations = computed(() => {
  const roles = authStore.user?.roles || []
  return roles.includes('system_admin') || roles.includes('review_admin')
})

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
  }
})

// Format delegation status
const formatStatus = (status?: string | null): string => {
  if (!status) return 'Unknown'
  const statusMap: Record<string, string> = {
    active: 'Active',
    pending: 'Pending',
    expired: 'Expired',
    revoked: 'Revoked',
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
      'Are you sure you want to revoke this delegation?',
      'Confirm Revoke',
      { type: 'warning' }
    )
    
    await rbacApi.revokeDelegation(assignmentId, { reason: 'Revoked by delegator' })
    ElMessage.success('Delegation revoked successfully')
    loadSentDelegations()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('Failed to revoke delegation')
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
    ElMessage.warning('Please fill in all required fields')
    return
  }
  
  if (!pendingDelegationData.value) {
    ElMessage.warning('Please complete the delegation form')
    return
  }
  
  try {
    creating.value = true
    await rbacApi.createDelegation(pendingDelegationData.value)
    
    ElMessage.success('Delegation created successfully')
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
      ElMessage.error(error?.response?.data?.detail || 'Failed to create delegation')
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
        ElMessage.success('Password changed successfully. Please login with your new password.')
        
        // Logout and redirect to login page
        setTimeout(async () => {
          await authStore.logout()
          router.push('/login')
        }, 1500)
      } catch (error) {
        ElMessage.error('Failed to change password')
      } finally {
        changingPassword.value = false
      }
    }
  })
}
</script>

<style scoped>
.profile-container {
  max-width: 800px;
  margin: 0 auto;
}

.profile-card {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 18px;
  font-weight: bold;
}

h3 {
  margin: 20px 0 16px 0;
  color: var(--el-text-color-primary);
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
</style>
