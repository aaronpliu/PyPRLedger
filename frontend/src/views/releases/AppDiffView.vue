<template>
  <div class="page app-diff">
    <header class="page-header">
      <div class="header-start">
        <h1>{{ t('appDiff.title') }}</h1>
        <p v-if="appName && releases.length" class="subtitle" data-test="subtitle">
          {{ t('appDiff.subtitle', { app: appName, count: releases.length }) }}
        </p>
      </div>
      <div class="header-end">
        <el-button
          :disabled="!canCompare"
          :loading="comparing"
          data-test="refresh"
          @click="refresh"
        >
          {{ t('appDiff.refresh') }}
        </el-button>
      </div>
    </header>

    <!-- The same coordinates the repository comparison and the dependency graph
         ask for: the application is resolved from the repository, so the reader
         picks a repository and the rest follows. -->
    <el-form class="coordinates" :model="repo" label-width="130px">
      <el-row :gutter="16">
        <el-col :xs="24" :sm="12" :md="5">
          <el-form-item :label="t('releaseDiff.project_key')" required>
            <el-select
              v-model="repo.project_key"
              filterable
              clearable
              allow-create
              :loading="projectsLoading"
              :placeholder="t('releaseDiff.select_project')"
              style="width: 100%"
              data-test="project-select"
            >
              <el-option
                v-for="project in projects"
                :key="project.project_key"
                :label="project.project_key"
                :value="project.project_key"
              >
                <span class="option-key">{{ project.project_key }}</span>
                <span
                  v-if="secondaryName(project.project_key, project.project_name)"
                  class="option-name"
                >
                  {{ project.project_name }}
                </span>
              </el-option>
            </el-select>
          </el-form-item>
        </el-col>

        <el-col :xs="24" :sm="12" :md="5">
          <el-form-item :label="t('releaseDiff.repository_slug')" required>
            <el-select
              v-model="repo.repository_slug"
              filterable
              clearable
              allow-create
              :disabled="!repo.project_key"
              :loading="repositoriesLoading"
              :placeholder="t('releaseDiff.select_repository')"
              style="width: 100%"
              data-test="repository-select"
            >
              <el-option
                v-for="repository in repositories"
                :key="repository.repository_slug"
                :label="repository.repository_slug"
                :value="repository.repository_slug"
              >
                <span class="option-key">{{ repository.repository_slug }}</span>
                <span
                  v-if="secondaryName(repository.repository_slug, repository.repository_name)"
                  class="option-name"
                >
                  {{ repository.repository_name }}
                </span>
              </el-option>
            </el-select>
          </el-form-item>
        </el-col>

        <el-col v-if="isCloudProvider" :xs="24" :sm="12" :md="3">
          <el-form-item :label="t('releaseDiff.workspace_slug')">
            <el-select
              v-model="repo.workspace_slug"
              filterable
              clearable
              allow-create
              default-first-option
              :loading="workspacesLoading"
              :placeholder="t('releaseDiff.workspace_slug_placeholder')"
              style="width: 100%"
            >
              <el-option
                v-for="workspace in cloudWorkspaces"
                :key="workspace.slug"
                :label="workspace.slug"
                :value="workspace.slug"
              />
            </el-select>
          </el-form-item>
        </el-col>

        <el-col :xs="24" :sm="12" :md="6">
          <el-form-item :label="t('appDiff.releases_label')" required>
            <el-select
              v-model="selectedRefs"
              multiple
              filterable
              remote
              default-first-option
              :remote-method="onRefSearch"
              :disabled="!hasCoordinates"
              :loading="refsLoading"
              :placeholder="t('appDiff.select_releases')"
              style="width: 100%"
              data-test="releases-select"
              @visible-change="onRefVisibility"
            >
              <el-option-group v-if="visibleTags.length" :label="t('appDiff.tags_group')">
                <el-option
                  v-for="tag in visibleTags"
                  :key="`tag:${tag}`"
                  :label="tag"
                  :value="tag"
                />
              </el-option-group>
              <el-option-group v-if="visibleBranches.length" :label="t('appDiff.branches_group')">
                <el-option
                  v-for="branch in visibleBranches"
                  :key="`branch:${branch}`"
                  :label="branch"
                  :value="branch"
                />
              </el-option-group>
              <!-- A release the repository does not report is not offered, and only
                   an offered release can be picked: a comparison needs releases that
                   exist. -->
              <template #empty>
                <p class="ref-empty">{{ t('appDiff.ref_no_match') }}</p>
              </template>
            </el-select>
          </el-form-item>
        </el-col>

        <!-- How deep this comparison reads, in the same row as the choices it is about:
             the numbers behind each depth belong to the server, which clamps them to
             its own ceilings and reports what it actually read, so this is a preference
             rather than a promise - and one a reader can keep, since the same releases
             are usually compared over and over. -->
        <el-col :xs="24" :sm="12" :md="5">
          <el-form-item :label="t('appDiff.depth_label')">
            <div class="depth">
              <el-select v-model="depth" class="depth-select" data-test="depth-select">
                <el-option
                  v-for="choice in DEPTHS"
                  :key="choice"
                  :label="t(`appDiff.depth_${choice}`)"
                  :value="choice"
                >
                  <span class="option-key">{{ t(`appDiff.depth_${choice}`) }}</span>
                  <span v-if="depthNumbers(choice)" class="option-name">
                    {{ depthNumbers(choice) }}
                  </span>
                </el-option>
              </el-select>
              <el-checkbox v-model="remembered" data-test="depth-remember">
                {{ t('appDiff.depth_remember') }}
              </el-checkbox>
            </div>
          </el-form-item>
        </el-col>
      </el-row>
    </el-form>

    <!-- Reading a repository's refs is a provider call, and nothing else on the page
         moves while it is in flight: saying so is what keeps the wait from reading as
         a page that did nothing at all. -->
    <p v-if="refsLoading" class="refs-note" data-test="refs-loading">
      <el-icon class="is-loading"><Loading /></el-icon>
      {{ t('appDiff.reading_refs') }}
    </p>

    <!-- The picker offers the recent releases and searches the rest, so it says
         which of the two it is doing rather than leaving a short list to look like
         a short repository. -->
    <p v-else-if="refsCapped" class="refs-note" data-test="refs-capped">
      {{ t('appDiff.refs_capped', { loaded: loadedRefCount, total: totalRefCount }) }}
    </p>
    <p v-else-if="refsSearchable" class="refs-note" data-test="refs-searchable">
      {{ t('appDiff.refs_searchable', { total: totalRefCount }) }}
    </p>

    <el-empty v-if="!hasCoordinates" :description="t('appDiff.pick_repository')" />

    <el-empty
      v-else-if="selectedRefs.length < 2"
      :description="t('appDiff.pick_releases')"
      data-test="need-two"
    />

    <ContentLoader
      v-else-if="comparing"
      :rows="8"
      :label="t('appDiff.loading')"
      min-height="360px"
    />

    <!-- A source that could not be read is reported, never shown as "nothing
         changed": an empty matrix would say exactly that. -->
    <el-alert
      v-else-if="failed"
      type="error"
      :closable="false"
      :title="t('appDiff.failed_title')"
      :description="t('appDiff.failed_hint')"
      data-test="failed"
    />

    <template v-else-if="result">
      <div class="verdict" data-test="verdict-row">
        <el-tag :type="verdictType" effect="dark" data-test="verdict">
          {{ t(`appDiff.verdict_${result.verdict}`) }}
        </el-tag>
        <span class="scope" data-test="scope">{{ t('appDiff.scope') }}</span>
      </div>

      <el-alert
        v-if="hasIncomplete"
        type="warning"
        :closable="false"
        :title="t('appDiff.incomplete_title')"
        :description="t('appDiff.incomplete_hint')"
        data-test="incomplete"
      />

      <!-- The matrix first: it is the whole comparison at a glance - every package
           against every release - and it is what the details below are read against.
           A page of pair-by-pair details used to sit above it and push it off the
           screen the moment a comparison had more than one pair. -->
      <el-empty v-if="!rows.length" :description="t('appDiff.no_records')" data-test="no-records" />

      <div v-else class="matrix-wrap">
        <table class="matrix" data-test="matrix">
          <thead>
            <tr>
              <th class="package-col" scope="col">{{ t('appDiff.package') }}</th>
              <th
                v-for="release in releases"
                :key="release.ref"
                scope="col"
                :class="{ 'col-missing': !release.has_record }"
              >
                <span class="release-ref">{{ release.ref }}</span>
                <span class="release-date">
                  {{ release.released_at || t('appDiff.no_date') }}
                </span>
                <el-tag
                  v-if="!release.has_record"
                  size="small"
                  type="info"
                  data-test="column-missing"
                >
                  {{ t('appDiff.no_record') }}
                </el-tag>
              </th>
            </tr>
          </thead>
          <tbody>
            <!-- A row is a package (the application's own version first). The whole
                 row carries the RAG status of its commits, and opening it reveals the
                 commit comparison in place - the diff info is the row's, not a list
                 of its own below the table. -->
            <template v-for="row in rows" :key="`${row.kind}:${row.name}`">
              <tr
                :class="[
                  'matrix-row',
                  rowRagClass(row),
                  { 'row-application': row.kind === 'application', toggleable: rowCodes(row).length > 0 },
                ]"
                :data-test="`matrix-row-${row.name}`"
                @click="toggleRow(rowKey(row))"
              >
                <th class="package-col" scope="row">
                  <span
                    v-if="rowCodes(row).length > 0"
                    class="row-chevron"
                    :class="{ open: isRowExpanded(rowKey(row)) }"
                    aria-hidden="true"
                    >▸</span
                  >
                  <span class="package-name">{{ row.name }}</span>
                  <!-- the application's own version is a row like the others, and
                       is marked so it does not read as one of its dependencies -->
                  <el-tag
                    v-if="row.kind === 'application'"
                    class="kind"
                    size="small"
                    type="primary"
                    data-test="application-row"
                  >
                    {{ t('appDiff.application') }}
                  </el-tag>
                </th>
                <td
                  v-for="(cell, index) in row.cells"
                  :key="`${row.name}:${cell.ref}`"
                  :class="cellClass(cell)"
                  :data-test="`cell-${row.name}-${index}`"
                >
                  <span
                    v-if="isMarked(cell.move)"
                    class="move"
                    :class="`move-${moveTone(cell.move)}`"
                    :title="t(moveLabelKey(moveTone(cell.move)))"
                    data-test="move"
                  >
                    {{ moveSymbol(moveTone(cell.move)) }}
                  </span>
                  <span class="version" :class="versionClass(cell)">{{ cellText(cell) }}</span>
                  <span v-if="isRisk(cell.move)" class="risk" data-test="risk">
                    {{ t('appDiff.risk') }}
                  </span>
                </td>
              </tr>

              <!-- The diff info for this row, one comparison per pair it moved in. -->
              <tr
                v-if="isRowExpanded(rowKey(row)) && rowCodes(row).length"
                class="row-detail"
                :data-test="`matrix-detail-${row.name}`"
              >
                <td :colspan="releases.length + 1">
                  <CommitComparison
                    v-for="entry in rowCodes(row)"
                    :key="entry.key"
                    :code="entry.code"
                    :scope="`matrix-${row.name}`"
                    :expanded="isExpanded(commitKey(row, entry.key))"
                    @toggle="toggleCommits(commitKey(row, entry.key))"
                  >
                    <template #note>
                      <p class="detail-pair">{{ entry.label }}</p>
                    </template>
                  </CommitComparison>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>

      <!-- A pair that moved dozens of packages is drawn from its first few
           comparisons while the rest are read behind it, and what is still unread
           says so rather than reading as a package that was checked. -->
      <p
        v-if="deferredTotal && (autoCompareRunning || pendingPackages)"
        class="refs-note"
        data-test="packages-pending"
      >
        {{
          autoCompareRunning
            ? t('appDiff.packages_progress', { done: deferredDone, total: deferredTotal })
            : t('appDiff.packages_left', { count: pendingPackages })
        }}
      </p>
      <el-button
        v-if="!autoCompareRunning && pendingPackages"
        class="packages-action"
        size="small"
        data-test="packages-read-rest"
        @click="readRemainingPackages"
      >
        {{ t('appDiff.packages_read_rest', { count: pendingPackages }) }}
      </el-button>

    </template>

    <el-empty v-else :description="t('appDiff.no_result')" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Loading } from '@element-plus/icons-vue'
