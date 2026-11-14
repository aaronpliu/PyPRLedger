<template>
  <div class="code" :data-test="testId('axis')">
    <!-- What the comparison is about, read before how it went: a comparison that
         could not be read still says which two versions it was between. -->
    <slot name="note" />

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
        <span v-if="code.missing_count" class="code-missing-count" :data-test="testId('missing')">
          · {{ t('appDiff.code_missing', { count: code.missing_count }) }}
        </span>
      </p>

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
            <li v-for="commit in code.added_commits" :key="commit.id" class="commit">
              <a
                v-if="commit.url"
                class="commit-id"
                :href="commit.url"
                target="_blank"
                rel="noopener"
              >
                <code>{{ shortCommitId(commit) }}</code>
              </a>
              <code v-else>{{ shortCommitId(commit) }}</code>
              <div class="commit-body">
                <span class="subject" :title="fullMessage(commit)">
                  {{ commitSubject(commit) }}
                </span>
                <span v-if="commitMeta(commit)" class="commit-meta">
                  {{ commitMeta(commit) }}
                </span>
              </div>
            </li>
          </ul>
        </template>

        <template v-if="code.missing_commits.length">
          <h4 class="missing-heading">
            <el-icon><WarningFilled /></el-icon>
            {{ t('appDiff.code_missing_heading') }}
          </h4>
          <ul>
            <li v-for="commit in code.missing_commits" :key="commit.id" class="commit missing">
              <a
                v-if="commit.url"
                class="commit-id"
                :href="commit.url"
                target="_blank"
                rel="noopener"
              >
                <code>{{ shortCommitId(commit) }}</code>
              </a>
              <code v-else>{{ shortCommitId(commit) }}</code>
              <div class="commit-body">
                <span class="subject" :title="fullMessage(commit)">
                  {{ commitSubject(commit) }}
                </span>
                <span v-if="commitMeta(commit)" class="commit-meta">
                  {{ commitMeta(commit) }}
                </span>
              </div>
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
import dayjs from 'dayjs'
import { WarningFilled } from '@element-plus/icons-vue'
import type { AppVersionDiffCode, AppVersionDiffCommit } from '@/api/appVersionDiff'
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

/** The whole message, body lines included, for the hover title. */
function fullMessage(commit: AppVersionDiffCommit): string {
  return commit.message ?? ''
}

/** Who wrote it and when, in one short line under the subject. */
function commitMeta(commit: AppVersionDiffCommit): string {
  const parts: string[] = []
  const author = commit.author_name || commit.author_username
  if (author) parts.push(author)
  if (commit.author_timestamp) {
    parts.push(dayjs(commit.author_timestamp).format('YYYY-MM-DD'))
  }
  return parts.join(' · ')
}
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

/* the count that asks for action reads as soon as the verdict does */
.code-missing-count {
  color: var(--el-color-danger);
  font-weight: 600;
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

.commits h4 .el-icon {
  vertical-align: -2px;
  margin-right: 2px;
}

.commits ul {
  margin: 0;
  padding-left: 0;
  list-style: none;
}

.commits li.commit {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 2px 4px;
  border-radius: 3px;
}

/* a commit the later ref does not hold: the row asks for attention before it is read */
.commits li.commit.missing {
  border-left: 3px solid var(--el-color-danger);
  background: var(--el-color-danger-light-9);
}

.missing-heading {
  color: var(--el-color-danger) !important;
}

.commits code {
  color: var(--el-text-color-secondary);
  font-size: 11px;
  flex-shrink: 0;
}

/* the UA stylesheet underlines the anchor itself, and a decoration set on the
   ancestor is painted over every inline descendant - so it has to be cleared
   on the anchor, not on the code inside it */
a.commit-id {
  text-decoration: none;
}

a.commit-id:hover code {
  text-decoration: underline;
}

.commit-body {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
}

.commits .subject {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: default;
}

.commit-meta {
  font-size: 11px;
  color: var(--el-text-color-secondary);
}

.truncated {
  margin: 4px 0 0;
  color: var(--el-text-color-secondary);
  font-style: italic;
}
</style>
