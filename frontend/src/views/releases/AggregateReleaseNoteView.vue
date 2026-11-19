<template>
  <div class="aggregate-note-container">
    <el-card shadow="never" class="context-card">
      <template #header>
        <div class="card-header">
          <div>
            <h2>{{ t('aggregateNote.title') }}</h2>
            <p class="subtitle">{{ t('aggregateNote.subtitle') }}</p>
          </div>
          <div class="header-end">
            <el-button
              v-if="result"
              plain
              :icon="Download"
              :data-test="'export-button'"
              @click="exportNote"
            >
              {{ t('aggregateNote.export') }}
            </el-button>
            <el-button
              v-if="result"
              type="success"
              plain
              data-test="save-button"
              @click="openSaveDialog"
            >
              {{ t('aggregateNote.save') }}
            </el-button>
            <el-button
              type="primary"
              :icon="Loading"
              :loading="building"
              :disabled="!canBuild"
              data-test="build-button"
              @click="build"
            >
              {{ t('aggregateNote.build') }}
            </el-button>
          </div>
        </div>
      </template>

      <el-form class="coordinates" :model="repo" label-width="130px">
        <el-row :gutter="16">
          <el-col :xs="24" :sm="12" :md="6">
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

          <el-col :xs="24" :sm="12" :md="6">
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

          <el-col :xs="24" :sm="12" :md="4">
            <el-form-item :label="t('aggregateNote.source_ref_label')" required>
              <el-select
                v-model="sourceRef"
                filterable
                remote
                clearable
                default-first-option
                :remote-method="onSourceRefSearch"
                :disabled="!hasCoordinates"
                :loading="refsLoading"
                :placeholder="t('aggregateNote.select_ref')"
                style="width: 100%"
                data-test="source-ref-select"
                @visible-change="onSourceRefVisibility"
              >
                <el-option-group v-if="sourceTags.length" :label="t('releaseDependencyGraph.tags_group')">
                  <el-option v-for="tag in sourceTags" :key="`tag:${tag}`" :label="tag" :value="tag" />
                </el-option-group>
                <el-option-group
                  v-if="sourceBranches.length"
                  :label="t('releaseDependencyGraph.branches_group')"
                >
                  <el-option
                    v-for="branch in sourceBranches"
                    :key="`branch:${branch}`"
                    :label="branch"
                    :value="branch"
                  />
                </el-option-group>
              </el-select>
            </el-form-item>
          </el-col>

          <el-col :xs="24" :sm="12" :md="4">
            <el-form-item :label="t('aggregateNote.target_ref_label')" required>
              <el-select
                v-model="targetRef"
                filterable
                remote
                clearable
                default-first-option
                :remote-method="onTargetRefSearch"
                :disabled="!hasCoordinates"
                :loading="refsLoading"
                :placeholder="t('aggregateNote.select_ref')"
                style="width: 100%"
                data-test="target-ref-select"
                @visible-change="onTargetRefVisibility"
              >
                <el-option-group v-if="targetTags.length" :label="t('releaseDependencyGraph.tags_group')">
                  <el-option v-for="tag in targetTags" :key="`tag:${tag}`" :label="tag" :value="tag" />
                </el-option-group>
                <el-option-group
                  v-if="targetBranches.length"
                  :label="t('releaseDependencyGraph.branches_group')"
                >
                  <el-option
                    v-for="branch in targetBranches"
                    :key="`branch:${branch}`"
                    :label="branch"
                    :value="branch"
                  />
                </el-option-group>
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <el-empty v-if="!hasCoordinates" :description="t('aggregateNote.pick_repository')" />
      <el-empty
        v-else-if="!sourceRef || !targetRef"
        :description="t('aggregateNote.pick_refs')"
        data-test="pick-refs"
      />
      <ContentLoader v-else-if="building" :rows="8" :label="t('aggregateNote.loading')" min-height="420px" />
      <el-empty v-else-if="!result" :description="t('aggregateNote.idle')" />

      <!-- ─── The note ─────────────────────────────────────────────── -->
      <div v-else class="note" data-test="note">
        <el-alert
          :type="result.application.verdict === 'contained' ? 'success' : 'error'"
          :closable="false"
          class="app-verdict"
          :title="t('aggregateNote.app_verdict_title', { app: result.app_name })"
          :description="t(`releaseDiff.verdict_${result.application.verdict}`)"
        />

        <div class="summary" data-test="summary">
          <span class="summary-item">{{ t('aggregateNote.stat_app_commits') }}: {{ result.summary.app_commits }}</span>
          <span class="summary-item">
            {{ t('aggregateNote.stat_packages_changed') }}: {{ result.summary.packages_changed }}
          </span>
          <span class="summary-item">
            {{ t('aggregateNote.stat_package_commits') }}: {{ result.summary.package_commits }}
          </span>
          <span v-if="result.summary.packages_failed" class="summary-item summary-warn">
            {{ t('aggregateNote.stat_failed') }}: {{ result.summary.packages_failed }}
          </span>
        </div>

        <!-- The application's own commits -->
        <h3 class="section-heading">{{ t('aggregateNote.report_application') }}</h3>
        <CommitTable
          :commits="result.application.added_commits"
          :page-size="10"
          :empty-text="t('aggregateNote.no_commits')"
          data-test="application-commits"
        />

        <!-- One block per moved package -->
        <h3 class="section-heading">{{ t('aggregateNote.packages_heading') }}</h3>
        <el-empty v-if="result.packages.length === 0" :description="t('aggregateNote.no_packages_moved')" />
        <el-collapse v-else class="packages" data-test="packages">
          <el-collapse-item v-for="entry in result.packages" :key="entry.name" :name="entry.name">
            <template #title>
              <span class="package-title">
                <strong>{{ entry.name }}</strong>
                <span class="package-versions">{{ versionSpan(entry) }}</span>
                <el-tag :type="changeTone(entry.change)" size="small" class="package-tag">
                  {{ t(`aggregateNote.change_${entry.change}`) }}
                </el-tag>
                <el-tag :type="statusTone(entry.status)" size="small" effect="plain" class="package-tag">
                  {{ t(`aggregateNote.status_${entry.status}`) }}
                </el-tag>
                <el-tag
                  v-if="entry.comparison && entry.status === 'compared'"
                  :type="entry.comparison.verdict === 'contained' ? 'success' : 'danger'"
                  size="small"
                  effect="plain"
                  class="package-tag"
                >
                  {{ t(`releaseDiff.verdict_${entry.comparison.verdict}`) }}
                </el-tag>
              </span>
            </template>

            <p v-if="entry.reason" class="package-reason" data-test="package-reason">
              {{ t('aggregateNote.report_reason') }}: {{ entry.reason }}
            </p>
            <p v-if="entry.repository" class="package-repo">
              {{ t('aggregateNote.report_from_repository') }}:
              {{ entry.repository.project_key }}/{{ entry.repository.repository_slug }}
            </p>
            <CommitTable
              v-if="entry.comparison && entry.status === 'compared'"
              :commits="entry.comparison.added_commits"
              :page-size="10"
              :empty-text="t('aggregateNote.no_commits')"
            />
          </el-collapse-item>
        </el-collapse>

        <div v-if="result.unchanged_packages.length" class="unchanged" data-test="unchanged">
          <span class="unchanged-label">{{ t('aggregateNote.unchanged_label') }}</span>
          <el-tag v-for="item in result.unchanged_packages" :key="item" size="small" type="info" effect="plain">
            {{ item }}
          </el-tag>
        </div>
      </div>

      <!-- Saving the note files it under the application's target release, from
           where the existing flows carry it: the Release Notes page, the git
           provider release, the Confluence page. -->
      <el-dialog
        v-model="saveDialogVisible"
        :title="t('aggregateNote.save_title')"
        width="520px"
        data-test="save-dialog"
      >
        <el-form label-width="130px">
          <el-form-item :label="t('aggregateNote.save_tag')">
            <el-input v-model="saveForm.tag_name" data-test="save-tag" />
          </el-form-item>
          <el-form-item :label="t('aggregateNote.save_name')">
            <el-input v-model="saveForm.name" data-test="save-name" />
          </el-form-item>
          <el-form-item :label="t('aggregateNote.save_status')">
            <el-radio-group v-model="saveForm.status" data-test="save-status">
              <el-radio-button value="draft">{{ t('aggregateNote.save_draft') }}</el-radio-button>
              <el-radio-button value="published">{{ t('aggregateNote.save_published') }}</el-radio-button>
            </el-radio-group>
          </el-form-item>
          <el-form-item v-if="saveForm.status === 'published'">
            <el-checkbox v-model="saveForm.sync_to_confluence" data-test="save-confluence">
              {{ t('aggregateNote.save_confluence') }}
            </el-checkbox>
          </el-form-item>
          <p class="save-note">{{ t('aggregateNote.save_note') }}</p>
        </el-form>
        <template #footer>
          <el-button @click="saveDialogVisible = false">{{ t('common.cancel') }}</el-button>
          <el-button
            type="primary"
            :loading="saving"
            data-test="save-confirm"
            @click="saveNote"
          >
            {{ t('aggregateNote.save_confirm') }}
          </el-button>
        </template>
      </el-dialog>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { Download, Loading } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import ContentLoader from '@/components/common/ContentLoader.vue'
