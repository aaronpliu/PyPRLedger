<template>
  <div class="force-password-change-container">
    <!-- Background Image Slider -->
    <AuthBackground />

    <!-- Main Content -->
    <div class="auth-content">
      <!-- Header -->
      <div class="auth-header">
        <h1 class="brand-title">PR Ledger</h1>
        <p class="brand-subtitle">{{ t('auth.password_change_required') }}</p>
        <div class="rainbow-line"></div>
      </div>

      <!-- Password Change Card -->
      <el-card class="auth-card" shadow="always">
        <div class="card-header">
          <h2 class="card-title">{{ t('auth.change_password_title') }}</h2>
          <p class="card-subtitle">{{ t('auth.first_login_password_change') }}</p>
        </div>
        
        <el-form :model="form" :rules="rules" ref="formRef" label-width="0" class="auth-form">
          <el-alert
            type="info"
            :closable="false"
            style="margin-bottom: 20px;"
          >
            {{ t('auth.admin_reset_password_notice') }}
          </el-alert>

          <el-form-item prop="new_password">
            <el-input
              v-model="form.new_password"
              type="password"
              :placeholder="t('auth.new_password')"
              size="large"
              show-password
            >
              <template #prefix>
                <el-icon><Lock /></el-icon>
              </template>
            </el-input>
          </el-form-item>
          
          <el-form-item prop="confirm_password">
            <el-input
              v-model="form.confirm_password"
              type="password"
              :placeholder="t('auth.confirm_new_password')"
              size="large"
              show-password
              @keyup.enter="handleChangePassword"
            >
              <template #prefix>
                <el-icon><Lock /></el-icon>
              </template>
            </el-input>
          </el-form-item>
          
          <el-form-item>
            <el-button
              type="primary"
              size="large"
              :loading="loading"
              @click="handleChangePassword"
              class="submit-button"
            >
              {{ loading ? t('common.updating') : t('auth.update_password') }}
            </el-button>
          </el-form-item>
          
          <!-- Inline Error Message -->
          <el-alert
            v-if="errorMessage"
            :title="errorMessage"
            type="error"
            :closable="true"
            @close="errorMessage = ''"
            show-icon
            class="inline-error"
          />
        </el-form>
      </el-card>

      <!-- Theme Switcher -->
      <div class="theme-switcher-container">
        <ThemeSwitcher />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage } from 'element-plus'
import { Lock } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'
import ThemeSwitcher from '@/components/common/ThemeSwitcher.vue'
import AuthBackground from '@/components/auth/AuthBackground.vue'
import { authApi } from '@/api/auth'

const router = useRouter()
const authStore = useAuthStore()
const { t } = useI18n()

const formRef = ref<FormInstance>()
const loading = ref(false)
const errorMessage = ref('')

const form = reactive({
  new_password: '',
  confirm_password: '',
})

const validatePass = (rule: any, value: string, callback: any) => {
  if (value === '') {
    callback(new Error(t('auth.new_password_required')))
  } else if (value.length < 8) {
    callback(new Error(t('auth.password_min_length_8')))
  } else {
    if (form.confirm_password !== '') {
      formRef.value?.validateField('confirm_password')
    }
    callback()
  }
}

const validatePass2 = (rule: any, value: string, callback: any) => {
  if (value === '') {
    callback(new Error(t('auth.confirm_password_required')))
  } else if (value !== form.new_password) {
    callback(new Error(t('auth.passwords_not_match')))
  } else {
    callback()
  }
}

const rules: FormRules = {
  new_password: [
    { validator: validatePass, trigger: 'blur' },
  ],
  confirm_password: [
    { validator: validatePass2, trigger: 'blur' },
  ],
}

const handleChangePassword = async () => {
  if (!formRef.value) return
  
  // Clear previous errors
  errorMessage.value = ''
  
  await formRef.value.validate(async (valid) => {
    if (valid) {
      loading.value = true
      try {
        // Call change password API
        await authApi.changePassword({
          old_password: '', // Backend will skip verification when must_change_password is true
          new_password: form.new_password,
        })
        
        // Show success message
        ElMessage.success(t('auth.password_changed'))
        
        // Refresh user profile to update must_change_password flag
        // The backend automatically clears must_change_password after successful password change
        await authStore.fetchUserProfile()
        
        // Navigate to dashboard - user stays logged in with updated session
        router.push({ name: 'Dashboard' })
      } catch (error: any) {
        console.error('Password change error:', error)
        errorMessage.value = error.response?.data?.detail || t('auth.password_change_failed')
      } finally {
        loading.value = false
      }
    }
  })
}
</script>

<style scoped>
.force-password-change-container {
  min-height: 100vh;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
}

.auth-background {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  z-index: 0;
}

.gradient-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.05'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E");
}

.auth-content {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 480px;
  padding: 20px;
}

.auth-header {
  text-align: center;
  margin-bottom: 32px;
}

.brand-title {
  font-size: 36px;
  font-weight: 700;
  color: white;
  margin: 0 0 8px 0;
  /* Enhanced visibility against rotating backgrounds */
  text-shadow: 
    0 2px 4px rgba(0, 0, 0, 0.3),
    0 0 20px rgba(0, 0, 0, 0.2),
    0 0 40px rgba(0, 0, 0, 0.1);
  transition: all 0.3s ease;
}

.brand-title:hover {
  text-shadow: 
    0 2px 8px rgba(0, 0, 0, 0.4),
    0 0 30px rgba(0, 0, 0, 0.3),
    0 0 60px rgba(0, 0, 0, 0.2);
  transform: translateY(-1px);
}

.brand-subtitle {
  font-size: 16px;
  color: rgba(255, 255, 255, 0.9);
  margin: 0;
  /* Ensure visibility against rotating backgrounds */
  text-shadow: 
    0 1px 2px rgba(0, 0, 0, 0.3),
    0 0 10px rgba(0, 0, 0, 0.15);
}

.rainbow-line {
  height: 3px;
  background: linear-gradient(90deg, 
    rgba(255, 107, 107, 0.8), 
    rgba(254, 202, 87, 0.8), 
    rgba(72, 219, 251, 0.8), 
    rgba(255, 159, 243, 0.8), 
    rgba(84, 160, 255, 0.8));
  border-radius: 2px;
  margin-top: 16px;
  box-shadow: 
    0 2px 8px rgba(255, 107, 107, 0.4),
    0 0 20px rgba(254, 202, 87, 0.2);
}

.auth-card {
  border-radius: 12px;
  overflow: hidden;
}

.card-header {
  text-align: center;
  margin-bottom: 24px;
}

.card-title {
  font-size: 24px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin: 0 0 8px 0;
}

.card-subtitle {
  font-size: 14px;
  color: var(--el-text-color-secondary);
  margin: 0;
}

.auth-form {
  padding: 0 8px;
}

.submit-button {
  width: 100%;
  height: 44px;
  font-size: 16px;
  font-weight: 500;
}

.inline-error {
  margin-top: 16px;
}

.theme-switcher-container {
  position: fixed;
  top: 20px;
  right: 20px;
  z-index: 1000;
}

[data-theme='dark'] .auth-background {
  background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
}

[data-theme='dark'] .gradient-overlay {
  opacity: 0.3;
}
</style>
