<template>
  <div class="code" :data-test="testId('axis')">
    <!-- Waiting its turn is not the same as impossible and not the same as read:
         it says so, and the page fills it in as the batches come back. -->
    <p v-if="code.deferred" class="code-deferred" :data-test="testId('deferred')">
      {{ t('appDiff.code_deferred') }}
    </p>

    <p v-else-if="code.unavailable" class="code-unavailable" :data-test="testId('unavailable')">
      {{ t('appDiff.code_unavailable', { reason: code.unavailable }) }}
    </p>

    <template v-else>
      <p class="code-counts" :data-test="testId('counts')">
        <!-- the verdict is the answer the counts only suggest: does the later ref
             hold everything of the earlier one -->
        <el-tag size="small" effect="plain" :type="verdictType" :data-test="testId('verdict')">
          {{ t(`appDiff.code_verdict_${code.verdict}`) }}
        </el-tag>
        <span :class="`code-${tone}`">
          {{ t('appDiff.code_added', { count: code.added_count }) }}
        </span>
        <span v-if="code.missing_count" :data-test="testId('missing')">
          · {{ t('appDiff.code_missing', { count: code.missing_count }) }}
        </span>
      </p>

      <slot name="note" />

      <el-button
        v-if="total"
        link
        type="primary"
        :data-test="testId('toggle')"
        @click="emit('toggle')"
      >
        {{ expanded ? t('appDiff.code_hide') : t('appDiff.code_show') }}
      </el-button>

      <div v-if="expanded" class="commits" :data-test="testId('commits')">
        <template v-if="code.added_commits.length">
          <h4>{{ t('appDiff.code_added_heading') }}</h4>
          <ul>
            <li v-for="commit in code.added_commits" :key="commit.id">
              <code>{{ shortCommitId(commit) }}</code>
              <span class="subject">{{ commitSubject(commit) }}</span>
            </li>
          </ul>
        </template>

        <template v-if="code.missing_commits.length">
          <h4>{{ t('appDiff.code_missing_heading') }}</h4>
          <ul>
            <li v-for="commit in code.missing_commits" :key="commit.id">
              <code>{{ shortCommitId(commit) }}</code>
              <span class="subject">{{ commitSubject(commit) }}</span>
            </li>
          </ul>
        </template>

        <p v-if="code.truncated" class="truncated" :data-test="testId('truncated')">
          {{ t('appDiff.code_truncated') }}
        </p>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { AppVersionDiffCode } from '@/api/appVersionDiff'
import { codeTone, commitSubject, commitTotal, shortCommitId } from '@/utils/appVersionDiff'

/**
 * The commits between two refs, and how the comparison went.
 *
 * One shape for both axes of the page: the application's own pair of refs, and the
 * two versions of a dependency. A comparison that could not be read says why in
 * the same place one that was read says how it went, and the test hooks carry the
 * scope so a reader of the tests can tell the two axes apart.
 */
const props = defineProps<{
  code: AppVersionDiffCode
  /** Whether the commit lists are open. The caller owns the key they are kept under. */
  expanded?: boolean
  /** What this comparison is about, used to build its test hooks. */
  scope?: string
}>()

const emit = defineEmits<{ toggle: [] }>()

const { t } = useI18n()

const testId = (part: string) => `${props.scope ?? 'code'}-${part}`

const tone = computed(() => codeTone(props.code))
const total = computed(() => commitTotal(props.code))
const verdictType = computed<'success' | 'danger' | 'info'>(() => {
  if (props.code.verdict === 'contained') return 'success'
  return props.code.verdict === 'missing' ? 'danger' : 'info'
})
</script>

<style scoped>
.code {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed var(--el-border-color-lighter);
  font-size: 12px;
}

.code-counts {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0;
  color: var(--el-text-color-regular);
}

.code-counts .code-commits {
  font-weight: 600;
}

.code-counts .code-none {
  color: var(--el-text-color-secondary);
}

.code-unavailable {
  margin: 0;
  color: var(--el-color-warning-dark-2);
}

.code-deferred {
  margin: 0;
  color: var(--el-text-color-secondary);
  font-style: italic;
}

.commits {
  margin-top: 6px;
}

.commits h4 {
  margin: 6px 0 2px;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--el-text-color-secondary);
}

.commits ul {
  margin: 0;
  padding-left: 0;
  list-style: none;
}

.commits li {
  display: flex;
  gap: 6px;
  padding: 1px 0;
}

.commits code {
  color: var(--el-text-color-secondary);
  font-size: 11px;
}

.commits .subject {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.truncated {
  margin: 4px 0 0;
  color: var(--el-text-color-secondary);
  font-style: italic;
}
</style>