import ContentLoader from '@/components/common/ContentLoader.vue'
import CommitComparison from '@/components/release/CommitComparison.vue'
import { projectsApi } from '@/api/projects'
import type {
  CloudWorkspaceOption,
  ProjectSummary,
  RepositorySummary,
} from '@/api/projects'
import { releaseDiffApi } from '@/api/releaseDiff'
import { appVersionDiffApi } from '@/api/appVersionDiff'
import type {
  AppVersionDiffCode,
  AppVersionDiffInterval,
  AppVersionDiffPackageComparison,
  AppVersionDiffResponse,
} from '@/api/appVersionDiff'
import { useRefCandidates } from '@/composables/useRefCandidates'
import { DEPTHS, depthNumbers, useAppDiffDepth } from '@/composables/useAppDiffDepth'
import {
  buildRows,
  isMarked,
  isRisk,
  moveLabelKey,
  moveSymbol,
  moveTone,
  ragTone,
} from '@/utils/appVersionDiff'
import type { AppDiffCell, AppDiffRow } from '@/utils/appVersionDiff'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const repo = ref({
  project_key: '',
  repository_slug: '',
  git_provider: null as string | null,
  workspace_slug: '',
})

const projects = ref<ProjectSummary[]>([])
const repositories = ref<RepositorySummary[]>([])
const cloudWorkspaces = ref<CloudWorkspaceOption[]>([])
const projectsLoading = ref(false)
const repositoriesLoading = ref(false)
const workspacesLoading = ref(false)
const workspacesLoaded = ref(false)
const refsLoading = ref(false)
// The provider's whole listing, searched, with the recent releases offered up front
const {
  search: refSearch,
  visibleTags,
  visibleBranches,
  loadedCount: loadedRefCount,
  totalCount: totalRefCount,
  capped: refsCapped,
  searchable: refsSearchable,
  setCandidates: setRefCandidates,
  clearCandidates: clearRefCandidates,
} = useRefCandidates()

