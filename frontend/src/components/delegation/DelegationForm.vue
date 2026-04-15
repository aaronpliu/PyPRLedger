<template>
  <el-form :model="form" :rules="rules" ref="formRef" label-width="140px">
    <!-- Delegator Info -->
    <el-form-item label="Delegator (You)">
      <el-input :value="`${currentUsername} (User #${currentUserId})`" disabled />
    </el-form-item>
    
    <!-- Delegatee Search -->
    <el-form-item label="Delegatee" prop="delegatee_id">
      <el-autocomplete
        v-model="delegateeSearch"
        :fetch-suggestions="filterUsers"
        placeholder="Search by username..."
        style="width: 100%"
        @select="handleSelectUser"
        clearable
      >
        <template #default="{ item }">
          <div class="user-option">
            <span class="username">{{ item.username }}</span>
            <span class="user-info">
              <el-tag 
                v-if="item.git_user_id" 
                size="small" 
                type="success"
              >
                ✓ Bitbucket
              </el-tag>
              <el-tag 
                v-else 
                size="small" 
                type="warning"
              >
                ⚠ No Bitbucket
              </el-tag>
            </span>
          </div>
        </template>
      </el-autocomplete>
      <div v-if="selectedUser" style="margin-top: 8px;">
        <el-alert
          :title="`Selected: ${selectedUser.username}`"
          type="success"
          :closable="false"
          show-icon
        >
          <template #default>
            <div style="font-size: 12px; margin-top: 4px;">
              <div style="margin-bottom: 4px;">
                Bitbucket Status: 
                <el-tag v-if="selectedUser.git_user_id" size="small" type="success">
                  ✓ Linked (ID: {{ selectedUser.git_user_id }})
                </el-tag>
                <el-tag v-else size="small" type="warning">
                  ⚠ Not linked to Bitbucket
                </el-tag>
              </div>
              <div>
                Current Roles: 
                <el-tag v-for="role in selectedUser.roles" :key="role" size="small" style="margin: 2px;">
                  {{ role }}
                </el-tag>
                <span v-if="!selectedUser.roles || selectedUser.roles.length === 0" style="color: var(--el-color-warning);">
                  No roles assigned
                </span>
              </div>
            </div>
          </template>
        </el-alert>
      </div>
      <div style="margin-top: 4px; color: var(--el-text-color-secondary); font-size: 12px;">
        💡 Showing all active users. Users with Bitbucket linkage are recommended.
      </div>
    </el-form-item>
    
    <!-- Role Selection -->
    <el-form-item label="Role to Delegate" prop="role_id">
      <el-select v-model="form.role_id" placeholder="Select role" style="width: 100%">
        <el-option
          v-for="role in availableRoles"
          :key="role.id"
          :label="role.name"
          :value="role.id"
        >
          <span>{{ role.name }}</span>
          <span style="float: right; color: var(--el-text-color-secondary); font-size: 13px;">
            {{ role.description }}
          </span>
        </el-option>
      </el-select>
    </el-form-item>
    
    <!-- Resource Type -->
    <el-form-item label="Resource Type" prop="resource_type">
      <el-select v-model="form.resource_type" style="width: 100%">
        <el-option label="Global (All Resources)" value="global" />
        <el-option label="Project Specific" value="project" />
        <el-option label="Repository Specific" value="repository" />
      </el-select>
    </el-form-item>
    
    <!-- Resource ID (conditional) -->
    <el-form-item 
      v-if="form.resource_type !== 'global'" 
      label="Resource ID" 
      prop="resource_id"
    >
      <el-input v-model="form.resource_id" placeholder="Enter project or repository ID" />
    </el-form-item>
    
    <!-- Time Range -->
    <el-form-item label="Valid Period" required>
      <el-row :gutter="10">
        <el-col :span="12">
          <el-form-item prop="starts_at" style="margin-bottom: 0;">
            <el-date-picker
              v-model="form.starts_at"
              type="datetime"
              placeholder="Start time"
              style="width: 100%"
            />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item prop="expires_at" style="margin-bottom: 0;">
            <el-date-picker
              v-model="form.expires_at"
              type="datetime"
              placeholder="Expiry time"
              style="width: 100%"
            />
          </el-form-item>
        </el-col>
      </el-row>
    </el-form-item>
    
    <!-- Permission Matrix -->
    <el-form-item label="Permissions" prop="permissions">
      <div class="permission-matrix">
        <el-alert
          v-if="!form.role_id"
          title="Please select a role first to see available permissions"
          type="info"
          :closable="false"
          show-icon
          style="margin-bottom: 12px;"
        />
        
        <el-table v-else-if="permissionRows.length > 0" :data="permissionRows" border size="small">
          <el-table-column prop="resource" label="Resource" width="150" fixed />
          <el-table-column label="Read" width="80" align="center">
            <template #default="{ row }">
              <el-checkbox 
                v-model="row.read" 
                :disabled="!hasActionForResource(row.resource, 'read')"
                @change="updatePermissions" 
              />
            </template>
          </el-table-column>
          <el-table-column label="Create" width="80" align="center">
            <template #default="{ row }">
              <el-checkbox 
                v-model="row.create" 
                :disabled="!hasActionForResource(row.resource, 'create')"
                @change="updatePermissions" 
              />
            </template>
          </el-table-column>
          <el-table-column label="Update" width="80" align="center">
            <template #default="{ row }">
              <el-checkbox 
                v-model="row.update" 
                :disabled="!hasActionForResource(row.resource, 'update')"
                @change="updatePermissions" 
              />
            </template>
          </el-table-column>
          <el-table-column label="Delete" width="80" align="center">
            <template #default="{ row }">
              <el-checkbox 
                v-model="row.delete" 
                :disabled="!hasActionForResource(row.resource, 'delete')"
                @change="updatePermissions" 
              />
            </template>
          </el-table-column>
          <el-table-column label="Manage" width="80" align="center">
            <template #default="{ row }">
              <el-checkbox 
                v-model="row.manage" 
                :disabled="!hasActionForResource(row.resource, 'manage')"
                @change="updatePermissions" 
              />
            </template>
          </el-table-column>
        </el-table>
        
        <el-empty v-else description="No permissions available for this role" />
        
        <div style="margin-top: 8px; color: var(--el-text-color-secondary); font-size: 12px;">
          💡 Select the permissions you want to delegate. Only permissions from your role can be delegated.
        </div>
        
        <!-- Preview JSON -->
        <el-collapse v-if="permissionRows.length > 0" style="margin-top: 12px;">
          <el-collapse-item title="View JSON Format" name="json">
            <pre style="background: var(--el-fill-color-light); padding: 12px; border-radius: 4px; font-size: 12px; overflow-x: auto;">{{ permissionJson }}</pre>
          </el-collapse-item>
        </el-collapse>
      </div>
    </el-form-item>
    
    <!-- Reason -->
    <el-form-item label="Reason">
      <el-input
        v-model="form.reason"
        type="textarea"
        :rows="2"
        placeholder="Optional: Explain why you're delegating this role..."
      />
    </el-form-item>
  </el-form>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { usersApi } from '@/api/users'
