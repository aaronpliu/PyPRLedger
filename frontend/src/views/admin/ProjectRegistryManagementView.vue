<template>
  <div class="project-registry-management">
    <el-card>
      <template #header>
        <div class="card-header">
          <h2>{{ t('admin.projectRegistry') }}</h2>
          <el-button type="primary" @click="showRegisterDialog = true">
            <el-icon><Plus /></el-icon>
            Register Project
          </el-button>
        </div>
      </template>

      <!-- Application Filter -->
      <el-form :inline="true" class="filter-form">
        <el-form-item label="Application">
          <el-select v-model="selectedApp" placeholder="All Applications" clearable style="width: 250px" @change="loadProjects">
            <el-option 
              v-for="app in apps" 
              :key="app.app_name" 
              :label="`${app.app_name} (${app.project_count} projects)`" 
              :value="app.app_name" 
            />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadProjects">
            <el-icon><Search /></el-icon>
            Refresh
          </el-button>
        </el-form-item>
      </el-form>

      <!-- Projects Table -->
      <el-table :data="projects" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="app_name" label="Application" width="180" />
        <el-table-column prop="project_key" label="Project Key" width="150" />
        <el-table-column prop="repository_slug" label="Repository Slug" min-width="200" />
        <el-table-column prop="description" label="Description" min-width="200" show-overflow-tooltip />
        <el-table-column prop="created_date" label="Created" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_date) }}
          </template>
        </el-table-column>
        <el-table-column label="Actions" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="handleUpdate(row)">
              Move App
            </el-button>
            <el-button size="small" type="danger" @click="handleUnregister(row)">
              Unregister
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Register Project Dialog -->
    <el-dialog v-model="showRegisterDialog" title="Register Project to Application" width="600px">
      <el-form :model="registerForm" :rules="registerRules" ref="registerFormRef" label-width="140px">
        <el-form-item label="Application Name" prop="appName">
          <el-input v-model="registerForm.appName" placeholder="e.g., ECOMMERCE, MOBILE-APP" />
        </el-form-item>
        
        <el-form-item label="Project Key" prop="projectKey">
          <el-input v-model="registerForm.projectKey" placeholder="e.g., ECOM" />
        </el-form-item>
        
        <el-form-item label="Repository Slug" prop="repositorySlug">
          <el-input v-model="registerForm.repositorySlug" placeholder="e.g., frontend-store" />
        </el-form-item>
        
        <el-form-item label="Description" prop="description">
          <el-input 
            v-model="registerForm.description" 
            type="textarea" 
            :rows="3"
            placeholder="Optional description" 
          />
        </el-form-item>
      </el-form>
      
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showRegisterDialog = false">Cancel</el-button>
          <el-button type="primary" :loading="registering" @click="handleRegister">
            Register
          </el-button>
        </span>
      </template>
    </el-dialog>

    <!-- Update Project Dialog -->
    <el-dialog v-model="showUpdateDialog" title="Move Project to Different Application" width="600px">
      <el-form :model="updateForm" :rules="updateRules" ref="updateFormRef" label-width="140px">
        <el-alert 
          :title="`Current: ${selectedProject?.app_name}`" 
          type="info" 
          :closable="false"
          style="margin-bottom: 16px;"
        />
        
        <el-form-item label="Project Key">
          <el-input :value="selectedProject?.project_key" disabled />
        </el-form-item>
        
        <el-form-item label="Repository Slug">
          <el-input :value="selectedProject?.repository_slug" disabled />
        </el-form-item>
        
        <el-form-item label="New Application" prop="newAppName">
          <el-input v-model="updateForm.newAppName" placeholder="Enter new application name" />
        </el-form-item>
      </el-form>
      
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showUpdateDialog = false">Cancel</el-button>
          <el-button type="primary" :loading="updating" @click="handleUpdateSubmit">
            Update
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { Plus, Search } from '@element-plus/icons-vue'
import { projectRegistryApi } from '@/api/projectRegistry'
import type { ProjectRegistry, AppInfo } from '@/api/projectRegistry'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { useI18n } from 'vue-i18n'
import dayjs from 'dayjs'

const { t } = useI18n()

// State
const loading = ref(false)
const registering = ref(false)
const updating = ref(false)
const apps = ref<AppInfo[]>([])
const projects = ref<ProjectRegistry[]>([])
const selectedApp = ref<string | null>(null)
const selectedProject = ref<ProjectRegistry | null>(null)

// Dialogs
const showRegisterDialog = ref(false)
const showUpdateDialog = ref(false)

// Forms
const registerFormRef = ref<FormInstance>()
const updateFormRef = ref<FormInstance>()