/** What the reader typed: it searches the whole listing, not the offered page. */
function onRefSearch(query: string) {
  refSearch.value = query ?? ''
}

/** A picker that has just closed goes back to offering the recent releases. */
function onRefVisibility(visible: boolean) {
  if (!visible) {
    refSearch.value = ''
  }
}

const selectedRefs = ref<string[]>([])
const comparing = ref(false)
const failed = ref(false)
const result = ref<AppVersionDiffResponse | null>(null)
// How deep a comparison reads, and whether the reader keeps that choice. The
// numbers behind each depth are the server's to grant: it clamps them to its own
// ceilings and the answer says what was actually read.
const { depth, remembered, depthRequest } = useAppDiffDepth()
// The first response answers each pair with its first few package comparisons; the
// rest are read behind it, so a release that moved dozens of packages is drawn
// without waiting for every one of them.
const autoCompareRunning = ref(false)
const autoComparePaused = ref(false)
const deferredTotal = ref(0)
// Every read belongs to one comparison: a result cleared, or a comparison started
// again, leaves the batches of the previous one with nowhere to land.
let compareRun = 0
// Refs a URL asked for, held until the ref list arrives so the picker does not
// overwrite them.
const requestedRefs = ref<string[] | null>(null)

const selectedProjectKey = computed(() => (repo.value.project_key ?? '').trim())
const selectedRepositorySlug = computed(() => (repo.value.repository_slug ?? '').trim())
const isCloudProvider = computed(() => repo.value.git_provider === 'bitbucket_cloud')
const selectedWorkspaceSlug = computed(() =>
  isCloudProvider.value ? (repo.value.workspace_slug ?? '').trim() : '',
)
const hasCoordinates = computed(
  () => Boolean(selectedProjectKey.value) && Boolean(selectedRepositorySlug.value),
)

