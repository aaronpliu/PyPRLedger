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
            @clear="loadUsers"
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
      <el-form :model="createForm" :rules="createRules" ref="createFormRef" label-width="120px">
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
        <el-button @click="showCreateDialog = false">Cancel</el-button>
        <el-button type="primary" :loading="creating" @click="handleCreate">
          Create User
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { Plus, Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { useI18n } from 'vue-i18n'
import dayjs from 'dayjs'

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

const loadUsers = async () => {
  loading.value = true
  try {
    // TODO: Implement actual API call
    // For now, using mock data
    users.value = []
    total.value = 0
  } catch (error) {
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

const viewRoles = (user: any) => {
  // TODO: Navigate to user roles page or open dialog
  ElMessage.info(`Viewing roles for user: ${user.username}`)
}

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
</style>
