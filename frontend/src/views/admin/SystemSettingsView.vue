<template>
  <div class="system-settings">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span>{{ t('admin.systemSettings.title') }}</span>
        </div>
      </template>

      <el-form label-width="200px" style="max-width: 600px;">
        <!-- Registration Enabled Setting -->
        <el-form-item :label="t('admin.systemSettings.registrationEnabled')">
          <el-switch
            v-model="settings.registration_enabled"
            :active-text="t('common.enabled')"
            :inactive-text="t('common.disabled')"
            :loading="saving"
            @change="handleRegistrationToggle"
          />
          <div class="setting-description">
            {{ t('admin.systemSettings.registrationEnabledDesc') }}
          </div>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { rbacApi } from '@/api/rbac'

const { t } = useI18n()

const settings = ref({
  registration_enabled: true,
})

const saving = ref(false)

// Load settings on mount
onMounted(async () => {
  await loadSettings()
})

const loadSettings = async () => {
  try {
    const response = await rbacApi.getRegistrationEnabled()
    settings.value.registration_enabled = response.registration_enabled
  } catch (error) {
    console.error('Failed to load settings:', error)
    ElMessage.error(t('admin.systemSettings.loadFailed'))
  }
}

const handleRegistrationToggle = async (value: boolean) => {
  saving.value = true
  try {
    await rbacApi.updateRegistrationEnabled(value)
    ElMessage.success(t('admin.systemSettings.saveSuccess'))
  } catch (error: any) {
    console.error('Failed to save settings:', error)
    ElMessage.error(error.response?.data?.detail || t('admin.systemSettings.saveFailed'))
    // Revert the switch on error
    settings.value.registration_enabled = !value
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.system-settings {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 18px;
  font-weight: 600;
}

.setting-description {
  margin-top: 8px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
  line-height: 1.5;
}
</style>
