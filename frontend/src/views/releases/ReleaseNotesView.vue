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

    <el-alert
      v-if="!canManage"
      class="read-only-alert"
      type="info"
      :closable="false"
      show-icon
      :title="t('releaseNotes.read_only_title')"
      :description="t('releaseNotes.read_only_help')"
    />

    <el-row :gutter="16" class="notes-row">
      <!-- ============ Column 1: releases and tags ============ -->
      <el-col :xs="24" :lg="8">
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
                  @click="startNewRelease()"
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

          <el-tabs v-else v-model="activeTab" class="nav-tabs">
            <!-- ============ Stored releases, paginated ============ -->
            <el-tab-pane name="releases" :label="t('releaseNotes.list_title')">
              <div v-if="notesLoading" class="loading-block">
                <el-skeleton :rows="4" animated />
              </div>

              <el-empty
                v-else-if="notes.length === 0"
                :description="t('releaseNotes.empty')"
                :image-size="60"
              />

              <template v-else>
                <ul class="nav-list">
                  <li
                    v-for="note in notes"
                    :key="note.id"
                    class="nav-item"
                    :class="{ active: tabIsReleases && selectedNote?.id === note.id && !editorOpen }"
                    @click="selectNote(note)"
                  >
                    <div class="nav-item-main">
                      <span class="nav-item-name">{{ note.name }}</span>
                      <el-tag size="small" effect="plain">{{ note.tag_name }}</el-tag>
                    </div>
                    <div class="nav-item-badges">
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
                    <div class="nav-item-meta">
                      {{ formatDate(note.published_date || note.updated_date) }}
                    </div>
                  </li>
                </ul>

                <el-pagination
                  v-if="notesTotal > notesPageSize"
                  v-model:current-page="notesPage"
                  v-model:page-size="notesPageSize"
                  class="nav-pagination"
                  size="small"
                  background
                  :page-sizes="[5, 10, 20, 50]"
                  :total="notesTotal"
                  layout="total, sizes, prev, pager, next"
                />
              </template>
            </el-tab-pane>

            <!-- ============ Every tag of the repository, paginated ============ -->
            <el-tab-pane name="tags" :label="t('releaseNotes.panel_tags')">
              <div class="nav-section-title">
                <span>{{ t('releaseNotes.tags_hint') }}</span>
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
              </div>

              <el-empty
                v-if="tags.length === 0"
                :description="t('releaseNotes.tags_empty')"
                :image-size="60"
              />

              <template v-else>
                <ul class="nav-list">
                  <li
                    v-for="tag in visibleTags"
                    :key="tag"
                    class="nav-item tag-item"
                    :class="{ active: selectedTag === tag && !editorOpen }"
                    @click="selectTag(tag)"
                  >
                    <div class="nav-item-main">
                      <span class="nav-item-name">{{ tag }}</span>
                    </div>
                  </li>
                </ul>

                <el-pagination
                  v-if="tags.length > tagPageSize"
                  v-model:current-page="tagPage"
                  v-model:page-size="tagPageSize"
                  class="nav-pagination"
                  size="small"
                  background
                  :page-sizes="[10, 20, 50, 100]"
                  :total="tags.length"
                  layout="total, sizes, prev, pager, next"
                />
              </template>
            </el-tab-pane>
          </el-tabs>
        </el-card>
      </el-col>

      <!-- ============ Column 2: notes of the selection (or the editor) ============ -->
      <el-col :xs="24" :lg="16">
        <div ref="formCard" class="form-anchor">
        <el-card shadow="never" class="detail-card">
          <template #header>
            <div class="section-header">
              <div class="section-title">
                <h3>{{ detailTitle }}</h3>
                <template v-if="selectedNote && !editorOpen">
                  <el-tag size="small" effect="plain">{{ selectedNote.tag_name }}</el-tag>
                  <el-tag v-if="selectedNote.is_latest" size="small" type="success" round>
                    {{ t('releaseNotes.badge_latest') }}
                  </el-tag>
                  <el-tag v-if="selectedNote.is_prerelease" size="small" type="warning" round>
                    {{ t('releaseNotes.badge_prerelease') }}
                  </el-tag>
                  <el-tag v-if="selectedNote.status === 'draft'" size="small" type="info" round>
                    {{ t('releaseNotes.badge_draft') }}
                  </el-tag>
                </template>
                <el-tag v-else-if="tabIsTags && selectedTag && !editorOpen" size="small" effect="plain">
                  {{ selectedTag }}
                </el-tag>
              </div>

              <div class="header-actions">
                <el-button
                  v-if="editorOpen"
                  link
                  size="small"
                  :icon="Close"
                  :aria-label="t('releaseNotes.close_editor')"
                  @click="closeForm"
                >
                  {{ t('releaseNotes.close_editor') }}
                </el-button>
                <el-button
                  v-else-if="tabIsTags && selectedTag && canManage"
                  type="primary"
                  size="small"
                  @click="startNewRelease(selectedTag)"
                >
                  {{ t('releaseNotes.draft_for_tag') }}
                </el-button>
                <template v-else-if="tabIsReleases && selectedNote">
                  <el-button
                    v-if="selectedNote.external_url"
                    link
                    size="small"
                    tag="a"
                    :href="selectedNote.external_url"
                    target="_blank"
                    rel="noopener"
                  >
                    {{ t('releaseNotes.view_on_provider') }}
                  </el-button>
                  <template v-if="canManage">
                    <el-button link type="primary" size="small" @click="editNote(selectedNote)">
                      {{ t('releaseNotes.edit_release') }}
                    </el-button>
                    <el-button
                      v-if="selectedNote.status === 'draft'"
                      link
                      type="success"
                      size="small"
                      @click="publishNote(selectedNote)"
                    >
                      {{ t('releaseNotes.publish') }}
                    </el-button>
                    <el-button
                      v-if="canImportFromProvider"
                      link
                      type="primary"
                      size="small"
                      @click="pushNote(selectedNote)"
                    >
                      {{ t('releaseNotes.push_to_provider') }}
                    </el-button>
                    <el-button link type="danger" size="small" @click="confirmDelete(selectedNote)">
                      {{ t('releaseNotes.delete') }}
                    </el-button>
                  </template>
                </template>
              </div>
            </div>
          </template>

          <el-form v-if="editorOpen" class="editor-form" :model="form" label-position="top">
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
              <el-tooltip :content="t('releaseNotes.refresh_tags')" placement="top">
                <el-button
                  link
                  type="primary"
                  size="small"
                  :icon="Refresh"
                  :loading="refsLoading"
                  :disabled="!hasCoordinates"
                  :aria-label="t('releaseNotes.refresh_tags')"
                  @click="loadRefs(true)"
                />
              </el-tooltip>
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
                  :theme="mdTheme"
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
              <el-button @click="closeForm">{{ t('releaseNotes.cancel') }}</el-button>
            </div>
          </el-form>

          <!-- Commits released by the selected tag (mapping tag -> commits) -->
          <template v-else-if="tabIsTags && selectedTag">
            <div class="release-meta">
              <span>
                {{
                  tagPrevious
                    ? t('releaseNotes.range', { from: tagPrevious, to: selectedTag })
                    : t('releaseNotes.full_history', { tag: selectedTag })
                }}
              </span>
              <span v-if="!tagCommitsLoading"> · {{ t('releaseNotes.commit_count', { count: tagCommitCount }) }}</span>
            </div>

            <el-alert
              v-if="tagTruncated"
              class="status-alert"
              type="warning"
              :closable="false"
              :title="t('releaseNotes.commits_truncated')"
            />

            <el-skeleton v-if="tagCommitsLoading" class="loading-block" :rows="5" animated />

            <commit-table v-else :commits="tagCommits" :empty-text="t('releaseNotes.commits_empty')" />
          </template>

          <!-- Read-only notes of the selected release -->
          <template v-else-if="tabIsReleases && selectedNote">
            <div class="release-meta">
              <span v-if="selectedNote.author">
                {{ t('releaseNotes.released_by', { author: selectedNote.author }) }}
              </span>
              <span v-if="selectedNote.published_date">
                · {{ formatDate(selectedNote.published_date) }}
              </span>
              <span v-else-if="selectedNote.updated_date">
                · {{ t('releaseNotes.updated_at', { date: formatDate(selectedNote.updated_date) }) }}
              </span>
              <span v-if="selectedNote.previous_tag" class="release-range">
                ·
                {{
                  t('releaseNotes.range', {
                    from: selectedNote.previous_tag,
                    to: selectedNote.tag_name,
                  })
                }}
              </span>
            </div>

            <div v-if="selectedNote.body" class="release-body" @click="openNoteLink">
              <MdPreview :model-value="selectedNote.body" :theme="mdTheme" preview-theme="github" />
            </div>
            <p v-else class="muted">{{ t('releaseNotes.notes_empty') }}</p>
          </template>

          <el-skeleton v-else-if="notesLoading" :rows="6" animated />

          <el-empty
            v-else
            :description="t(hasCoordinates ? 'releaseNotes.select_hint' : 'releaseNotes.needs_repository')"
          />
        </el-card>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Close, Refresh } from '@element-plus/icons-vue'
