<template>
  <div class="profile-container">
    <el-card class="profile-card">
      <template #header>
        <div class="card-header">
          <span>Profile</span>
        </div>
      </template>

      <!-- User Info -->
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
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { authApi } from '@/api/auth'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { InfoFilled, WarningFilled } from '@element-plus/icons-vue'
import dayjs from 'dayjs'

const router = useRouter()
const authStore = useAuthStore()
const passwordFormRef = ref<FormInstance>()
const changingPassword = ref(false)

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
