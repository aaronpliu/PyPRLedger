<template>
  <AuthSplitLayout>
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
</style>