const appName = computed(() => result.value?.app_name ?? '')
const releases = computed(() => result.value?.releases ?? [])
const intervals = computed(() => result.value?.intervals ?? [])
const rows = computed<AppDiffRow[]>(() => (result.value ? buildRows(result.value) : []))
const hasIncomplete = computed(() => result.value?.verdict === 'incomplete')
const canCompare = computed(() => hasCoordinates.value && selectedRefs.value.length >= 2)

const verdictType = computed<'success' | 'warning' | 'info'>(() => {
  if (result.value?.verdict === 'identical') return 'success'
  if (result.value?.verdict === 'changed') return 'warning'
  return 'info'
})

function coordinates() {
  return {
    project_key: selectedProjectKey.value,
    repository_slug: selectedRepositorySlug.value,
    // derived rather than chosen: the registry decides where a repository lives, and
    // this stands only for one it says nothing about
    git_provider: repo.value.git_provider || undefined,
    workspace_slug: selectedWorkspaceSlug.value || undefined,
  }
}

/** A key reads better with the name the provider holds beside it. */
function secondaryName(value: string, name?: string | null): string | undefined {
  return name && name !== value ? name : undefined
}

async function loadProjects() {
  projectsLoading.value = true
  try {
    projects.value = await projectsApi.getAllProjects()
  } catch {
    projects.value = []
  } finally {
    projectsLoading.value = false
  }
}

