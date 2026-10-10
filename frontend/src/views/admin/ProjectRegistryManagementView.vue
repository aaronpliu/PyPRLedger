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
          <el-select v-model="selectedApp" placeholder="All Applications" clearable style="width: 250px" @change="handleFilterChange">
            <el-option 
              v-for="app in apps" 
              :key="app.app_name" 
              :label="`${app.app_name} (${app.project_count} projects)`" 
              :value="app.app_name" 
            />
          </el-select>
        </el-form-item>
        <el-form-item label="Search">
          <el-input
            v-model="searchTerm"
            placeholder="Search project key, repo slug, or description"
            clearable
            style="width: 320px"
            @clear="handleFilterChange"
            @keyup.enter="handleFilterChange"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleFilterChange">
            <el-icon><Search /></el-icon>
            Search
          </el-button>
        </el-form-item>
      </el-form>

      <!-- Projects Table -->
      <el-table :data="projects" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="app_name" label="Application" width="180" />
        <el-table-column label="App alias" width="200">
          <template #default="{ row }">
            <!-- An empty alias is not a gap: it means the application name is asked for -->
            <span v-if="row.app_alias" class="alias-value" data-test="app-alias">
              {{ row.app_alias }}
            </span>
            <span v-else class="alias-follows">
              Follows {{ row.app_name }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="Kind" width="130">
          <template #default="{ row }">
            <!-- What a registration is decides which pickers offer it: the pages that
                 read an application's releases leave out what is marked as a package,
                 and offer everything nobody has classified -->
            <el-tag :type="kindTagType(row.registry_kind)" size="small" data-test="registry-kind">
              {{ kindLabel(row.registry_kind) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="project_key" label="Project Key" width="150" />
        <el-table-column prop="repository_slug" label="Repository Slug" min-width="200" />
        <el-table-column prop="git_provider" label="Git Provider" width="180">
          <template #default="{ row }">
            <el-tag :type="getProviderTagType(row.git_provider)" size="small">
              {{ getProviderLabel(row.git_provider) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="Description" min-width="200" show-overflow-tooltip />
        <el-table-column prop="created_date" label="Created" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_date) }}
          </template>
        </el-table-column>
        <el-table-column label="Actions" width="520" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleEditAlias(row)">
              Edit Alias
            </el-button>
            <!-- What this registration is. Empty is a choice of its own - where every
                 registration starts, and what keeps behaving as it always did. -->
            <el-select
              :model-value="row.registry_kind ?? ''"
              class="kind-select"
              size="small"
              data-test="kind-select"
              @change="(value: string) => handleKindChange(row, value)"
            >
              <el-option label="Not set" value="" />
              <el-option label="Application" value="application" />
              <el-option label="Package" value="package" />
            </el-select>
            <el-button size="small" type="primary" @click="handleUpdate(row)">
              Move App
            </el-button>
            <el-button size="small" type="danger" @click="handleUnregister(row)">
              Unregister
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- Pagination -->
      <div class="pagination-container">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="totalItems"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSizeChange"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>

    <!-- Register Project Dialog -->
    <el-dialog v-model="showRegisterDialog" title="Register Project to Application" width="600px">
      <el-form :model="registerForm" :rules="registerRules" ref="registerFormRef" label-width="140px">
        <el-form-item label="Application Name" prop="appName">
          <el-input v-model="registerForm.appName" placeholder="e.g., ECOMMERCE, MOBILE-APP" />
        </el-form-item>
        
        <el-form-item label="Project Key" prop="projectKey">
          <el-select 
            v-model="registerForm.projectKey" 
            placeholder="Select project key" 
            filterable
            style="width: 100%"
          >
            <el-option 
              v-for="project in availableProjects" 
              :key="project.project_key" 
              :label="`${project.project_key} - ${project.project_name}`" 
              :value="project.project_key" 
            />
          </el-select>
        </el-form-item>
        
        <el-form-item label="Repository Slug" prop="repositorySlug">
          <el-select 
            v-model="registerForm.repositorySlug" 
            placeholder="Select repository slug" 
            filterable
            :disabled="!registerForm.projectKey"
            :loading="loadingRepositories"
            style="width: 100%"
          >
            <el-option 
              v-for="repo in availableRepositories" 
              :key="repo.repository_slug" 
              :label="`${repo.repository_slug} - ${repo.repository_name}`" 
              :value="repo.repository_slug" 
            />
          </el-select>
        </el-form-item>
        
        <el-form-item label="Git Provider" prop="gitProvider">
          <el-select v-model="registerForm.gitProvider" style="width: 100%">
            <el-option
              v-for="option in GIT_PROVIDER_OPTIONS"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="App alias" prop="appAlias">
          <el-input
            v-model="registerForm.appAlias"
            maxlength="64"
            placeholder="Optional - follows the application name when empty"
          />
          <div class="field-hint">
            The name the dependency database knows this application as, when it differs from
            the application name. Only the Releases pages ask it for this name.
          </div>
        </el-form-item>

        <el-form-item label="Kind" prop="registryKind">
          <el-select v-model="registerForm.registryKind" style="width: 100%">
            <el-option label="Application" value="application" />
            <el-option label="Package" value="package" />
            <el-option label="Not set" value="" />
          </el-select>
          <div class="field-hint">
            What this repository is. The Release Dependency Graph and the App Diff leave
            out the repositories marked as packages, because the dependency database holds
            no release records for those - and they offer everything that is not
            classified, so leaving this unset changes nothing.
          </div>
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

    <!-- App Alias Dialog -->
    <el-dialog v-model="showAliasDialog" title="Dependency Database Name" width="600px">
      <el-form :model="aliasForm" label-width="140px">
        <el-form-item label="Project Key">
          <el-input :value="selectedProject?.project_key" disabled />
        </el-form-item>

        <el-form-item label="Repository Slug">
          <el-input :value="selectedProject?.repository_slug" disabled />
        </el-form-item>

        <el-form-item label="Application">
          <el-input :value="selectedProject?.app_name" disabled />
        </el-form-item>

        <el-form-item label="App alias">
          <el-input
            v-model="aliasForm.appAlias"
            maxlength="64"
            show-word-limit
            clearable
            :placeholder="aliasPlaceholder"
          />
          <div class="field-hint">
            The name the dependency database knows this application as, when it differs from
            the application name. Leave it empty to ask for the application name, and only
            the Releases pages are affected either way.
          </div>
        </el-form-item>
      </el-form>

      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showAliasDialog = false">Cancel</el-button>
          <el-button type="primary" :loading="updatingAlias" @click="handleAliasSubmit">
            Save
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, reactive, onMounted, watch } from 'vue'
import { Plus, Search } from '@element-plus/icons-vue'
import { projectRegistryApi } from '@/api/projectRegistry'
import { projectsApi } from '@/api/projects'
import type { ProjectRegistry, AppInfo } from '@/api/projectRegistry'
import type { ProjectSummary, RepositorySummary } from '@/api/projects'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { useI18n } from 'vue-i18n'
import dayjs from 'dayjs'
import {
  DEFAULT_GIT_PROVIDER,
  GIT_PROVIDER_OPTIONS,
  getGitProviderLabel,
  getGitProviderTagType,
} from '@/constants/gitProvider'

const { t } = useI18n()

// State
const loading = ref(false)
const registering = ref(false)
const updating = ref(false)
const apps = ref<AppInfo[]>([])
const projects = ref<ProjectRegistry[]>([])
const selectedApp = ref<string | null>(null)
const selectedProject = ref<ProjectRegistry | null>(null)

// Pagination
const currentPage = ref(1)
const pageSize = ref(20)
const totalItems = ref(0)
const searchTerm = ref('')

// Dropdown data
const availableProjects = ref<ProjectSummary[]>([])
const availableRepositories = ref<RepositorySummary[]>([])
const loadingRepositories = ref(false)

// Dialogs
const showRegisterDialog = ref(false)
const showUpdateDialog = ref(false)
const showAliasDialog = ref(false)

// Forms
const registerFormRef = ref<FormInstance>()
const updateFormRef = ref<FormInstance>()

const registerForm = reactive({
  appName: '',
  projectKey: '',
  repositorySlug: '',
  gitProvider: DEFAULT_GIT_PROVIDER,
  appAlias: '',
  // a registration that says nothing is an application: that is what this table was for
  registryKind: 'application',
  description: '',
})

/** What a registration is, as the page reads it. Empty is not a kind: nobody has said. */
const kindLabel = (kind: string | null | undefined) =>
  kind === 'package' ? 'Package' : kind === 'application' ? 'Application' : 'Not set'

/** How the tag reads: a package is set aside, an unclassified row claims nothing. */
const kindTagType = (kind: string | null | undefined): '' | 'success' | 'info' =>
  kind === 'package' ? 'info' : kind === 'application' ? 'success' : ''

const getProviderLabel = (provider: string) => getGitProviderLabel(provider)

const getProviderTagType = (provider: string): '' | 'success' | 'warning' | 'info' | 'danger' =>
  getGitProviderTagType(provider)

const updateForm = reactive({
  newAppName: '',
})

const updatingAlias = ref(false)
const aliasForm = reactive({
  appAlias: '',
})

/** An empty alias is the application name, so the field says which one it would be. */
const aliasPlaceholder = computed(
  () => `Follows the application name (${selectedProject.value?.app_name ?? ''})`
)

// Watch for project key changes to load repositories
watch(
  () => registerForm.projectKey,
  async (newProjectKey) => {
    if (newProjectKey) {
      await loadRepositoriesForProject(newProjectKey)
      // Clear repository slug when project changes
      registerForm.repositorySlug = ''
    } else {
      availableRepositories.value = []
    }
  }
)

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

const loadAvailableProjects = async () => {
  try {
    availableProjects.value = await projectsApi.getAllProjects()
  } catch (error) {
    console.error('Failed to load projects:', error)
    ElMessage.error('Failed to load projects for dropdown')
  }
}

const loadRepositoriesForProject = async (projectKey: string) => {
  if (!projectKey) {
    availableRepositories.value = []
    return
  }
  
  loadingRepositories.value = true
  try {
    availableRepositories.value = await projectsApi.getProjectRepositories(projectKey)
  } catch (error) {
    console.error('Failed to load repositories:', error)
    ElMessage.error('Failed to load repositories')
    availableRepositories.value = []
  } finally {
    loadingRepositories.value = false
  }
}

const loadProjects = async () => {
  loading.value = true
  try {
    const response = await projectRegistryApi.listRegistryProjectsPaginated({
      app_name: selectedApp.value || undefined,
      search: searchTerm.value || undefined,
      page: currentPage.value,
      page_size: pageSize.value,
    })
    projects.value = response.items
    totalItems.value = response.total
  } catch (error) {
    console.error('Failed to load projects:', error)
    ElMessage.error('Failed to load projects')
    projects.value = []
    totalItems.value = 0
  } finally {
    loading.value = false
  }
}

const handleFilterChange = () => {
  currentPage.value = 1
  loadProjects()
}

const handlePageChange = (page: number) => {
  currentPage.value = page
  loadProjects()
}

const handleSizeChange = (size: number) => {
  pageSize.value = size
  currentPage.value = 1
  loadProjects()
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
          registerForm.description || undefined,
          registerForm.gitProvider,
          registerForm.appAlias || undefined,
          registerForm.registryKind
        )
        ElMessage.success('Project registered successfully')
        showRegisterDialog.value = false
        // Reset form
        registerForm.appName = ''
        registerForm.projectKey = ''
        registerForm.repositorySlug = ''
        registerForm.gitProvider = DEFAULT_GIT_PROVIDER
        registerForm.appAlias = ''
        registerForm.registryKind = 'application'
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

/**
 * Set, change, or take back what a registration is.
 *
 * The pages that read an application's releases leave out what is marked as a
 * package and offer everything else, so an empty value is how an administrator
 * returns a repository to the behaviour an unclassified one gets.
 */
const handleKindChange = async (project: ProjectRegistry, kind: string) => {
  try {
    await projectRegistryApi.updateRegistryKind(
      project.project_key,
      project.repository_slug,
      kind === '' ? null : (kind as 'application' | 'package')
    )
    ElMessage.success(
      kind === ''
        ? `${project.project_key}/${project.repository_slug} is left unclassified`
        : `${project.project_key}/${project.repository_slug} is now a ${kind}`
    )
    await loadProjects()
  } catch (error: any) {
    const message = error.response?.data?.detail?.message || 'Failed to update the kind'
    ElMessage.error(message)
  }
}

const handleEditAlias = (project: ProjectRegistry) => {
  selectedProject.value = project
  // the stored alias, not the effective name: an empty field keeps following
  aliasForm.appAlias = project.app_alias ?? ''
  showAliasDialog.value = true
}

const handleAliasSubmit = async () => {
  if (!selectedProject.value) return

  updatingAlias.value = true
  try {
    const result = await projectRegistryApi.updateAppAlias(
      selectedProject.value.project_key,
      selectedProject.value.repository_slug,
      aliasForm.appAlias.trim()
    )
    ElMessage.success(
      `The dependency database will be asked for '${result.dependency_app_name}'`
    )
    showAliasDialog.value = false
    await loadProjects()
  } catch (error: any) {
    const message = error.response?.data?.detail?.message || 'Failed to update the app alias'
    ElMessage.error(message)
  } finally {
    updatingAlias.value = false
  }
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
  // Load available projects for dropdown
  await loadAvailableProjects()
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

.pagination-container {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

/* the name the dependency database is asked for, when it differs from the app */
.alias-value {
  font-family: var(--el-font-family-mono, monospace);
}

/* an empty alias is the application name, said rather than left blank */
.alias-follows {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

/* the kind, set from the row it belongs to */
.kind-select {
  width: 128px;
  margin: 0 8px;
}

.field-hint {
  margin-top: 4px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.5;
}
</style>
