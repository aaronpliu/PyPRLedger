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

    <el-card shadow="hover" style="margin-top: 20px;">
      <template #header>
        <div class="card-header">
          <span>{{ t('admin.systemSettings.banner') }}</span>
        </div>
      </template>

      <el-form label-width="200px" style="max-width: 600px;">
        <!-- Banner Enabled Toggle -->
        <el-form-item :label="t('admin.systemSettings.bannerEnabled')">
          <el-switch
            v-model="bannerSettings.enabled"
            :active-text="t('common.enabled')"
            :inactive-text="t('common.disabled')"
            :loading="bannerSaving"
          />
        </el-form-item>

        <!-- Banner Content -->
        <el-form-item :label="t('admin.systemSettings.bannerContent')">
          <el-input
            v-model="bannerSettings.content"
            type="textarea"
            :rows="3"
            :placeholder="t('admin.systemSettings.bannerContentPlaceholder')"
            clearable
          />
        </el-form-item>

        <!-- Banner Date Range -->
        <el-form-item :label="t('admin.systemSettings.bannerDateRange')">
          <el-date-picker
            v-model="bannerDateRange"
            type="datetimerange"
            range-separator="—"
            :start-placeholder="'Start Date'"
            :end-placeholder="'End Date'"
            value-format="YYYY-MM-DDTHH:mm:ssZ"
            style="width: 100%"
          />
          <div class="setting-description">
            {{ t('admin.systemSettings.bannerDateRangeDesc') }}
          </div>
        </el-form-item>

        <!-- Save Button & Preview -->
        <el-form-item>
          <el-button
            type="primary"
            :loading="bannerSaving"
            @click="handleBannerSave"
          >
            {{ t('common.save') }}
          </el-button>
        </el-form-item>

        <!-- Banner Preview -->
        <el-form-item v-if="bannerSettings.content" :label="t('admin.systemSettings.bannerPreview')">
          <div class="banner-preview-box">
            <el-alert
              :title="bannerSettings.content"
              type="info"
              show-icon
              :closable="false"
            />
          </div>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { rbacApi, type BannerConfig } from '@/api/rbac'

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

const bannerSettings = ref<BannerConfig>({
  enabled: false,
  content: '',
  start_date: '',
  end_date: '',
})
const bannerDateRange = ref<[string, string] | null>(null)
const bannerSaving = ref(false)

// Sync date picker with banner settings
watch(bannerDateRange, (range) => {
  if (range) {
    bannerSettings.value.start_date = range[0]
    bannerSettings.value.end_date = range[1]
  } else {
    bannerSettings.value.start_date = ''
    bannerSettings.value.end_date = ''
  }
})

// Load settings on mount
onMounted(async () => {
  await Promise.all([
    loadSettings(),
    loadLlmSettings(),
    loadBannerSettings(),
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
    // Notify PageAgent composable to re-check config immediately
    window.dispatchEvent(new CustomEvent('pageagent-config-changed'))
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

const loadBannerSettings = async () => {
  try {
    const config = await rbacApi.getBanner()
    bannerSettings.value = config
    // Sync date picker with loaded values
    if (config.start_date && config.end_date) {
      bannerDateRange.value = [config.start_date, config.end_date]
    } else {
      bannerDateRange.value = null
    }
  } catch (error) {
    console.error('Failed to load banner settings:', error)
    ElMessage.error(t('admin.systemSettings.loadFailed'))
  }
}

const handleBannerSave = async () => {
  bannerSaving.value = true
  try {
    await rbacApi.updateBanner(bannerSettings.value)
    await loadBannerSettings()
    ElMessage.success(t('admin.systemSettings.bannerSaveSuccess'))
  } catch (error: any) {
    console.error('Failed to save banner settings:', error)
    ElMessage.error(error.response?.data?.detail || t('admin.systemSettings.saveFailed'))
  } finally {
    bannerSaving.value = false
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

.banner-preview-box {
  width: 100%;
  border: 1px dashed var(--el-border-color);
  border-radius: 4px;
  padding: 8px;
  background: var(--el-fill-color-lighter);
}
</style>
