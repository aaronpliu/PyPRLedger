<template>
  <AuthSplitLayout>
      <!-- Loading State -->
      <el-card v-if="loadingCheck" class="auth-card" shadow="always">
        <div class="loading-state">
          <el-icon class="is-loading" :size="48"><Loading /></el-icon>
          <p>{{ t('common.loading') }}</p>
        </div>
      </el-card>

      <!-- Registration Card -->
      <el-card v-else-if="registrationEnabled" class="auth-card" shadow="always">
        <div class="card-header">
          <h2 class="card-title">{{ t('auth.register_title') }}</h2>
          <p class="card-subtitle">{{ t('auth.registerPrompt') }}</p>
        </div>
        
        <el-form :model="form" :rules="rules" ref="formRef" label-width="0" class="auth-form">
          <el-form-item prop="username">
            <el-input
              v-model="form.username"
              :placeholder="t('auth.username')"
              size="large"
              clearable
            >
              <template #prefix>
                <el-icon><User /></el-icon>
              </template>
            </el-input>
          </el-form-item>
          
          <el-form-item prop="email">
            <el-input
              v-model="form.email"
              :placeholder="t('auth.email')"
              size="large"
              clearable
            >
              <template #prefix>
                <el-icon><Message /></el-icon>
              </template>
            </el-input>
          </el-form-item>
          
          <el-form-item prop="password">
            <el-input
              v-model="form.password"
              type="password"
              :placeholder="t('auth.password')"
              size="large"
              show-password
            >
              <template #prefix>
                <el-icon><Lock /></el-icon>
              </template>
            </el-input>
          </el-form-item>
          
          <el-form-item prop="confirmPassword">
            <el-input
              v-model="form.confirmPassword"
              type="password"
              :placeholder="t('auth.confirm_password')"
              size="large"
              show-password
              @keyup.enter="handleRegister"
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
              @click="handleRegister"
              class="submit-button"
            >
              {{ loading ? t('common.creating_account') : t('common.register') }}
            </el-button>
          </el-form-item>
          
          <!-- Inline Error Message -->
          <el-alert
            v-if="registerError"
            :title="registerError"
            type="error"
            :closable="true"
            @close="registerError = ''"
            show-icon
            class="inline-error"
          />
          
          <div class="auth-footer">
            <span>{{ t('auth.already_have_account') }}</span>
            <router-link to="/login" class="auth-link">{{ t('common.login') }}</router-link>
          </div>
        </el-form>
      </el-card>
    
      <!-- Disabled Registration Card -->
      <el-card v-else class="auth-card" shadow="always">
        <div class="disabled-registration">
          <el-result icon="warning" :title="t('auth.registration_disabled')">
            <template #sub-title>
              <p>{{ t('auth.registration_disabled_message') }}</p>
              <p>{{ t('auth.contact_admin') }}</p>
            </template>
            <template #extra>
              <el-button type="primary" size="large" @click="$router.push('/login')">
                {{ t('auth.back_to_login') }}
              </el-button>
            </template>
          </el-result>
        </div>
      </el-card>
  </AuthSplitLayout>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { User, Lock, Message, Loading } from '@element-plus/icons-vue'
import { rbacApi } from '@/api/rbac'
import { useI18n } from 'vue-i18n'
import AuthSplitLayout from '@/components/auth/AuthSplitLayout.vue'

const router = useRouter()
const authStore = useAuthStore()
const { t } = useI18n()

const formRef = ref<FormInstance>()
const loading = ref(false)
const loadingCheck = ref(true)
const registrationEnabled = ref(false)
const registerError = ref('')

// Check if registration is enabled
onMounted(async () => {
  try {
    const response = await rbacApi.getRegistrationEnabled()
    registrationEnabled.value = response.registration_enabled
  } catch (error) {
    console.error('Failed to check registration status:', error)
    // Default to disabled on error for security
    registrationEnabled.value = false
  } finally {
    loadingCheck.value = false
  }
})

const form = reactive({
  username: '',
  email: '',
  password: '',
  confirmPassword: '',
})

const validatePass = (rule: any, value: string, callback: any) => {
  if (value === '') {
    callback(new Error(t('auth.password_required')))
  } else {
    if (form.confirmPassword !== '') {
      formRef.value?.validateField('confirmPassword')
    }
    callback()
  }
}

const validatePass2 = (rule: any, value: string, callback: any) => {
  if (value === '') {
    callback(new Error(t('auth.confirm_password_required')))
  } else if (value !== form.password) {
    callback(new Error(t('auth.passwords_not_match')))
  } else {
    callback()
  }
}

const rules: FormRules = {
  username: [
    { required: true, message: t('auth.username_required'), trigger: 'blur' },
    { min: 3, max: 20, message: t('auth.username_length'), trigger: 'blur' },
  ],
  email: [
    { required: true, message: t('auth.email_required'), trigger: 'blur' },
    { type: 'email', message: t('auth.email_invalid'), trigger: 'blur' },
  ],
  password: [
    { validator: validatePass, trigger: 'blur' },
    { min: 6, message: t('auth.password_min_length'), trigger: 'blur' },
  ],
  confirmPassword: [
    { validator: validatePass2, trigger: 'blur' },
  ],
}