import { rbacApi } from '@/api/rbac'
import type { FormInstance, FormRules } from 'element-plus'
import type { User } from '@/types'
import dayjs from 'dayjs'

interface Props {
  currentUserId: number
  currentUsername: string
  initialData?: any
}

const props = defineProps<Props>()

const emit = defineEmits<{
  submit: [data: any]
}>()

const formRef = ref<FormInstance>()
const delegateeSearch = ref('')
const selectedUser = ref<User | null>(null)
const availableRoles = ref<any[]>([])
const allUsers = ref<User[]>([])  // Preloaded users
const filteredUsers = ref<User[]>([])  // Filtered for display

// Permission matrix data - will be populated dynamically based on selected role
const permissionRows = ref<any[]>([])
const availablePermissions = ref<Record<string, string[]>>({})  // Available permissions from role

const form = reactive({
  delegatee_id: 0,
  role_id: undefined as number | undefined,
  resource_type: 'global',
  resource_id: '',
  starts_at: new Date(),
  expires_at: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000),
  reason: '',
})

const rules: FormRules = {
  delegatee_id: [{ required: true, message: 'Please select a delegatee', trigger: 'change' }],
  role_id: [{ required: true, message: 'Please select a role', trigger: 'change' }],
  resource_type: [{ required: true, message: 'Please select resource type', trigger: 'change' }],
  starts_at: [{ required: true, message: 'Please select start time', trigger: 'change' }],
  expires_at: [{ required: true, message: 'Please select expiry time', trigger: 'change' }],
}

