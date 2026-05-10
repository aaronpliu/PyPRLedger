<template>
  <div class="pat-management">
    <div class="pat-header">
      <h3>Personal Access Tokens</h3>
      <el-button type="primary" @click="showCreateDialog = true">
        <el-icon><Plus /></el-icon>
        Generate New Token
      </el-button>
    </div>

    <p class="pat-description">
      Personal access tokens function like passwords for programmatic API access. 
      Tokens are shown only once at creation time, so make sure to copy them immediately.
    </p>

    <!-- Token List -->
    <div v-loading="loading" class="token-list">
      <el-empty v-if="!loading && tokens.length === 0" description="No personal access tokens">
        <el-button type="primary" @click="showCreateDialog = true">Generate Token</el-button>
      </el-empty>

      <el-table v-else :data="tokens" stripe style="width: 100%">
        <el-table-column prop="name" label="Token Name" min-width="200">
          <template #default="{ row }">
            <div class="token-name-cell">
              <span>{{ row.name }}</span>
              <el-tag v-if="!row.is_active" size="small" type="info">Revoked</el-tag>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="Token Prefix" width="150">
          <template #default="{ row }">
            <code class="token-prefix">{{ row.prefix }}...</code>
          </template>
        </el-table-column>

        <el-table-column label="Created" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>

        <el-table-column label="Expires" width="180">
          <template #default="{ row }">
            <div v-if="row.expires_at">
              <el-tag :type="getExpiryType(row.expires_at)" size="small">
                {{ formatDate(row.expires_at) }}
              </el-tag>
            </div>
            <span v-else style="color: var(--el-text-color-secondary);">Never</span>
          </template>
        </el-table-column>

        <el-table-column label="Last Used" width="180">
          <template #default="{ row }">
            {{ row.last_used_at ? formatDate(row.last_used_at) : 'Never' }}
          </template>
        </el-table-column>

        <el-table-column label="Actions" width="120" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.is_active"
              size="small"
              type="danger"
              @click="handleRevokeToken(row.id, row.name)"
            >
              Revoke
            </el-button>
            <span v-else style="color: var(--el-text-color-secondary);">-</span>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- Create Token Dialog -->
    <el-dialog
      v-model="showCreateDialog"
      title="Generate Personal Access Token"
      width="600px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="createFormRef"
        :model="createForm"
        :rules="createRules"
        label-width="140px"
      >
        <el-form-item label="Token Name" prop="name">
          <el-input
            v-model="createForm.name"
            placeholder="e.g., CI/CD Pipeline, Local Development"
            maxlength="100"
            show-word-limit
          />
          <div class="form-help">
            Choose a descriptive name to help you identify this token's purpose
          </div>
        </el-form-item>

        <el-form-item label="Expiration" prop="expires_in_days">
          <el-select v-model="createForm.expires_in_days" placeholder="Select expiration" style="width: 100%">
            <el-option label="7 days" :value="7" />
            <el-option label="30 days" :value="30" />
            <el-option label="90 days (recommended)" :value="90" />
            <el-option label="365 days" :value="365" />
            <el-option label="No expiration" :value="null" />
          </el-select>
          <div class="form-help">
            Tokens will automatically expire after the selected period
          </div>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="showCreateDialog = false">Cancel</el-button>
        <el-button type="primary" :loading="creating" @click="handleCreateToken">
          Generate Token
        </el-button>
      </template>
    </el-dialog>

    <!-- Show Token Dialog (shown only once) -->
    <el-dialog
      v-model="showTokenDialog"
      title="Your New Personal Access Token"
      width="700px"
      :close-on-click-modal="false"
      :show-close="false"
    >
      <div class="token-warning">
        <el-alert
          title="Important: Copy your token now!"
          type="warning"
          :closable="false"
          show-icon
        >
          <p>This token will only be shown once. If you lose it, you'll need to generate a new one.</p>
        </el-alert>
      </div>

      <div class="token-display">
        <label>Token Name:</label>
        <div class="token-value">{{ createdToken?.name }}</div>
      </div>

      <div class="token-display">
        <label>Token Value:</label>
        <div class="token-value-container">
          <code class="token-value-code">{{ createdToken?.token }}</code>
          <el-button
            type="primary"
            size="small"
            @click="copyTokenToClipboard"
          >
            <el-icon><DocumentCopy /></el-icon>
            Copy
          </el-button>
        </div>
      </div>

      <div class="token-display">
        <label>Expires:</label>
        <div class="token-value">
          {{ createdToken?.expires_at ? formatDate(createdToken.expires_at) : 'Never' }}
        </div>
      </div>

      <template #footer>
        <el-button type="primary" @click="handleTokenDialogClose">
          I've Copied My Token
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, DocumentCopy } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'
import dayjs from 'dayjs'
import utc from 'dayjs/plugin/utc'
import timezone from 'dayjs/plugin/timezone'
import { patApi, type PersonalAccessToken, type PATCreateRequest } from '@/api/pat'

// Initialize dayjs plugins
dayjs.extend(utc)
dayjs.extend(timezone)

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
    { required: true, message: 'Please enter a token name', trigger: 'blur' },
    { min: 1, max: 100, message: 'Name must be between 1 and 100 characters', trigger: 'blur' },
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
    ElMessage.error('Failed to load personal access tokens')
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
      ElMessage.error(error?.response?.data?.message || 'Failed to create token')
    } finally {
      creating.value = false
    }
  })
}

// Revoke token
const handleRevokeToken = async (tokenId: number, tokenName: string) => {
  try {
    await ElMessageBox.confirm(
      `Are you sure you want to revoke the token "${tokenName}"? This action cannot be undone.`,
      'Revoke Token',
      { type: 'warning' }
    )

    await patApi.revokeToken(tokenId)
    ElMessage.success('Token revoked successfully')
    await loadTokens()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('Failed to revoke token')
    }
  }
}

// Copy token to clipboard
const copyTokenToClipboard = async () => {
  if (!createdToken.value?.token) return

  try {
    await navigator.clipboard.writeText(createdToken.value.token)
    ElMessage.success('Token copied to clipboard')
  } catch (error) {
    ElMessage.error('Failed to copy token')
  }
}

// Handle token dialog close
const handleTokenDialogClose = () => {
  showTokenDialog.value = false
  createdToken.value = null
}

// Format date - converts UTC to local timezone
const formatDate = (dateStr: string) => {
  return dayjs.utc(dateStr).local().format('YYYY-MM-DD HH:mm:ss')
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
