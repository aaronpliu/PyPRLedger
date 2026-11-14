<template>
  <div class="pat-management">
    <div class="pat-header">
      <h3>{{ t('profile.pat.title') }}</h3>
      <div class="header-actions">
        <el-button type="primary" @click="loadTokens" :loading="loading">
          <el-icon><Refresh /></el-icon>
          {{ t('profile.pat.refresh') }}
        </el-button>
        <el-button type="primary" @click="showCreateDialog = true">
          <el-icon><Plus /></el-icon>
          {{ t('profile.pat.generate_new') }}
        </el-button>
      </div>
    </div>

    <p class="pat-description">{{ t('profile.pat.description') }}</p>

    <!-- Token List -->
    <div v-loading="loading" class="token-list">
      <el-empty v-if="!loading && tokens.length === 0" :description="t('profile.pat.empty')">
        <el-button type="primary" @click="showCreateDialog = true">
          <el-icon><Plus /></el-icon>
          {{ t('profile.pat.generate_token') }}
        </el-button>
      </el-empty>

      <el-table v-else :data="tokens" stripe style="width: 100%">
        <el-table-column prop="name" :label="t('profile.pat.token_name')" min-width="200">
          <template #default="{ row }">
            <div class="token-name-cell">
              <span>{{ row.name }}</span>
              <el-tag v-if="!row.is_active" size="small" type="info">{{ t('profile.pat.revoked') }}</el-tag>
            </div>
          </template>
        </el-table-column>

        <el-table-column :label="t('profile.pat.prefix')" width="150">
          <template #default="{ row }">
            <code class="token-prefix">{{ row.prefix }}...</code>
          </template>
        </el-table-column>

        <el-table-column :label="t('profile.pat.created')" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>

        <el-table-column :label="t('profile.pat.expires')" width="180">
          <template #default="{ row }">
            <div v-if="row.expires_at">
              <el-tag :type="getExpiryType(row.expires_at)" size="small">
                {{ formatDate(row.expires_at) }}
              </el-tag>
            </div>
            <span v-else style="color: var(--el-text-color-secondary);">{{ t('profile.pat.never') }}</span>
          </template>
        </el-table-column>

        <el-table-column :label="t('profile.pat.last_used')" width="180">
          <template #default="{ row }">
            {{ row.last_used_at ? formatDate(row.last_used_at) : t('profile.pat.never') }}
          </template>
        </el-table-column>

        <el-table-column :label="t('profile.pat.actions')" width="120" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.is_active"
              size="small"
              type="danger"
              @click="handleRevokeToken(row.id, row.name)"
            >
              {{ t('profile.delegations.revoke') }}
            </el-button>
            <span v-else style="color: var(--el-text-color-secondary);">-</span>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- Create Token Dialog -->
    <el-dialog
      v-model="showCreateDialog"
      :title="t('profile.pat.dialog_title')"
      width="600px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="createFormRef"
        :model="createForm"
        :rules="createRules"
        label-width="140px"
      >
        <el-form-item :label="t('profile.pat.token_name')" prop="name">
          <el-input
            v-model="createForm.name"
            :placeholder="t('profile.pat.name_ph')"
            maxlength="100"
            show-word-limit
          />
          <div class="form-help">
            {{ t('profile.pat.name_help') }}
          </div>
        </el-form-item>

        <el-form-item :label="t('profile.pat.expiration')" prop="expires_in_days">
          <el-select v-model="createForm.expires_in_days" :placeholder="t('profile.pat.exp_ph')" style="width: 100%">
            <el-option :label="t('profile.pat.exp_7')" :value="7" />
            <el-option :label="t('profile.pat.exp_30')" :value="30" />
            <el-option :label="t('profile.pat.exp_90')" :value="90" />
            <el-option :label="t('profile.pat.exp_365')" :value="365" />
            <el-option :label="t('profile.pat.exp_none')" :value="null" />
          </el-select>
          <div class="form-help">
            {{ t('profile.pat.exp_help') }}
          </div>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="showCreateDialog = false">{{ t('common.cancel', 'Cancel') }}</el-button>
        <el-button type="primary" :loading="creating" @click="handleCreateToken">
          <el-icon><Plus /></el-icon>
          {{ t('profile.pat.generate_token') }}
        </el-button>
      </template>
    </el-dialog>

    <!-- Show Token Dialog (shown only once) -->
    <el-dialog
      v-model="showTokenDialog"
      :title="t('profile.pat.new_token_title')"
      width="700px"
      :close-on-click-modal="false"
      :show-close="false"
    >
      <div class="token-warning">
        <el-alert
          :title="t('profile.pat.copy_alert')"
          type="warning"
          :closable="false"
          show-icon
        >
          <p>{{ t('profile.pat.copy_alert_body') }}</p>
        </el-alert>
      </div>

      <div class="token-display">
        <label>{{ t('profile.pat.token_name_label') }}</label>
        <div class="token-value">{{ createdToken?.name }}</div>
      </div>

      <div class="token-display">
        <label>{{ t('profile.pat.token_value_label') }}</label>
        <div class="token-value-container">
          <code class="token-value-code">{{ createdToken?.token }}</code>
          <el-button
            type="primary"
            size="small"
            @click="copyTokenToClipboard"
          >
            <el-icon><DocumentCopy /></el-icon>
            {{ t('profile.pat.copy') }}
          </el-button>
        </div>
      </div>

      <div class="token-display">
        <label>{{ t('profile.pat.expires_label') }}</label>
        <div class="token-value">
          {{ createdToken?.expires_at ? formatDate(createdToken.expires_at) : t('profile.pat.never') }}
        </div>
      </div>

      <template #footer>
        <el-button type="primary" @click="handleTokenDialogClose">
          {{ t('profile.pat.copied_button') }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, DocumentCopy, Refresh } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'
