<template>
  <div class="delegation-management">
    <el-card>
      <template #header>
        <div class="card-header">
          <h2>Role Delegation Management</h2>
          <el-button type="primary" @click="showCreateDialog = true">
            <el-icon><Plus /></el-icon>
            Create Delegation
          </el-button>
        </div>
      </template>

      <!-- Filters -->
      <el-form :inline="true" class="filter-form">
        <el-form-item label="Delegator">
          <el-input v-model="filters.delegator_id" placeholder="User ID" clearable style="width: 150px" />
        </el-form-item>
        
        <el-form-item label="Delegatee">
          <el-input v-model="filters.delegatee_id" placeholder="User ID" clearable style="width: 150px" />
        </el-form-item>
        
        <el-form-item label="Status">
          <el-select v-model="filters.status" placeholder="All Status" clearable style="width: 150px">
            <el-option label="Active" value="active" />
            <el-option label="Pending" value="pending" />
            <el-option label="Expired" value="expired" />
            <el-option label="Revoked" value="revoked" />
          </el-select>
        </el-form-item>
        
        <el-form-item>
          <el-checkbox v-model="filters.include_expired">Include Expired</el-checkbox>
        </el-form-item>
        
        <el-form-item>
          <el-button type="primary" @click="loadDelegations">
            <el-icon><Search /></el-icon>
            Search
          </el-button>
          <el-button @click="resetFilters">Reset</el-button>
        </el-form-item>
      </el-form>

      <!-- Delegations Table -->
      <el-table :data="delegations" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column label="Role" width="150">
          <template #default="{ row }">
            <el-tag :type="getRoleTagType(row.role_name || '')" size="small">
              {{ row.role_name || `Role ${row.role_id}` }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="resource_type" label="Resource Type" width="120" />
        <el-table-column label="Delegator" width="120">
          <template #default="{ row }">
            User #{{ row.delegator_id }}
          </template>
        </el-table-column>
        <el-table-column label="Delegatee" width="120">
          <template #default="{ row }">
            User #{{ row.auth_user_id }}
          </template>
        </el-table-column>
        <el-table-column label="Status" width="120">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.delegation_status)">
              {{ formatStatus(row.delegation_status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="Valid Period" min-width="220">
          <template #default="{ row }">
            <div v-if="row.starts_at && row.expires_at">
              {{ formatDate(row.starts_at) }} → {{ formatDate(row.expires_at) }}
            </div>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="Reason" min-width="200">
          <template #default="{ row }">
            {{ row.delegation_reason || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="Actions" width="150" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.delegation_status === 'active' || row.delegation_status === 'pending'"
              size="small"
              type="danger"
              @click="handleRevoke(row)"
            >
              Revoke
            </el-button>
            <span v-else style="color: var(--el-text-color-secondary);">-</span>
          </template>
        </el-table-column>
      </el-table>

      <!-- Statistics -->
      <el-divider />
      <div class="statistics">
        <el-row :gutter="20">
          <el-col :span="6">
            <el-statistic title="Total Delegations" :value="delegations.length" />
          </el-col>
          <el-col :span="6">
            <el-statistic title="Active" :value="activeCount" />
          </el-col>
          <el-col :span="6">
            <el-statistic title="Pending" :value="pendingCount" />
          </el-col>
          <el-col :span="6">
            <el-statistic title="Expired/Revoked" :value="inactiveCount" />
          </el-col>
        </el-row>
      </div>
    </el-card>

    <!-- Create Delegation Dialog -->
    <el-dialog v-model="showCreateDialog" title="Create Role Delegation" width="700px">
      <el-form :model="createForm" :rules="createRules" ref="createFormRef" label-width="140px">
        <el-form-item label="Delegator (You)" prop="delegator">
          <el-input :value="`User #${authStore.user?.id} (${authStore.user?.username})`" disabled />
        </el-form-item>
        
        <el-form-item label="Delegatee User ID" prop="delegatee_id">
          <el-input-number v-model="createForm.delegatee_id" :min="1" style="width: 100%" />
        </el-form-item>
        
        <el-form-item label="Role" prop="role_id">
          <el-select v-model="createForm.role_id" placeholder="Select role" style="width: 100%">
            <el-option
              v-for="role in availableRoles"
              :key="role.id"
              :label="role.name"
              :value="role.id"
            />
          </el-select>
        </el-form-item>
        
        <el-form-item label="Resource Type" prop="resource_type">
          <el-select v-model="createForm.resource_type" style="width: 100%">
            <el-option label="Global" value="global" />
            <el-option label="Project" value="project" />
            <el-option label="Repository" value="repository" />
          </el-select>
        </el-form-item>
        
        <el-form-item label="Resource ID" prop="resource_id">
          <el-input v-model="createForm.resource_id" placeholder="Leave empty for global" />
        </el-form-item>
        
        <el-form-item label="Start Time" prop="starts_at">
          <el-date-picker
            v-model="createForm.starts_at"
            type="datetime"
            placeholder="Select start time"
            style="width: 100%"
          />
        </el-form-item>
        
        <el-form-item label="Expiry Time" prop="expires_at">
          <el-date-picker
            v-model="createForm.expires_at"
            type="datetime"
            placeholder="Select expiry time"
            style="width: 100%"
          />
        </el-form-item>
        
        <el-form-item label="Delegation Scope" prop="delegation_scope">
          <el-input
            v-model="scopeText"
            type="textarea"
            :rows="4"
            placeholder='{"reviews": ["read", "create"], "scores": ["read"]}'
          />
          <div style="margin-top: 8px; color: var(--el-text-color-secondary); font-size: 12px;">
            JSON format: specify which permissions to delegate (subset of your permissions)
          </div>
        </el-form-item>
        
        <el-form-item label="Reason">
          <el-input
            v-model="createForm.reason"
            type="textarea"
            :rows="2"
            placeholder="Reason for delegation..."
          />
        </el-form-item>
      </el-form>
      
      <template #footer>
        <el-button @click="showCreateDialog = false">Cancel</el-button>
        <el-button type="primary" :loading="creating" @click="handleCreate">
          Create Delegation
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { Plus, Search } from '@element-plus/icons-vue'
import { rbacApi, type DelegationResponse, type DelegationListQuery } from '@/api/rbac'
import { useAuthStore } from '@/stores/auth'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import dayjs from 'dayjs'

const authStore = useAuthStore()
const loading = ref(false)
const creating = ref(false)
const delegations = ref<DelegationResponse[]>([])
const showCreateDialog = ref(false)
const createFormRef = ref<FormInstance>()
const scopeText = ref('')
const availableRoles = ref<any[]>([])

const filters = reactive<DelegationListQuery>({
  delegator_id: undefined,
  delegatee_id: undefined,
  status: undefined,
  include_expired: false,
})

const createForm = reactive({
  delegatee_id: 1,
  role_id: undefined as number | undefined,
  resource_type: 'global',
  resource_id: '',
  delegation_scope: {} as Record<string, string[]>,
  starts_at: new Date(),
  expires_at: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000), // 30 days later
  reason: '',
})

const createRules: FormRules = {
  delegatee_id: [{ required: true, message: 'Please input delegatee user ID', trigger: 'blur' }],
  role_id: [{ required: true, message: 'Please select a role', trigger: 'change' }],
  resource_type: [{ required: true, message: 'Please select resource type', trigger: 'change' }],
  starts_at: [{ required: true, message: 'Please select start time', trigger: 'change' }],
  expires_at: [{ required: true, message: 'Please select expiry time', trigger: 'change' }],
}

// Statistics
const activeCount = computed(() => delegations.value.filter(d => d.delegation_status === 'active').length)
const pendingCount = computed(() => delegations.value.filter(d => d.delegation_status === 'pending').length)
const inactiveCount = computed(() => delegations.value.filter(d => 
  d.delegation_status === 'expired' || d.delegation_status === 'revoked'
).length)

const formatDate = (dateStr: string) => {
  return dayjs(dateStr).format('YYYY-MM-DD HH:mm')
}

const formatStatus = (status?: string | null): string => {
  if (!status) return 'Unknown'
  const statusMap: Record<string, string> = {
    active: 'Active',
    pending: 'Pending',
    expired: 'Expired',
    revoked: 'Revoked',
  }
  return statusMap[status] || status
}

const getStatusType = (status?: string | null): 'success' | 'warning' | 'info' | 'danger' => {
  if (!status) return 'info'
  const typeMap: Record<string, 'success' | 'warning' | 'info' | 'danger'> = {
    active: 'success',
    pending: 'warning',
    expired: 'info',
    revoked: 'danger',
  }
  return typeMap[status] || 'info'
}

const getRoleTagType = (roleName: string): 'success' | 'warning' | 'danger' | 'info' => {
  const roleTypes: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
    viewer: 'info',
    reviewer: 'success',
    review_admin: 'warning',
    system_admin: 'danger',
  }
  return roleTypes[roleName.toLowerCase()] || 'info'
}

const loadDelegations = async () => {
  loading.value = true
  try {
    const params: DelegationListQuery = {
      delegator_id: filters.delegator_id ? Number(filters.delegator_id) : undefined,
      delegatee_id: filters.delegatee_id ? Number(filters.delegatee_id) : undefined,
      status: filters.status || undefined,
      include_expired: filters.include_expired,
    }
    delegations.value = await rbacApi.listDelegations(params)
  } catch (error) {
    ElMessage.error('Failed to load delegations')
  } finally {
    loading.value = false
  }
}

const resetFilters = () => {
  filters.delegator_id = undefined
  filters.delegatee_id = undefined
  filters.status = undefined
  filters.include_expired = false
  loadDelegations()
}

const handleRevoke = async (row: DelegationResponse) => {
  try {
    await ElMessageBox.confirm(
      `Are you sure you want to revoke delegation #${row.id}?`,
      'Confirm Revoke',
      { type: 'warning' }
    )
    
    await rbacApi.revokeDelegation(row.id, { reason: 'Revoked by admin' })
    ElMessage.success('Delegation revoked successfully')
    loadDelegations()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('Failed to revoke delegation')
    }
  }
}

const handleCreate = async () => {
  if (!createFormRef.value) return
  
  await createFormRef.value.validate(async (valid) => {
    if (valid) {
      try {
        // Parse delegation scope from text
        let delegationScope
        try {
          delegationScope = scopeText.value ? JSON.parse(scopeText.value) : {}
        } catch (e) {
          ElMessage.error('Invalid JSON format for delegation scope')
          return
        }
        
        creating.value = true
        await rbacApi.createDelegation({
          delegatee_id: createForm.delegatee_id,
          role_id: createForm.role_id!,
          resource_type: createForm.resource_type,
          resource_id: createForm.resource_id || null,
          delegation_scope: delegationScope,
          starts_at: dayjs(createForm.starts_at).toISOString(),
          expires_at: dayjs(createForm.expires_at).toISOString(),
          reason: createForm.reason || null,
        })
        
        ElMessage.success('Delegation created successfully')
        showCreateDialog.value = false
        resetCreateForm()
        loadDelegations()
      } catch (error) {
        ElMessage.error('Failed to create delegation')
      } finally {
        creating.value = false
      }
    }
  })
}

const resetCreateForm = () => {
  createForm.delegatee_id = 1
  createForm.role_id = undefined
  createForm.resource_type = 'global'
  createForm.resource_id = ''
  createForm.delegation_scope = {}
  createForm.starts_at = new Date()
  createForm.expires_at = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000)
  createForm.reason = ''
  scopeText.value = ''
}

onMounted(() => {
  loadDelegations()
})
</script>

<style scoped>
.delegation-management {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header h2 {
  margin: 0;
  font-size: 20px;
  color: var(--el-text-color-primary);
}

.filter-form {
  margin-bottom: 20px;
}

.statistics {
  margin-top: 20px;
}

:deep(.el-statistic__head) {
  color: var(--el-text-color-secondary);
  font-size: 14px;
}

:deep(.el-statistic__content) {
  color: var(--el-text-color-primary);
  font-size: 24px;
  font-weight: bold;
}
</style>
