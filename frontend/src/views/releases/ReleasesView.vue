<template>
  <div class="releases-container">
    <el-card shadow="never" class="context-card">
      <template #header>
        <div class="card-header">
          <div>
            <h2>{{ t('releaseDiff.title') }}</h2>
            <p class="subtitle">{{ t('releaseDiff.subtitle') }}</p>
          </div>
        </div>
      </template>

      <!-- Repository coordinates shared by both tools -->
      <el-form :model="repo" label-width="150px" class="repo-form">
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
                  :label="`${project.project_key} - ${project.project_name}`"
                  :value="project.project_key"
                >
                  <span class="option-key">{{ project.project_key }}</span>
                  <span class="option-name">{{ project.project_name }}</span>
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
                >
                  <span class="option-key">{{ repository.repository_slug }}</span>
                  <span class="option-name">{{ repository.repository_name }}</span>
                </el-option>
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
          <el-col :xs="24" :sm="12" :md="6">
            <el-form-item :label="t('releaseDiff.max_commits')">
              <el-input-number v-model="maxCommits" :min="1" :max="5000" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

    </el-card>

    <!-- ================= Compare two releases ================= -->
    <div ref="compareSection" class="tool-section">
      <el-card shadow="never">
        <template #header>
          <div class="section-header">
            <div>
              <h3>
                <el-tag size="small" round type="primary">1</el-tag>
                {{ t('releaseDiff.tab_compare') }}
              </h3>
              <p class="subtitle">{{ t('releaseDiff.compare_help') }}</p>
            </div>
          </div>
        </template>

        <el-form :model="compareForm" label-width="180px">
          <el-row :gutter="16">
            <el-col :xs="24" :md="12">
              <el-form-item :label="t('releaseDiff.old_release_ref')" required>
                <el-input
                  v-model="compareForm.old_release_ref"
                  :placeholder="t('releaseDiff.ref_placeholder')"
                />
              </el-form-item>
            </el-col>
            <el-col :xs="24" :md="12">
              <el-form-item :label="t('releaseDiff.new_release_ref')" required>
                <el-input
                  v-model="compareForm.new_release_ref"
                  :placeholder="t('releaseDiff.ref_placeholder')"
                />
              </el-form-item>
            </el-col>
          </el-row>

          <div class="scope-block">
            <el-switch
              v-model="compareScopeEnabled"
              size="small"
              @change="onCompareScopeToggle"
            />
            <span class="scope-title">{{ t('releaseDiff.scope_toggle') }}</span>
            <el-tooltip :content="t('releaseDiff.scope_help')" placement="top" :show-after="100">
              <el-icon class="help-icon"><QuestionFilled /></el-icon>
            </el-tooltip>
          </div>

          <el-row v-if="compareScopeEnabled" :gutter="16">
            <el-col :xs="24" :md="10">
              <el-form-item :label="t('releaseDiff.old_release_base_ref')">
                <el-input
                  v-model="compareForm.old_release_base_ref"
                  :placeholder="t('releaseDiff.base_ref_placeholder')"
                />
              </el-form-item>
              <div class="scope-preview">
                {{ t('releaseDiff.scope_of') }} {{ t('releaseDiff.old_release_ref') }}:
                <code>{{ scopeText(compareForm.old_release_base_ref, compareForm.old_release_ref) }}</code>
              </div>
            </el-col>
            <el-col :xs="24" :md="10">
              <el-form-item :label="t('releaseDiff.new_release_base_ref')">
                <el-input
                  v-model="compareForm.new_release_base_ref"
                  :placeholder="t('releaseDiff.base_ref_placeholder')"
                />
              </el-form-item>
              <div class="scope-preview">
                {{ t('releaseDiff.scope_of') }} {{ t('releaseDiff.new_release_ref') }}:
                <code>{{ scopeText(compareForm.new_release_base_ref, compareForm.new_release_ref) }}</code>
              </div>
            </el-col>
            <el-col :xs="24" :md="4">
              <el-button
                link
                type="primary"
                :disabled="!compareForm.old_release_ref.trim()"
                @click="useOldAsNewBase"
              >
                {{ t('releaseDiff.scope_use_old_as_new_base') }}
              </el-button>
            </el-col>
          </el-row>

          <div class="actions">
            <el-checkbox v-model="includeCommits">
              {{ t('releaseDiff.include_commits') }}
            </el-checkbox>
            <el-button type="primary" :loading="compareLoading" @click="runCompare">
              {{ t('releaseDiff.run_compare') }}
            </el-button>
            <el-button @click="resetCompare">{{ t('releaseDiff.reset') }}</el-button>
          </div>
        </el-form>

        <div v-if="compareResult" class="result-block">
          <el-alert
            :type="compareAlertType"
            :title="compareStatusText"
            :closable="false"
            show-icon
            class="status-alert"
          />
          <el-alert
            v-if="compareResult.truncated"
            type="warning"
            :title="t('releaseDiff.truncated_warning')"
            :closable="false"
            class="status-alert"
          />

          <div v-if="compareResult.missing_commits.length" class="result-actions">
            <el-button size="small" type="warning" plain @click="sendMissingToCheck">
              {{ t('releaseDiff.send_missing_to_check') }}
            </el-button>
          </div>

          <div class="scope-used">
            <el-tag size="small" type="info">
              {{ t('releaseDiff.old_release_ref') }}:
              {{ scopeText(compareResult.old_release_base_ref, compareResult.old_release_ref) }}
            </el-tag>
            <el-tag size="small" type="info">
              {{ t('releaseDiff.new_release_ref') }}:
              {{ scopeText(compareResult.new_release_base_ref, compareResult.new_release_ref) }}
            </el-tag>
          </div>

          <el-row :gutter="16" class="stat-row">
            <el-col :xs="12" :md="6">
              <div class="stat-card">
                <span class="stat-value">{{ compareResult.summary.old_commit_count ?? 0 }}</span>
                <span class="stat-label">{{ t('releaseDiff.old_commit_count') }}</span>
              </div>
            </el-col>
            <el-col :xs="12" :md="6">
              <div class="stat-card">
                <span class="stat-value">{{ compareResult.summary.new_commit_count ?? 0 }}</span>
                <span class="stat-label">{{ t('releaseDiff.new_commit_count') }}</span>
              </div>
            </el-col>
            <el-col :xs="12" :md="4">
              <div class="stat-card danger">
                <span class="stat-value">{{ compareResult.summary.missing_count ?? 0 }}</span>
                <span class="stat-label">{{ t('releaseDiff.missing_count') }}</span>
              </div>
            </el-col>
            <el-col :xs="12" :md="4">
              <div class="stat-card success">
                <span class="stat-value">{{ compareResult.summary.added_count ?? 0 }}</span>
                <span class="stat-label">{{ t('releaseDiff.added_count') }}</span>
              </div>
            </el-col>
            <el-col :xs="12" :md="4">
              <div class="stat-card">
                <span class="stat-value">{{ compareResult.summary.common_count ?? 0 }}</span>
                <span class="stat-label">{{ t('releaseDiff.common_count') }}</span>
              </div>
            </el-col>
          </el-row>

          <el-collapse v-model="openSections">
            <el-collapse-item
              :title="`${t('releaseDiff.missing_commits_title')} (${compareResult.missing_commits.length})`"
              name="missing"
            >
              <commit-table :commits="compareResult.missing_commits" />
            </el-collapse-item>
            <el-collapse-item
              :title="`${t('releaseDiff.added_commits_title')} (${compareResult.added_commits.length})`"
              name="added"
            >
              <commit-table :commits="compareResult.added_commits" />
            </el-collapse-item>
            <el-collapse-item
              :title="`${t('releaseDiff.old_release_commits_title')} (${compareResult.old_release_commits.length})`"
              name="old"
            >
              <commit-table :commits="compareResult.old_release_commits" />
            </el-collapse-item>
            <el-collapse-item
              :title="`${t('releaseDiff.new_release_commits_title')} (${compareResult.new_release_commits.length})`"
              name="new"
            >
              <commit-table :commits="compareResult.new_release_commits" />
            </el-collapse-item>
          </el-collapse>
        </div>

        <el-empty v-else :description="t('releaseDiff.empty_result')" />
        </el-card>
      </div>

    <!-- ================= Check commits ================= -->
    <div ref="checkSection" class="tool-section">
      <el-card shadow="never">
        <template #header>
          <div class="section-header">
            <div>
              <h3>
                <el-tag size="small" round type="primary">2</el-tag>
                {{ t('releaseDiff.tab_check') }}
              </h3>
              <p class="subtitle">{{ t('releaseDiff.check_help') }}</p>
            </div>
          </div>
        </template>

        <el-form :model="checkForm" label-width="180px">
          <el-row :gutter="16">
            <el-col :xs="24" :md="12">
              <el-form-item :label="t('releaseDiff.target_release_ref')" required>
                <el-input
                  v-model="checkForm.target_release_ref"
                  :placeholder="t('releaseDiff.ref_placeholder')"
                />
              </el-form-item>
            </el-col>
          </el-row>

          <div class="scope-block">
            <el-switch v-model="checkScopeEnabled" size="small" @change="onCheckScopeToggle" />
            <span class="scope-title">{{ t('releaseDiff.scope_toggle') }}</span>
            <el-tooltip :content="t('releaseDiff.scope_help')" placement="top" :show-after="100">
              <el-icon class="help-icon"><QuestionFilled /></el-icon>
            </el-tooltip>
          </div>

          <el-row v-if="checkScopeEnabled" :gutter="16">
            <el-col :xs="24" :md="12">
              <el-form-item :label="t('releaseDiff.target_release_base_ref')">
                <el-input
                  v-model="checkForm.target_release_base_ref"
                  :placeholder="t('releaseDiff.base_ref_placeholder')"
                />
              </el-form-item>
              <div class="scope-preview">
                {{ t('releaseDiff.scope_of') }} {{ t('releaseDiff.target_release_ref') }}:
                <code>{{ scopeText(checkForm.target_release_base_ref, checkForm.target_release_ref) }}</code>
              </div>
            </el-col>
          </el-row>

          <el-form-item :label="t('releaseDiff.commits_input')" required>
            <el-input
              v-model="commitsInput"
              type="textarea"
              :rows="6"
              :placeholder="t('releaseDiff.commits_placeholder')"
            />
          </el-form-item>

          <div class="actions">
            <el-button type="primary" :loading="checkLoading" @click="runCheck">
              {{ t('releaseDiff.run_check') }}
            </el-button>
            <el-button @click="resetCheck">{{ t('releaseDiff.reset') }}</el-button>
          </div>
        </el-form>

        <div v-if="checkResult" class="result-block">
          <el-alert
            :type="checkResult.all_included ? 'success' : 'warning'"
            :title="
              checkResult.all_included
                ? t('releaseDiff.status_included')
                : t('releaseDiff.status_missing')
            "
            :closable="false"
            show-icon
            class="status-alert"
          />
          <el-alert
            v-if="checkResult.truncated"
            type="warning"
            :title="t('releaseDiff.truncated_warning')"
            :closable="false"
            class="status-alert"
          />

          <el-row :gutter="16" class="stat-row">
            <el-col :xs="12" :md="6">
              <div class="stat-card">
                <span class="stat-value">{{ checkResult.summary.requested ?? 0 }}</span>
                <span class="stat-label">{{ t('releaseDiff.requested') }}</span>
              </div>
            </el-col>
            <el-col :xs="12" :md="6">
              <div class="stat-card success">
                <span class="stat-value">{{ checkResult.summary.included_count ?? 0 }}</span>
                <span class="stat-label">{{ t('releaseDiff.included_count') }}</span>
              </div>
            </el-col>
            <el-col :xs="12" :md="6">
              <div class="stat-card danger">
                <span class="stat-value">{{ checkResult.summary.missing_count ?? 0 }}</span>
                <span class="stat-label">{{ t('releaseDiff.missing_count') }}</span>
              </div>
            </el-col>
            <el-col :xs="12" :md="6">
              <div class="stat-card">
                <span class="stat-value">{{ checkResult.summary.release_commit_count ?? 0 }}</span>
                <span class="stat-label">{{ t('releaseDiff.release_commit_count') }}</span>
              </div>
            </el-col>
          </el-row>

          <el-table :data="checkResult.results" stripe style="width: 100%">
            <el-table-column :label="t('releaseDiff.col_commit')" min-width="220">
              <template #default="{ row }">
                <span class="commit-sha" @click="copySha(row.matched_id || row.commit)">
                  {{ row.matched_id || row.commit }}
                </span>
              </template>
            </el-table-column>
            <el-table-column :label="t('releaseDiff.col_status')" width="140">
              <template #default="{ row }">
                <el-tag :type="row.included ? 'success' : 'danger'" size="small">
                  {{
                    row.included ? t('releaseDiff.result_included') : t('releaseDiff.result_missing')
                  }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column :label="t('releaseDiff.col_author')" width="180">
              <template #default="{ row }">
                {{ row.commit_info?.author_name || '-' }}
              </template>
            </el-table-column>
            <el-table-column :label="t('releaseDiff.col_date')" width="180">
              <template #default="{ row }">
                {{ formatTimestamp(row.commit_info?.author_timestamp) }}
              </template>
            </el-table-column>
            <el-table-column :label="t('releaseDiff.col_message')" min-width="260">
              <template #default="{ row }">
                {{ firstLine(row.commit_info?.message) }}
              </template>
            </el-table-column>
          </el-table>
        </div>

        <el-empty v-else :description="t('releaseDiff.empty_result')" />
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { QuestionFilled } from '@element-plus/icons-vue'
import dayjs from 'dayjs'
import CommitTable from '@/components/release/CommitTable.vue'
import { projectsApi } from '@/api/projects'
import type { ProjectSummary, RepositorySummary } from '@/api/projects'
import {
  releaseDiffApi,
  type ReleaseCommitCheckResponse,
  type ReleaseCompareResponse,
} from '@/api/releaseDiff'

const { t } = useI18n()

const projects = ref<ProjectSummary[]>([])
const repositories = ref<RepositorySummary[]>([])
const projectsLoading = ref(false)
const repositoriesLoading = ref(false)

const compareSection = ref<HTMLElement | null>(null)
const checkSection = ref<HTMLElement | null>(null)
const compareLoading = ref(false)
const checkLoading = ref(false)
const compareScopeEnabled = ref(false)
const checkScopeEnabled = ref(false)
const includeCommits = ref(true)
const maxCommits = ref(1000)
const openSections = ref<string[]>(['missing', 'added'])

const repo = ref({
  project_key: '' as string,
  repository_slug: '' as string,
  git_provider: null as string | null,
})

const compareForm = ref({
  old_release_ref: '',
  new_release_ref: '',
  old_release_base_ref: '',
  new_release_base_ref: '',
})

const checkForm = ref({
  target_release_ref: '',
  target_release_base_ref: '',
})

const commitsInput = ref('')
const compareResult = ref<ReleaseCompareResponse | null>(null)
const checkResult = ref<ReleaseCommitCheckResponse | null>(null)

const compareAlertType = computed<'success' | 'warning' | 'info'>(() => {
  if (!compareResult.value) return 'info'
  if (compareResult.value.status === 'identical') return 'info'
  return compareResult.value.old_commits_included ? 'success' : 'warning'
})

const compareStatusText = computed(() => {
  if (!compareResult.value) return ''
  if (compareResult.value.status === 'identical') return t('releaseDiff.status_identical')
  return compareResult.value.old_commits_included
    ? t('releaseDiff.status_included')
    : t('releaseDiff.status_missing')
})

// el-select emits undefined when cleared - always work with trimmed strings
const selectedProjectKey = computed(() => (repo.value.project_key ?? '').trim())
const selectedRepositorySlug = computed(() => (repo.value.repository_slug ?? '').trim())

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
  if (!projectKey) {
    return
  }

  repositoriesLoading.value = true
  try {
    repositories.value = await projectsApi.getProjectRepositories(projectKey)
  } catch {
    ElMessage.error(t('releaseDiff.load_repositories_failed'))
  } finally {
    repositoriesLoading.value = false
  }
}