async function loadRepositories(projectKey: string) {
  repositories.value = []
  if (!projectKey) return

  repositoriesLoading.value = true
  try {
    // The applications the project registry names - this page reads the releases the
    // dependency database holds, and a repository marked as a package has none to
    // read. A project nobody has classified falls back to every repository it has,
    // so nothing disappears before an administrator has said what things are.
    repositories.value = await projectsApi.getProjectRepositories(projectKey, {
      preferApplications: true,
    })
  } catch {
    repositories.value = []
  } finally {
    repositoriesLoading.value = false
  }
}

async function ensureWorkspaceSuggestions() {
  if (workspacesLoaded.value) return
  workspacesLoading.value = true
  try {
    cloudWorkspaces.value = await projectsApi.getCloudWorkspaces()
  } catch {
    cloudWorkspaces.value = []
  } finally {
    workspacesLoading.value = false
    workspacesLoaded.value = true
  }
  if (!repo.value.workspace_slug && cloudWorkspaces.value.length === 1) {
    repo.value.workspace_slug = cloudWorkspaces.value[0].slug
  }
}

/**
 * Read the repository's refs as the picker's candidate set.
 *
 * No `limit` is sent: the API answers with the repository's whole listing (up to
 * its safety ceiling) because a release the picker never received is one the
 * reader cannot choose.
 */
async function loadRefs() {
  clearRefCandidates()
  if (!hasCoordinates.value) return

  refsLoading.value = true
  try {
    const response = await releaseDiffApi.listRefs(coordinates())
    setRefCandidates(response)
    // A link that names its releases still opens on them. Otherwise nothing is
    // picked for the reader: the comparison runs when they choose the releases.
    const wanted = requestedRefs.value
    requestedRefs.value = null
    if (!wanted?.length) {
      selectedRefs.value = []
    } else if (wanted.join(',') !== selectedRefs.value.join(',')) {
      // The link's releases are already picked - they were taken from it before this
      // listing was read, which is what started their comparison. Picking them again
      // here would read the same two releases a second time, and start a second round
      // of the package comparisons that follow one.
      selectedRefs.value = wanted
    }
  } catch {
    // Left empty: the picker stays empty and the page waits for a repository
    // whose refs can be read.
  } finally {
    refsLoading.value = false
  }
}

/** Compare the selected releases, optionally reading past the cache. */
async function compare(refresh = false) {
  if (!canCompare.value) return

  // A comparison started again cancels the batches of the one before it.
  const run = ++compareRun
  autoCompareRunning.value = false
  autoComparePaused.value = false
  deferredTotal.value = 0
  comparing.value = true
  failed.value = false
  try {
    const response = await appVersionDiffApi.compare({
      ...coordinates(),
      refs: [...selectedRefs.value],
      refresh,
      // how deep this reader wants to read, within what the server will grant
      ...depthRequest(),
    })
    if (run !== compareRun) return
    result.value = response
    deferredTotal.value = countDeferred(response.intervals)
    if (deferredTotal.value) void readDeferredPackages(run)
  } catch {
    if (run !== compareRun) return
    // The failure is reported rather than emptied: an empty matrix would read as
    // a comparison in which nothing moved.
    result.value = null
    failed.value = true
  } finally {
    if (run === compareRun) comparing.value = false
  }
}

function refresh() {
  void compare(true)
}

/** How many of one pair's package comparisons are still waiting to be read. */
function pendingOf(interval: AppVersionDiffInterval): number {
  return interval.packages.filter((entry) => entry.code.deferred).length
}

/** How many package comparisons a set of pairs is leaving for later. */
function countDeferred(list: AppVersionDiffInterval[]): number {
  return list.reduce((count, interval) => count + pendingOf(interval), 0)
}

/** How many package comparisons are still waiting to be read. */
const pendingPackages = computed(() => countDeferred(intervals.value))

/** How many of the deferred ones have been read since the page was drawn. */
const deferredDone = computed(() => Math.max(deferredTotal.value - pendingPackages.value, 0))

/** Stop reading whatever batches are in flight: their answer is no longer wanted. */
function cancelPackageReads() {
  compareRun += 1
  autoCompareRunning.value = false
  autoComparePaused.value = false
  deferredTotal.value = 0
}

/** Put the answers where their entries were, so a row stops saying "not compared yet". */
function mergeComparisons(
  interval: AppVersionDiffInterval,
  answered: AppVersionDiffPackageComparison[],
) {
  const byName = new Map(answered.map((entry) => [entry.name, entry]))
  interval.packages = interval.packages.map((entry) => byName.get(entry.name) ?? entry)
}

