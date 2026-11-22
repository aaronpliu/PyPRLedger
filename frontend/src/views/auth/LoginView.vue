<template>
  <AuthSplitLayout>
    <!-- Login Card -->
    <el-card class="auth-card" shadow="always">
      <div class="card-header">
        <BrandLogo variant="mark" :height="46" chip alt="" class="brand-mark" />
        <h2 class="card-title">{{ t('auth.login_title') }}</h2>
        <p class="card-subtitle">{{ t('auth.login_subtitle') }}</p>
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
          
          <el-form-item prop="password">
            <el-input
              v-model="form.password"
              type="password"
              :placeholder="t('auth.password')"
              size="large"
              show-password
              @keyup.enter="handleLogin"
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
              @click="handleLogin"
              class="submit-button"
            >
              {{ loading ? t('common.logging_in') : t('common.login') }}
            </el-button>
          </el-form-item>
          
          <!-- Inline Error Message -->
          <el-alert
            v-if="loginError"
            :title="loginError"
            type="error"
            :closable="true"
            @close="loginError = ''"
            show-icon
            class="inline-error"
          />
          
          <div class="auth-footer" v-if="registrationEnabled">
            <span>{{ t('auth.dont_have_account') }}</span>
            <router-link to="/register" class="auth-link">{{ t('common.register') }}</router-link>
          </div>
        </el-form>
      </el-card>
</AuthSplitLayout>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import { rbacApi } from '@/api/rbac'
import { useI18n } from 'vue-i18n'
import AuthSplitLayout from '@/components/auth/AuthSplitLayout.vue'
import BrandLogo from '@/components/common/BrandLogo.vue'

const router = useRouter()
const authStore = useAuthStore()
const { t, locale } = useI18n()

const formRef = ref<FormInstance>()
const loading = ref(false)
const registrationEnabled = ref(false)
const loginError = ref('')

// Check if registration is enabled
onMounted(async () => {
  try {
    const response = await rbacApi.getRegistrationEnabled()
    registrationEnabled.value = response.registration_enabled
  } catch (error) {
    console.error('Failed to check registration status:', error)
    // Default to disabled on error for security
    registrationEnabled.value = false
  }
})

const form = reactive({
  username: '',
  password: '',
})

// Computed so validation messages follow a language change made on this page
const rules = computed<FormRules>(() => ({
  username: [
    { required: true, message: t('auth.username_required'), trigger: 'blur' },
  ],
  password: [
    { required: true, message: t('auth.password_required'), trigger: 'blur' },
    { min: 6, message: t('auth.password_min_length'), trigger: 'blur' },
  ],
}))

// A message already on screen was written in the previous language
watch(locale, () => {
  loginError.value = ''
  formRef.value?.clearValidate()
})

const handleLogin = async () => {
  if (!formRef.value) return
  
  // Clear previous errors
  loginError.value = ''
  
  await formRef.value.validate(async (valid) => {
    if (valid) {
      loading.value = true
      try {
        await authStore.login(form)
        router.push('/')
      } catch (error: any) {
        console.error('Login error:', error)
        
        // Extract specific error message from the response
        // Backend returns: { error: "CODE", message: "Human readable message", detail: null }
        const responseData = error?.response?.data
        loginError.value = responseData?.message || 
                         responseData?.detail || 
                         responseData?.error ||
                         error?.message ||
                         t('auth.login_failed')
        
        console.log('Extracted error message:', loginError.value)
      } finally {
        loading.value = false
      }
    }
  })
}

</script>

<style scoped>
/* The page's own styles start at the card: the container, the brand header and
   the switchers live in the shared split layout now */

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
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
  margin-bottom: 26px;
}

/* The system mark, in its white tile, ties the form to the brand panel */
.brand-mark {
  margin-bottom: 10px;
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

/* the field tells you it is listening: its icon joins the focus colour */
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

.submit-button:active {
  transform: translateY(0);
}

/* Footer */
.auth-footer {
  text-align: center;
  margin-top: 16px;
  padding-top: 16px;
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

/* Stacked, the panel behind the card already carries the theme surface, so the
   card drops its shadow and sits flat instead of nesting frames in frames */
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
