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

        <el-col :xs="24" :sm="12" :md="4">
          <el-form-item :label="t('releaseDiff.git_provider')">
            <el-select
              v-model="repo.git_provider"
              clearable
              :placeholder="t('releaseDiff.git_provider_placeholder')"
              style="width: 100%"
            >
              <el-option
                v-for="option in GIT_PROVIDER_OPTIONS"
                :key="option.value"
                :label="option.label"
                :value="option.value"
              />
            </el-select>
          </el-form-item>
        </el-col>

        <el-col v-if="isCloudProvider" :xs="24" :sm="12" :md="4">
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
      </el-row>
    </el-form>

    <!-- The picker offers the recent releases and searches the rest, so it says
         which of the two it is doing rather than leaving a short list to look like
         a short repository. -->
    <p v-if="refsCapped" class="refs-note" data-test="refs-capped">
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

      <section v-if="intervals.length" class="intervals" data-test="intervals">
        <article
          v-for="interval in intervals"
          :key="`${interval.source_ref}->${interval.target_ref}`"
          class="interval"
          :class="{ 'interval-incomplete': !interval.complete }"
        >
          <header class="interval-head">
            <span class="ref">{{ interval.source_ref }}</span>
            <span class="arrow" aria-hidden="true">→</span>
            <span class="ref">{{ interval.target_ref }}</span>
          </header>

          <p v-if="!interval.complete" class="interval-unknown" data-test="interval-incomplete">
            {{ t('appDiff.interval_incomplete') }}
          </p>

          <div v-else class="chips">
            <span
              v-for="entry in summaryEntries(interval.summary)"
              :key="entry.state"
              class="chip"
              :class="`chip-${entry.state}`"
            >
              {{ entry.count }} {{ t(`appDiff.state_${entry.state}`) }}
            </span>
            <span
              v-if="!summaryEntries(interval.summary).length"
              class="chip chip-none"
              data-test="interval-unchanged"
            >
              {{ t('appDiff.no_changes') }}
            </span>
            <span
              v-if="downgradeCount(interval.summary)"
              class="chip chip-downgrade"
              data-test="interval-risk"
            >
              {{ t('appDiff.risk_downgrade', { count: downgradeCount(interval.summary) }) }}
            </span>
          </div>

          <!-- The commits between the two releases. A pair whose commits could
               not be read says so: an empty list would read as "none". -->
          <div v-if="interval.code" class="code" data-test="code-axis">
            <p
              v-if="interval.code.unavailable"
              class="code-unavailable"
              data-test="code-unavailable"
            >
              {{ t('appDiff.code_unavailable', { reason: interval.code.unavailable }) }}
            </p>

            <template v-else>
              <p class="code-counts" data-test="code-counts">
                <span :class="`code-${codeTone(interval.code)}`">
                  {{ t('appDiff.code_added', { count: interval.code.added_count }) }}
                </span>
                <span v-if="interval.code.missing_count" data-test="code-missing">
                  · {{ t('appDiff.code_missing', { count: interval.code.missing_count }) }}
                </span>
              </p>

              <p
                v-if="rebuiltWithUnchangedDependencies(interval, interval.code)"
                class="rebuilt"
                data-test="rebuilt"
              >
                {{ t('appDiff.rebuilt') }}
              </p>

              <el-button
                v-if="commitTotal(interval.code)"
                link
                type="primary"
                data-test="code-toggle"
                @click="toggleCommits(intervalKey(interval))"
              >
                {{
                  isExpanded(intervalKey(interval))
                    ? t('appDiff.code_hide')
                    : t('appDiff.code_show')
                }}
              </el-button>

              <div v-if="isExpanded(intervalKey(interval))" class="commits" data-test="commits">
                <template v-if="interval.code.added_commits.length">
                  <h4>{{ t('appDiff.code_added_heading') }}</h4>
                  <ul>
                    <li v-for="commit in interval.code.added_commits" :key="commit.id">
                      <code>{{ shortCommitId(commit) }}</code>
                      <span class="subject">{{ commitSubject(commit) }}</span>
                    </li>
                  </ul>
                </template>

                <template v-if="interval.code.missing_commits.length">
                  <h4>{{ t('appDiff.code_missing_heading') }}</h4>
                  <ul>
                    <li v-for="commit in interval.code.missing_commits" :key="commit.id">
                      <code>{{ shortCommitId(commit) }}</code>
                      <span class="subject">{{ commitSubject(commit) }}</span>
                    </li>
                  </ul>
                </template>

                <p v-if="interval.code.truncated" class="truncated" data-test="code-truncated">
                  {{ t('appDiff.code_truncated') }}
                </p>
              </div>
            </template>
          </div>
        </article>
      </section>

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
            <tr
              v-for="row in rows"
              :key="`${row.kind}:${row.name}`"
              :class="{ 'row-application': row.kind === 'application' }"
              :data-test="`row-${row.kind}`"
            >
              <th class="package-col" scope="row">
                <span>{{ row.name }}</span>
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
          </tbody>
        </table>
      </div>
    </template>

    <el-empty v-else :description="t('appDiff.no_result')" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import ContentLoader from '@/components/common/ContentLoader.vue'