// Computed delegation scope JSON
const permissionJson = computed(() => {
  const scope: Record<string, string[]> = {}
  permissionRows.value.forEach(row => {
    const perms: string[] = []
    if (row.read) perms.push('read')
    if (row.create) perms.push('create')
    if (row.update) perms.push('update')
    if (row.delete) perms.push('delete')
    if (row.manage) perms.push('manage')
    if (perms.length > 0) {
      scope[row.resource] = perms
    }
  })
  return JSON.stringify(scope, null, 2)
})

// Filter users based on search query (frontend filtering)
const filterUsers = (queryString: string, cb: any) => {
  let users = allUsers.value
  
  // Filter by username if query provided
  if (queryString && queryString.length > 0) {
    const query = queryString.toLowerCase()
    users = users.filter(user => 
      user.username.toLowerCase().includes(query)
    )
  }
  
  // Sort: Bitbucket-linked users first, then by username
  const sorted = [...users].sort((a, b) => {
    // Prioritize users with Bitbucket linkage
    if (a.git_user_id && !b.git_user_id) return -1
    if (!a.git_user_id && b.git_user_id) return 1
    // Then sort by username
    return a.username.localeCompare(b.username)
  })
  
  // Format for autocomplete
  const results = sorted.map(user => ({
    ...user,
    value: user.username,
  }))
  
  cb(results)
}

// Load all users on component mount
const loadUsers = async () => {
  try {
    console.log('Loading users for delegation...')
    const users = await usersApi.getAllUsers(500)
    allUsers.value = Array.isArray(users) ? users : []
    console.log(`✓ Loaded ${allUsers.value.length} users for delegation`)
    if (allUsers.value.length > 0) {
      console.log('Sample user:', allUsers.value[0])
    }
  } catch (error) {
    console.error('✗ Failed to load users:', error)
    ElMessage.warning('Failed to load user list. Search will be limited.')
  }
}

// Handle user selection
const handleSelectUser = (user: User & { value: string }) => {
  selectedUser.value = user
  form.delegatee_id = user.id
  delegateeSearch.value = user.username
}

// Update permissions from checkbox matrix
const updatePermissions = () => {
  // Permissions are automatically updated via computed property
}

// Load role permissions and build permission matrix dynamically
const loadRolePermissions = async (roleId: number) => {
  try {
    const role = await rbacApi.getRoleById(roleId)
    
    if (!role || !role.permissions) {
      console.warn('No permissions found for role:', roleId)
      permissionRows.value = []
      availablePermissions.value = {}
      return
    }
    
    // Parse permissions (might be string or object)
    let perms: Record<string, string[]>
    if (typeof role.permissions === 'string') {
      perms = JSON.parse(role.permissions)
    } else {
      perms = role.permissions
    }
    
    availablePermissions.value = perms
    
    // Build permission rows dynamically based on available permissions
    const allActions = ['read', 'create', 'update', 'delete', 'manage']
    permissionRows.value = Object.keys(perms).map(resource => {
      const row: any = { resource }
      allActions.forEach(action => {
        row[action] = false  // Default unchecked
      })
      return row
    })
    
    console.log(`Loaded permissions for role '${role.name}':`, perms)
  } catch (error) {
    console.error('Failed to load role permissions:', error)
    permissionRows.value = []
    availablePermissions.value = {}
  }
}