import { MdEditor, MdPreview, type ToolbarNames } from 'md-editor-v3'
import 'md-editor-v3/lib/style.css'
import { projectsApi } from '@/api/projects'
import type { CloudWorkspaceOption, ProjectSummary, RepositorySummary } from '@/api/projects'
import { releaseDiffApi } from '@/api/releaseDiff'
import type { CommitInfo } from '@/api/releaseDiff'
import CommitTable from '@/components/release/CommitTable.vue'
import { releaseNotesApi, type ReleaseNote } from '@/api/releaseNotes'
import { useAuthStore } from '@/stores/auth'

type NavigatorTab = 'releases' | 'tags'

const { t } = useI18n()
const authStore = useAuthStore()

// Release notes are manageable by review administrators (RBAC: release_note.manage)
const MANAGE_ROLES = ['review_admin', 'system_admin']

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
// Column 1 is a navigator with two tabs: stored releases and repository tags
const activeTab = ref<NavigatorTab>('releases')
const tabIsReleases = computed(() => activeTab.value === 'releases')
const tabIsTags = computed(() => activeTab.value === 'tags')
// Releases are paginated by the backend, tags are paginated in the browser
const notesPage = ref(1)
const notesPageSize = ref(10)
const tagPage = ref(1)
const tagPageSize = ref(20)
// Either a stored release or a tag is selected, depending on the active tab
const selectedId = ref<number | null>(null)
const selectedTag = ref<string | null>(null)
const selectedNote = computed(() => notes.value.find((note) => note.id === selectedId.value) ?? null)
// Commits covered by the selected tag (the tag -> commits mapping)
const tagCommits = ref<CommitInfo[]>([])
const tagCommitCount = ref(0)
const tagCommitsLoading = ref(false)
const tagTruncated = ref(false)

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
// The draft / edit panel is only rendered while it is actually needed
const editorOpen = ref(false)