watch(
  () => repo.value.project_key,
  (projectKey) => {
    const key = (projectKey || '').trim()
    const project = projects.value.find((item) => item.project_key === key)

    repo.value.repository_slug = ''
    repo.value.git_provider = project?.git_provider || null

    // Unknown project keys (typed manually) have no local repository catalog
    repositories.value = []
    if (project) {
      void loadRepositories(key)
    }
  },
)

onMounted(loadProjects)

function basePayload() {
  return {
    project_key: selectedProjectKey.value,
    repository_slug: selectedRepositorySlug.value,
    git_provider: repo.value.git_provider || undefined,
  }
}

function optionalRef(value: string): string | undefined {
  const trimmed = value.trim()
  return trimmed || undefined
}

// A base ref is the exclusive lower bound of a release: only commits
// reachable from the release ref but not from the base ref count as
// "belonging to that release". Without it the whole history is used.
function scopeText(baseRef: string | null | undefined, releaseRef: string): string {
  const base = (baseRef ?? '').trim()
  const release = (releaseRef ?? '').trim() || '?'
  return base ? `${base}..${release}` : t('releaseDiff.scope_full_history', { ref: release })
}

function onCompareScopeToggle(enabled: boolean) {
  if (!enabled) {
    compareForm.value.old_release_base_ref = ''
    compareForm.value.new_release_base_ref = ''
  }
}

