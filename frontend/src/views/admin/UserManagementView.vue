<template>
  <div class="user-management">
    <el-card>
      <template #header>
        <div class="card-header">
          <h2>{{ t('admin.user_management') }}</h2>
          <el-button type="primary" @click="showCreateDialog = true">
            <el-icon><Plus /></el-icon>
            Add User
          </el-button>
        </div>
      </template>

      <!-- Search and Filters -->
      <el-form :inline="true" class="filter-form">
        <el-form-item label="Search">
          <el-input
            v-model="searchQuery"
            placeholder="Search by username or email"
            clearable
            style="width: 300px"
            @clear="handleSearchClear"
            @keyup.enter="loadUsers"
          >
            <template #append>
              <el-button @click="loadUsers">
                <el-icon><Search /></el-icon>
              </el-button>
            </template>
          </el-input>
        </el-form-item>
        
        <el-form-item label="Status">
          <el-select v-model="statusFilter" placeholder="All Status" clearable style="width: 150px" @change="loadUsers">
            <el-option label="Active" :value="true" />
            <el-option label="Inactive" :value="false" />
          </el-select>
        </el-form-item>
      </el-form>

      <!-- Users Table -->
      <el-table :data="users" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="username" label="Username" width="150" />
        <el-table-column prop="email" label="Email" min-width="200" />
        <el-table-column label="Roles" min-width="180">
          <template #default="{ row }">
            <div style="display: flex; align-items: center; gap: 4px; flex-wrap: wrap;">
              <el-tag 
                v-if="row.roles && row.roles.length > 0"
                v-for="role in row.roles.slice(0, 2)" 
                :key="role"
                size="small"
              >
                {{ role }}
              </el-tag>
              <span v-else class="text-muted">No Role</span>
              <el-tag 
                v-if="row.roles && row.roles.length > 2"
                size="small"
                type="info"
              >
                +{{ row.roles.length - 2 }}
              </el-tag>
              
              <!-- Delegated Role Badge -->
              <el-tooltip 
                v-if="hasDelegatedRole(row.id)"
                content="Has delegated role(s)"
                placement="top"
              >
                <el-tag size="small" type="warning" effect="plain">
                  <el-icon><Share /></el-icon>
                  Delegated
                </el-tag>
              </el-tooltip>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="is_active" label="Status" width="120">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'">
              {{ row.is_active ? 'Active' : 'Inactive' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="last_login_at" label="Last Login" width="180">
          <template #default="{ row }">
            {{ row.last_login_at ? formatDate(row.last_login_at) : 'Never' }}
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="Created" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="Actions" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="viewRoles(row)">
              Roles
            </el-button>
            <el-button
              size="small"
              :type="row.is_active ? 'warning' : 'success'"
              @click="toggleUserStatus(row)"
            >
              {{ row.is_active ? 'Deactivate' : 'Activate' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- Pagination -->
      <div class="pagination-container">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="loadUsers"
          @current-change="loadUsers"
        />
      </div>
    </el-card>

    <!-- Create User Dialog -->
    <el-dialog v-model="showCreateDialog" title="Add New User" width="600px">
      <el-form :model="createForm" :rules="createRules" ref="createFormRef" label-width="140px" class="user-form">
        <el-form-item label="Username" prop="username">
          <el-input v-model="createForm.username" placeholder="Enter username" />
        </el-form-item>
        
        <el-form-item label="Email" prop="email">
          <el-input v-model="createForm.email" placeholder="Enter email" />
        </el-form-item>
        
        <el-form-item label="Password" prop="password">
          <el-input v-model="createForm.password" type="password" placeholder="Enter password" show-password />
        </el-form-item>
        
        <el-form-item label="Confirm Password" prop="confirmPassword">
          <el-input v-model="createForm.confirmPassword" type="password" placeholder="Confirm password" show-password />
        </el-form-item>
      </el-form>
      
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showCreateDialog = false">Cancel</el-button>
          <el-button type="primary" :loading="creating" @click="handleCreate">
            Create User
          </el-button>
        </span>
      </template>
    </el-dialog>

    <!-- Role Management Dialog -->
    <el-dialog v-model="showRoleDialog" title="Manage User Roles" width="700px">
      <div v-if="selectedUser">
        <h4>User: {{ selectedUser.username }}</h4>
        
        <!-- Current Roles -->
        <h5 style="margin-top: 16px;">Current Roles:</h5>
        <el-table :data="currentRoles" size="small" border>
          <el-table-column prop="role_name" label="Role" width="150" />
          <el-table-column prop="resource_type" label="Scope" width="120" />
          <el-table-column prop="resource_id" label="Resource" min-width="150">
            <template #default="{ row }">
              {{ row.resource_id || '-' }}
            </template>
          </el-table-column>
          <el-table-column label="Actions" width="100">
            <template #default="{ row }">
              <el-button 
                size="small" 
                type="danger" 
                @click="revokeRole(row)"
              >
                Revoke
              </el-button>
            </template>
          </el-table-column>
        </el-table>
        
        <!-- Assign New Role -->
        <h5 style="margin-top: 24px;">Assign New Role:</h5>
        <el-form :model="roleForm" label-width="120px">
          <el-form-item label="Role">
            <el-select v-model="roleForm.role_id" placeholder="Select role" style="width: 100%">
              <el-option 
                v-for="role in availableRoles" 
                :key="role.id"
                :label="`${role.name} - ${role.description}`"
                :value="role.id"
              />
            </el-select>
          </el-form-item>
          
          <el-form-item label="Scope">
            <el-radio-group v-model="roleForm.resource_type">
              <el-radio value="global">Global</el-radio>
              <el-radio value="project">Project</el-radio>
              <el-radio value="repository">Repository</el-radio>
            </el-radio-group>
          </el-form-item>
          
          <el-form-item 
            v-if="roleForm.resource_type !== 'global'" 
            label="Resource ID"
          >
            <el-input 
              v-model="roleForm.resource_id" 
              :placeholder="roleForm.resource_type === 'project' ? 'Project Key (e.g., PROJ)' : 'Repository Slug (e.g., my-repo)'"
            />
          </el-form-item>
          
          <el-form-item>
            <el-button type="primary" @click="assignRole">
              Assign Role
            </el-button>
          </el-form-item>
        </el-form>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, watch } from 'vue'
import { Plus, Search, Share } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { useI18n } from 'vue-i18n'
import dayjs from 'dayjs'
import { rbacApi } from '@/api/rbac'
import { usersApi } from '@/api/users'
import type { ResourceType, Role, RoleAssignment } from '@/types'

const { t } = useI18n()
const loading = ref(false)
const creating = ref(false)
const users = ref<any[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const searchQuery = ref('')
const statusFilter = ref<boolean | null>(null)
const showCreateDialog = ref(false)
const createFormRef = ref<FormInstance>()

// Delegation tracking
const usersWithDelegations = ref<Set<number>>(new Set())

// Role management state
const showRoleDialog = ref(false)
const selectedUser = ref<any>(null)
const currentRoles = ref<RoleAssignment[]>([])
const availableRoles = ref<Role[]>([])
const roleForm = reactive({
  role_id: null as number | null,
  resource_type: 'global',
  resource_id: '',
})

const createForm = reactive({
  username: '',
  email: '',
  password: '',
  confirmPassword: '',
})

const validatePass = (rule: any, value: string, callback: any) => {
  if (value === '') {
    callback(new Error('Please input password'))
  } else {
    if (createForm.confirmPassword !== '') {
      createFormRef.value?.validateField('confirmPassword')
    }
    callback()
  }
}

const validatePass2 = (rule: any, value: string, callback: any) => {
  if (value === '') {
    callback(new Error('Please input password again'))
  } else if (value !== createForm.password) {
    callback(new Error("Two inputs don't match!"))
  } else {
    callback()
  }
}

const createRules: FormRules = {
  username: [
    { required: true, message: 'Please input username', trigger: 'blur' },
    { min: 3, max: 20, message: 'Length should be 3 to 20 characters', trigger: 'blur' },
  ],
  email: [
    { required: true, message: 'Please input email', trigger: 'blur' },
    { type: 'email', message: 'Please input correct email address', trigger: 'blur' },
  ],
  password: [
    { validator: validatePass, trigger: 'blur' },
    { min: 6, message: 'Password must be at least 6 characters', trigger: 'blur' },
  ],
  confirmPassword: [
    { validator: validatePass2, trigger: 'blur' },
  ],
}

const formatDate = (dateStr: string) => {
  return dayjs(dateStr).format('YYYY-MM-DD HH:mm')
}

// Check if user has delegated roles
const hasDelegatedRole = (userId: number): boolean => {
  return usersWithDelegations.value.has(userId)
}

// Load delegation information for a user
const loadUserDelegations = async (userId: number) => {
  try {
    const delegations = await rbacApi.getUserDelegations(userId, 'received', false)
    // Filter only active delegations (not expired and not revoked)
    const activeDelegations = delegations.filter(d => 
      d.is_delegated && 
      (!d.expires_at || new Date(d.expires_at) > new Date()) &&
      !d.revoked_at
    )
    
    if (activeDelegations.length > 0) {
      usersWithDelegations.value.add(userId)
    } else {
      usersWithDelegations.value.delete(userId)
    }
  } catch (error) {
    console.error(`Failed to load delegations for user ${userId}:`, error)
  }
}

const handleSearchClear = () => {
  searchQuery.value = ''
  loadUsers()
}

const loadUsers = async () => {
  loading.value = true
  try {
    // Build filter parameters for server-side filtering
    const activeFilter = statusFilter.value === null ? undefined : statusFilter.value
    const usernameFilter = searchQuery.value || undefined
    
    // Fetch auth users from backend API with filters
    const fetchedUsers = await usersApi.getAllUsers(500, activeFilter, usernameFilter)
    
    // Apply pagination on the filtered results
    total.value = fetchedUsers.length
    const start = (currentPage.value - 1) * pageSize.value
    const end = start + pageSize.value
    users.value = fetchedUsers.slice(start, end)
    
    // Load delegation information for displayed users
    await Promise.all(
      users.value.map(user => loadUserDelegations(user.id))
    )
  } catch (error) {
    console.error('Failed to load users:', error)
    ElMessage.error('Failed to load users')
  } finally {
    loading.value = false
  }
}

const handleCreate = async () => {
  if (!createFormRef.value) return
  
  await createFormRef.value.validate(async (valid) => {
    if (valid) {
      creating.value = true
      try {
        // TODO: Implement actual API call
        ElMessage.success('User created successfully')
        showCreateDialog.value = false
        // Reset form
        createForm.username = ''
        createForm.email = ''
        createForm.password = ''
        createForm.confirmPassword = ''
        loadUsers()
      } catch (error) {
        ElMessage.error('Failed to create user')
      } finally {
        creating.value = false
      }
    }
  })
}

const toggleUserStatus = async (user: any) => {
  try {
    const action = user.is_active ? 'deactivate' : 'activate'
    await ElMessageBox.confirm(
      `Are you sure you want to ${action} this user?`,
      'Confirm',
      { type: 'warning' }
    )
    
    // TODO: Implement actual API call
    ElMessage.success(`User ${action}d successfully`)
    loadUsers()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('Operation failed')
    }
  }
}

const viewRoles = async (user: any) => {
  selectedUser.value = user
  showRoleDialog.value = true
  
  try {
    // Load current roles
    currentRoles.value = await rbacApi.getUserRoles(user.id)
    
    // Load available roles
    availableRoles.value = await rbacApi.getRoles()
  } catch (error) {
    ElMessage.error('Failed to load role information')
  }
}

const assignRole = async () => {
  if (!selectedUser.value || !roleForm.role_id) {
    ElMessage.warning('Please select a role')
    return
  }
  
  try {
    await rbacApi.assignRole(selectedUser.value.id, {
      role_id: roleForm.role_id,
      resource_type: roleForm.resource_type as ResourceType,
      resource_id: roleForm.resource_id || null,
    })
    
    ElMessage.success('Role assigned successfully')
    
    // Close the dialog
    showRoleDialog.value = false
    
    // Reload current roles (in case dialog is reopened)
    currentRoles.value = await rbacApi.getUserRoles(selectedUser.value.id)
    
    // Reload the main user list to reflect changes
    await loadUsers()
    
    // Reset form
    roleForm.role_id = null
    roleForm.resource_type = 'global'
    roleForm.resource_id = ''
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || 'Failed to assign role')
  }
}

const revokeRole = async (assignment: RoleAssignment) => {
  if (!selectedUser.value) return
  
  try {
    await ElMessageBox.confirm(
      `Are you sure you want to revoke the "${assignment.role_name}" role?`,
      'Confirm Revocation',
      { 
        type: 'warning',
        confirmButtonText: 'Revoke',
        cancelButtonText: 'Cancel',
      }
    )
    
    await rbacApi.revokeRole(
      selectedUser.value.id,
      assignment.role_id,
      assignment.resource_type,
      assignment.resource_id
    )
    
    ElMessage.success('Role revoked successfully')
    
    // Reload current roles
    currentRoles.value = await rbacApi.getUserRoles(selectedUser.value.id)
    
    // Reload the main user list to reflect changes
    await loadUsers()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || 'Failed to revoke role')
    }
  }
}

// Reset form when dialog closes
watch(showRoleDialog, (visible) => {
  if (!visible) {
    selectedUser.value = null
    currentRoles.value = []
    availableRoles.value = []
    roleForm.role_id = null
    roleForm.resource_type = 'global'
    roleForm.resource_id = ''
  }
})

onMounted(() => {
  loadUsers()
})
</script>

<style scoped>
.user-management {
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
}

.filter-form {
  margin-bottom: 20px;
}

.pagination-container {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

.text-muted {
  color: #909399;
  font-size: 13px;
}

.user-form {
  padding-right: 20px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
