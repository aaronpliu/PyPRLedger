<template>
  <div class="card" :data-test="missing ? 'missing-commit' : 'added-commit'">
    <div class="card-body">
      <span class="subject" :title="fullMessage">{{ subject }}</span>
      <span v-if="meta" class="meta">{{ meta }}</span>
    </div>
    <a v-if="commit.url" class="id" :href="commit.url" target="_blank" rel="noopener">
      <code>{{ id }}</code>
    </a>
    <code v-else class="id">{{ id }}</code>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import dayjs from 'dayjs'
import type { AppVersionDiffCommit } from '@/api/appVersionDiff'
import { commitSubject, shortCommitId } from '@/utils/appVersionDiff'

/**
 * One commit as a card: subject first, who wrote it and when under it, and the
 * short id as the way in. The same shape serves both columns of the drawer -
 * only the tint differs, which the caller says with `missing`.
 */
const props = defineProps<{
  commit: AppVersionDiffCommit
  /** A commit the later ref does not hold, read in the missing column. */
  missing?: boolean
}>()

const subject = computed(() => commitSubject(props.commit))
const fullMessage = computed(() => props.commit.message ?? '')
const id = computed(() => shortCommitId(props.commit))

const meta = computed(() => {
  const parts: string[] = []
  const author = props.commit.author_name || props.commit.author_username
  if (author) parts.push(author)
  if (props.commit.author_timestamp) {
    parts.push(dayjs(props.commit.author_timestamp).format('YYYY-MM-DD'))
  }
  return parts.join(' · ')
})
</script>

<style scoped>
.card {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  padding: 6px 8px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  background: var(--el-bg-color);
  font-size: 12px;
}

/* the card that asks for attention is tinted before it is read */
.card.missing {
  border-color: color-mix(in srgb, var(--el-color-danger) 35%, transparent);
  background: var(--diff-fill-red);
}

.card-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.subject {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--el-text-color-primary);
}

.meta {
  font-size: 11px;
  color: var(--el-text-color-secondary);
}

.id {
  flex-shrink: 0;
  color: var(--el-text-color-secondary);
}

a.id:hover code {
  color: var(--el-color-primary);
}
</style>