import dayjs from 'dayjs'
import { useI18n } from 'vue-i18n'
import { patApi, type PersonalAccessToken, type PATCreateRequest } from '@/api/pat'

const { t } = useI18n()
const loading = ref(false)
const creating = ref(false)
const tokens = ref<PersonalAccessToken[]>([])

// Create dialog
const showCreateDialog = ref(false)
const createFormRef = ref<FormInstance>()
const createForm = reactive<PATCreateRequest>({
  name: '',
  expires_in_days: 90, // Default to 90 days
})

const createRules: FormRules = {
  name: [
    { required: true, message: t('profile.pat.rule_name'), trigger: 'blur' },
    { min: 1, max: 100, message: t('profile.pat.rule_name_len'), trigger: 'blur' },
  ],
}

// Show token dialog
const showTokenDialog = ref(false)
const createdToken = ref<{ name: string; token: string; expires_at: string | null } | null>(null)

// Load tokens
const loadTokens = async () => {
  loading.value = true
  try {
    const response = await patApi.listTokens(true) // Include expired for history
    tokens.value = response.items
  } catch (error) {
    ElMessage.error(t('profile.pat.load_failed'))
  } finally {
    loading.value = false
  }
}

// Create token
const handleCreateToken = async () => {
  if (!createFormRef.value) return

  await createFormRef.value.validate(async (valid) => {
    if (!valid) return

    creating.value = true
    try {
      const result = await patApi.createToken(createForm)
      
      // Store the token for display
      createdToken.value = {
        name: result.name,
        token: result.token,
        expires_at: result.expires_at,
      }

      // Close create dialog and show token dialog
      showCreateDialog.value = false
      
      // Reset form
      createForm.name = ''
      createForm.expires_in_days = 90

      // Show token dialog
      showTokenDialog.value = true

      // Reload token list
      await loadTokens()
    } catch (error: any) {
      ElMessage.error(error?.response?.data?.message || t('profile.pat.create_failed'))
    } finally {
      creating.value = false
    }
  })
}

// Revoke token
const handleRevokeToken = async (tokenId: number, tokenName: string) => {
  try {
    await ElMessageBox.confirm(
      t('profile.pat.revoke_body', { name: tokenName }),
      t('profile.pat.revoke_title'),
      { type: 'warning' }
    )

    await patApi.revokeToken(tokenId)
    ElMessage.success(t('profile.pat.revoked_success'))
    await loadTokens()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(t('profile.pat.revoke_failed'))
    }
  }
}

// Copy token to clipboard
const copyTokenToClipboard = async () => {
  if (!createdToken.value?.token) return

  try {
    await navigator.clipboard.writeText(createdToken.value.token)
    ElMessage.success(t('profile.pat.copied'))
  } catch (error) {
    ElMessage.error(t('profile.pat.copy_failed'))
  }
}

// Handle token dialog close
const handleTokenDialogClose = () => {
  showTokenDialog.value = false
  createdToken.value = null
}

// Format date. The backend stores local wall-clock time (USE_UTC_IN_DB=False),
// and the API serializes it without a timezone suffix, so it must be parsed as
// local time directly - treating it as UTC shifts the display by the local
// offset (e.g. +8h for Asia/Shanghai).
const formatDate = (dateStr: string) => {
  return dayjs(dateStr).format('YYYY-MM-DD HH:mm:ss')
}

// Get expiry type for tag color
const getExpiryType = (expiryDate: string): 'success' | 'warning' | 'danger' => {
  const now = dayjs()
  const expiry = dayjs(expiryDate)
  const diffDays = expiry.diff(now, 'day')

  if (diffDays < 7) return 'danger'
  if (diffDays < 30) return 'warning'
  return 'success'
}

onMounted(() => {
  loadTokens()
})
</script>

<style scoped>
.pat-management {
  padding: 20px;
}

.pat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.pat-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.pat-description {
  color: var(--el-text-color-secondary);
  font-size: 14px;
  line-height: 1.6;
  margin-bottom: 24px;
}

.token-list {
  min-height: 300px;
}

.token-name-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.token-prefix {
  font-family: 'Consolas', 'Courier New', monospace;
  font-size: 13px;
  color: var(--el-text-color-primary);
}

.form-help {
  color: var(--el-text-color-secondary);
  font-size: 12px;
  margin-top: 4px;
  line-height: 1.4;
}

.token-warning {
  margin-bottom: 20px;
}

.token-warning p {
  margin: 8px 0 0 0;
  font-size: 13px;
}

.token-display {
  margin-bottom: 16px;
}

.token-display label {
  display: block;
  font-weight: 600;
  margin-bottom: 8px;
  color: var(--el-text-color-primary);
}

.token-value {
  padding: 12px;
  background-color: var(--el-fill-color-light);
  border-radius: 4px;
  word-break: break-all;
  font-family: 'Consolas', 'Courier New', monospace;
  font-size: 13px;
}

.token-value-container {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.token-value-code {
  flex: 1;
  padding: 12px;
  background-color: var(--el-fill-color-light);
  border-radius: 4px;
  word-break: break-all;
  font-family: 'Consolas', 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.5;
}
</style>
