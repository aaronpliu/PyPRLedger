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
          <BrandLogo variant="mark" :height="46" chip alt="" class="brand-mark" />
          <div class="card-header-text">
            <h2 class="card-title">{{ t('auth.register_title') }}</h2>
            <p class="card-subtitle">{{ t('auth.registerPrompt') }}</p>
          </div>
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
import BrandLogo from '@/components/common/BrandLogo.vue'

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
  border-radius: 16px;
  background: var(--el-bg-color-overlay);
  border: 1px solid var(--el-border-color-lighter);
  box-shadow:
    0 1px 2px rgba(15, 23, 42, 0.04),
    0 12px 32px -12px rgba(15, 23, 42, 0.14);
}

[data-theme='dark'] .auth-card {
  box-shadow:
    0 1px 2px rgba(0, 0, 0, 0.35),
    0 12px 36px -10px rgba(0, 0, 0, 0.5);
}

.auth-card :deep(.el-card__body) {
  padding: 32px 28px;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 26px;
}

/* The mark in its tile, the words beside it: one line, vertically centred */
.card-header-text {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

/* The system mark, in its white tile, ties the form to the brand panel */
.brand-mark {
  flex-shrink: 0;
}

.card-title {
  font-size: 1.4rem;
  font-weight: 700;
  color: var(--el-text-color-primary);
  margin: 0;
  letter-spacing: -0.01em;
}

.card-subtitle {
  font-size: 0.9rem;
  color: var(--el-text-color-secondary);
  margin: 0;
  line-height: 1.5;
}

/* Form Styles */
.auth-form {
  width: 100%;
}

.auth-form :deep(.el-form-item) {
  margin-bottom: 18px;
}

.auth-form :deep(.el-input__wrapper) {
  border-radius: 10px;
  padding: 12px 14px;
  background: transparent;
  border: 1.5px solid var(--el-border-color);
  box-shadow: none;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.auth-form :deep(.el-input__wrapper:hover) {
  border-color: var(--el-border-color-hover);
}

.auth-form :deep(.el-input__wrapper.is-focus) {
  border-color: var(--el-color-primary);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--el-color-primary) 14%, transparent);
}

.auth-form :deep(.el-input__inner) {
  color: var(--el-text-color-primary);
  font-size: 0.95rem;
}

.auth-form :deep(.el-input__prefix) {
  color: var(--el-text-color-secondary);
  margin-right: 8px;
  transition: color 0.2s ease;
}

.auth-form :deep(.el-input__wrapper.is-focus .el-input__prefix) {
  color: var(--el-color-primary);
}

.submit-button {
  width: 100%;
  height: 46px;
  border-radius: 10px;
  font-size: 0.95rem;
  font-weight: 600;
  letter-spacing: 0.01em;
  background: var(--el-color-primary);
  border: none;
  transition: all 0.2s ease;
  margin-top: 8px;
}

.submit-button:hover {
  background: var(--el-color-primary-light-3);
  box-shadow: 0 4px 14px color-mix(in srgb, var(--el-color-primary) 35%, transparent);
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

/* Stacked, the card sits flat: the panel already carries the theme surface */
@media (max-width: 960px) {
  .auth-card {
    box-shadow: none;
  }
}

@media (max-width: 768px) {
  .card-title {
    font-size: 1.3rem;
  }
}

@media (max-width: 480px) {
  .auth-card :deep(.el-card__body) {
    padding: 24px 20px;
  }

  .card-title {
    font-size: 1.2rem;
  }
}
</style>