function onCheckScopeToggle(enabled: boolean) {
  if (!enabled) {
    checkForm.value.target_release_base_ref = ''
  }
}

function useOldAsNewBase() {
  compareForm.value.new_release_base_ref = compareForm.value.old_release_ref.trim()
}

function resetCompare() {
  compareForm.value = {
    old_release_ref: '',
    new_release_ref: '',
    old_release_base_ref: '',
    new_release_base_ref: '',
  }
  compareScopeEnabled.value = false
  compareResult.value = null
}

function resetCheck() {
  checkForm.value = {
    target_release_ref: '',
    target_release_base_ref: '',
  }
  checkScopeEnabled.value = false
  commitsInput.value = ''
  checkResult.value = null
}

async function scrollTo(element: HTMLElement | null) {
  await nextTick()
  element?.scrollIntoView?.({ behavior: 'smooth', block: 'start' })
}

async function sendMissingToCheck() {
  const shas = (compareResult.value?.missing_commits ?? []).map((commit) => commit.id)
  if (shas.length === 0) {
    return
  }

  commitsInput.value = shas.join('\n')
  ElMessage.success(t('releaseDiff.sent_missing_to_check', { count: shas.length }))
  await scrollTo(checkSection.value)
}

async function runCompare() {
  if (
    !selectedProjectKey.value ||
    !selectedRepositorySlug.value ||
    !compareForm.value.old_release_ref.trim() ||
    !compareForm.value.new_release_ref.trim()
  ) {
    ElMessage.warning(t('releaseDiff.validation_required'))
    return
  }

  compareLoading.value = true
  try {
    compareResult.value = await releaseDiffApi.compare({
      ...basePayload(),
      old_release_ref: compareForm.value.old_release_ref.trim(),
      new_release_ref: compareForm.value.new_release_ref.trim(),
      old_release_base_ref: compareScopeEnabled.value
        ? optionalRef(compareForm.value.old_release_base_ref)
        : undefined,
      new_release_base_ref: compareScopeEnabled.value
        ? optionalRef(compareForm.value.new_release_base_ref)
        : undefined,
      include_commits: includeCommits.value,
      max_commits: maxCommits.value,
    })
  } catch {
    ElMessage.error(t('releaseDiff.compare_failed'))
  } finally {
    compareLoading.value = false
  }
}

