<template>
  <div class="release-notes-container">
    <!-- Repository coordinates -->
    <el-card shadow="never" class="context-card">
      <template #header>
        <div class="card-header">
          <div>
            <h2>{{ t('releaseNotes.title') }}</h2>
            <p class="subtitle">{{ t('releaseNotes.subtitle') }}</p>
          </div>
        </div>
      </template>

      <el-form :model="repo" label-width="150px">
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
              >
                <el-option
                  v-for="project in projects"
                  :key="project.project_key"
                  :label="project.project_key"
                  :value="project.project_key"
                >
                  <span class="option-key">{{ project.project_key }}</span>
                  <span v-if="secondaryName(project.project_key, project.project_name)" class="option-name">
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
              >
                <el-option
                  v-for="repository in repositories"
                  :key="repository.repository_slug"
                  :label="repository.repository_slug"
                  :value="repository.repository_slug"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12" :md="6">
            <el-form-item :label="t('releaseDiff.git_provider')">
              <el-select
                v-model="repo.git_provider"
                clearable
                :placeholder="t('releaseDiff.git_provider_placeholder')"
                style="width: 100%"
              >
                <el-option label="bitbucket_server" value="bitbucket_server" />
                <el-option label="bitbucket_cloud" value="bitbucket_cloud" />
                <el-option label="github_enterprise" value="github_enterprise" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col v-if="isCloudProvider" :xs="24" :sm="12" :md="6">
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
        </el-row>
      </el-form>
    </el-card>

    <el-row :gutter="16" class="notes-row">
      <!-- ============ Release list ============ -->
      <el-col :xs="24" :lg="15">
        <el-card shadow="never" class="notes-card">
          <template #header>
            <div class="section-header">
              <div class="section-title">
                <h3>{{ t('releaseNotes.list_title') }}</h3>
                <el-tag v-if="notesTotal" size="small" type="info" round>{{ notesTotal }}</el-tag>
              </div>
              <div class="header-actions">
                <el-button
                  v-if="canImportFromProvider"
                  size="small"
                  :loading="importing"
                  :disabled="!hasCoordinates"
                  @click="importFromProvider"
                >
                  {{ t('releaseNotes.import_from_provider') }}
                </el-button>
                <el-button
                  v-if="canManage"
                  type="primary"
                  size="small"
                  :disabled="!hasCoordinates"
                  @click="startNewRelease"
                >
                  {{ t('releaseNotes.draft_new') }}
                </el-button>
              </div>
            </div>
          </template>

          <el-alert
            v-if="!hasCoordinates"
            type="info"
            :closable="false"
            :title="t('releaseNotes.needs_repository')"
          />

          <div v-else-if="notesLoading" class="loading-block">
            <el-skeleton :rows="4" animated />
          </div>

          <el-empty v-else-if="notes.length === 0" :description="t('releaseNotes.empty')" />

          <div v-else class="release-list">
            <div v-for="note in notes" :key="note.id" class="release-item">
              <div class="release-head">
                <div class="release-title">
                  <span class="release-name">{{ note.name }}</span>
                  <el-tag size="small" effect="plain">{{ note.tag_name }}</el-tag>
                  <el-tag v-if="note.is_latest" size="small" type="success" round>
                    {{ t('releaseNotes.badge_latest') }}
                  </el-tag>
                  <el-tag v-if="note.is_prerelease" size="small" type="warning" round>
                    {{ t('releaseNotes.badge_prerelease') }}
                  </el-tag>
                  <el-tag v-if="note.status === 'draft'" size="small" type="info" round>
                    {{ t('releaseNotes.badge_draft') }}
                  </el-tag>
                </div>
                <div class="release-actions">
                  <el-button
                    v-if="note.external_url"
                    link
                    size="small"
                    tag="a"
                    :href="note.external_url"
                    target="_blank"
                    rel="noopener"
                  >
                    {{ t('releaseNotes.view_on_provider') }}
                  </el-button>
                  <template v-if="canManage">
                    <el-button link type="primary" size="small" @click="editNote(note)">
                      {{ t('releaseNotes.edit_release') }}
                    </el-button>
                    <el-button
                      v-if="note.status === 'draft'"
                      link
                      type="success"
                      size="small"
                      @click="publishNote(note)"
                    >
                      {{ t('releaseNotes.publish') }}
                    </el-button>
                    <el-button
                      v-if="canImportFromProvider"
                      link
                      type="primary"
                      size="small"
                      @click="pushNote(note)"
                    >
                      {{ t('releaseNotes.push_to_provider') }}
                    </el-button>
                    <el-button link type="danger" size="small" @click="confirmDelete(note)">
                      {{ t('releaseNotes.delete') }}
                    </el-button>
                  </template>
                </div>
              </div>

              <div class="release-meta">
                <span v-if="note.author">
                  {{ t('releaseNotes.released_by', { author: note.author }) }}
                </span>
                <span v-if="note.published_date">
                  · {{ formatDate(note.published_date) }}
                </span>
                <span v-else-if="note.updated_date">
                  · {{ t('releaseNotes.updated_at', { date: formatDate(note.updated_date) }) }}
                </span>
                <span v-if="note.previous_tag" class="release-range">
                  · {{ t('releaseNotes.range', { from: note.previous_tag, to: note.tag_name }) }}
                </span>
              </div>

              <div v-if="note.body" class="release-body" :class="{ collapsed: !expanded[note.id] }">
                <MdPreview :model-value="note.body" preview-theme="github" />
                <div v-if="!expanded[note.id]" class="body-fade" />
              </div>
              <p v-else class="muted">{{ t('releaseNotes.notes_empty') }}</p>

              <el-button
                v-if="note.body && isLongBody(note.body)"
                link
                type="primary"
                size="small"
                class="expand-toggle"
                @click="toggleExpanded(note.id)"
              >
                {{
                  expanded[note.id]
                    ? t('releaseNotes.show_less')
                    : t('releaseNotes.show_more')
                }}
              </el-button>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- ============ Draft / edit form (review administrators only) ============ -->
      <el-col :xs="24" :lg="9">
        <div v-if="!canManage" class="form-anchor">
          <el-card shadow="never" class="form-card">
            <el-alert
              type="info"
              :closable="false"
              :title="t('releaseNotes.read_only_title')"
              :description="t('releaseNotes.read_only_help')"
            />
          </el-card>
        </div>
        <div v-else ref="formCard" class="form-anchor">
        <el-card shadow="never" class="form-card">
          <template #header>
            <div class="section-header">
              <div class="section-title">
                <h3>
                  {{
                    editingId
                      ? t('releaseNotes.edit_release')
                      : t('releaseNotes.draft_new')
                  }}
                </h3>
              </div>
            </div>
          </template>

          <el-form :model="form" label-position="top">
            <el-form-item :label="t('releaseNotes.tag')" required>
              <el-select
                v-model="form.tag_name"
                filterable
                clearable
                allow-create
                default-first-option
                :loading="refsLoading"
                :disabled="Boolean(editingId)"
                :placeholder="t('releaseNotes.tag_placeholder')"
                style="width: 100%"
              >
                <el-option
                  v-for="tag in tags"
                  :key="tag"
                  :label="tag"
                  :value="tag"
                />
              </el-select>
              <el-button
                link
                type="primary"
                size="small"
                :loading="refsLoading"
                :disabled="!hasCoordinates"
                @click="loadRefs(true)"
              >
                {{ t('releaseNotes.refresh_tags') }}
              </el-button>
            </el-form-item>

            <el-form-item :label="t('releaseNotes.previous_tag')">
              <el-select
                v-model="form.previous_tag"
                filterable
                clearable
                allow-create
                :disabled="Boolean(editingId)"
                :placeholder="t('releaseNotes.previous_tag_placeholder')"
                style="width: 100%"
              >
                <el-option v-for="ref in selectableRefs" :key="ref" :label="ref" :value="ref" />
              </el-select>
              <div class="field-hint">{{ t('releaseNotes.previous_tag_help') }}</div>
            </el-form-item>

            <el-form-item :label="t('releaseNotes.release_title')">
              <el-input
                v-model="form.name"
                clearable
                :placeholder="form.tag_name || t('releaseNotes.title_placeholder')"
              />
            </el-form-item>

            <el-form-item :label="t('releaseNotes.notes')">
              <div class="notes-editor">
                <div class="notes-toolbar">
                  <el-button
                    size="small"
                    :loading="generating"
                    :disabled="!hasCoordinates || !form.tag_name"
                    @click="generateNotes"
                  >
                    {{ t('releaseNotes.generate_notes') }}
                  </el-button>
                  <span v-if="generatedCount !== null" class="generated-hint">
                    {{ t('releaseNotes.generated', { count: generatedCount }) }}
                  </span>
                </div>
                <MdEditor
                  v-model="form.body"
                  :toolbars="toolbars"
                  :preview="false"
                  :style="{ height: '320px' }"
                  :placeholder="t('releaseNotes.notes_placeholder')"
                />
              </div>
            </el-form-item>

            <el-form-item>
              <el-checkbox v-model="form.is_prerelease">
                {{ t('releaseNotes.prerelease') }}
              </el-checkbox>
            </el-form-item>

            <template v-if="isGithubProvider">
              <el-form-item>
                <el-checkbox v-model="form.push_to_provider">
                  {{ t('releaseNotes.push_to_provider') }}
                </el-checkbox>
              </el-form-item>
              <el-form-item v-if="form.push_to_provider" :label="t('releaseNotes.target_branch')">
                <el-input
                  v-model="form.target_commitish"
                  clearable
                  :placeholder="t('releaseNotes.target_branch_placeholder')"
                />
                <div class="field-hint">{{ t('releaseNotes.target_branch_help') }}</div>
              </el-form-item>
            </template>

            <div class="form-actions">
              <el-button
                type="primary"
                :loading="saving"
                :disabled="!canSave"
                @click="saveRelease('published')"
              >
                {{ editingId && editingStatus === 'published' ? t('releaseNotes.save') : t('releaseNotes.publish') }}
              </el-button>
              <el-button :loading="saving" :disabled="!canSave" @click="saveRelease('draft')">
                {{ t('releaseNotes.save_draft') }}
              </el-button>
              <el-button v-if="editingId" @click="resetForm">
                {{ t('releaseNotes.cancel') }}
              </el-button>
            </div>
          </el-form>
        </el-card>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { MdEditor, MdPreview, type ToolbarNames } from 'md-editor-v3'
