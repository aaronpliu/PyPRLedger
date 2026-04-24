<template>
  <div class="auth-container">
    <!-- Background Pattern -->
    <div class="auth-background">
      <div class="gradient-overlay"></div>
    </div>

    <!-- Main Content -->
    <div class="auth-content">
      <!-- Header -->
      <div class="auth-header">
        <h1 class="brand-title">PR Ledger</h1>
        <p class="brand-subtitle">{{ t('auth.login_subtitle') }}</p>
        <div class="rainbow-line"></div>
      </div>

      <!-- Login Card -->
      <el-card class="auth-card" shadow="always">
        <div class="card-header">
          <h2 class="card-title">{{ t('auth.login_title') }}</h2>
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
          
          <div class="auth-footer" v-if="registrationEnabled">
            <span>{{ t('auth.dont_have_account') }}</span>
            <router-link to="/register" class="auth-link">{{ t('common.register') }}</router-link>
          </div>
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
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import { rbacApi } from '@/api/rbac'
import { useI18n } from 'vue-i18n'
import ThemeSwitcher from '@/components/common/ThemeSwitcher.vue'

const router = useRouter()
const authStore = useAuthStore()
const { t } = useI18n()

const formRef = ref<FormInstance>()
const loading = ref(false)
const registrationEnabled = ref(false)

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

const rules: FormRules = {
  username: [
    { required: true, message: t('auth.username_required'), trigger: 'blur' },
  ],
  password: [
    { required: true, message: t('auth.password_required'), trigger: 'blur' },
    { min: 6, message: t('auth.password_min_length'), trigger: 'blur' },
  ],
}

const handleLogin = async () => {
  if (!formRef.value) return
  
  await formRef.value.validate(async (valid) => {
    if (valid) {
      loading.value = true
      try {
        await authStore.login(form)
        ElMessage.success(t('auth.login_success'))
        router.push('/')
      } catch (error) {
        ElMessage.error(t('auth.login_failed'))
      } finally {
        loading.value = false
      }
    }
  })
}
</script>

<style scoped>
.auth-container {
  position: relative;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  background: var(--el-bg-color);
}

/* Background Pattern */
.auth-background {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 0;
}

.gradient-overlay {
  position: absolute;
  width: 100%;
  height: 100%;
  background: radial-gradient(circle at 50% 0%, rgba(99, 102, 241, 0.08) 0%, transparent 50%),
              radial-gradient(circle at 80% 80%, rgba(168, 85, 247, 0.06) 0%, transparent 40%);
}

[data-theme='dark'] .gradient-overlay {
  background: radial-gradient(circle at 50% 0%, rgba(99, 102, 241, 0.12) 0%, transparent 50%),
              radial-gradient(circle at 80% 80%, rgba(168, 85, 247, 0.1) 0%, transparent 40%);
}

/* Main Content */
.auth-content {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 520px;
  padding: 24px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 32px;
}

/* Header Section */
.auth-header {
  text-align: center;
  width: 100%;
}

.brand-title {
  font-size: 2.25rem;
  font-weight: 700;
  margin: 0 0 8px 0;
  color: var(--el-text-color-primary);
  letter-spacing: -0.02em;
}

.brand-subtitle {
  font-size: 0.95rem;
  color: var(--el-text-color-secondary);
  margin: 0 0 16px 0;
  font-weight: 400;
}

.rainbow-line {
  width: 100%;
  max-width: 440px;
  height: 3px;
  margin: 0 auto 24px auto;
  background: linear-gradient(90deg, 
    rgba(99, 102, 241, 0.3) 0%, 
    rgba(139, 92, 246, 0.3) 25%, 
    rgba(236, 72, 153, 0.3) 50%, 
    rgba(245, 158, 11, 0.3) 75%, 
    rgba(16, 185, 129, 0.3) 100%);
  border-radius: 2px;
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.15);
  animation: pulse 3s ease-in-out infinite;
}

[data-theme='dark'] .rainbow-line {
  box-shadow: 0 2px 12px rgba(99, 102, 241, 0.25);
  background: linear-gradient(90deg, 
    rgba(99, 102, 241, 0.4) 0%, 
    rgba(139, 92, 246, 0.4) 25%, 
    rgba(236, 72, 153, 0.4) 50%, 
    rgba(245, 158, 11, 0.4) 75%, 
    rgba(16, 185, 129, 0.4) 100%);
}

@keyframes pulse {
  0%, 100% {
    opacity: 0.6;
  }
  50% {
    opacity: 1;
  }
}

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
  margin: 0;
}

.card-subtitle {
  font-size: 0.9rem;
  color: var(--el-text-color-secondary);
  margin: 0;
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

/* Theme Switcher */
.theme-switcher-container {
  position: fixed;
  top: 20px;
  right: 20px;
  z-index: 1000;
}

/* Responsive Design */
@media (max-width: 768px) {
  .auth-content {
    padding: 20px;
    gap: 24px;
  }

  .brand-title {
    font-size: 2rem;
  }

  .card-title {
    font-size: 1.35rem;
  }
}

@media (max-width: 480px) {
  .auth-content {
    padding: 16px;
  }

  .brand-title {
    font-size: 1.75rem;
  }

  .card-title {
    font-size: 1.25rem;
  }

  .theme-switcher-container {
    top: 12px;
    right: 12px;
  }
}

/* Landscape orientation on mobile */
@media (max-height: 600px) and (orientation: landscape) {
  .auth-container {
    padding: 16px 0;
  }

  .auth-content {
    gap: 20px;
  }

  .brand-title {
    font-size: 1.5rem;
  }
}

/* High resolution screens */
@media (min-width: 1920px) {
  .auth-content {
    max-width: 480px;
  }

  .brand-title {
    font-size: 2.5rem;
  }
}

/* Print styles */
@media print {
  .auth-background,
  .theme-switcher-container {
    display: none;
  }

  .auth-container {
    background: white;
  }
}
</style>
