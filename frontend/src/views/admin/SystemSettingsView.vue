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

      <!-- Every banner in one list, so the page stays the same length however
           many there are; adding and editing happen in a dialog. -->
      <div class="banner-toolbar">
        <el-button type="primary" data-test="banner-add" @click="openEditor()">
          {{ t('admin.systemSettings.bannerAdd') }}
        </el-button>
      </div>

      <el-empty
        v-if="banners.length === 0"
        :description="t('admin.systemSettings.bannerEmpty')"
        :image-size="60"
      />

      <el-table v-else :data="banners" row-key="id">
        <el-table-column :label="t('admin.systemSettings.bannerContent')" min-width="240">
          <template #default="{ row }">
            <span class="banner-content-cell" :title="row.content">{{ row.content }}</span>
          </template>
        </el-table-column>

        <el-table-column :label="t('admin.systemSettings.bannerLevel')" width="110">
          <template #default="{ row }">
            <el-tag size="small" :type="row.level">{{ levelLabel(row.level) }}</el-tag>
          </template>
        </el-table-column>

        <el-table-column :label="t('admin.systemSettings.bannerWindow')" min-width="200">
          <template #default="{ row }">
            <span class="banner-window-text">{{ windowLabel(row) }}</span>
          </template>
        </el-table-column>

        <el-table-column
          :label="t('admin.systemSettings.bannerPriority')"
          width="90"
          align="center"
        >
          <template #default="{ row }">{{ row.priority }}</template>
        </el-table-column>

        <!-- Wide enough for both state labels: a switch shows the one it is in
             beside the track, not inside it. -->
        <el-table-column :label="t('admin.systemSettings.bannerStatus')" width="210">
          <template #default="{ row }">
            <!-- One-way bound on purpose: the switch shows the stored state, so a
                 write that fails leaves it where it was instead of lying. -->
            <el-switch
              :model-value="row.enabled"
              :disabled="bannerSaving"
              :active-text="t('common.enabled')"
              :inactive-text="t('common.disabled')"
              data-test="banner-enabled"
              @change="(value: string | number | boolean) => toggleBannerEnabled(row, value as boolean)"
            />
          </template>
        </el-table-column>

        <el-table-column
          :label="t('admin.systemSettings.bannerActions')"
          width="140"
          align="right"
        >
          <template #default="{ row, $index }">
            <el-button link type="primary" data-test="banner-edit" @click="openEditor(row)">
              {{ t('common.edit') }}
            </el-button>
            <el-button link type="danger" data-test="banner-remove" @click="confirmRemove($index)">
              {{ t('common.delete') }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- Add and edit share one dialog -->
      <el-dialog
        v-model="editorVisible"
        :title="editingId ? t('admin.systemSettings.bannerEdit') : t('admin.systemSettings.bannerAdd')"
        width="560px"
        :close-on-click-modal="false"
      >
        <el-form v-if="editing" label-width="150px">
          <el-form-item :label="t('admin.systemSettings.bannerEnabled')">
            <el-switch
              v-model="editing.enabled"
              :active-text="t('common.enabled')"
              :inactive-text="t('common.disabled')"
            />
          </el-form-item>

          <el-form-item :label="t('admin.systemSettings.bannerContent')" required>
            <el-input
              v-model="editing.content"
              type="textarea"
              :rows="2"
              :placeholder="t('admin.systemSettings.bannerContentPlaceholder')"
              clearable
            />
          </el-form-item>

          <el-form-item :label="t('admin.systemSettings.bannerLevel')">
            <el-radio-group v-model="editing.level">
              <el-radio-button value="info">
                {{ t('admin.systemSettings.bannerLevelInfo') }}
              </el-radio-button>
              <el-radio-button value="warning">
                {{ t('admin.systemSettings.bannerLevelWarning') }}
              </el-radio-button>
              <el-radio-button value="success">
                {{ t('admin.systemSettings.bannerLevelSuccess') }}
              </el-radio-button>
            </el-radio-group>
          </el-form-item>

          <el-form-item :label="t('admin.systemSettings.bannerPriority')">
            <el-input-number v-model="editing.priority" :min="0" :max="99" />
            <div class="setting-description">
              {{ t('admin.systemSettings.bannerPriorityDesc') }}
            </div>
          </el-form-item>

          <el-form-item :label="t('admin.systemSettings.bannerDateRange')">
            <div class="banner-window">
              <el-date-picker
                v-model="editing.start_date"
                type="datetime"
                :placeholder="t('admin.systemSettings.bannerStart')"
                value-format="YYYY-MM-DDTHH:mm:ssZ"
              />
              <span class="banner-window-separator">—</span>
              <el-date-picker
                v-model="editing.end_date"
                type="datetime"
                :placeholder="t('admin.systemSettings.bannerEnd')"
                value-format="YYYY-MM-DDTHH:mm:ssZ"
              />
            </div>
            <div class="setting-description">
              {{ t('admin.systemSettings.bannerDateRangeDesc') }}
            </div>
          </el-form-item>

          <el-form-item :label="t('admin.systemSettings.bannerLink')">
            <el-input
              v-model="editing.link_url"
              :placeholder="t('admin.systemSettings.bannerLinkUrl')"
              clearable
            />
            <el-input
              v-model="editing.link_label"
              class="banner-link-label"
              :placeholder="t('admin.systemSettings.bannerLinkLabel')"
              clearable
            />
            <div class="setting-description">
              {{ t('admin.systemSettings.bannerLinkDesc') }}
            </div>
          </el-form-item>

          <el-form-item
            v-if="editing.content.trim()"
            :label="t('admin.systemSettings.bannerPreview')"
          >
            <div class="banner-preview-box">
              <el-alert
                :title="editing.content"
                :type="editing.level"
                show-icon
                :closable="false"
              />
            </div>
          </el-form-item>
        </el-form>

        <template #footer>
          <el-button @click="editorVisible = false">{{ t('common.cancel') }}</el-button>
          <el-button
            type="primary"
            data-test="banner-save"
            :loading="bannerSaving"
            @click="saveEditor"
          >
            {{ t('common.save') }}
          </el-button>
        </template>
      </el-dialog>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useI18n } from 'vue-i18n'
