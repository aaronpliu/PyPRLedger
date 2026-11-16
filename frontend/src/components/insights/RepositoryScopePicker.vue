<template>
  <div class="scope-picker" data-test="scope-picker">
    <el-select
      :model-value="modelValue.projectKey"
      class="scope-select"
      :placeholder="t('insights.select_project')"
      filterable
      :loading="loadingProjects"
      data-test="scope-project"
      @update:model-value="handleProject"
    >
      <el-option
        v-for="project in projects"
        :key="project.project_key"
        :label="project.project_name || project.project_key"
        :value="project.project_key"
      />
    </el-select>

    <el-select
      :model-value="modelValue.repositorySlug"
      class="scope-select"
      :placeholder="t('insights.select_repository')"
      filterable
      :disabled="!modelValue.projectKey"
      :loading="loadingRepositories"
      data-test="scope-repository"
      @update:model-value="handleRepository"
    >
      <!-- Reading the project as a whole is the default: one repository is the
           drill-down, not the entry point. -->
      <el-option :label="t('insights.all_repositories')" value="" />
      <el-option
        v-for="repository in repositories"
        :key="repository.repository_slug"
        :label="repository.repository_name || repository.repository_slug"
        :value="repository.repository_slug"
      />
    </el-select>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { projectsApi, type ProjectSummary, type RepositorySummary } from '@/api/projects'

export interface RepositoryScope {
  projectKey: string
  repositorySlug: string
}

const props = defineProps<{
  modelValue: RepositoryScope
}>()

const emit = defineEmits<{
  'update:modelValue': [value: RepositoryScope]
}>()

const { t } = useI18n()

const projects = ref<ProjectSummary[]>([])
const repositories = ref<RepositorySummary[]>([])
const loadingProjects = ref(false)
const loadingRepositories = ref(false)

async function loadProjects() {
  loadingProjects.value = true
  try {
    projects.value = await projectsApi.getAllProjects()
  } catch {
    // A picker that cannot reach the project list says nothing rather than
    // breaking the page around it.
    projects.value = []
  } finally {
    loadingProjects.value = false
  }
}

async function loadRepositories(projectKey: string) {
  if (!projectKey) {
    repositories.value = []
    return
  }
  loadingRepositories.value = true
  try {
    repositories.value = await projectsApi.getProjectRepositories(projectKey)
  } catch {
    repositories.value = []
  } finally {
    loadingRepositories.value = false
  }
}

function handleProject(projectKey: string) {
  // A repository belongs to its project, so picking another project drops the
  // pick and falls back to reading the project as a whole.
  emit('update:modelValue', { projectKey, repositorySlug: '' })
}

function handleRepository(repositorySlug: string) {
  emit('update:modelValue', {
    projectKey: props.modelValue.projectKey,
    repositorySlug: repositorySlug || '',
  })
}

watch(
  () => props.modelValue.projectKey,
  (projectKey) => loadRepositories(projectKey),
  { immediate: true },
)

onMounted(loadProjects)
</script>

<style scoped>
.scope-picker {
  display: flex;
  align-items: center;
  gap: 8px;
}

.scope-select {
  width: 200px;
}
</style>