const handleRegister = async () => {
  if (!formRef.value) return
  
  // Clear previous errors
  registerError.value = ''
  
  await formRef.value.validate(async (valid) => {
    if (valid) {
      loading.value = true
      try {
        await authStore.register({
          username: form.username,
          email: form.email,
          password: form.password,
        })
        router.push('/')
      } catch (error: any) {
        console.error('Registration error:', error)
        
        // Extract specific error message from the response
        // Backend returns: { error: "CODE", message: "Human readable message", detail: null }
        const responseData = error?.response?.data
        registerError.value = responseData?.message || 
                            responseData?.detail || 
                            responseData?.error ||
                            error?.message ||
                            t('auth.register_failed')
        
        console.log('Extracted error message:', registerError.value)
      } finally {
        loading.value = false
      }
    }
  })
}

</script>

<style scoped>
/* The container, brand header and background belong to the shared split
   layout now; this page styles only its cards and form */

/* Auth Card */
.auth-card {
  width: 100%;
  border-radius: 12px;
  background: var(--el-bg-color-overlay);
  border: 1px solid var(--el-border-color);
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.06);
  transition: all 0.3s ease;
}

.auth-card:hover {
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
  transform: translateY(-2px);
}

.card-header {
  margin-bottom: 24px;
  text-align: center;
}

.card-title {
  font-size: 1.5rem;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin: 0 0 8px 0;
}

.card-subtitle {
  font-size: 0.95rem;
  color: var(--el-color-primary);
  margin: 0;
  padding: 8px 16px;
  background: var(--el-fill-color-light);
  border-radius: 6px;
  display: inline-block;
  font-weight: 500;
  border: 1px solid var(--el-border-color-light);
}

[data-theme='dark'] .card-subtitle {
  background: rgba(var(--el-color-primary-rgb), 0.1);
  border-color: rgba(var(--el-color-primary-rgb), 0.3);
}

/* Form Styles */
.auth-form {
  width: 100%;
}

.auth-form :deep(.el-form-item) {
  margin-bottom: 20px;
}

.auth-form :deep(.el-input__wrapper) {
  border-radius: 8px;
  padding: 12px 14px;
  background: var(--el-fill-color-light);
  border: 1.5px solid var(--el-border-color);
  box-shadow: none;
  transition: all 0.2s ease;
}

.auth-form :deep(.el-input__wrapper:hover) {
  border-color: var(--el-border-color-hover);
  background: var(--el-fill-color);
}

.auth-form :deep(.el-input__wrapper.is-focus) {
  border-color: var(--el-color-primary);
  background: var(--el-fill-color);
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
}

.auth-form :deep(.el-input__inner) {
  color: var(--el-text-color-primary);
  font-size: 0.95rem;
}

.auth-form :deep(.el-input__prefix) {
  color: var(--el-text-color-secondary);
  margin-right: 8px;
}

.submit-button {
  width: 100%;
  height: 44px;
  border-radius: 8px;
  font-size: 0.95rem;
  font-weight: 600;
  background: var(--el-color-primary);
  border: none;
  transition: all 0.2s ease;
  margin-top: 8px;
}

.submit-button:hover {
  background: var(--el-color-primary-light-3);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
}

.submit-button:active {
  transform: translateY(0);
}

/* Inline Error Message */
.inline-error {
  margin-top: 16px;
  margin-bottom: 0;
  border-radius: 8px;
  animation: slideDown 0.3s ease;
}

@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Footer */
.auth-footer {
  text-align: center;
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid var(--el-border-color-lighter);
  color: var(--el-text-color-secondary);
  font-size: 0.9rem;
}

.auth-link {
  color: var(--el-color-primary);
  text-decoration: none;
  font-weight: 600;
  margin-left: 4px;
  transition: all 0.2s ease;
}

.auth-link:hover {
  color: var(--el-color-primary-light-3);
  text-decoration: underline;
}

/* Disabled Registration */
.disabled-registration {
  padding: 40px 20px;
}

.disabled-registration :deep(.el-result__title) {
  font-size: 1.5rem;
  font-weight: 600;
}

.disabled-registration :deep(.el-result__subtitle p) {
  font-size: 0.95rem;
  line-height: 1.6;
}

/* Loading State */
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: 60px 20px;
  color: var(--el-text-color-secondary);
}

.loading-state p {
  margin: 0;
  font-size: 0.95rem;
}

.loading-state .el-icon {
  color: var(--el-color-primary);
}

@media (max-width: 768px) {
  .card-title {
    font-size: 1.35rem;
  }
}

@media (max-width: 480px) {
  .card-title {
    font-size: 1.25rem;
  }
}
</style>