async function runCheck() {
  const commits = commitsInput.value
    .split(/[\n,\s]+/)
    .map((item) => item.trim())
    .filter(Boolean)

  if (
    !selectedProjectKey.value ||
    !selectedRepositorySlug.value ||
    !checkForm.value.target_release_ref.trim() ||
    commits.length === 0
  ) {
    ElMessage.warning(t('releaseDiff.validation_commits_required'))
    return
  }

  checkLoading.value = true
  try {
    checkResult.value = await releaseDiffApi.check({
      ...basePayload(),
      target_release_ref: checkForm.value.target_release_ref.trim(),
      target_release_base_ref: checkScopeEnabled.value
        ? optionalRef(checkForm.value.target_release_base_ref)
        : undefined,
      commits,
      max_commits: maxCommits.value,
    })
  } catch {
    ElMessage.error(t('releaseDiff.check_failed'))
  } finally {
    checkLoading.value = false
  }
}

function formatTimestamp(value?: number | null): string {
  if (!value) return '-'
  return dayjs(value).format('YYYY-MM-DD HH:mm')
}

function firstLine(message?: string | null): string {
  if (!message) return '-'
  return message.split('\n')[0]
}

async function copySha(value: string) {
  try {
    await navigator.clipboard.writeText(value)
    ElMessage.success(t('releaseDiff.copied'))
  } catch {
    ElMessage.info(value)
  }
}

