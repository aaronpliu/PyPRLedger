<template>
  <div class="commit-table">
    <el-table :data="visibleCommits" stripe style="width: 100%" max-height="420px">
    <template #empty>
      <el-empty :description="emptyText" :image-size="60" />
    </template>
    <el-table-column :label="t('releaseDiff.col_commit')" min-width="220">
      <template #default="{ row }">
        <a
          v-if="row.url"
          class="commit-sha"
          :href="row.url"
          target="_blank"
          rel="noopener"
          @click.stop="copy(row.id)"
        >
          {{ row.display_id || row.id }}
        </a>
        <span v-else class="commit-sha" @click="copy(row.id)">{{ row.display_id || row.id }}</span>
      </template>
    </el-table-column>
    <el-table-column :label="t('releaseDiff.col_author')" width="180">
      <template #default="{ row }">
        {{ row.author_name || '-' }}
      </template>
    </el-table-column>
    <el-table-column :label="t('releaseDiff.col_date')" width="180">
      <template #default="{ row }">
        {{ formatTimestamp(row.author_timestamp) }}
      </template>
    </el-table-column>
    <el-table-column :label="t('releaseDiff.col_message')" min-width="260">
      <template #default="{ row }">
        {{ firstLine(row.message) }}
      </template>
    </el-table-column>
    </el-table>

    <!-- Client side paging keeps the DOM small: a long lived repository can bring
         hundreds (or thousands) of commits into one of these tables. -->
    <el-pagination
      v-if="commits.length > pageSize"
      v-model:current-page="currentPage"
      v-model:page-size="pageSize"
      class="commit-pagination"
      size="small"
      background
      :page-sizes="[20, 50, 100, 200]"
      :total="commits.length"
      layout="total, sizes, prev, pager, next"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import dayjs from 'dayjs'
import type { CommitInfo } from '@/api/releaseDiff'

const props = withDefaults(
  defineProps<{
    commits: CommitInfo[]
    emptyText?: string
    pageSize?: number
  }>(),
  {
    emptyText: 'No commits',
    pageSize: 20,
  },
)

const { t } = useI18n()

const currentPage = ref(1)
const pageSize = ref(props.pageSize)

// A new commit list always starts at the first page
watch(
  () => props.commits,
  () => {
    currentPage.value = 1
  },
)

const visibleCommits = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return props.commits.slice(start, start + pageSize.value)
})

function formatTimestamp(value?: number | null): string {
  if (!value) return '-'
  return dayjs(value).format('YYYY-MM-DD HH:mm')
}

function firstLine(message?: string | null): string {
  if (!message) return '-'
  return message.split('\n')[0]
}

async function copy(value: string) {
  try {
    await navigator.clipboard.writeText(value)
    ElMessage.success(t('releaseDiff.copied'))
  } catch {
    ElMessage.info(value)
  }
}
</script>

<style scoped>
.commit-pagination {
  margin-top: 8px;
  justify-content: flex-end;
}

.commit-sha {
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', monospace;
  font-size: 12px;
  color: var(--el-color-primary);
  cursor: pointer;
  text-decoration: none;
}

.commit-sha:hover {
  text-decoration: underline;
}
</style>
