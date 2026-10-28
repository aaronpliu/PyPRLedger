<template>
  <div class="rules-management-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <div class="header-title-group">
            <h2>{{ t('auto_rules.management_title') }}</h2>
            <el-tag type="info">{{ t('auto_rules.review_admin_only') }}</el-tag>
          </div>
          <div class="header-actions">
            <el-button type="primary" @click="openCreateDialog">
              <el-icon><Plus /></el-icon>
              {{ t('auto_rules.create_rule') }}
            </el-button>
            <el-button @click="loadRules">
              <el-icon><Refresh /></el-icon>
              {{ t('auto_rules.refresh') }}
            </el-button>
          </div>
        </div>
      </template>

      <!-- App Name Filter -->
      <div v-if="rules.length > 0" class="app-filter-bar">
        <el-select
          v-model="appFilter"
          placeholder="All Applications"
          clearable
          style="width: 250px"
          @change="currentPage = 1"
        >
          <el-option
            v-for="app in appOptions"
            :key="app.app_name"
            :label="app.app_name"
            :value="app.app_name"
          />
        </el-select>
        <span v-if="appFilter" class="filter-hint">
          Showing rules matching {{ appFilter }}
        </span>
      </div>

      <!-- Empty State -->
      <div v-if="!loading && rules.length === 0" class="empty-state">
        <el-empty :description="t('auto_rules.empty_description')">
          <el-button type="primary" @click="openCreateDialog">
            <el-icon><Plus /></el-icon>
            {{ t('auto_rules.create_rule') }}
          </el-button>
        </el-empty>
      </div>

      <!-- Rules Table -->
      <div v-else>
        <div class="table-wrapper">
        <el-table
          :data="displayRules"
          v-loading="loading"
          stripe
          border
          style="width: 100%"
        >
          <el-table-column prop="name" :label="t('auto_rules.col_name')" min-width="160" />
          <el-table-column prop="priority" :label="t('auto_rules.col_priority')" width="80" align="center" />
          <el-table-column :label="t('auto_rules.col_conditions')" min-width="200">
            <template #default="{ row }">
              <el-tooltip
                placement="top"
                trigger="click"
                :content="formatConditionsJson(row.conditions)"
              >
                <span class="conditions-preview">{{ truncateConditions(row.conditions) }}</span>
              </el-tooltip>
            </template>
          </el-table-column>
          <el-table-column :label="t('auto_rules.col_assign_to')" min-width="160">
            <template #default="{ row }">
              <el-tag
                v-for="username in row.assign_to"
                :key="username"
                size="small"
                style="margin: 2px"
              >
                {{ username }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column :label="t('auto_rules.col_starts_at')" width="175" align="center">
            <template #default="{ row }">
              <span class="date-cell" :class="{ 'date-null': !row.starts_at }">
                {{ formatDateTime(row.starts_at) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column :label="t('auto_rules.col_expires_at')" width="175" align="center">
            <template #default="{ row }">
              <span class="date-cell" :class="{ 'date-null': !row.expires_at }">
                {{ formatDateTime(row.expires_at) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column :label="t('auto_rules.col_status')" width="100" align="center">
            <template #default="{ row }">
              <el-switch
                :model-value="row.is_active"
                :loading="togglingId === row.id"
                @change="(val: boolean) => handleToggle(row, val)"
              />
            </template>
          </el-table-column>
          <el-table-column :label="t('auto_rules.col_created')" width="110">
            <template #default="{ row }">
              {{ formatDate(row.created_at) }}
            </template>
          </el-table-column>
          <!-- The day a rule last changed says whether it was edited or switched off
               since; the hour and minute are a hover away rather than another column -->
          <el-table-column :label="t('auto_rules.col_updated')" width="110">
            <template #default="{ row }">
              <span :title="formatDateTime(row.updated_at)">
                {{ formatDate(row.updated_at) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column :label="t('auto_rules.col_actions')" width="140" fixed="right" align="center">
            <template #default="{ row }">
              <el-button size="small" type="primary" link @click="openEditDialog(row)">
                <el-icon><Edit /></el-icon>
                {{ t('auto_rules.edit') }}
              </el-button>
              <el-button size="small" type="danger" link @click="handleDelete(row)">
                <el-icon><Delete /></el-icon>
                {{ t('auto_rules.delete') }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        </div>

        <!-- Pagination -->
        <div class="pagination-wrapper">
          <el-pagination
            v-model:current-page="currentPage"
            v-model:page-size="pageSize"
            :total="displayRules.length"
            :page-sizes="[10, 20, 50, 100]"
            layout="total, sizes, prev, pager, next"
            @current-change="loadRules"
            @size-change="loadRules"
          />
        </div>
      </div>
    </el-card>

    <!-- Create/Edit Dialog -->
    <!-- Room for two columns where the screen allows it, one where it does not, and a
         body that scrolls inside the dialog: Cancel and Save stay in reach whatever
         the window height. -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEditing ? t('auto_rules.edit_rule') : t('auto_rules.create_rule')"
      width="min(1024px, 92vw)"
      body-class="rule-dialog-body"
      :close-on-click-modal="false"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="formRules"
        label-position="top"
        class="rule-form"
      >
        <!-- Two columns, so the whole rule fits a screen: what the rule is and who
             reviews on the left, what it matches on the right. Six stacked sections
             used to run past the viewport and put Save below the fold. -->
        <el-row :gutter="28">
          <el-col :xs="24" :md="12">
            <h3 class="section-title">{{ t('auto_rules.section_basic') }}</h3>

            <el-form-item :label="t('auto_rules.f_name')" prop="name">
              <el-input v-model="form.name" :placeholder="t('auto_rules.f_name_placeholder')" maxlength="128" />
            </el-form-item>

            <el-form-item :label="t('auto_rules.f_description')" prop="description">
              <el-input
                v-model="form.description"
                type="textarea"
                :rows="2"
                :placeholder="t('auto_rules.f_description_placeholder')"
                maxlength="1000"
              />
            </el-form-item>

            <el-form-item :label="t('auto_rules.f_priority')" prop="priority">
              <el-input-number v-model="form.priority" :min="0" :max="9999" style="width: 100%" />
            </el-form-item>

            <h3 class="section-title">{{ t('auto_rules.section_assign') }}</h3>

            <el-form-item :label="t('auto_rules.f_assign_to')" prop="assign_to">
              <el-select
                v-model="form.assign_to"
                class="tag-select"
                multiple
                filterable
                clearable
                :placeholder="t('auto_rules.f_assign_to_placeholder')"
                style="width: 100%"
              >
                <el-option
                  v-for="u in reviewerUsers"
                  :key="u.username"
                  :label="`${u.display_name} (${u.username})`"
                  :value="u.username"
                />
              </el-select>
              <div class="form-help-text">{{ t('auto_rules.f_assign_to_hint') }}</div>
            </el-form-item>

            <h3 class="section-title">{{ t('auto_rules.section_temporal') }}</h3>

            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item :label="t('auto_rules.f_starts_at')" prop="starts_at">
                  <el-date-picker
                    v-model="form.starts_at"
                    type="datetime"
                    :placeholder="t('auto_rules.f_date_placeholder')"
                    style="width: 100%"
                    clearable
                  />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item :label="t('auto_rules.f_expires_at')" prop="expires_at">
                  <el-date-picker
                    v-model="form.expires_at"
                    type="datetime"
                    :placeholder="t('auto_rules.f_date_placeholder')"
                    style="width: 100%"
                    clearable
                  />
                </el-form-item>
              </el-col>
            </el-row>

            <el-form-item :label="t('auto_rules.f_is_active')">
              <el-switch v-model="form.is_active" />
            </el-form-item>
          </el-col>

          <el-col :xs="24" :md="12">
            <h3 class="section-title">{{ t('auto_rules.section_conditions') }}</h3>

            <el-form-item label="App Name">
              <el-select
                v-model="cond.app_name"
                class="tag-select"
                multiple
                filterable
                clearable
                placeholder="Select applications"
                style="width: 100%"
                @change="onAppsChosen"
              >
                <el-option
                  v-for="app in appOptions"
                  :key="app.app_name"
                  :label="`${app.app_name} (${app.project_count} projects)`"
                  :value="app.app_name"
                />
              </el-select>
              <div class="form-help-text">Conditions will be resolved to project_key and repository_slug in JSON</div>
            </el-form-item>

            <el-form-item :label="t('auto_rules.f_pr_user')">
              <el-select
                v-model="cond.pull_request_user"
                class="tag-select"
                multiple
                filterable
                clearable
                placeholder="e.g. alice"
                style="width: 100%"
              >
                <el-option
                  v-for="u in gitUsers"
                  :key="u.username"
                  :label="`${u.display_name} (${u.username})`"
                  :value="u.username"
                />
              </el-select>
              <div class="form-help-text">{{ t('auto_rules.f_pr_user_hint') }}</div>
            </el-form-item>

            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item :label="t('auto_rules.f_source_branch_prefix')">
                  <el-input
                    v-model="cond.source_branch_prefix"
                    placeholder="e.g. feature/"
                    clearable
                  />
                  <div class="form-help-text">{{ t('auto_rules.f_source_branch_hint') }}</div>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item :label="t('auto_rules.f_target_branch')">
                  <el-select
                    v-model="cond.target_branch"
                    multiple
                    filterable
                    allow-create
                    clearable
                    default-first-option
                    placeholder="e.g. main"
                    style="width: 100%"
                  >
                    <el-option label="main" value="main" />
                    <el-option label="master" value="master" />
                    <el-option label="develop" value="develop" />
                    <el-option label="staging" value="staging" />
                  </el-select>
                  <div class="form-help-text">{{ t('auto_rules.f_target_branch_hint') }}</div>
                </el-form-item>
              </el-col>
            </el-row>

            <el-form-item :label="t('auto_rules.f_pr_status')">
              <el-select
                v-model="cond.pull_request_status"
                multiple
                filterable
                clearable
                placeholder="Select PR statuses"
                style="width: 100%"
              >
                <el-option label="open" value="open" />
                <el-option label="merged" value="merged" />
                <el-option label="closed" value="closed" />
                <el-option label="draft" value="draft" />
              </el-select>
              <div class="form-help-text">{{ t('auto_rules.f_pr_status_hint') }}</div>
            </el-form-item>

            <el-form-item :label="t('auto_rules.f_issue_severity')">
              <el-select
                v-model="cond.issue_severity"
                multiple
                clearable
                :placeholder="t('auto_rules.f_issue_severity_placeholder')"
                style="width: 100%"
              >
                <el-option
                  v-for="level in ISSUE_SEVERITIES"
                  :key="level"
                  :label="t(`auto_rules.severity_${level}`)"
                  :value="level"
                />
              </el-select>
              <div class="form-help-text">{{ t('auto_rules.f_issue_severity_hint') }}</div>
            </el-form-item>
          </el-col>
        </el-row>

        <!-- The JSON is what the rule becomes rather than what is typed into it: it
             opens on demand, so it no longer costs every edit a scroll. -->
        <el-collapse class="preview-fold">
          <el-collapse-item :title="t('auto_rules.section_preview')" name="preview">
            <el-form-item :label="t('auto_rules.f_conditions')">
              <el-input
                :model-value="conditionsPreview"
                type="textarea"
                :rows="4"
                readonly
              />
              <div class="form-help-text">{{ t('auto_rules.f_preview_hint') }}</div>
            </el-form-item>
          </el-collapse-item>
        </el-collapse>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">{{ t('auto_rules.cancel') }}</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">
          {{ isEditing ? t('auto_rules.save') : t('auto_rules.create') }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, Edit, Delete } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'
import {
  autoAssignRulesApi,
  type AutoAssignRule,
  type AutoAssignRuleCreate,
} from '@/api/autoAssignRules'
import { projectsApi, type ProjectSummary, type RepositorySummary } from '@/api/projects'
import { usersApi, type ReviewerUser } from '@/api/users'
import { projectRegistryApi } from '@/api/projectRegistry'
import type { AppInfo } from '@/api/projectRegistry'
import { appsForTargets, targetsForApps } from '@/utils/ruleConditions'

const { t } = useI18n()

// === Data ===
const rules = ref<AutoAssignRule[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const saving = ref(false)
const togglingId = ref<number | null>(null)

// === Dropdown Options ===
const projects = ref<ProjectSummary[]>([])
const gitUsers = ref<ReviewerUser[]>([])
const reviewerUsers = ref<ReviewerUser[]>([])

// === App Filter ===
const appFilter = ref('')
const appOptions = ref<AppInfo[]>([])
const registryMap = ref<Record<string, string[]>>({}) // app_name -> ['project_key/repo_slug', ...]

// === Dialog State ===
const dialogVisible = ref(false)
const isEditing = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref<any>(null)

// === Condition form fields (structured, mapped to conditions JSON) ===
const cond = reactive({
  app_name: [] as string[],
  project_key: [] as string[],
  repository_slug: [] as string[],
  pull_request_user: [] as string[],
  source_branch_prefix: '',
  target_branch: [] as string[],
  pull_request_status: [] as string[],
  issue_severity: [] as string[],
})

// The severities an AI review reports per issue, most severe first
const ISSUE_SEVERITIES = ['critical', 'high', 'medium', 'low'] as const

const defaultForm = {
  name: '',
  description: null as string | null,
  priority: 100,
  conditions: {} as Record<string, any>,
  assign_to: [] as string[],
  starts_at: null as string | null,
  expires_at: null as string | null,
  is_active: true,
}

const form = ref<AutoAssignRuleCreate>({ ...defaultForm })

// === Condition building ===
const conditionsPreview = computed(() => {
  const built = buildConditions()
  return Object.keys(built).length > 0 ? JSON.stringify(built, null, 2) : '{}'
})

function buildConditions(): Record<string, any> {
  const c: Record<string, any> = {}
  if (cond.project_key.length > 0) c.project_key = [...cond.project_key]
  if (cond.repository_slug.length > 0) c.repository_slug = [...cond.repository_slug]
  if (cond.pull_request_user.length > 0) c.pull_request_user = [...cond.pull_request_user]
  if (cond.source_branch_prefix) c.source_branch_prefix = cond.source_branch_prefix
  if (cond.target_branch.length > 0) c.target_branch = [...cond.target_branch]
  if (cond.pull_request_status.length > 0) c.pull_request_status = [...cond.pull_request_status]
  if (cond.issue_severity.length > 0) c.issue_severity = [...cond.issue_severity]
  return c
}

// Resolve the chosen app names into project_key + repository_slug, on the reader's
// choice only - never on a programmatic assignment. Opening a rule for editing sets
// app_name from its conditions; a watcher here would read that back as a fresh choice
// and rebuild the conditions from it, which a rule the registry cannot explain
// (an extra project key, say) would answer by emptying them.
function onAppsChosen(apps: string[]) {
  const targets = targetsForApps(registryMap.value, apps)
  cond.project_key = targets.projectKeys
  cond.repository_slug = targets.repositorySlugs
  form.value.conditions = buildConditions()
}

// Sync conditions from cond form -> form.conditions (for the API payload)
watch(
  () => conditionsPreview.value,
  () => {
    form.value.conditions = buildConditions()
  },
  { deep: true }
)

// === Filtered repos based on selected projects ===
// Map of project_key -> repos; populated during loadProjects()
const projectReposMap = ref<Record<string, RepositorySummary[]>>({})

// === Computed ===
const paginatedRules = computed(() => rules.value)

// Filter rules by selected app name (client-side)
const displayRules = computed(() => {
  if (!appFilter.value || !registryMap.value[appFilter.value]) {
    return rules.value
  }
  const appEntries = registryMap.value[appFilter.value] || []
  return rules.value.filter(rule => {
    const cond = rule.conditions || {}
    const pks = Array.isArray(cond.project_key) ? cond.project_key : (cond.project_key ? [cond.project_key] : [])
    const slugs = Array.isArray(cond.repository_slug) ? cond.repository_slug : (cond.repository_slug ? [cond.repository_slug] : [])
    // If no project/repo conditions, the rule applies to all -> include it
    if (pks.length === 0 && slugs.length === 0) return true
    // Check if any (project_key, repository_slug) combo matches the selected app
    if (pks.length === 0) {
      // Only repo slugs specified - match if any slug belongs to this app
      return slugs.some(slug => appEntries.some(entry => entry.endsWith(`/${slug}`)))
    }
    // Check each project_key against app entries
    return pks.some(pk => {
      if (slugs.length === 0) {
        return appEntries.some(entry => entry.startsWith(`${pk}/`))
      }
      return slugs.some(slug => appEntries.includes(`${pk}/${slug}`))
    })
  })
})

// === Form Validation ===
const formRules = {
  name: [
    { required: true, message: t('auto_rules.required_name'), trigger: 'blur' },
  ],
}

// === Load dropdown data ===
async function loadProjects() {
  try {
    const result = await projectsApi.getAllProjects()
    projects.value = result
    // Load repos per project into the map
    projectReposMap.value = {}
    for (const p of projects.value) {
      try {
        const repos = await projectsApi.getProjectRepositories(p.project_key)
        if (Array.isArray(repos)) {
          projectReposMap.value[p.project_key] = repos
        }
      } catch {
        projectReposMap.value[p.project_key] = []
      }
    }
  } catch {
    // Projects can't load — proceed without them
  }
}

async function loadUsers() {
  try {
    gitUsers.value = await usersApi.getGitUsers({ limit: 500 })
  } catch {
    gitUsers.value = []
  }
  try {
    const reviewersResp = await usersApi.getReviewers(500)
    reviewerUsers.value = reviewersResp.items || []
  } catch {
    reviewerUsers.value = []
  }
}

// === Load rules ===
async function loadRules() {
  loading.value = true
  try {
    const response = await autoAssignRulesApi.listRules({
      page: currentPage.value,
      page_size: pageSize.value,
    })
    rules.value = response.items
    total.value = response.total
  } catch (err: any) {
    ElMessage.error(err?.detail?.message || t('auto_rules.load_failed'))
  } finally {
    loading.value = false
  }
}

// === Utils ===
function truncateConditions(conditions: Record<string, any>): string {
  const text = JSON.stringify(conditions)
  if (text.length <= 60) return text
  return text.substring(0, 57) + '...'
}

function formatConditionsJson(conditions: Record<string, any>): string {
  return JSON.stringify(conditions, null, 2)
}

function formatDate(dateStr: string): string {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleDateString()
}

function formatDateTime(dateStr: string | null | undefined): string {
  if (!dateStr) return '-'
  const d = new Date(dateStr)
  return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

// === Replace cond fields from conditions JSON (used when editing) ===
function asList(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String)
  return value ? [String(value)] : []
}

function applyConditionsToForm(conditions: Record<string, any>) {
  const projectKeys = asList(conditions.project_key)
  const repositorySlugs = asList(conditions.repository_slug)
  cond.project_key = projectKeys
  cond.repository_slug = repositorySlugs
  cond.pull_request_user = asList(conditions.pull_request_user)
  cond.source_branch_prefix = conditions.source_branch_prefix || ''
  cond.target_branch = asList(conditions.target_branch)
  cond.pull_request_status = asList(conditions.pull_request_status)
  cond.issue_severity = asList(conditions.issue_severity)
  // The rule keeps the two lists, not the applications they were picked from: read
  // them back when a selection of applications explains them, and leave the field
  // empty when it does not.
  cond.app_name = appsForTargets(registryMap.value, projectKeys, repositorySlugs)
  form.value.conditions = buildConditions()
}

function resetConditions() {
  cond.app_name = []
  cond.project_key = []
  cond.repository_slug = []
  cond.pull_request_user = []
  cond.source_branch_prefix = ''
  cond.target_branch = []
  cond.pull_request_status = []
  cond.issue_severity = []
  form.value.conditions = {}
}

// === Dialog ===
function openCreateDialog() {
  isEditing.value = false
  editingId.value = null
  form.value = { ...defaultForm }
  resetConditions()
  dialogVisible.value = true
  nextTick(() => formRef.value?.clearValidate())
}

function openEditDialog(rule: AutoAssignRule) {
  isEditing.value = true
  editingId.value = rule.id
  form.value = {
    name: rule.name,
    description: rule.description ?? null,
    priority: rule.priority,
    conditions: { ...rule.conditions },
    assign_to: [...rule.assign_to],
    starts_at: rule.starts_at ?? null,
    expires_at: rule.expires_at ?? null,
    is_active: rule.is_active,
  }
  applyConditionsToForm(rule.conditions || {})
  dialogVisible.value = true
  nextTick(() => formRef.value?.clearValidate())
}

async function handleSave() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  saving.value = true
  try {
    const payload = {
      ...form.value,
      starts_at: form.value.starts_at
        ? new Date(form.value.starts_at).toISOString()
        : null,
      expires_at: form.value.expires_at
        ? new Date(form.value.expires_at).toISOString()
        : null,
    }

    if (isEditing.value && editingId.value !== null) {
      await autoAssignRulesApi.updateRule(editingId.value, payload)
      ElMessage.success(t('auto_rules.updated_success'))
    } else {
      await autoAssignRulesApi.createRule(payload as AutoAssignRuleCreate)
      ElMessage.success(t('auto_rules.created_success'))
    }
    dialogVisible.value = false
    await loadRules()
  } catch (err: any) {
    ElMessage.error(err?.detail?.message || t('auto_rules.save_failed'))
  } finally {
    saving.value = false
  }
}

async function handleToggle(rule: AutoAssignRule, _val: boolean) {
  togglingId.value = rule.id
  try {
    const response = await autoAssignRulesApi.toggleRule(rule.id)
    ElMessage.success(response.message)
    const idx = rules.value.findIndex(r => r.id === rule.id)
    if (idx !== -1) {
      rules.value[idx] = { ...rules.value[idx], is_active: response.is_active }
    }
  } catch (err: any) {
    ElMessage.error(err?.detail?.message || t('auto_rules.toggle_failed'))
  } finally {
    togglingId.value = null
  }
}

async function handleDelete(rule: AutoAssignRule) {
  try {
    await ElMessageBox.confirm(
      t('auto_rules.delete_confirm_message', { name: rule.name }),
      t('auto_rules.delete_confirm_title'),
      {
        confirmButtonText: t('auto_rules.delete'),
        cancelButtonText: t('auto_rules.cancel'),
        type: 'warning',
      }
    )
    await autoAssignRulesApi.deleteRule(rule.id)
    ElMessage.success(t('auto_rules.deleted_success'))
    await loadRules()
  } catch {
    // Cancel or error — do nothing
  }
}

// === Lifecycle ===
onMounted(async () => {
  await Promise.all([
    loadRules(),
    loadProjects(),
    loadUsers(),
    loadAppOptions(),
  ])
})

// Load app names and registry map for filtering
async function loadAppOptions() {
  try {
    appOptions.value = await projectRegistryApi.listApps()
    const allRegistry = await projectRegistryApi.listAllRegisteredProjects()
    // Build map: app_name -> ['project_key/repo_slug', ...]
    const map: Record<string, string[]> = {}
    for (const entry of allRegistry) {
      if (!map[entry.app_name]) {
        map[entry.app_name] = []
      }
      map[entry.app_name].push(`${entry.project_key}/${entry.repository_slug}`)
    }
    registryMap.value = map
  } catch (e) {
    console.error('Failed to load app options:', e)
  }
}
</script>

<style scoped>
.rules-management-container {
  padding: 0;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.header-title-group {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-title-group h2 {
  margin: 0;
  font-size: 18px;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.empty-state {
  display: flex;
  justify-content: center;
  padding: 60px 0;
}

.app-filter-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 0;
  margin-bottom: 4px;
}

.filter-hint {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.table-wrapper {
  overflow-x: auto;
}

.table-wrapper :deep(.el-table) {
  min-width: 100%;
}

.date-cell {
  font-family: 'SF Mono', 'Fira Code', 'Courier New', monospace;
  font-size: 12px;
  white-space: nowrap;
}

.date-cell.date-null {
  color: var(--el-text-color-placeholder);
  font-family: inherit;
  font-style: italic;
}

.conditions-preview {
  cursor: pointer;
  color: var(--el-color-primary);
  font-family: 'Courier New', Courier, monospace;
  font-size: 12px;
}

.pagination-wrapper {
  display: flex;
  justify-content: center;
  padding: 20px 0;
}

.form-help-text {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
  line-height: 1.4;
}

.form-error-text {
  font-size: 12px;
  color: var(--el-color-danger);
  margin-top: 4px;
}

/* A section heading that names the group beside it rather than dividing the form:
   the two columns are read side by side, so a full-width rule would cut across. */
.section-title {
  margin: 0 0 12px;
  padding-left: 8px;
  border-left: 3px solid var(--el-color-primary);
  font-size: 13px;
  font-weight: 600;
  line-height: 1.2;
  color: var(--el-text-color-primary);
}

.section-title:not(:first-child) {
  margin-top: 20px;
}

/* Room is what the dialog was short of: a hint under every field is worth its line,
   the space between them is not. */
.rule-form :deep(.el-form-item) {
  margin-bottom: 14px;
}

/* A picker whose list can be long scrolls inside itself instead of stretching the
   dialog: three rows of tags, then the rest are a scroll away. Without this, choosing
   a dozen applications pushed every control below it out of the column and left the
   two columns uneven. */
.rule-form :deep(.tag-select .el-select__selection) {
  max-height: 88px;
  overflow-y: auto;
  padding-right: 4px;
}

.preview-fold {
  margin-top: 4px;
  border-top: 1px solid var(--el-border-color-lighter);
}

.preview-fold :deep(.el-collapse-item__header) {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

/* The body scrolls, not the page: Cancel and Save stay where they are even when the
   window is shorter than the form. */
:global(.rule-dialog-body) {
  max-height: calc(100vh - 280px);
  overflow-y: auto;
  padding-right: 6px;
}
</style>
