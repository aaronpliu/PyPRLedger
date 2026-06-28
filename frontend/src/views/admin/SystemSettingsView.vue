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

    <el-card shadow="hover" style="margin-top: 20px;">
      <template #header>
        <div class="card-header">
          <span>{{ t('admin.systemSettings.llmSettings') }}</span>
        </div>
      </template>

      <el-form label-width="200px" style="max-width: 600px;">
        <!-- LLM Enabled Toggle -->
        <el-form-item :label="t('admin.systemSettings.llmEnabled')">
          <el-switch
            v-model="llmSettings.enabled"
            :active-text="t('common.enabled')"
            :inactive-text="t('common.disabled')"
            :loading="llmSaving"
            @change="handleLlmSave"
          />
          <div class="setting-description">
            {{ t('admin.systemSettings.llmEnabledDesc') }}
          </div>
        </el-form-item>

        <!-- LLM Model -->
        <el-form-item :label="t('admin.systemSettings.llmModel')">
          <el-input
            v-model="llmSettings.model"
            :placeholder="t('admin.systemSettings.llmModelPlaceholder')"
            clearable
            @blur="handleLlmSave"
          />
          <div class="setting-description">
            {{ t('admin.systemSettings.llmModelDesc') }}
          </div>
        </el-form-item>

        <!-- LLM Base URL -->
        <el-form-item :label="t('admin.systemSettings.llmBaseUrl')">
          <el-input
            v-model="llmSettings.base_url"
            :placeholder="t('admin.systemSettings.llmBaseUrlPlaceholder')"
            clearable
            @blur="handleLlmSave"
          />
          <div class="setting-description">
            {{ t('admin.systemSettings.llmBaseUrlDesc') }}
          </div>
        </el-form-item>

        <!-- LLM API Key -->
        <el-form-item :label="t('admin.systemSettings.llmApiKey')">
          <el-input
            v-model="llmSettings.api_key"
            type="password"
            show-password
            :placeholder="llmSettings.has_api_key ? t('admin.systemSettings.llmApiKeyMasked') : t('admin.systemSettings.llmApiKeyPlaceholder')"
            clearable
            @blur="handleLlmSave"
          />
          <div class="setting-description">
            {{ t('admin.systemSettings.llmApiKeyDesc') }}
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

const llmSettings = ref({
  enabled: false,
  model: '',
  base_url: '',
  api_key: '',
  has_api_key: false,
})

const saving = ref(false)
const llmSaving = ref(false)

// Load settings on mount
onMounted(async () => {
  await Promise.all([
    loadSettings(),
    loadLlmSettings(),
  ])
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

const loadLlmSettings = async () => {
  try {
    const response = await rbacApi.getLlmConfig()
    llmSettings.value.enabled = response.enabled
    llmSettings.value.model = response.model
    llmSettings.value.base_url = response.base_url
    llmSettings.value.has_api_key = response.has_api_key
    llmSettings.value.api_key = '' // Never pre-fill the masked key
  } catch (error) {
    console.error('Failed to load LLM settings:', error)
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

const handleLlmSave = async () => {
  llmSaving.value = true
  try {
    const data: Record<string, any> = {
      enabled: llmSettings.value.enabled,
      model: llmSettings.value.model,
      base_url: llmSettings.value.base_url,
    }
    // Only send api_key if user provided a new one
    if (llmSettings.value.api_key) {
      data.api_key = llmSettings.value.api_key
    }
    await rbacApi.updateLlmConfig(data)
    // Reload to get fresh has_api_key status
    await loadLlmSettings()
    ElMessage.success(t('admin.systemSettings.saveSuccess'))
  } catch (error: any) {
    console.error('Failed to save LLM settings:', error)
    ElMessage.error(error.response?.data?.detail || t('admin.systemSettings.saveFailed'))
    // Reload to revert UI state
    await loadLlmSettings()
  } finally {
    llmSaving.value = false
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