// Check if any resource has the specified action
const hasPermission = (action: string): boolean => {
  // Check if any resource in availablePermissions has this action
  return Object.values(availablePermissions.value).some(actions => 
    actions.includes(action)
  )
}

// Check if a specific resource has the specified action
const hasActionForResource = (resource: string, action: string): boolean => {
  const actions = availablePermissions.value[resource]
  return actions ? actions.includes(action) : false
}

// Load available roles (only roles that current user has)
const loadRoles = async () => {
  try {
    const allRoles = await rbacApi.getRoles()
    
    // Get current user's role assignments to filter available roles
    const userAssignments = await rbacApi.getUserRoles(props.currentUserId)
    
    // Extract role IDs that current user has
    const currentUserRoleIds = new Set(userAssignments.map((assignment: any) => assignment.role_id))
    
    // Filter roles to only show those the current user has
    availableRoles.value = allRoles.filter((role: any) => currentUserRoleIds.has(role.id))
    
    console.log('Available roles for delegation:', availableRoles.value.map((r: any) => r.name))
  } catch (error) {
    console.error('Failed to load roles:', error)
    // Fallback: show all roles if we can't get user assignments
    try {
      availableRoles.value = await rbacApi.getRoles()
    } catch (e) {
      console.error('Fallback also failed:', e)
    }
  }
}

// Validate and submit
const validate = async (): Promise<boolean> => {
  if (!formRef.value) return false
  
  const valid = await new Promise<boolean>((resolve) => {
    formRef.value!.validate((valid: boolean) => {
      resolve(valid)
    })
  })
  
  if (!valid) return false
  
  // Check if delegatee is selected
  if (!form.delegatee_id) {
    return false
  }
  
  // Build delegation scope from matrix
  const delegationScope: Record<string, string[]> = {}
  permissionRows.value.forEach(row => {
    const perms: string[] = []
    if (row.read) perms.push('read')
    if (row.create) perms.push('create')
    if (row.update) perms.push('update')
    if (row.delete) perms.push('delete')
    if (row.manage) perms.push('manage')
    if (perms.length > 0) {
      delegationScope[row.resource] = perms
    }
  })
  
  // Check if at least one permission is selected
  if (Object.keys(delegationScope).length === 0) {
    return false
  }
  
  emit('submit', {
    ...form,
    delegation_scope: delegationScope,
  })
  
  return true
}

// Reset form
const reset = () => {
  if (formRef.value) {
    formRef.value.resetFields()
  }
  form.delegatee_id = 0
  form.role_id = undefined
  form.resource_type = 'global'
  form.resource_id = ''
  form.starts_at = new Date()
  form.expires_at = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000)
  form.reason = ''
  delegateeSearch.value = ''
  selectedUser.value = null
  
  // Reset permission matrix
  permissionRows.value.forEach(row => {
    row.read = false
    row.create = false
    row.update = false
    row.delete = false
    row.manage = false
  })
}

// Watch for role changes to load permissions
watch(() => form.role_id, (newRoleId) => {
  if (newRoleId) {
    loadRolePermissions(newRoleId)
  } else {
    permissionRows.value = []
    availablePermissions.value = {}
  }
})

// Initialize
onMounted(() => {
  loadUsers()
  loadRoles()
})

// Expose methods
defineExpose({
  validate,
  reset,
})
</script>

<style scoped>
.user-option {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.username {
  font-weight: 500;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.permission-matrix {
  width: 100%;
}

:deep(.el-table) {
  --el-table-border-color: var(--el-border-color-lighter);
}

:deep(.el-table th) {
  background-color: var(--el-fill-color-light);
  font-weight: 600;
}
</style>
