<template>
  <el-drawer
    :model-value="visible"
    size="640px"
    :with-header="false"
    append-to-body
    @update:model-value="emit('update:visible', $event)"
  >
    <div v-if="row" class="drawer-body">
      <!-- What this drawer is about: the package, and what kind of row it is. -->
      <header class="drawer-head">
        <h3 class="drawer-name" data-test="drawer-name">{{ row.name }}</h3>
        <el-tag v-if="row.kind === 'application'" size="small" type="primary">
          {{ t('appDiff.application') }}
        </el-tag>
      </header>

      <!-- The version timeline: one node per release, and every edge between two
           releases is the pair whose commits can be read. An edge the row has no
           comparison for is drawn but not clickable - it says so on hover. -->
      <div class="timeline" data-test="drawer-timeline">
        <template v-for="(boundary, index) in boundaries" :key="boundary.key">
          <span class="tl-node">
            <span class="tl-dot" :class="{ gap: !boundary.from.hasRecord }" />
            <span class="tl-version" :title="boundary.from.ref">
              {{ boundary.from.version ?? '—' }}
            </span>
          </span>
          <button
            class="tl-edge"
            :class="{ active: boundary.key === selectedKey, dim: !boundary.entry }"
            :disabled="!boundary.entry"
            :data-test="`drawer-edge-${index}`"
            :title="boundary.entry ? boundary.entry.label : t('appDiff.drawer_no_comparison')"
            @click="boundary.entry && select(boundary.key)"
          >
            <el-icon><ArrowRight /></el-icon>
          </button>
        </template>
        <span v-if="cells.length" class="tl-node">
          <span class="tl-dot" :class="{ gap: !cells[cells.length - 1].hasRecord }" />
          <span class="tl-version" :title="cells[cells.length - 1].ref">
            {{ cells[cells.length - 1].version ?? '—' }}
          </span>
        </span>
      </div>

      <!-- The pair the timeline points at, read in two columns: what the later
           version gained on the left, what it does not hold on the right. -->
      <template v-if="selectedEntry">
        <p class="drawer-pair" data-test="drawer-pair">{{ selectedEntry.label }}</p>

        <p v-if="selectedEntry.code.deferred" class="drawer-note" :data-test="`${scope}-deferred`">
          {{ t('appDiff.code_deferred') }}
        </p>
        <p
          v-else-if="selectedEntry.code.unavailable"
          class="drawer-note"
          :data-test="`${scope}-unavailable`"
        >
          {{ t('appDiff.code_unavailable', { reason: selectedEntry.code.unavailable }) }}
        </p>

        <template v-else>
          <p class="drawer-counts" :data-test="`${scope}-counts`">
            <el-tag
              size="small"
              effect="plain"
              :type="verdictType"
              :data-test="`${scope}-verdict`"
            >
              {{ t(`appDiff.code_verdict_${selectedEntry.code.verdict}`) }}
            </el-tag>
            <span :class="`count-${tone}`">
              {{ t('appDiff.code_added', { count: selectedEntry.code.added_count }) }}
            </span>
            <span v-if="selectedEntry.code.missing_count" class="count-missing">
              · {{ t('appDiff.code_missing', { count: selectedEntry.code.missing_count }) }}
            </span>
          </p>

          <div class="commit-columns">
            <section class="commit-col" :data-test="`${scope}-added`">
              <h4>
                <span class="col-dot col-added" />
                {{ t('appDiff.code_added_heading') }} ({{ selectedEntry.code.added_commits.length }})
              </h4>
              <ul>
                <li
                  v-for="commit in selectedEntry.code.added_commits"
                  :key="commit.id"
                  class="commit-card"
                >
                  <CommitCard :commit="commit" />
                </li>
              </ul>
              <p
                v-if="!selectedEntry.code.added_commits.length"
                class="col-empty"
              >
                {{ t('appDiff.drawer_empty') }}
              </p>
            </section>

            <section
              class="commit-col"
              :class="{ alerted: hasMissing }"
              :data-test="`${scope}-missing`"
            >
              <h4 class="missing-heading">
                <el-icon><WarningFilled /></el-icon>
                {{ t('appDiff.code_missing_heading') }} ({{
                  selectedEntry.code.missing_commits.length
                }})
              </h4>
              <ul>
                <li
                  v-for="commit in selectedEntry.code.missing_commits"
                  :key="commit.id"
                  class="commit-card missing"
                >
                  <CommitCard :commit="commit" missing />
                </li>
              </ul>
              <p
                v-if="!selectedEntry.code.missing_commits.length"
                class="col-empty"
              >
                {{ t('appDiff.drawer_empty') }}
              </p>
            </section>
          </div>

          <p v-if="selectedEntry.code.truncated" class="drawer-note" :data-test="`${scope}-truncated`">
            {{ t('appDiff.code_truncated') }}
          </p>
        </template>
      </template>
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ArrowRight, WarningFilled } from '@element-plus/icons-vue'
import CommitCard from './CommitDiffCard.vue'
import type { AppVersionDiffCode } from '@/api/appVersionDiff'
import type { AppDiffCell, AppDiffRow } from '@/utils/appVersionDiff'
import { codeTone } from '@/utils/appVersionDiff'