import { GIT_PROVIDER_OPTIONS } from '@/constants/gitProvider'
import { projectsApi } from '@/api/projects'
import type {
  CloudWorkspaceOption,
  ProjectSummary,
  RepositorySummary,
} from '@/api/projects'
import { releaseDiffApi } from '@/api/releaseDiff'
import { appVersionDiffApi } from '@/api/appVersionDiff'
import type { AppVersionDiffResponse } from '@/api/appVersionDiff'
import { useRefCandidates } from '@/composables/useRefCandidates'
import {
  buildRows,
  codeTone,
  commitSubject,
  commitTotal,
  downgradeCount,
  isMarked,
  isRisk,
  moveLabelKey,
  moveSymbol,
  moveTone,
  rebuiltWithUnchangedDependencies,
  shortCommitId,
  summaryEntries,
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
    repositories.value = await projectsApi.getProjectRepositories(projectKey)
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
    selectedRefs.value = requestedRefs.value?.length ? [...requestedRefs.value] : []
    requestedRefs.value = null
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

  comparing.value = true
  failed.value = false
  try {
    result.value = await appVersionDiffApi.compare({
      ...coordinates(),
      refs: [...selectedRefs.value],
      refresh,
    })
  } catch {
    // The failure is reported rather than emptied: an empty matrix would read as
    // a comparison in which nothing moved.
    result.value = null
    failed.value = true
  } finally {
    comparing.value = false
  }
}

function refresh() {
  void compare(true)
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
  if (repositorySlug && hasCoordinates.value) void loadRefs()
})

watch(isCloudProvider, (cloud) => {
  if (cloud) void ensureWorkspaceSuggestions()
})

watch([selectedProjectKey, selectedRepositorySlug, selectedRefs], syncUrl)

watch(selectedRefs, (refs) => {
  if (refs.length >= 2 && hasCoordinates.value) void compare()
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
  margin: 0 0 12px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
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

.intervals {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
}

.interval {
  flex: 1 1 260px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  padding: 10px 12px;
}

.interval-incomplete {
  border-style: dashed;
  border-color: var(--el-color-warning);
  background: var(--el-color-warning-light-9);
}

.interval-head {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
}

.interval-head .arrow {
  color: var(--el-text-color-secondary);
}

.interval-unknown {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--el-color-warning-dark-2);
}

.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.chip {
  font-size: 12px;
  padding: 1px 8px;
  border-radius: 10px;
  background: var(--el-fill-color-light);
}

.chip-added {
  color: var(--el-color-success);
}

.chip-removed {
  color: var(--el-color-info);
}

.chip-downgrade {
  color: #fff;
  background: var(--el-color-danger);
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

.code {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed var(--el-border-color-lighter);
  font-size: 12px;
}

.code-counts {
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

.rebuilt {
  margin: 6px 0 0;
  color: var(--el-color-warning-dark-2);
  font-weight: 600;
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
