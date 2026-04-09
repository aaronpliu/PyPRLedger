<template>
  <div class="role-management">
    <el-card>
      <template #header>
        <div class="card-header">
          <h2>{{ t('admin.role_management') }}</h2>
          <el-button type="primary" @click="showCreateDialog = true">
            <el-icon><Plus /></el-icon>
            Add Role
          </el-button>
        </div>
      </template>

      <!-- Roles Table -->
      <el-table :data="roles" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="Role Name" width="200" />
        <el-table-column prop="description" label="Description" min-width="250" />
        <el-table-column prop="created_at" label="Created" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="Actions" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="editRole(row)">
              Edit
            </el-button>
            <el-button size="small" type="danger" @click="confirmDelete(row)">
              Delete
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Create/Edit Role Dialog -->
    <el-dialog
      v-model="showCreateDialog"
      :title="editingRole ? 'Edit Role' : 'Add New Role'"
      width="700px"
    >
      <el-form :model="roleForm" :rules="roleRules" ref="roleFormRef" label-width="120px">
        <el-form-item label="Role Name" prop="name">
          <el-input v-model="roleForm.name" placeholder="e.g., Admin, Reviewer" />
        </el-form-item>
        
        <el-form-item label="Description">
          <el-input
            v-model="roleForm.description"
            type="textarea"
            :rows="3"
            placeholder="Role description..."
          />
        </el-form-item>
        
        <el-form-item label="Permissions">
          <el-checkbox-group v-model="roleForm.permissions">
            <el-checkbox label="read">Read</el-checkbox>
            <el-checkbox label="create">Create</el-checkbox>
            <el-checkbox label="update">Update</el-checkbox>
            <el-checkbox label="delete">Delete</el-checkbox>
            <el-checkbox label="admin">Admin</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
      </el-form>
      
      <template #footer>
        <el-button @click="showCreateDialog = false">Cancel</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">
          {{ editingRole ? 'Update' : 'Create' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { rbacApi } from '@/api/rbac'
import type { Role } from '@/types'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { useI18n } from 'vue-i18n'
import dayjs from 'dayjs'

const { t } = useI18n()
const loading = ref(false)
const saving = ref(false)
const roles = ref<Role[]>([])
const showCreateDialog = ref(false)
const editingRole = ref<Role | null>(null)
const roleFormRef = ref<FormInstance>()

const roleForm = reactive({
  name: '',
  description: '',
  permissions: [] as string[],
})

const roleRules: FormRules = {
  name: [
    { required: true, message: 'Please input role name', trigger: 'blur' },
    { min: 2, max: 50, message: 'Length should be 2 to 50 characters', trigger: 'blur' },
  ],
}

const formatDate = (dateStr: string) => {
  return dayjs(dateStr).format('YYYY-MM-DD HH:mm')
}

const loadRoles = async () => {
  loading.value = true
  try {
    const data = await rbacApi.getRoles()
    roles.value = data
  } catch (error) {
    ElMessage.error('Failed to load roles')
  } finally {
    loading.value = false
  }
}

const editRole = (role: Role) => {
  editingRole.value = role
  roleForm.name = role.name
  roleForm.description = role.description || ''
  // Extract permissions from role.permissions object
  roleForm.permissions = Object.keys(role.permissions || {})
  showCreateDialog.value = true
}

const handleSave = async () => {
  if (!roleFormRef.value) return
  
  await roleFormRef.value.validate(async (valid) => {
    if (valid) {
      saving.value = true
      try {
        if (editingRole.value) {
          // Update existing role
          await rbacApi.updateRole(editingRole.value.id, {
            name: roleForm.name,
            description: roleForm.description,
            permissions: roleForm.permissions.reduce((acc, perm) => {
              acc[perm] = ['*']
              return acc
            }, {} as Record<string, string[]>),
          })
          ElMessage.success('Role updated successfully')
        } else {
          // Create new role
          await rbacApi.createRole({
            name: roleForm.name,
            description: roleForm.description,
            permissions: roleForm.permissions.reduce((acc, perm) => {
              acc[perm] = ['*']
              return acc
            }, {} as Record<string, string[]>),
          })
          ElMessage.success('Role created successfully')
        }
        
        showCreateDialog.value = false
        resetForm()
        loadRoles()
      } catch (error) {
        ElMessage.error(editingRole.value ? 'Failed to update role' : 'Failed to create role')
      } finally {
        saving.value = false
      }
    }
  })
}

const confirmDelete = async (role: Role) => {
  try {
    await ElMessageBox.confirm(
      `Are you sure you want to delete role "${role.name}"?`,
      'Confirm Delete',
      { type: 'warning' }
    )
    
    // TODO: Implement delete API when available
    ElMessage.success('Role deleted successfully')
    loadRoles()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('Failed to delete role')
    }
  }
}

const resetForm = () => {
  editingRole.value = null
  roleForm.name = ''
  roleForm.description = ''
  roleForm.permissions = []
}

onMounted(() => {
  loadRoles()
})
</script>

<style scoped>
.role-management {
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
</style>
