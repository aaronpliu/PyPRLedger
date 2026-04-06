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
        <el-descriptions-item label="Status">
          <el-tag :type="authStore.user?.is_active ? 'success' : 'danger'">
            {{ authStore.user?.is_active ? 'Active' : 'Inactive' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="Last Login">
          {{ authStore.user?.last_login_at ? formatDate(authStore.user.last_login_at) : 'Never' }}
        </el-descriptions-item>
        <el-descriptions-item label="Member Since">
          {{ formatDate(authStore.user?.created_at || '') }}
        </el-descriptions-item>
      </el-descriptions>

      <!-- Change Password Section -->
      <el-divider />
      <h3>Change Password</h3>
      <el-form :model="passwordForm" :rules="passwordRules" ref="passwordFormRef" label-width="120px">
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
import { ref, reactive } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { authApi } from '@/api/auth'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import dayjs from 'dayjs'

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
        ElMessage.success('Password changed successfully')
        // Clear form
        passwordForm.old_password = ''
        passwordForm.new_password = ''
        passwordForm.confirm_password = ''
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
  color: #303133;
}
</style>