import 'md-editor-v3/lib/style.css'
import { projectsApi } from '@/api/projects'
import type { CloudWorkspaceOption, ProjectSummary, RepositorySummary } from '@/api/projects'
import { releaseDiffApi } from '@/api/releaseDiff'
import { releaseNotesApi, type ReleaseNote } from '@/api/releaseNotes'
import { useAuthStore } from '@/stores/auth'

const { t } = useI18n()
const authStore = useAuthStore()

// Release notes are manageable by review administrators (RBAC: release_note.manage)
const MANAGE_ROLES = ['review_admin', 'system_admin']

const LONG_BODY_THRESHOLD = 600
const PREVIEW_MAX_COMMITS = 500

const toolbars: ToolbarNames[] = [
  'bold',
  'italic',
  'strikeThrough',
  '-',
  'title',
  'quote',
  'unorderedList',
  'orderedList',
  'task',
  '-',
  'link',
  'code',
  'codeRow',
  '-',
  'revoke',
  'next',
]

const projects = ref<ProjectSummary[]>([])
const repositories = ref<RepositorySummary[]>([])
const cloudWorkspaces = ref<CloudWorkspaceOption[]>([])
const projectsLoading = ref(false)
const repositoriesLoading = ref(false)
const workspacesLoading = ref(false)
const workspacesLoaded = ref(false)
const refsLoading = ref(false)
const tags = ref<string[]>([])
const branches = ref<string[]>([])

