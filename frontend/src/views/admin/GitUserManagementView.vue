<template>
  <div class="git-user-management">
    <el-card>
      <template #header>
        <div class="card-header">
          <h2>{{ t('admin.git_user_management', 'Git User Management') }}</h2>
          <el-button type="primary" @click="showCreateDialog = true">
            <el-icon><Plus /></el-icon>
            {{ t('admin.add_git_user', 'Add Git User') }}
          </el-button>
        </div>
      </template>

      <!-- Search and Filters -->
      <el-form :inline="true" class="filter-form">
        <el-form-item label="Search">
          <el-input
            v-model="searchQuery"
            placeholder="Search by username or display name"
            clearable
            style="width: 280px"
            @clear="handleSearchClear"
            @keyup.enter="applyFilters"
          >
            <template #append>
              <el-button @click="applyFilters">
                <el-icon><Search /></el-icon>
              </el-button>
            </template>
          </el-input>
        </el-form-item>

        <el-form-item label="Status">
          <el-select v-model="statusFilter" placeholder="All" clearable style="width: 130px" @change="applyFilters">
            <el-option label="Active" :value="true" />
            <el-option label="Inactive" :value="false" />
          </el-select>
        </el-form-item>

        <el-form-item label="Reviewer">
          <el-select v-model="reviewerFilter" placeholder="All" clearable style="width: 130px" @change="applyFilters">
            <el-option label="Reviewer" :value="true" />
            <el-option label="Not Reviewer" :value="false" />
          </el-select>
        </el-form-item>
      </el-form>

      <!-- Users Table -->
      <el-table :data="users" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="user_id" label="User ID" width="80" />
        <el-table-column prop="username" label="Username" width="150" />
        <el-table-column prop="display_name" label="Display Name" min-width="160" />
        <el-table-column prop="email_address" label="Email" min-width="200" show-overflow-tooltip />
        <el-table-column label="Active" width="90">
          <template #default="{ row }">
            <el-tag :type="row.active ? 'success' : 'danger'" size="small">
              {{ row.active ? 'Yes' : 'No' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="Reviewer" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_reviewer ? 'primary' : 'info'" size="small" effect="plain">
              {{ row.is_reviewer ? 'Yes' : 'No' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="Created" width="160">
          <template #default="{ row }">
            {{ formatDate(row.created_date) }}
          </template>
        </el-table-column>
        <el-table-column label="Updated" width="160">
          <template #default="{ row }">
            {{ formatDate(row.updated_date) }}
          </template>
        </el-table-column>
        <el-table-column label="Actions" width="200" fixed="right">
          <template #default="{ row }">
            <div class="action-btns">
              <el-button size="small" type="primary" @click="handleEdit(row)">
                <el-icon><Edit /></el-icon>
                Edit
              </el-button>
              <el-dropdown trigger="click" @command="(command: string) => handleAction(command, row)">
                <el-button size="small">
                  More<el-icon class="el-icon--right"><ArrowDown /></el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item :command="'toggle'">
                      {{ row.is_reviewer ? 'Unset Reviewer' : 'Set Reviewer' }}
                    </el-dropdown-item>
                    <el-dropdown-item :command="'delete'" divided style="color: #f56c6c;">
                      <el-icon><Delete /></el-icon> Delete
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
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

    <!-- Create Git User Dialog -->
    <el-dialog v-model="showCreateDialog" title="Add Git User" width="550px">
      <el-form :model="createForm" :rules="createRules" ref="createFormRef" label-width="140px">
        <el-form-item label="User ID" prop="user_id">
          <el-input-number v-model="createForm.user_id" :min="1" style="width: 100%" placeholder="Business ID (e.g., GitHub user ID)" />
        </el-form-item>
        <el-form-item label="Username" prop="username">
          <el-input v-model="createForm.username" placeholder="Enter username" />
        </el-form-item>
        <el-form-item label="Display Name" prop="display_name">
          <el-input v-model="createForm.display_name" placeholder="Enter display name" />
        </el-form-item>
        <el-form-item label="Email" prop="email_address">
          <el-input v-model="createForm.email_address" placeholder="Enter email address" />
        </el-form-item>
        <el-form-item label="Is Reviewer">
          <el-switch v-model="createForm.is_reviewer" />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showCreateDialog = false">Cancel</el-button>
          <el-button type="primary" :loading="creating" @click="handleCreate">
            Create
          </el-button>
        </span>
      </template>
    </el-dialog>

    <!-- Edit Git User Dialog -->
    <el-dialog v-model="showEditDialog" title="Edit Git User" width="550px">
      <el-form :model="editForm" :rules="editRules" ref="editFormRef" label-width="140px">
        <el-form-item label="Username">
          <el-input :model-value="editForm.username" disabled />
        </el-form-item>
        <el-form-item label="Display Name" prop="display_name">
          <el-input v-model="editForm.display_name" placeholder="Enter display name" />
        </el-form-item>
        <el-form-item label="Email" prop="email_address">
          <el-input v-model="editForm.email_address" placeholder="Enter email address" />
        </el-form-item>
        <el-form-item label="Active">
          <el-switch v-model="editForm.active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showEditDialog = false">Cancel</el-button>
          <el-button type="primary" :loading="updating" @click="handleUpdate">
            Save
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { Plus, Search, Edit, ArrowDown, Delete } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { useI18n } from 'vue-i18n'
import dayjs from 'dayjs'
import { usersApi } from '@/api/users'

interface GitUser {
  id: number
  user_id: number
  username: string
  display_name: string
  email_address: string
  active: boolean
  is_reviewer: boolean
  created_date: string
  updated_date: string
}

const { t } = useI18n()
const loading = ref(false)
const users = ref<GitUser[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const searchQuery = ref('')
const statusFilter = ref<boolean | null>(null)
const reviewerFilter = ref<boolean | null>(null)

// Create dialog state
const showCreateDialog = ref(false)
const creating = ref(false)
const createFormRef = ref<FormInstance>()
const createForm = reactive({
  user_id: 1,
  username: '',
  display_name: '',
  email_address: '',
  is_reviewer: false,
})

// Edit dialog state
const showEditDialog = ref(false)
const updating = ref(false)
const editFormRef = ref<FormInstance>()
const editingUser = ref<GitUser | null>(null)
const editForm = reactive({
  username: '',
  display_name: '',
  email_address: '',
  active: true,
})

const createRules: FormRules = {
  user_id: [
    { required: true, message: 'Please input user ID', trigger: 'blur' },
    { type: 'number', min: 1, message: 'User ID must be a positive number', trigger: 'blur' },
  ],
  username: [
    { required: true, message: 'Please input username', trigger: 'blur' },
    { min: 3, max: 64, message: 'Length should be 3 to 64 characters', trigger: 'blur' },
  ],
  display_name: [
    { required: true, message: 'Please input display name', trigger: 'blur' },
    { min: 1, max: 128, message: 'Length should be 1 to 128 characters', trigger: 'blur' },
  ],
  email_address: [
    { required: true, message: 'Please input email address', trigger: 'blur' },
    { type: 'email', message: 'Please input a valid email address', trigger: 'blur' },
  ],
}

const editRules: FormRules = {
  display_name: [
    { required: true, message: 'Please input display name', trigger: 'blur' },
  ],
  email_address: [
    { required: true, message: 'Please input email address', trigger: 'blur' },
    { type: 'email', message: 'Please input a valid email address', trigger: 'blur' },
  ],
}

const formatDate = (dateStr: string) => {
  if (!dateStr) return '-'
  return dayjs(dateStr).format('YYYY-MM-DD HH:mm')
}

const handleSearchClear = () => {
  searchQuery.value = ''
  currentPage.value = 1
  loadUsers()
}

// Reset to the first page whenever filters/search change so the newest user
// (sorted first by created_date) is visible and results aren't stranded on a later page.
const applyFilters = () => {
  currentPage.value = 1
  loadUsers()
}

const loadUsers = async () => {
  loading.value = true
  try {
    const resp = await usersApi.getGitUsersPaginated({
      page: currentPage.value,
      page_size: pageSize.value,
      active: statusFilter.value !== null ? statusFilter.value : undefined,
      is_reviewer: reviewerFilter.value !== null ? reviewerFilter.value : undefined,
      username: searchQuery.value || undefined,
    })

    // Use the server's true total (not the truncated page length) so the
    // unfiltered list paginates over ALL users instead of being capped at 500.
    users.value = resp.items
    total.value = resp.total
  } catch (error) {
    console.error('Failed to load git users:', error)
    ElMessage.error('Failed to load git users')
  } finally {
    loading.value = false
  }
}

const handleCreate = async () => {
  if (!createFormRef.value) return

  await createFormRef.value.validate(async (valid) => {
    if (!valid) return

    creating.value = true
    try {
      await usersApi.createGitUser({
        user_id: createForm.user_id,
        username: createForm.username,
        display_name: createForm.display_name,
        email_address: createForm.email_address,
        is_reviewer: createForm.is_reviewer,
      })
      ElMessage.success('Git user created successfully')
      showCreateDialog.value = false
      createForm.user_id = 1
      createForm.username = ''
      createForm.display_name = ''
      createForm.email_address = ''
      createForm.is_reviewer = false
      // New users sort first (created_date desc); jump back to page 1 so the
      // newly created user is actually visible instead of staying on a later page.
      currentPage.value = 1
      loadUsers()
    } catch (error: any) {
      ElMessage.error(error.response?.data?.detail?.message || 'Failed to create git user')
    } finally {
      creating.value = false
    }
  })
}

const handleEdit = (user: GitUser) => {
  editingUser.value = user
  editForm.username = user.username
  editForm.display_name = user.display_name
  editForm.email_address = user.email_address
  editForm.active = user.active
  showEditDialog.value = true
}

const handleUpdate = async () => {
  if (!editFormRef.value) return
  const target = editingUser.value
  if (!target) return

  await editFormRef.value.validate(async (valid) => {
    if (!valid) return

    updating.value = true
    try {
      await usersApi.updateUser(target.id, {
        display_name: editForm.display_name,
        email_address: editForm.email_address,
        active: editForm.active,
      })
      ElMessage.success('Git user updated successfully')
      showEditDialog.value = false
      editingUser.value = null
      loadUsers()
    } catch (error: any) {
      ElMessage.error(error.response?.data?.detail?.message || 'Failed to update git user')
    } finally {
      updating.value = false
    }
  })
}

const handleToggleReviewer = async (user: GitUser) => {
  const action = user.is_reviewer ? 'unset reviewer' : 'set as reviewer'
  try {
    await ElMessageBox.confirm(
      `Are you sure you want to ${action} "${user.username}"?`,
      'Confirm',
      { type: 'warning' }
    )

    await usersApi.toggleReviewerStatus(user.id)
    ElMessage.success(`Reviewer status toggled for "${user.username}"`)
    loadUsers()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail?.message || 'Failed to toggle reviewer status')
    }
  }
}

const handleAction = (command: string, user: GitUser) => {
  if (command === 'toggle') {
    handleToggleReviewer(user)
  } else if (command === 'delete') {
    handleDelete(user)
  }
}

const handleDelete = async (user: GitUser) => {
  try {
    await ElMessageBox.confirm(
      `Are you sure you want to permanently delete git user "${user.username}"?\n\n` +
      `This will also remove all associated review assignments and scores.\n` +
      `This action CANNOT be undone.`,
      'Permanently Delete Git User',
      {
        type: 'warning',
        confirmButtonText: 'Yes, delete permanently',
        confirmButtonClass: 'el-button--danger',
        cancelButtonText: 'Cancel',
      }
    )

    await usersApi.deleteGitUser(user.id)
    ElMessage.success(`Git user "${user.username}" deleted permanently`)
    loadUsers()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail?.message || 'Failed to delete git user')
    }
  }
}

onMounted(() => {
  loadUsers()
})
</script>

<style scoped>
.git-user-management {
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

.action-btns {
  display: flex;
  align-items: center;
  gap: 8px;
  white-space: nowrap;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