const registerForm = reactive({
  appName: '',
  projectKey: '',
  repositorySlug: '',
  description: '',
})

const updateForm = reactive({
  newAppName: '',
})

// Validation rules
const registerRules: FormRules = {
  appName: [
    { required: true, message: 'Please input application name', trigger: 'blur' },
    { min: 1, max: 64, message: 'Length should be 1 to 64 characters', trigger: 'blur' },
  ],
  projectKey: [
    { required: true, message: 'Please input project key', trigger: 'blur' },
    { min: 1, max: 32, message: 'Length should be 1 to 32 characters', trigger: 'blur' },
  ],
  repositorySlug: [
    { required: true, message: 'Please input repository slug', trigger: 'blur' },
    { min: 1, max: 128, message: 'Length should be 1 to 128 characters', trigger: 'blur' },
  ],
}

const updateRules: FormRules = {
  newAppName: [
    { required: true, message: 'Please input new application name', trigger: 'blur' },
    { min: 1, max: 64, message: 'Length should be 1 to 64 characters', trigger: 'blur' },
  ],
}

// Utility functions
const formatDate = (dateStr: string) => {
  return dayjs(dateStr).format('YYYY-MM-DD HH:mm:ss')
}

// Data loading
const loadApps = async () => {
  try {
    apps.value = await projectRegistryApi.listApps()
  } catch (error) {
    console.error('Failed to load apps:', error)
    ElMessage.error('Failed to load applications')
  }
}

const loadProjects = async () => {
  loading.value = true
  try {
    if (selectedApp.value) {
      // Load projects for selected app only
      projects.value = await projectRegistryApi.listProjectsByApp(selectedApp.value)
    } else {
      // ✅ Use new efficient endpoint to fetch all registered projects in a single request
      projects.value = await projectRegistryApi.listAllRegisteredProjects()
    }
  } catch (error) {
    console.error('Failed to load projects:', error)
    ElMessage.error('Failed to load projects')
    projects.value = []
  } finally {
    loading.value = false
  }
}

// Actions
const handleRegister = async () => {
  if (!registerFormRef.value) return
  
  await registerFormRef.value.validate(async (valid) => {
    if (valid) {
      registering.value = true
      try {
        await projectRegistryApi.registerProject(
          registerForm.appName,
          registerForm.projectKey,
          registerForm.repositorySlug,
          registerForm.description || undefined
        )
        ElMessage.success('Project registered successfully')
        showRegisterDialog.value = false
        // Reset form
        registerForm.appName = ''
        registerForm.projectKey = ''
        registerForm.repositorySlug = ''
        registerForm.description = ''
        // Reload data
        await loadApps()
        await loadProjects()
      } catch (error: any) {
        const message = error.response?.data?.detail?.message || 'Failed to register project'
        ElMessage.error(message)
      } finally {
        registering.value = false
      }
    }
  })
}

const handleUpdate = (project: ProjectRegistry) => {
  selectedProject.value = project
  updateForm.newAppName = ''
  showUpdateDialog.value = true
}

const handleUpdateSubmit = async () => {
  if (!updateFormRef.value || !selectedProject.value) return
  
  await updateFormRef.value.validate(async (valid) => {
    if (valid && selectedProject.value) {
      updating.value = true
      try {
        await projectRegistryApi.updateProjectApp(
          selectedProject.value.project_key,
          selectedProject.value.repository_slug,
          updateForm.newAppName
        )
        ElMessage.success('Project updated successfully')
        showUpdateDialog.value = false
        // Reload data
        await loadApps()
        await loadProjects()
      } catch (error: any) {
        const message = error.response?.data?.detail?.message || 'Failed to update project'
        ElMessage.error(message)
      } finally {
        updating.value = false
      }
    }
  })
}

const handleUnregister = async (project: ProjectRegistry) => {
  try {
    await ElMessageBox.confirm(
      `Are you sure you want to unregister ${project.project_key}/${project.repository_slug}?`,
      'Confirm Unregistration',
      { type: 'warning' }
    )
    
    await projectRegistryApi.unregisterProject(project.project_key, project.repository_slug)
    ElMessage.success('Project unregistered successfully')
    // Reload data
    await loadApps()
    await loadProjects()
  } catch (error: any) {
    if (error !== 'cancel') {
      const message = error.response?.data?.detail?.message || 'Failed to unregister project'
      ElMessage.error(message)
    }
  }
}

// Lifecycle
onMounted(async () => {
  // Load apps first, then load projects (which depends on apps list)
  await loadApps()
  await loadProjects()
})
</script>

<style scoped>
.project-registry-management {
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

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
