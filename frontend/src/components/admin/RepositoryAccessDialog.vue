<template>
  <el-dialog
    :model-value="modelValue"
    :title="`Repository access${username ? ` — ${username}` : ''}`"
    width="760px"
    @update:model-value="close"
  >
    <div v-loading="loading">
      <div class="access-toolbar">
        <el-input
          v-model="filter"
          class="access-filter"
          size="small"
          clearable
          placeholder="Filter projects or repositories"
          :prefix-icon="Search"
        />
        <el-button size="small" @click="selectAll">Select all</el-button>
        <el-button size="small" @click="clearAll">Clear</el-button>
        <span class="access-count">{{ selected.length }} / {{ catalog.length }} repositories</span>
      </div>

      <!-- The catalog reads as a tree: a project is the parent row and its
           repositories are indented children, so a project is never confused
           with a repository. Checking a project takes all of its repositories,
           and a half-picked project shows the mixed state on its checkbox. -->
      <div class="access-tree" data-test="access-tree">
        <el-tree
          ref="treeRef"
          :data="treeData"
          node-key="key"
          show-checkbox
          default-expand-all
          :filter-node-method="filterNode"
          @check="syncSelection"
        >
          <template #default="{ data }">
            <span
              class="node-label"
              :class="{ 'node-project': isProject(data) }"
              :title="data.label"
            >
              {{ data.label }}
            </span>
            <span v-if="isProject(data)" class="node-count">
              {{ projectSelectedCount(data.key) }} / {{ projectTotal(data.key) }}
            </span>
          </template>
        </el-tree>
        <p v-if="catalog.length > 0 && filter && visibleGroups.length === 0" class="no-match">
          No project matches “{{ filter }}”.
        </p>
      </div>
      <el-empty v-if="!loading && catalog.length === 0" description="No repositories registered" />
    </div>

    <template #footer>
      <el-button @click="close">Cancel</el-button>
      <el-button type="primary" :loading="saving" @click="save">Save</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { TreeInstance } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import {
  repositoryAccessApi,
  type RepositoryCatalogItem,
} from '@/api/repositoryAccess'

const props = defineProps<{
  modelValue: boolean
  subjectType: 'auth_user' | 'git_user'
  subjectId: number | null
  username?: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'saved'): void
}>()

const catalog = ref<RepositoryCatalogItem[]>([])
const selected = ref<string[]>([])
const filter = ref('')
const loading = ref(false)
const saving = ref(false)

const pairKey = (item: { project_key: string; repository_slug: string }) =>
  JSON.stringify([item.project_key, item.repository_slug])

interface RepoEntry {
  key: string
  slug: string
  title: string
}

interface ProjectGroup {
  project_key: string
  repos: RepoEntry[]
}

/** The catalog read as project groups, in project order, repositories in slug order. */
const groups = computed<ProjectGroup[]>(() => {
  const byProject = new Map<string, RepoEntry[]>()
  for (const item of catalog.value) {
    const repos = byProject.get(item.project_key) ?? []
    repos.push({
      key: pairKey(item),
      slug: item.repository_slug,
      title: item.app_name ? `${item.repository_slug} (${item.app_name})` : item.repository_slug,
    })
    byProject.set(item.project_key, repos)
  }
  return [...byProject.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([project_key, repos]) => ({
      project_key,
      repos: repos.sort((a, b) => a.slug.localeCompare(b.slug)),
    }))
})

interface AccessNode {
  key: string
  label: string
  children?: AccessNode[]
}

/** Two levels: the project is the parent, its repositories the children. */
const treeData = computed<AccessNode[]>(() =>
  groups.value.map((group) => ({
    key: group.project_key,
    label: group.project_key,
    children: group.repos.map((repo) => ({ key: repo.key, label: repo.title })),
  }))
)

/** The groups the filter leaves standing, for the "nothing matches" note. */
const visibleGroups = computed<ProjectGroup[]>(() => {
  const needle = filter.value.trim().toLowerCase()
  if (!needle) return groups.value
  return groups.value
    .map((group) => ({
      project_key: group.project_key,
      repos: group.repos.filter(
        (repo) =>
          repo.slug.toLowerCase().includes(needle) ||
          group.project_key.toLowerCase().includes(needle)
      ),
    }))
    .filter((group) => group.repos.length > 0)
})

const isProject = (node: AccessNode) => Array.isArray(node.children)

const groupOf = (projectKey: string) =>
  groups.value.find((group) => group.project_key === projectKey)

const projectTotal = (projectKey: string) => groupOf(projectKey)?.repos.length ?? 0

const projectSelectedCount = (projectKey: string) =>
  (groupOf(projectKey)?.repos ?? []).filter((repo) => selected.value.includes(repo.key)).length

const treeRef = ref<TreeInstance>()

const filterNode = (value: string, data: AccessNode) => {
  const needle = value.trim().toLowerCase()
  if (!needle) return true
  return data.label.toLowerCase().includes(needle)
}

/** The tree is the source of truth for what is picked; read its leaf keys. */
const syncSelection = () => {
  selected.value = (treeRef.value?.getCheckedKeys(true) ?? []) as string[]
}

const selectAll = () => {
  const keys = catalog.value.map(pairKey)
  treeRef.value?.setCheckedKeys(keys)
  selected.value = keys
}

const clearAll = () => {
  treeRef.value?.setCheckedKeys([])
  selected.value = []
}

const load = async () => {
  if (props.subjectId === null) return
  loading.value = true
  try {
    const [all, current] = await Promise.all([
      repositoryAccessApi.getCatalog(),
      repositoryAccessApi.getAccess(props.subjectType, props.subjectId),
    ])
    catalog.value = all
    selected.value = current.items.map((item) =>
      pairKey({
        project_key: String(item.project_key),
        repository_slug: String(item.repository_slug),
      })
    )
    // the tree mounts lazily with the dialog, so the saved keys land once its
    // nodes exist
    await nextTick()
    treeRef.value?.setCheckedKeys(selected.value)
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || 'Failed to load repository access')
  } finally {
    loading.value = false
  }
}

const save = async () => {
  if (props.subjectId === null) return
  saving.value = true
  try {
    const items = selected.value.map((key) => {
      const [project_key, repository_slug] = JSON.parse(key) as [string, string]
      return { project_key, repository_slug }
    })
    await repositoryAccessApi.replaceAccess(props.subjectType, props.subjectId, items)
    ElMessage.success('Repository access saved')
    emit('saved')
    emit('update:modelValue', false)
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || 'Failed to save repository access')
  } finally {
    saving.value = false
  }
}

const close = () => {
  emit('update:modelValue', false)
}

watch(
  () => props.modelValue,
  (visible) => {
    if (visible) {
      filter.value = ''
      void load()
    }
  }
)

watch(filter, (value) => {
  treeRef.value?.filter(value)
})
</script>

<style scoped>
.access-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}
.access-filter {
  width: 220px;
}
.access-count {
  margin-left: auto;
  color: #909399;
  font-size: 13px;
  white-space: nowrap;
}

.access-tree {
  max-height: 460px;
  overflow-y: auto;
  padding: 4px 6px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
}

/* the two levels read differently: the project is a bold row, the repository
   underneath it is the indented child the tree indents for itself */
.node-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
  color: var(--el-text-color-regular);
}
.node-label.node-project {
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.node-count {
  margin-left: 8px;
  flex-shrink: 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  font-variant-numeric: tabular-nums;
}

.no-match {
  margin: 16px 0;
  text-align: center;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
</style>