/**
 * Read the package comparisons the first response deferred.
 *
 * The response answers each pair with its first few packages so the page can be
 * drawn without waiting for all of them; the rest are asked for here, a batch at a
 * time, until nothing is left. The allowance the response carries bounds what the
 * page reads on its own - a reader who asks by hand is not bounded by it, because
 * it exists to keep the page from reading without end, not to stop the person
 * looking at it.
 */
async function readDeferredPackages(run: number, manual = false) {
  const response = result.value
  if (!response) return

  // How much of the allowance is left, and how many packages one batch carries: both
  // are the server's numbers, sent with the answer, so the page paces itself by what
  // this deployment does rather than by what a page was compiled with.
  let allowance = manual ? Number.POSITIVE_INFINITY : response.package_comparisons.remaining
  const batchSize = Math.max(response.package_comparisons.batch, 1)
  autoCompareRunning.value = true
  autoComparePaused.value = false
  try {
    for (const interval of response.intervals) {
      if (run !== compareRun) return
      const waiting = interval.packages.filter((entry) => entry.code.deferred)
      while (waiting.length && allowance > 0) {
        const batch = waiting.splice(0, Math.min(batchSize, allowance))
        allowance -= batch.length
        let answer
        try {
          answer = await appVersionDiffApi.comparePackages({
            ...coordinates(),
            source_ref: interval.source_ref,
            target_ref: interval.target_ref,
            packages: batch.map((entry) => ({
              name: entry.name,
              source_version: entry.source_version ?? '',
              target_version: entry.target_version ?? '',
            })),
          })
        } catch {
          // A batch that could not be read leaves its packages as they were: still
          // visibly unread, and askable again - never shown as compared, and never
          // as a package that contained nothing.
          if (run === compareRun) autoComparePaused.value = true
          return
        }
        if (run !== compareRun) return
        mergeComparisons(interval, answer.packages)
      }
    }
  } finally {
    if (run === compareRun) {
      autoCompareRunning.value = false
      autoComparePaused.value = pendingPackages.value > 0
    }
  }
}

/** Ask for the packages the automatic read did not get to. */
function readRemainingPackages() {
  void readDeferredPackages(compareRun, true)
}

function cellText(cell: AppDiffCell): string {
  if (!cell.hasRecord) return '?'
  return cell.version ?? '—'
}

function cellClass(cell: AppDiffCell) {
  return [
    `cell-${moveTone(cell.move)}`,
    { 'col-missing': !cell.hasRecord, 'cell-absent': cell.hasRecord && !cell.version },
  ]
}

function versionClass(cell: AppDiffCell) {
  return { unknown: !cell.hasRecord, absent: cell.hasRecord && !cell.version }
}

/** A pair's identity, for the commit lists a reader opens by hand. */
function intervalKey(interval: { source_ref: string; target_ref: string }): string {
  return `${interval.source_ref}->${interval.target_ref}`
}

/** The comparison of one matrix row within one pair, or nothing where there is none. */
function rowCode(row: AppDiffRow, interval: AppVersionDiffInterval): AppVersionDiffCode | null {
  if (row.kind === 'application') return interval.code
  return interval.packages.find((entry) => entry.name === row.name)?.code ?? null
}

/** Every pair's comparison for one row, labelled by the pair it sits between. */
function rowCodes(row: AppDiffRow): { key: string; label: string; code: AppVersionDiffCode }[] {
  return (result.value?.intervals ?? []).flatMap((interval) => {
    const code = rowCode(row, interval)
    if (!code) return []
    return [
      {
        key: intervalKey(interval),
        label: `${interval.source_ref} → ${interval.target_ref}`,
        code,
      },
    ]
  })
}

/** The identity a row's own detail is held under. */
function rowKey(row: AppDiffRow): string {
  return `${row.kind}:${row.name}`
}

const expandedRows = ref<string[]>([])

function isRowExpanded(key: string): boolean {
  return expandedRows.value.includes(key)
}

function toggleRow(key: string) {
  expandedRows.value = isRowExpanded(key)
    ? expandedRows.value.filter((item) => item !== key)
    : [...expandedRows.value, key]
}

/** The key one commit list of a row's detail is expanded under. */
function commitKey(row: AppDiffRow, intervalKeyValue: string): string {
  return `${row.name}@${intervalKeyValue}`
}

