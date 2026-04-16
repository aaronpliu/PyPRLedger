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
          <el-autocomplete
            v-model="filters.delegator_username"
            :fetch-suggestions="filterDelegators"
            placeholder="Search by username or name..."
            clearable
            style="width: 200px"
            @select="handleSelectDelegator"
          >
            <template #default="{ item }">
              <div class="user-option">
                <span class="username">{{ item.value }}</span>
                <span v-if="item.display_name" class="display-name">{{ item.display_name }}</span>
              </div>
            </template>
          </el-autocomplete>
        </el-form-item>
        
        <el-form-item label="Delegatee">
          <el-autocomplete
            v-model="filters.delegatee_username"
            :fetch-suggestions="filterDelegatees"
            placeholder="Search by username or name..."
            clearable
            style="width: 200px"
            @select="handleSelectDelegatee"
          >
            <template #default="{ item }">
              <div class="user-option">
                <span class="username">{{ item.value }}</span>
                <span v-if="item.display_name" class="display-name">{{ item.display_name }}</span>
              </div>
            </template>
          </el-autocomplete>
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
        <el-table-column label="Delegator" width="180">
          <template #default="{ row }">
            <div class="user-info-cell">
              <div v-if="row.delegator_display_name" class="display-name">{{ row.delegator_display_name }}</div>
              <div class="username">{{ row.delegator_username || `User ${row.delegator_id}` }}</div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="Delegatee" width="180">
          <template #default="{ row }">
            <div class="user-info-cell">
              <div v-if="row.delegatee_display_name" class="display-name">{{ row.delegatee_display_name }}</div>
              <div class="username">{{ row.delegatee_username || `User ${row.auth_user_id}` }}</div>
            </div>
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
    <el-dialog v-model="showCreateDialog" title="Create Role Delegation" width="800px">
      <DelegationForm
        ref="delegationFormRef"
        :current-user-id="authStore.user?.id || 0"
        :current-username="authStore.user?.username || ''"
        @submit="handleSubmitDelegation"
      />
      
      <template #footer>
        <el-button @click="showCreateDialog = false">Cancel</el-button>
        <el-button type="primary" :loading="creating" @click="handleConfirmCreate">
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
import dayjs from 'dayjs'
import DelegationForm from '@/components/delegation/DelegationForm.vue'

const authStore = useAuthStore()
const loading = ref(false)
const creating = ref(false)
const delegations = ref<DelegationResponse[]>([])
const showCreateDialog = ref(false)
const delegationFormRef = ref<InstanceType<typeof DelegationForm>>()
const pendingDelegationData = ref<any>(null)

const filters = reactive({
  delegator_id: undefined as number | undefined,
  delegator_username: undefined as string | undefined,
  delegatee_id: undefined as number | undefined,
  delegatee_username: undefined as string | undefined,
  status: undefined as string | undefined,
  include_expired: false,
})

// User search data
const allUsers = ref<any[]>([])
const filteredDelegators = ref<any[]>([])
const filteredDelegatees = ref<any[]>([])

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

// Load all users for autocomplete
const loadUsers = async () => {
  try {
    const response = await fetch('/api/v1/users')
    if (response.ok) {
      const data = await response.json()
      // Ensure allUsers is always an array
      allUsers.value = Array.isArray(data) ? data : []
    } else {
      console.error('Failed to fetch users:', response.status)
      allUsers.value = []
    }
  } catch (error) {
    console.error('Failed to load users:', error)
    allUsers.value = []
  }
}

// Filter users for delegator autocomplete
const filterDelegators = (queryString: string, cb: any) => {
  // Ensure allUsers.value is an array
  const users = Array.isArray(allUsers.value) ? allUsers.value : []
  
  const results = queryString
    ? users.filter(user => 
        user.username.toLowerCase().includes(queryString.toLowerCase()) ||
        (user.display_name && user.display_name.toLowerCase().includes(queryString.toLowerCase()))
      )
    : users
  
  cb(results.map(user => ({
    value: user.username,
    id: user.id,
    display_name: user.display_name,
    label: user.display_name ? `${user.display_name} (${user.username})` : user.username,
  })))
}

// Filter users for delegatee autocomplete
const filterDelegatees = (queryString: string, cb: any) => {
  // Ensure allUsers.value is an array
  const users = Array.isArray(allUsers.value) ? allUsers.value : []
  
  const results = queryString
    ? users.filter(user => 
        user.username.toLowerCase().includes(queryString.toLowerCase()) ||
        (user.display_name && user.display_name.toLowerCase().includes(queryString.toLowerCase()))
      )
    : users
  
  cb(results.map(user => ({
    value: user.username,
    id: user.id,
    display_name: user.display_name,
    label: user.display_name ? `${user.display_name} (${user.username})` : user.username,
  })))
}

// Handle delegator selection
const handleSelectDelegator = (item: any) => {
  filters.delegator_username = item.value
}

// Handle delegatee selection
const handleSelectDelegatee = (item: any) => {
  filters.delegatee_username = item.value
}

const loadDelegations = async () => {
  loading.value = true
  try {
    const params: DelegationListQuery = {
      delegator_id: filters.delegator_id,
      delegator_username: filters.delegator_username,
      delegatee_id: filters.delegatee_id,
      delegatee_username: filters.delegatee_username,
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
  filters.delegator_username = undefined
  filters.delegatee_id = undefined
  filters.delegatee_username = undefined
  filters.status = undefined
  filters.include_expired = false
  filteredDelegators.value = []
  filteredDelegatees.value = []
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

// Handle delegation form submit (called by child component)
const handleSubmitDelegation = (formData: any) => {
  pendingDelegationData.value = formData
}

// Confirm and create delegation
const handleConfirmCreate = async () => {
  if (!pendingDelegationData.value) return
  
  try {
    creating.value = true
    await rbacApi.createDelegation(pendingDelegationData.value)
    
    ElMessage.success('Delegation created successfully')
    showCreateDialog.value = false
    pendingDelegationData.value = null
    
    // Reset the form
    if (delegationFormRef.value) {
      delegationFormRef.value.reset()
    }
    
    loadDelegations()
  } catch (error: any) {
    // Don't show permission errors
    if (error?.response?.status !== 403) {
      ElMessage.error(error?.response?.data?.detail || 'Failed to create delegation')
    }
  } finally {
    creating.value = false
  }
}

onMounted(() => {
  loadDelegations()
  loadUsers()
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

.user-info-cell {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
}

.user-info-cell .display-name {
  font-weight: bold;
}

.user-info-cell .username {
  color: var(--el-text-color-secondary);
}

.user-option {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.user-option .username {
  font-weight: 500;
  color: var(--el-text-color-primary);
}

.user-option .display-name {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
</style>