import CommitTable from '@/components/release/CommitTable.vue'
import { projectsApi } from '@/api/projects'
import type { CloudWorkspaceOption, ProjectSummary, RepositorySummary } from '@/api/projects'
import { releaseDiffApi } from '@/api/releaseDiff'
import { releaseNotesApi } from '@/api/releaseNotes'
import type { ReleaseNoteStatus } from '@/api/releaseNotes'
import { aggregateReleaseNoteApi } from '@/api/aggregateReleaseNote'
import type {
  AggregatePackageChange,
  AggregatePackageEntry,
  AggregatePackageStatus,
  AggregateReleaseNoteResponse,
} from '@/api/aggregateReleaseNote'
import { useRefCandidates } from '@/composables/useRefCandidates'
import { useJira } from '@/composables/useJira'
import {
  aggregateNoteFilename,
  buildAggregateReleaseNoteHtml,
  buildAggregateReleaseNoteMarkdown,
  downloadAggregateReleaseNote,
} from '@/utils/export/aggregateReleaseNote'

const { t } = useI18n()

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

// Two spans of the same listing: the release it starts from and the one it
// becomes. Each picker keeps its own search state, so picking a source never
// scrambles the target's offered page.
const sourceRefs = useRefCandidates()
const targetRefs = useRefCandidates()
// One listing feeds both pickers, so one loading flag serves both
const refsLoading = ref(false)