/**
 * The RAG highlight of a whole row, the worst of every pair it appears in: missing
 * commits anywhere read as red, added commits as green, and anything else as amber.
 */
function rowRagClass(row: AppDiffRow): string {
  const tones = rowCodes(row).map((entry) => ragTone(entry.code))
  if (tones.includes('red')) return 'rag-red'
  if (tones.includes('green')) return 'rag-green'
  return tones.length ? 'rag-amber' : ''
}

const expandedCommits = ref<string[]>([])

function isExpanded(key: string): boolean {
  return expandedCommits.value.includes(key)
}

function toggleCommits(key: string) {
  expandedCommits.value = isExpanded(key)
    ? expandedCommits.value.filter((item) => item !== key)
    : [...expandedCommits.value, key]
}

function syncUrl() {
  const query: Record<string, string> = {}
  if (selectedProjectKey.value) query.project_key = selectedProjectKey.value
  if (selectedRepositorySlug.value) query.repository_slug = selectedRepositorySlug.value
  if (repo.value.git_provider) query.git_provider = repo.value.git_provider
  if (selectedWorkspaceSlug.value) query.workspace_slug = selectedWorkspaceSlug.value
  if (selectedRefs.value.length) query.refs = selectedRefs.value.join(',')
  void router.replace({ query })
}

/** Take the coordinates and releases a link carried, so a comparison is shareable. */
function readUrl() {
  const query = route.query
  const text = (value: unknown): string => (typeof value === 'string' ? value.trim() : '')

  repo.value.project_key = text(query.project_key)
  repo.value.repository_slug = text(query.repository_slug)
  repo.value.git_provider = text(query.git_provider) || null
  repo.value.workspace_slug = text(query.workspace_slug)

  const refs = text(query.refs)
    .split(',')
    .map((ref) => ref.trim())
    .filter(Boolean)
  requestedRefs.value = refs.length ? refs : null
  selectedRefs.value = refs
}

// A link's coordinates are applied without the watchers a reader's own pick
// would drive: restoring a comparison must not clear what it just restored.
const restoring = ref(false)

onMounted(async () => {
  restoring.value = true
  try {
    readUrl()
    await loadProjects()
    if (repo.value.project_key && repo.value.repository_slug) {
      await loadRepositories(selectedProjectKey.value)
      if (isCloudProvider.value) void ensureWorkspaceSuggestions()
      await loadRefs()
    }
  } finally {
    restoring.value = false
  }
})

// Leaving the page ends the reads it started: a batch landing afterwards has
// nowhere to be shown, and no reader waiting for it.
onUnmounted(cancelPackageReads)

// The project catalog carries the provider each repository lives on, so picking
// a project fills it in - the reader never has to know which one it is.
watch(selectedProjectKey, async (projectKey) => {
  if (restoring.value) return

  const project = projects.value.find((item) => item.project_key === projectKey)

  repo.value.repository_slug = ''
  if (!repo.value.git_provider) {
    repo.value.git_provider = project?.git_provider || null
  }
  clearRefCandidates()
  result.value = null
  cancelPackageReads()

  // Unknown project keys (typed manually) have no local repository catalog
  if (project) {
    await loadRepositories(projectKey)
  }
  if (isCloudProvider.value) {
    void ensureWorkspaceSuggestions()
  }
})

watch(selectedRepositorySlug, (repositorySlug) => {
  if (restoring.value) return

  result.value = null
  selectedRefs.value = []
  requestedRefs.value = null
  clearRefCandidates()
  cancelPackageReads()
  if (repositorySlug && hasCoordinates.value) void loadRefs()
})

watch(isCloudProvider, (cloud) => {
  if (cloud) void ensureWorkspaceSuggestions()
})

watch([selectedProjectKey, selectedRepositorySlug, selectedRefs], syncUrl)

watch(selectedRefs, (refs) => {
  if (refs.length >= 2 && hasCoordinates.value) void compare()
})

// Asking to read deeper is a different question, so it is answered rather than left
// until the next comparison: what is on screen is read again at the new depth.
watch(depth, () => {
  if (result.value && canCompare.value) void compare()
})
</script>

<style scoped>
.page {
  padding: 20px;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}