// ------------------------------------------------------------------ #
// Theme
// ------------------------------------------------------------------ #

// md-editor-v3 switches to its dark palette through the ``theme`` prop (the
// ``.md-editor-dark`` class), it does not follow the app theme by itself.
const themeTrigger = ref(0)
const isDarkTheme = computed(() => {
  void themeTrigger.value
  return document.documentElement.getAttribute('data-theme') === 'dark'
})
const mdTheme = computed<'dark' | 'light'>(() => (isDarkTheme.value ? 'dark' : 'light'))

let themeObserver: MutationObserver | null = null

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

// Newest first: versions compare numerically so v1.10.0 sorts above v1.9.0
const sortedTags = computed(() =>
  [...tags.value].sort((a, b) => b.localeCompare(a, undefined, { numeric: true })),
)
const visibleTags = computed(() => {
  const start = (tagPage.value - 1) * tagPageSize.value
  return sortedTags.value.slice(start, start + tagPageSize.value)
})
// The release scope of a tag runs from the next older tag to the tag itself
const tagPrevious = computed(() =>
  selectedTag.value ? previousTagFor(selectedTag.value) : null,
)

// Header of the right column: the editor, the selected release or the tag commits
const detailTitle = computed(() => {
  if (editorOpen.value) {
    return editingId.value ? t('releaseNotes.edit_release') : t('releaseNotes.draft_new')
  }
  if (tabIsTags.value) {
    return selectedTag.value
      ? t('releaseNotes.tag_commits_title', { tag: selectedTag.value })
      : t('releaseNotes.select_title')
  }
  if (selectedNote.value) {
    return selectedNote.value.name
  }
  return t('releaseNotes.select_title')
})

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