const notes = ref<ReleaseNote[]>([])
const notesTotal = ref(0)
const notesLoading = ref(false)
const expanded = reactive<Record<number, boolean>>({})

const saving = ref(false)
const importing = ref(false)
const generating = ref(false)
const generatedCount = ref<number | null>(null)
const formCard = ref<HTMLElement | null>(null)

const repo = ref({
  project_key: '',
  repository_slug: '',
  git_provider: null as string | null,
  workspace_slug: '',
})

const form = ref({
  tag_name: '',
  previous_tag: '',
  name: '',
  body: '',
  is_prerelease: false,
  push_to_provider: false,
  target_commitish: '',
})

const editingId = ref<number | null>(null)
const editingStatus = ref<'draft' | 'published'>('draft')

const selectedProjectKey = computed(() => (repo.value.project_key ?? '').trim())
const selectedRepositorySlug = computed(() => (repo.value.repository_slug ?? '').trim())
const isCloudProvider = computed(() => repo.value.git_provider === 'bitbucket_cloud')
const selectedWorkspaceSlug = computed(() =>
  isCloudProvider.value ? (repo.value.workspace_slug ?? '').trim() : '',
)
const hasCoordinates = computed(
  () => Boolean(selectedProjectKey.value) && Boolean(selectedRepositorySlug.value),
)
const isGithubProvider = computed(() => repo.value.git_provider === 'github_enterprise')
const canManage = computed(() =>
  (authStore.user?.roles ?? []).some((role) => MANAGE_ROLES.includes(role)),
)
// Importing / pushing only works for providers with a release API
const canImportFromProvider = computed(() => canManage.value && isGithubProvider.value)
const canSave = computed(() => hasCoordinates.value && Boolean(form.value.tag_name.trim()))
const selectableRefs = computed(() => [...tags.value, ...branches.value])

