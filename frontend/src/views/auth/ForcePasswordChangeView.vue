<template>
  <AuthSplitLayout>
    <!-- Password Change Card -->
    <el-card class="auth-card" shadow="always">
      <div class="card-header">
        <BrandLogo variant="mark" :height="46" chip alt="" class="brand-mark" />
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
  </AuthSplitLayout>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage } from 'element-plus'
import { Lock } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'
import AuthSplitLayout from '@/components/auth/AuthSplitLayout.vue'
import BrandLogo from '@/components/common/BrandLogo.vue'
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
/* The container, brand header and switchers live in the shared split layout;
   this page styles only its card and form */
.auth-card {
  width: 100%;
  border-radius: 16px;
  overflow: hidden;
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

.auth-form {
  padding: 0;
}

.auth-form :deep(.el-form-item) {
  margin-bottom: 18px;
}

.auth-form :deep(.el-input__wrapper) {
  border-radius: 10px;
  background: transparent;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.auth-form :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--el-color-primary) 14%, transparent);
}

.auth-form :deep(.el-input__wrapper.is-focus .el-input__prefix) {
  color: var(--el-color-primary);
}

.submit-button {
  width: 100%;
  height: 46px;
  border-radius: 10px;
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 0.01em;
}

.inline-error {
  margin-top: 16px;
}

/* Stacked, the card sits flat: the panel already carries the theme surface */
@media (max-width: 960px) {
  .auth-card {
    box-shadow: none;
  }
}

@media (max-width: 480px) {
  .auth-card :deep(.el-card__body) {
    padding: 24px 20px;
  }
}
</style>