const sourceRef = ref('')
const targetRef = ref('')
const building = ref(false)
const result = ref<AggregateReleaseNoteResponse | null>(null)

// JIRA link settings are per session and shared; the commit subjects link to
// the instance when one is configured.
const { jiraSettings, loadJiraSettings } = useJira()

const selectedProjectKey = computed(() => (repo.value.project_key ?? '').trim())
const selectedRepositorySlug = computed(() => (repo.value.repository_slug ?? '').trim())
const isCloudProvider = computed(() => repo.value.git_provider === 'bitbucket_cloud')
const selectedWorkspaceSlug = computed(() =>
  isCloudProvider.value ? (repo.value.workspace_slug ?? '').trim() : '',
)
const hasCoordinates = computed(
  () => Boolean(selectedProjectKey.value) && Boolean(selectedRepositorySlug.value),
)
const canBuild = computed(
  () => hasCoordinates.value && Boolean(sourceRef.value) && Boolean(targetRef.value),
)

// Template aliases: two pickers over one listing
const sourceTags = computed(() => sourceRefs.visibleTags.value)
const sourceBranches = computed(() => sourceRefs.visibleBranches.value)
const targetTags = computed(() => targetRefs.visibleTags.value)
const targetBranches = computed(() => targetRefs.visibleBranches.value)

/** What the reader typed: it searches the whole listing, not the offered page. */
function onSourceRefSearch(query: string) {
  sourceRefs.search.value = query ?? ''
}

function onTargetRefSearch(query: string) {
  targetRefs.search.value = query ?? ''
}

/** A picker that has just closed goes back to offering the recent releases. */
function onSourceRefVisibility(visible: boolean) {
  if (!visible) sourceRefs.search.value = ''
}

function onTargetRefVisibility(visible: boolean) {
  if (!visible) targetRefs.search.value = ''
}

function versionSpan(entry: AggregatePackageEntry): string {
  const from = entry.from_version || '—'
  const to = entry.to_version || '—'
  return `${from} → ${to}`
}

function changeTone(change: AggregatePackageChange) {
  return change === 'removed' ? 'danger' : change === 'added' ? 'warning' : 'primary'
}

function statusTone(status: AggregatePackageStatus) {
  return status === 'failed' ? 'danger' : status === 'skipped' ? 'info' : 'success'
}

function secondaryName(key: string, name?: string | null): string {
  return name && name !== key ? name : ''
}