.page-header h1 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.subtitle {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.coordinates {
  margin-bottom: 8px;
}

.refs-note {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0 0 12px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

/* The select and the checkbox share the field, and the checkbox drops beneath the
   select rather than squeezing it when the column is narrow. */
.depth {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  width: 100%;
}

/* The depth names are single words, so the control stays narrow enough for the row
   it shares with the other fields */
.depth-select {
  flex: 1 1 120px;
  min-width: 110px;
}

.packages-action {
  margin: 0 0 12px;
}

.ref-empty {
  margin: 0;
  padding: 8px 0;
  text-align: center;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.option-key {
  font-weight: 600;
}

.option-name {
  margin-left: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.verdict {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.scope {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.matrix-wrap {
  overflow-x: auto;
}

.matrix {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.matrix th,
.matrix td {
  border: 1px solid var(--el-border-color-lighter);
  padding: 6px 10px;
  text-align: left;
  white-space: nowrap;
}

.matrix thead th {
  background: var(--el-fill-color-light);
  vertical-align: top;
}

.matrix .release-ref {
  display: block;
  font-weight: 600;
}

.matrix .release-date {
  display: block;
  font-size: 11px;
  font-weight: 400;
  color: var(--el-text-color-secondary);
}

.matrix .package-col {
  position: sticky;
  left: 0;
  background: var(--el-bg-color);
  z-index: 1;
}

.matrix .package-col .kind {
  margin-left: 8px;
  font-weight: 400;
}

.matrix .row-application .package-col {
  font-weight: 700;
}

.matrix thead .package-col {
  background: var(--el-fill-color-light);
}

.col-missing {
  background: repeating-linear-gradient(
    45deg,
    var(--el-fill-color-light),
    var(--el-fill-color-light) 6px,
    transparent 6px,
    transparent 12px
  );
}

.cell-upgrade .move {
  color: var(--el-color-success);
}

.cell-downgrade .move,
.cell-downgrade .risk {
  color: var(--el-color-danger);
}

.cell-added .move {
  color: var(--el-color-success);
}

.cell-removed .move {
  color: var(--el-color-info);
}

.cell-changed .move,
.cell-unknown .move {
  color: var(--el-color-warning);
}

.move {
  display: inline-block;
  width: 14px;
  font-weight: 700;
}

.risk {
  margin-left: 6px;
  font-size: 11px;
  font-weight: 600;
}

.version.unknown {
  color: var(--el-text-color-placeholder);
}

.version.absent {
  color: var(--el-text-color-placeholder);
}

/* The RAG status is a whole-row tint, so a package that lost commits is spotted
   without reading it: red = missing commits, green = new commits, amber = neither. */
/* The RAG status is a whole-row tint that has to stay readable in light and dark
   themes alike, so the fill is mixed from the theme's own colour onto the page
   background, and the package column carries the full-strength colour as a bar. */
.matrix-row.rag-red {
  background: color-mix(in srgb, var(--el-color-danger) 15%, var(--el-bg-color));
}

.matrix-row.rag-green {
  background: color-mix(in srgb, var(--el-color-success) 15%, var(--el-bg-color));
}

.matrix-row.rag-amber {
  background: color-mix(in srgb, var(--el-color-warning) 18%, var(--el-bg-color));
}

/* The package column is sticky, so it paints its own background - carry the row's
   tint onto it and mark it with the full-strength colour, so a red row never
   leaves its name cell white and the status reads at a glance. */
.matrix-row.rag-red .package-col {
  background: color-mix(in srgb, var(--el-color-danger) 15%, var(--el-bg-color));
  box-shadow: inset 3px 0 0 var(--el-color-danger);
}

.matrix-row.rag-green .package-col {
  background: color-mix(in srgb, var(--el-color-success) 15%, var(--el-bg-color));
  box-shadow: inset 3px 0 0 var(--el-color-success);
}

.matrix-row.rag-amber .package-col {
  background: color-mix(in srgb, var(--el-color-warning) 18%, var(--el-bg-color));
  box-shadow: inset 3px 0 0 var(--el-color-warning);
}

/* A row whose commits can be read is the toggle for its own diff detail, and the
   chevron says which way it is folded. */
.matrix-row.toggleable {
  cursor: pointer;
}

.row-chevron {
  display: inline-block;
  width: 0.8em;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  transition: transform 0.15s ease;
}

.row-chevron.open {
  transform: rotate(90deg);
}

/* The diff detail unfolds in place under its row, one comparison per pair. */
.row-detail td {
  padding: 8px 10px 12px;
  background: var(--el-fill-color-lighter);
}

.detail-pair {
  margin: 2px 0 0;
  font-size: 11px;
  color: var(--el-text-color-secondary);
}
</style>