function secondaryName(value: string, name?: string | null): string | undefined {
  const trimmed = (name ?? '').trim()
  if (!trimmed) return undefined
  return trimmed.toLowerCase() === (value ?? '').trim().toLowerCase() ? undefined : trimmed
}

function formatDate(value?: string | null): string {
  if (!value) return ''
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString()
}

function isLongBody(body: string): boolean {
  return body.length > LONG_BODY_THRESHOLD || body.split('\n').length > 12
}

function toggleExpanded(noteId: number) {
  expanded[noteId] = !expanded[noteId]
}

function coordinates() {
  return {
    project_key: selectedProjectKey.value,
    repository_slug: selectedRepositorySlug.value,
    git_provider: repo.value.git_provider || undefined,
    workspace_slug: selectedWorkspaceSlug.value || undefined,
  }
}

// ------------------------------------------------------------------ #
// Data loading
// ------------------------------------------------------------------ #

async function loadProjects() {
  projectsLoading.value = true
  try {
    projects.value = await projectsApi.getAllProjects()
  } catch {
    ElMessage.error(t('releaseDiff.load_projects_failed'))
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
    ElMessage.error(t('releaseDiff.load_repositories_failed'))
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
 * Load the tag / branch suggestions.
 *
 * ``force`` bypasses the backend cache so a tag that was just created on the
 * git side shows up immediately.
 */
async function loadRefs(force = false) {
  tags.value = []
  branches.value = []
  if (!hasCoordinates.value) return

  refsLoading.value = true
  try {
    const response = await releaseDiffApi.listRefs({
      ...coordinates(),
      limit: 200,
      refresh: force,
    })
    tags.value = response.tags ?? []
    branches.value = response.branches ?? []
    if (force) {
      ElMessage.success(t('releaseNotes.refresh_tags_ok'))
    }
  } catch {
    // refs are only suggestions - typing the tag manually stays possible
  } finally {
    refsLoading.value = false
  }
}

async function loadNotes() {
  notes.value = []
  notesTotal.value = 0
  if (!hasCoordinates.value) return

  notesLoading.value = true
  try {
    const response = await releaseNotesApi.list({
      project_key: selectedProjectKey.value,
      repository_slug: selectedRepositorySlug.value,
      limit: 100,
    })
    notes.value = response.items ?? []
    notesTotal.value = response.total ?? notes.value.length
  } catch {
    ElMessage.error(t('releaseNotes.load_failed'))
  } finally {
    notesLoading.value = false
  }
}

// ------------------------------------------------------------------ #
// Form actions
// ------------------------------------------------------------------ #

function resetForm() {
  editingId.value = null
  editingStatus.value = 'draft'
  generatedCount.value = null
  form.value = {
    tag_name: '',
    previous_tag: '',
    name: '',
    body: '',
    is_prerelease: false,
    push_to_provider: false,
    target_commitish: '',
  }
}

function startNewRelease() {
  resetForm()
  // Preselect the newest tag so a new version can be drafted quickly
  const newest = tags.value[0]
  if (newest) {
    form.value.tag_name = newest
  }
  formCard.value?.scrollIntoView?.({ behavior: 'smooth', block: 'start' })
}

function editNote(note: ReleaseNote) {
  editingId.value = note.id
  editingStatus.value = note.status
  generatedCount.value = null
  form.value = {
    tag_name: note.tag_name,
    previous_tag: note.previous_tag ?? '',
    name: note.name,
    body: note.body ?? '',
    is_prerelease: note.is_prerelease,
    push_to_provider: false,
    target_commitish: '',
  }
  formCard.value?.scrollIntoView?.({ behavior: 'smooth', block: 'start' })
}

async function generateNotes() {
  if (!hasCoordinates.value || !form.value.tag_name) return

  generating.value = true
  try {
    const preview = await releaseNotesApi.preview({
      ...coordinates(),
      version: form.value.tag_name.trim(),
      previous_version: form.value.previous_tag.trim() || undefined,
      max_commits: PREVIEW_MAX_COMMITS,
    })
    form.value.body = preview.body
    if (!form.value.name.trim()) {
      form.value.name = preview.suggested_name
    }
    generatedCount.value = preview.commit_count
    if (preview.truncated) {
      ElMessage.warning(t('releaseNotes.generate_truncated'))
    }
  } catch {
    ElMessage.error(t('releaseNotes.generate_failed'))
  } finally {
    generating.value = false
  }
}

async function saveRelease(status: 'draft' | 'published') {
  if (!canSave.value) {
    ElMessage.warning(t('releaseNotes.tag_required'))
    return
  }

  saving.value = true
  try {
    let saved: ReleaseNote
    if (editingId.value) {
      saved = await releaseNotesApi.update(editingId.value, {
        name: form.value.name.trim() || form.value.tag_name.trim(),
        body: form.value.body,
        previous_tag: form.value.previous_tag.trim() || null,
        is_prerelease: form.value.is_prerelease,
        status,
      })
    } else {
      saved = await releaseNotesApi.create({
        ...coordinates(),
        tag_name: form.value.tag_name.trim(),
        name: form.value.name.trim() || form.value.tag_name.trim(),
        body: form.value.body,
        previous_tag: form.value.previous_tag.trim() || null,
        is_prerelease: form.value.is_prerelease,
        status,
      })
    }

    ElMessage.success(
      status === 'published' ? t('releaseNotes.published_ok') : t('releaseNotes.saved_ok'),
    )

    if (status === 'published' && form.value.push_to_provider && isGithubProvider.value) {
      await pushNote(saved, true)
    }

    resetForm()
    await loadNotes()
  } catch {
    ElMessage.error(t('releaseNotes.save_failed'))
  } finally {
    saving.value = false
  }
}

/** Publish (or re-sync) the release on the git provider. */
async function pushNote(note: ReleaseNote, silent = false) {
  try {
    const pushed = await releaseNotesApi.push(note.id, {
      ...coordinates(),
      target_commitish: form.value.target_commitish.trim() || undefined,
      update_existing: true,
    })
    if (!silent) {
      ElMessage.success(
        pushed.external_url
          ? t('releaseNotes.pushed_ok', { url: pushed.external_url })
          : t('releaseNotes.pushed_ok_plain'),
      )
      await loadNotes()
    }
  } catch {
    ElMessage.error(t('releaseNotes.push_failed'))
  }
}

/** Import the releases that already exist on the git provider. */
async function importFromProvider() {
  if (!hasCoordinates.value) return

  importing.value = true
  try {
    const result = await releaseNotesApi.importReleases({
      ...coordinates(),
      limit: 100,
    })
    ElMessage.success(
      t('releaseNotes.imported_ok', {
        imported: result.imported,
        updated: result.updated,
        skipped: result.skipped,
      }),
    )
    await loadNotes()
  } catch {
    ElMessage.error(t('releaseNotes.import_failed'))
  } finally {
    importing.value = false
  }
}

async function publishNote(note: ReleaseNote) {
  try {
    await releaseNotesApi.update(note.id, { status: 'published' })
    ElMessage.success(t('releaseNotes.published_ok'))
    await loadNotes()
  } catch {
    ElMessage.error(t('releaseNotes.save_failed'))
  }
}

async function confirmDelete(note: ReleaseNote) {
  try {
    await ElMessageBox.confirm(
      t('releaseNotes.delete_confirm', { tag: note.tag_name }),
      t('releaseNotes.delete'),
      { type: 'warning' },
    )
  } catch {
    return
  }

  try {
    await releaseNotesApi.remove(note.id)
    ElMessage.success(t('releaseNotes.deleted_ok'))
    if (editingId.value === note.id) {
      resetForm()
    }
    await loadNotes()
  } catch {
    ElMessage.error(t('releaseNotes.delete_failed'))
  }
}

// ------------------------------------------------------------------ #
// Reactivity
// ------------------------------------------------------------------ #

watch(
  () => repo.value.project_key,
  async (projectKey) => {
    const key = (projectKey || '').trim()
    const project = projects.value.find((item) => item.project_key === key)

    repo.value.repository_slug = ''
    repo.value.git_provider = project?.git_provider || null

    repositories.value = []
    if (project) {
      await loadRepositories(key)
    }
    if (isCloudProvider.value) {
      void ensureWorkspaceSuggestions()
    }
  },
)

watch(isCloudProvider, (isCloud) => {
  if (isCloud) {
    void ensureWorkspaceSuggestions()
  }
})

watch(
  () => [selectedProjectKey.value, selectedRepositorySlug.value, selectedWorkspaceSlug.value, repo.value.git_provider],
  () => {
    resetForm()
    void loadRefs()
    void loadNotes()
  },
)

onMounted(loadProjects)
</script>

<style scoped>
.release-notes-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 4px;
}

.card-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.subtitle {
  margin: 4px 0 0;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.section-title h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.header-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.notes-row {
  align-items: stretch;
}

.notes-card,
.form-anchor {
  height: 100%;
}

.form-card {
  height: 100%;
}

.loading-block {
  padding: 8px 0;
}

.release-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.release-item {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  padding: 16px;
}

.release-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.release-title {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.release-name {
  font-size: 16px;
  font-weight: 600;
}

.release-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  flex-shrink: 0;
}

.release-meta {
  margin-top: 6px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.release-body {
  position: relative;
  margin-top: 12px;
}

.release-body.collapsed {
  max-height: 260px;
  overflow: hidden;
}

.body-fade {
  position: absolute;
  inset: auto 0 0 0;
  height: 48px;
  background: linear-gradient(to bottom, transparent, var(--el-bg-color));
  pointer-events: none;
}

.expand-toggle {
  margin-top: 4px;
}

.muted {
  margin: 12px 0 0;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.notes-editor {
  width: 100%;
}

.notes-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.generated-hint {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.field-hint {
  margin-top: 4px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.form-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

::deep(.el-select-dropdown__item) .option-key {
  font-weight: 600;
}

::deep(.el-select-dropdown__item) .option-name {
  margin-left: 8px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
</style>