function coordinates() {
  return {
    project_key: selectedProjectKey.value,
    repository_slug: selectedRepositorySlug.value,
    git_provider: repo.value.git_provider || undefined,
    workspace_slug: selectedWorkspaceSlug.value || undefined,
  }
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

/** Reads the repository's refs once; both pickers share the candidate set. */
async function loadRefs() {
  sourceRefs.clearCandidates()
  targetRefs.clearCandidates()
  sourceRef.value = ''
  targetRef.value = ''
  if (!hasCoordinates.value) return

  refsLoading.value = true
  try {
    const response = await releaseDiffApi.listRefs(coordinates())
    sourceRefs.setCandidates(response)
    targetRefs.setCandidates(response)
  } catch {
    // Left empty: the pickers stay empty and the page stays blank.
  } finally {
    refsLoading.value = false
  }
}

async function build() {
  if (!canBuild.value) return
  building.value = true
  result.value = null
  try {
    result.value = await aggregateReleaseNoteApi.build({
      ...coordinates(),
      source_ref: sourceRef.value,
      target_ref: targetRef.value,
    })
  } catch {
    result.value = null
    ElMessage.error(t('aggregateNote.build_failed'))
  } finally {
    building.value = false
  }
}

function exportNote() {
  if (!result.value) return
  const context = {
    project_key: selectedProjectKey.value,
    repository_slug: selectedRepositorySlug.value,
    git_provider: repo.value.git_provider,
    workspace_slug: selectedWorkspaceSlug.value || undefined,
    jira: jiraSettings.value,
  }
  const html = buildAggregateReleaseNoteHtml({ result: result.value, context })
  downloadAggregateReleaseNote(html, aggregateNoteFilename(context))
}

// ─── Saving the note as a version release ─────────────────────────────────

const saveDialogVisible = ref(false)
const saving = ref(false)
const saveForm = ref({
  tag_name: '',
  name: '',
  status: 'draft' as ReleaseNoteStatus,
  sync_to_confluence: false,
})

function openSaveDialog() {
  if (!result.value) return
  saveForm.value = {
    // the note files under the span's target release, with its source remembered
    tag_name: result.value.target_ref,
    name: `${result.value.app_name} ${result.value.target_ref}`,
    status: 'draft',
    sync_to_confluence: false,
  }
  saveDialogVisible.value = true
}

async function saveNote() {
  if (!result.value) return
  saving.value = true
  try {
    await releaseNotesApi.create({
      project_key: selectedProjectKey.value,
      repository_slug: selectedRepositorySlug.value,
      git_provider: repo.value.git_provider,
      workspace_slug: selectedWorkspaceSlug.value || undefined,
      tag_name: saveForm.value.tag_name.trim(),
      name: saveForm.value.name.trim() || undefined,
      previous_tag: result.value.source_ref,
      body: buildAggregateReleaseNoteMarkdown(result.value),
      status: saveForm.value.status,
      sync_to_confluence: saveForm.value.status === 'published' && saveForm.value.sync_to_confluence,
    })
    saveDialogVisible.value = false
    ElMessage.success(t('aggregateNote.saved'))
  } catch {
    // the error message names the conflict (a release under that tag) or the
    // failure; the dialog stays open so the reader can adjust and retry
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  void loadProjects()
  void loadJiraSettings()
})

// The project catalog carries the provider each repository lives on, so picking
// a project fills it in - the reader never has to know which one it is.
watch(selectedProjectKey, async (projectKey) => {
  const project = projects.value.find((item) => item.project_key === projectKey)

  repo.value.repository_slug = ''
  repo.value.git_provider = project?.git_provider || null
  sourceRefs.clearCandidates()
  targetRefs.clearCandidates()
  sourceRef.value = ''
  targetRef.value = ''
  result.value = null

  if (project) {
    await loadRepositories(projectKey)
  }
  if (isCloudProvider.value) {
    void ensureWorkspaceSuggestions()
  }
})

watch(hasCoordinates, (ready) => {
  if (ready) void loadRefs()
})

watch(isCloudProvider, (cloud) => {
  if (cloud) void ensureWorkspaceSuggestions()
})
</script>

<style scoped>
.aggregate-note-container {
  padding: 16px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.card-header h2 {
  margin: 0 0 4px;
  font-size: 18px;
}

.subtitle {
  margin: 0;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.header-end {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.option-key {
  margin-right: 8px;
}

.option-name {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.app-verdict {
  margin-bottom: 12px;
}

.summary {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  margin-bottom: 16px;
  font-size: 13px;
  color: var(--el-text-color-regular);
}

.summary-warn {
  color: var(--el-color-danger);
  font-weight: 600;
}

.section-heading {
  margin: 20px 0 8px;
  font-size: 15px;
}

.packages :deep(.el-collapse-item__header) {
  height: auto;
  min-height: 48px;
  padding: 4px 0;
}

.package-title {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.package-versions {
  color: var(--el-text-color-secondary);
  font-size: 12px;
  font-family: monospace;
}

.package-tag {
  flex-shrink: 0;
}

.package-reason,
.package-repo {
  margin: 0 0 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.unchanged {
  margin-top: 20px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.unchanged-label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin-right: 4px;
}

.save-note {
  margin: 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
