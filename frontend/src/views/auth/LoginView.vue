<template>
  <div class="auth-container">
    <!-- Background Image Slider -->
    <AuthBackground />

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

      <!-- Theme and Language Switchers -->
      <div class="auth-switchers">
        <ThemeSwitcher />
        <el-dropdown @command="handleLanguageChange" trigger="click">
          <span class="language-flag">
            {{ languageStore.getLanguageFlag(languageStore.currentLanguage as any) }}
          </span>
          <template #dropdown>
            <el-dropdown-menu role="menu" aria-label="Language options">
              <el-dropdown-item
                v-for="lang in languageStore.availableLanguages"
                :key="lang.code"
                :command="lang.code"
                role="menuitem"
              >
                {{ lang.flag }} {{ lang.name }}
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
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
import { useLanguage } from '@/composables/useLanguage'
import ThemeSwitcher from '@/components/common/ThemeSwitcher.vue'
import AuthBackground from '@/components/auth/AuthBackground.vue'

const router = useRouter()
const authStore = useAuthStore()
const { t } = useI18n()
const languageStore = useLanguage()

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

const handleLanguageChange = (lang: string) => {
  languageStore.setLanguage(lang as any)
  ElMessage.success(`Language changed to ${languageStore.getLanguageName(lang)}`)
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
  color: #ffffff;
  letter-spacing: -0.02em;
  /* Ensure visibility against rotating backgrounds */
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
  font-size: 0.95rem;
  color: rgba(255, 255, 255, 0.9);
  margin: 0 0 16px 0;
  font-weight: 400;
  /* Ensure visibility against rotating backgrounds */
  text-shadow: 
    0 1px 2px rgba(0, 0, 0, 0.3),
    0 0 10px rgba(0, 0, 0, 0.15);
}

.rainbow-line {
  width: 100%;
  max-width: 440px;
  height: 3px;
  margin: 0 auto 24px auto;
  background: linear-gradient(90deg, 
    rgba(99, 102, 241, 0.8) 0%, 
    rgba(139, 92, 246, 0.8) 25%, 
    rgba(236, 72, 153, 0.8) 50%, 
    rgba(245, 158, 11, 0.8) 75%, 
    rgba(16, 185, 129, 0.8) 100%);
  border-radius: 2px;
  box-shadow: 
    0 2px 8px rgba(99, 102, 241, 0.4),
    0 0 20px rgba(139, 92, 246, 0.2);
  animation: pulse 3s ease-in-out infinite;
}

[data-theme='dark'] .rainbow-line {
  box-shadow: 
    0 2px 12px rgba(99, 102, 241, 0.5),
    0 0 30px rgba(139, 92, 246, 0.3);
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

/* Theme and Language Switchers */
.auth-switchers {
  position: fixed;
  top: 20px;
  right: 20px;
  z-index: 1000;
  display: flex;
  align-items: center;
  gap: 12px;
}

.language-flag {
  font-size: 20px;
  cursor: pointer;
  line-height: 1;
  user-select: none;
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