/** The tag released just before ``tag`` (the base of its release scope). */
function previousTagFor(tag: string): string | null {
  const index = sortedTags.value.indexOf(tag)
  return index >= 0 ? (sortedTags.value[index + 1] ?? null) : null
}

/** Select a stored release and show its notes. */
function selectNote(note: ReleaseNote) {
  closeForm()
  selectedId.value = note.id
}

/** Select a tag and show the commits it released. */
function selectTag(tag: string) {
  closeForm()
  selectedTag.value = tag
  void loadTagCommits(tag)
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
    tagPage.value = 1
    // The tags tab always has a selection so the commits of a tag are visible
    if (tabIsTags.value && !selectedTag.value) {
      const newest = sortedTags.value[0]
      if (newest) {
        selectTag(newest)
      }
    }
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
      limit: notesPageSize.value,
      offset: (notesPage.value - 1) * notesPageSize.value,
    })
    notes.value = response.items ?? []
    notesTotal.value = response.total ?? notes.value.length
    // Keep the selection meaningful: fall back to the first release of the page
    if (!notes.value.some((note) => note.id === selectedId.value)) {
      selectedId.value = notes.value[0]?.id ?? null
    }
  } catch {
    ElMessage.error(t('releaseNotes.load_failed'))
  } finally {
    notesLoading.value = false
  }
}

/**
 * Load the commits of a tag's release scope (from the previous tag to the tag).
 *
 * This is the tag -> commits mapping shown in the tags tab; the generated note
 * body of the same scope is ignored on purpose.
 */
async function loadTagCommits(tag: string) {
  tagCommits.value = []
  tagCommitCount.value = 0
  tagTruncated.value = false
  if (!hasCoordinates.value) return

  tagCommitsLoading.value = true
  try {
    const response = await releaseNotesApi.preview({
      ...coordinates(),
      version: tag,
      previous_version: previousTagFor(tag) ?? undefined,
      max_commits: PREVIEW_MAX_COMMITS,
    })
    // a newer click may have overtaken this response
    if (selectedTag.value !== tag) return
    tagCommits.value = (response.commits ?? []) as CommitInfo[]
    tagCommitCount.value = response.commit_count ?? tagCommits.value.length
    tagTruncated.value = Boolean(response.truncated)
  } catch {
    ElMessage.error(t('releaseNotes.commits_load_failed'))
  } finally {
    tagCommitsLoading.value = false
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

/**
 * Notes link to the git platform (commit links, the "Full Changelog" comparison):
 * open them in a new tab so the release page is not replaced.
 */
function openNoteLink(event: MouseEvent) {
  const href = (event.target as HTMLElement | null)?.closest?.('a')?.getAttribute('href')
  if (!href) {
    return
  }
  event.preventDefault()
  window.open(href, '_blank', 'noopener,noreferrer')
}

/** Close the draft / edit panel and clear the form. */
function closeForm() {
  resetForm()
  editorOpen.value = false
}

function startNewRelease(tag?: string) {
  resetForm()
  editorOpen.value = true
  // Draft from the clicked tag, or preselect the newest one
  const initial = tag ?? tags.value[0]
  if (initial) {
    form.value.tag_name = initial
  }
  formCard.value?.scrollIntoView?.({ behavior: 'smooth', block: 'start' })
}

function editNote(note: ReleaseNote) {
  selectedId.value = note.id
  selectedTag.value = null
  editingId.value = note.id
  editingStatus.value = note.status
  generatedCount.value = null
  editorOpen.value = true
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

    closeForm()
    // Show what was just written instead of falling back to the newest release
    selectedId.value = saved.id
    selectedTag.value = null
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
      closeForm()
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
    // Another repository means another release: drop a half filled draft as well
    closeForm()
    selectedId.value = null
    selectedTag.value = null
    tagCommits.value = []
    tagCommitCount.value = 0
    notesPage.value = 1
    tagPage.value = 1
    void loadRefs()
    void loadNotes()
  },
)

// Releases are paged on the server, tags in the browser
watch(notesPage, () => void loadNotes())

// Changing the page size always restarts from the first page
watch(notesPageSize, () => {
  if (notesPage.value === 1) {
    void loadNotes()
  } else {
    notesPage.value = 1
  }
})

watch(tagPageSize, () => {
  tagPage.value = 1
})

// The tags tab maps a tag to the commits it released: pick the newest tag when
// the tab is opened without an explicit selection
watch(activeTab, (tab) => {
  if (tab === 'tags' && !selectedTag.value) {
    const newest = sortedTags.value[0]
    if (newest) {
      selectTag(newest)
    }
  }
})

onMounted(() => {
  // The theme lives on the <html> element, so watch it instead of re-reading it
  // on every render
  themeObserver = new MutationObserver(() => {
    themeTrigger.value++
  })
  themeObserver.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['data-theme', 'class'],
  })
  void loadProjects()
})