</script>

<style scoped>
.releases-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 4px;
}

.tool-section {
  scroll-margin-top: 16px;
}

.section-header h3 {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  font-size: 16px;
  font-weight: 600;
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

.repo-form {
  margin-bottom: 8px;
}

.result-actions {
  margin-bottom: 12px;
}

.actions {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 8px;
}

.result-block {
  margin-top: 20px;
}

.status-alert {
  margin-bottom: 12px;
}

.stat-row {
  margin-bottom: 16px;
}

.stat-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 12px 8px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  background: var(--el-fill-color-lighter);
}

.stat-card.success {
  border-color: var(--el-color-success-light-5);
  background: var(--el-color-success-light-9);
}

.stat-card.danger {
  border-color: var(--el-color-danger-light-5);
  background: var(--el-color-danger-light-9);
}

.stat-value {
  font-size: 22px;
  font-weight: 700;
}

.stat-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.commit-sha {
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', monospace;
  font-size: 12px;
  color: var(--el-color-primary);
  cursor: pointer;
}

:deep(.el-select-dropdown__item) .option-key {
  font-weight: 600;
}

:deep(.el-select-dropdown__item) .option-name {
  margin-left: 8px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.scope-block {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 4px 0 12px;
}

.scope-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-regular);
}

.help-icon {
  color: var(--el-text-color-secondary);
  cursor: help;
}

.scope-preview {
  margin: -6px 0 12px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.scope-preview code {
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', monospace;
  color: var(--el-color-primary);
}

.scope-used {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}
</style>