/**
 * The drawer a matrix row opens: the row's version timeline on top, and the
 * selected pair's commit comparison read side by side below it.
 *
 * One entry per pair the row appears in, keyed by the same interval refs the
 * timeline edges carry, so a click on an edge is the comparison it names.
 */
const props = defineProps<{
  visible: boolean
  row: AppDiffRow | null
  entries: { key: string; label: string; code: AppVersionDiffCode }[]
}>()

const emit = defineEmits<{ 'update:visible': [value: boolean] }>()

const { t } = useI18n()

const scope = computed(() => `drawer-${props.row?.name ?? 'row'}`)

interface Boundary {
  key: string
  from: AppDiffCell
  entry: { key: string; label: string; code: AppVersionDiffCode } | undefined
}

const cells = computed(() => props.row?.cells ?? [])

const boundaries = computed<Boundary[]>(() =>
  cells.value.slice(0, -1).map((cell, index) => ({
    key: `${cell.ref}->${cells.value[index + 1].ref}`,
    from: cell,
    entry: props.entries.find((entry) => entry.key === `${cell.ref}->${cells.value[index + 1].ref}`),
  })),
)

const selectedKey = ref<string | null>(null)

// Opening the drawer lands on its first readable pair; reopening another row
// does the same instead of remembering the last selection's key.
watch(
  () => [props.visible, props.row?.name] as const,
  ([visible]) => {
    if (visible) {
      selectedKey.value = boundaries.value.find((boundary) => boundary.entry)?.key ?? null
    }
  },
)

function select(key: string) {
  selectedKey.value = key
}

const selectedEntry = computed(
  () => props.entries.find((entry) => entry.key === selectedKey.value) ?? null,
)

const tone = computed(() => (selectedEntry.value ? codeTone(selectedEntry.value.code) : 'none'))
// A pair that does not hold what it should is the reading that asks for action,
// so its column wears the warning instead of sitting beside the added one.
const hasMissing = computed(
  () => selectedEntry.value !== null && selectedEntry.value.code.missing_count > 0,
)
const verdictType = computed<'success' | 'danger' | 'info'>(() => {
  if (!selectedEntry.value) return 'info'
  if (selectedEntry.value.code.verdict === 'contained') return 'success'
  return selectedEntry.value.code.verdict === 'missing' ? 'danger' : 'info'
})
</script>

<style scoped>
.drawer-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.drawer-head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.drawer-name {
  margin: 0;
  font-size: 16px;
}

/* The timeline: nodes are the versions the row carried, edges are the pairs. */
.timeline {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 2px;
  padding: 8px 10px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  background: var(--el-fill-color-lighter);
}

.tl-node {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.tl-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--el-color-primary);
}

/* a release with no record has no version to pin: its node reads as a gap */
.tl-dot.gap {
  background: var(--el-fill-color-dark);
  border: 1px dashed var(--el-border-color);
}

.tl-version {
  font-size: 13px;
  font-weight: 600;
  font-family: var(--el-font-family, sans-serif);
}

.tl-edge {
  display: inline-flex;
  align-items: center;
  padding: 2px 6px;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: var(--el-text-color-secondary);
  cursor: pointer;
}

.tl-edge:not(:disabled):hover {
  background: var(--el-fill-color);
  color: var(--el-color-primary);
}

.tl-edge.active {
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
  font-weight: 700;
}

/* an edge without a comparison is drawn, but cannot be walked */
.tl-edge:disabled {
  cursor: not-allowed;
  opacity: 0.4;
}

.drawer-pair {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.drawer-note {
  margin: 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  font-style: italic;
}

.drawer-counts {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0;
  font-size: 12px;
}

.drawer-counts .count-green {
  color: var(--diff-ink-green);
  font-weight: 600;
}

.drawer-counts .count-red {
  color: var(--diff-ink-red);
  font-weight: 600;
}

.drawer-counts .count-missing {
  color: var(--el-color-danger);
  font-weight: 600;
}

/* Two columns, side by side: gained on the left, not held on the right. */
.commit-columns {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.commit-col {
  min-width: 0;
}

.commit-col h4 {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0 0 6px;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--el-text-color-secondary);
}

.col-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.col-added {
  background: var(--diff-ink-green);
}

/* The Not contained heading is the alarm: red, bold, before it is read. The
   selector outranks `.commit-col h4`, whose grey would otherwise win. */
.commit-col h4.missing-heading {
  color: var(--el-color-danger);
  font-weight: 700;
}

/* A pair that does not hold what it should gets a whole-column border and tint
   (theme-aware diff tokens), so the box itself announces the problem. */
.commit-col.alerted {
  padding: 8px;
  border: 1px solid color-mix(in srgb, var(--el-color-danger) 45%, transparent);
  border-radius: 8px;
  background: var(--diff-fill-red);
}

.commit-col ul {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.col-empty {
  margin: 0;
  font-size: 12px;
  color: var(--el-text-color-placeholder);
  font-style: italic;
}
</style>
