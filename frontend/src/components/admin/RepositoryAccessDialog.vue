<template>
  <el-dialog
    :model-value="modelValue"
    :title="`Repository access${username ? ` — ${username}` : ''}`"
    width="640px"
    @update:model-value="close"
  >
    <div v-loading="loading">
      <div class="access-toolbar">
        <el-button size="small" @click="selectAll">Select all</el-button>
        <el-button size="small" @click="clearAll">Clear</el-button>
        <span class="access-count">{{ selected.length }} / {{ catalog.length }} repositories</span>
      </div>
      <el-checkbox-group v-model="selected" class="access-list">
        <el-checkbox v-for="item in catalog" :key="pairKey(item)" :label="pairKey(item)">
          {{ item.project_key }} / {{ item.repository_slug }}
        </el-checkbox>
      </el-checkbox-group>
      <el-empty v-if="!loading && catalog.length === 0" description="No repositories registered" />
    </div>

    <template #footer>
      <el-button @click="close">Cancel</el-button>
      <el-button type="primary" :loading="saving" @click="save">Save</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
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
const loading = ref(false)
const saving = ref(false)

const pairKey = (item: { project_key: string; repository_slug: string }) =>
  JSON.stringify([item.project_key, item.repository_slug])

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
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || 'Failed to load repository access')
  } finally {
    loading.value = false
  }
}

const selectAll = () => {
  selected.value = catalog.value.map(pairKey)
}

const clearAll = () => {
  selected.value = []
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
    if (visible) void load()
  }
)
</script>

<style scoped>
.access-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}
.access-count {
  margin-left: auto;
  color: #909399;
  font-size: 13px;
}
.access-list {
  display: flex;
  flex-direction: column;
  max-height: 420px;
  overflow-y: auto;
}
</style>