onBeforeUnmount(() => {
  themeObserver?.disconnect()
  themeObserver = null
})
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
.form-anchor,
.detail-card {
  height: 100%;
}

.loading-block {
  padding: 8px 0;
}

/* Navigator: releases and tags of the repository, one tab each */
.nav-tabs :deep(.el-tabs__header) {
  margin-bottom: 12px;
}

.nav-tabs :deep(.el-tabs__item) {
  padding: 0 12px;
}

.nav-section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.nav-pagination {
  margin-top: 10px;
  justify-content: flex-end;
}

.nav-pagination :deep(.el-pagination__total),
.nav-pagination :deep(.el-pagination__sizes) {
  margin-right: auto;
}

.nav-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 520px;
  margin: 0;
  padding: 0 4px 0 0;
  overflow-y: auto;
  list-style: none;
}

.nav-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px 10px;
  border: 1px solid transparent;
  border-radius: 8px;
  cursor: pointer;
  transition: background-color 0.15s ease, border-color 0.15s ease;
}

.nav-item:hover {
  background: var(--el-fill-color-light);
}

.nav-item.active {
  border-color: var(--el-color-primary-light-5);
  background: var(--el-color-primary-light-9);
}

.nav-item-main {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.nav-item-name {
  font-weight: 600;
  overflow-wrap: anywhere;
}

.nav-item-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.nav-item-meta {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.tag-item .nav-item-main {
  justify-content: space-between;
}

.detail-card .release-meta {
  margin-top: 0;
}

.detail-card .release-body {
  margin-top: 12px;
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

/* The card already provides the surface: keep the rendered markdown on it instead
   of letting md-editor paint its own (pure black in dark mode) background */
.release-body :deep(.md-editor),
.release-body :deep(.md-editor-preview-wrapper),
.release-body :deep(.md-editor-preview),
.notes-editor :deep(.md-editor) {
  background-color: transparent;
}

.notes-editor :deep(.md-editor) {
  border-radius: 8px;
}

/* md-editor ships its own dark palette (black surfaces) - blend it with the app one */
[data-theme='dark'] .release-body :deep(.md-editor),
[data-theme='dark'] .notes-editor :deep(.md-editor) {
  --md-bk-color: var(--el-bg-color);
  --md-bk-color-outstand: var(--el-fill-color);
  --md-border-color: var(--el-border-color);
  --md-color: var(--el-text-color-primary);
}

[data-theme='dark'] .release-body :deep(.github-theme) {
  --md-theme-color: var(--el-text-color-regular);
  --md-theme-heading-color: var(--el-text-color-primary);
  --md-theme-heading-bg-color: transparent;
  --md-theme-heading-1-border: 1px solid var(--el-border-color);
  --md-theme-heading-2-border: 1px solid var(--el-border-color);
  --md-theme-quote-color: var(--el-text-color-secondary);
  --md-theme-quote-border: 0.25em solid var(--el-border-color);
  --md-theme-table-stripe-color: var(--el-fill-color);
  --md-theme-table-td-border-color: var(--el-border-color);
  --md-theme-code-inline-bg-color: var(--el-fill-color);
  --md-theme-code-block-bg-color: var(--el-fill-color-light);
  --md-theme-code-before-bg-color: var(--el-fill-color-light);
  --md-theme-link-color: var(--el-color-primary-light-3);
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