import dayjs from 'dayjs'
import { createBanner, rbacApi, type BannerItem, type BannerLevel } from '@/api/rbac'

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

const banners = ref<BannerItem[]>([])
const bannerSaving = ref(false)

// Adding and editing share one dialog, so the list stays the only thing on the page.
const editorVisible = ref(false)
const editing = ref<BannerItem | null>(null)
const editingId = ref<string | null>(null)

const LEVEL_LABEL_KEYS: Record<BannerLevel, string> = {
  info: 'admin.systemSettings.bannerLevelInfo',
  warning: 'admin.systemSettings.bannerLevelWarning',
  success: 'admin.systemSettings.bannerLevelSuccess',
}

const levelLabel = (level: BannerLevel) => t(LEVEL_LABEL_KEYS[level])

/** The window as the list shows it; no bound at all reads as "always". */
function windowLabel(banner: BannerItem): string {
  if (!banner.start_date && !banner.end_date) {
    return t('admin.systemSettings.bannerAlways')
  }
  const bound = (value: string) => (value ? dayjs(value).format('YYYY-MM-DD HH:mm') : '—')
  return `${bound(banner.start_date)} → ${bound(banner.end_date)}`
}

function openEditor(banner?: BannerItem) {
  editingId.value = banner ? banner.id : null
  // Edit a copy: the list must not change until the save goes through.
  editing.value = banner ? { ...banner } : createBanner()
  editorVisible.value = true
}

/** A cleared picker hands back null; the endpoint takes an empty string for that. */
function normalizeBanner(banner: BannerItem): BannerItem {
  return {
    ...banner,
    content: banner.content.trim(),
    start_date: banner.start_date || '',
    end_date: banner.end_date || '',
    link_url: (banner.link_url || '').trim(),
    link_label: (banner.link_label || '').trim(),
  }
}

/**
 * Write the whole collection, which is the shape the endpoint takes.
 *
 * The list on screen is only replaced once the write went through, so a failed
 * save leaves what is shown matching what is stored.
 */
async function persistBanners(next: BannerItem[]): Promise<boolean> {
  bannerSaving.value = true
  try {
    const response = await rbacApi.updateBanner({ banners: next.map(normalizeBanner) })
    banners.value = (response.banners ?? next).map(normalizeBanner)
    return true
  } catch (error: any) {
    console.error('Failed to save banner settings:', error)
    ElMessage.error(error.response?.data?.detail || t('admin.systemSettings.saveFailed'))
    return false
  } finally {
    bannerSaving.value = false
  }
}

async function saveEditor() {
  const banner = editing.value
  if (!banner) return
  if (!banner.content.trim()) {
    ElMessage.warning(t('admin.systemSettings.bannerContentRequired'))
    return
  }

  const edited = normalizeBanner(banner)
  const next = editingId.value
    ? banners.value.map((item) => (item.id === editingId.value ? edited : item))
    : [...banners.value, edited]

  if (await persistBanners(next)) {
    editorVisible.value = false
    ElMessage.success(t('admin.systemSettings.bannerSaveSuccess'))
  }
}

/** Flip one banner on or off from the list, without opening the dialog. */
async function toggleBannerEnabled(banner: BannerItem, enabled: boolean) {
  const next = banners.value.map((item) => (item.id === banner.id ? { ...item, enabled } : item))
  await persistBanners(next)
}

async function confirmRemove(index: number) {
  try {
    await ElMessageBox.confirm(
      t('admin.systemSettings.bannerDeleteConfirm'),
      t('common.delete'),
      {
        type: 'warning',
        confirmButtonText: t('common.confirm'),
        cancelButtonText: t('common.cancel'),
      },
    )
  } catch {
    return // dismissed
  }

  const next = banners.value.filter((_, position) => position !== index)
  if (await persistBanners(next)) {
    ElMessage.success(t('admin.systemSettings.bannerSaveSuccess'))
  }
}

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
    banners.value = (config.banners ?? []).map(normalizeBanner)
  } catch (error) {
    console.error('Failed to load banner settings:', error)
    ElMessage.error(t('admin.systemSettings.loadFailed'))
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
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 100%;
  border: 1px dashed var(--el-border-color);
  border-radius: 4px;
  padding: 8px;
  background: var(--el-fill-color-lighter);
}

.banner-toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 12px;
}

/* Long wording is cut in the cell rather than widening the table. */
.banner-content-cell {
  display: block;
  max-width: 420px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.banner-window-text {
  font-size: 13px;
  color: var(--el-text-color-regular);
}

.banner-window {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.banner-window-separator {
  color: var(--el-text-color-secondary);
}

.banner-link-label {
  margin-top: 8px;
}

/* A table cell breaks words to fit; the switch's state label must stay in one
   piece, since a broken "Enab / led" is what it looks like when it does not. */
:deep(.el-switch__label) {
  white-space: nowrap;
}
</style>
