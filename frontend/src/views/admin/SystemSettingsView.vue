<template>
  <div class="system-settings">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span>{{ t('admin.systemSettings.title') }}</span>
        </div>
      </template>

      <el-form label-width="200px" style="max-width: 600px;">
        <!-- Registration Enabled Setting -->
        <el-form-item :label="t('admin.systemSettings.registrationEnabled')">
          <el-switch
            v-model="settings.registration_enabled"
            :active-text="t('common.enabled')"
            :inactive-text="t('common.disabled')"
            :loading="saving"
            @change="handleRegistrationToggle"
          />
          <div class="setting-description">
            {{ t('admin.systemSettings.registrationEnabledDesc') }}
          </div>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="hover" style="margin-top: 20px;">
      <template #header>
        <div class="card-header">
          <span>{{ t('admin.systemSettings.llmSettings') }}</span>
        </div>
      </template>

      <el-form label-width="200px" style="max-width: 600px;">
        <!-- LLM Enabled Toggle -->
        <el-form-item :label="t('admin.systemSettings.llmEnabled')">
          <el-switch
            v-model="llmSettings.enabled"
            :active-text="t('common.enabled')"
            :inactive-text="t('common.disabled')"
            :loading="llmSaving"
            @change="handleLlmSave"
          />
          <div class="setting-description">
            {{ t('admin.systemSettings.llmEnabledDesc') }}
          </div>
        </el-form-item>

        <!-- LLM Model -->
        <el-form-item :label="t('admin.systemSettings.llmModel')">
          <el-input
            v-model="llmSettings.model"
            :placeholder="t('admin.systemSettings.llmModelPlaceholder')"
            clearable
            @blur="handleLlmSave"
          />
          <div class="setting-description">
            {{ t('admin.systemSettings.llmModelDesc') }}
          </div>
        </el-form-item>

        <!-- LLM Base URL -->
        <el-form-item :label="t('admin.systemSettings.llmBaseUrl')">
          <el-input
            v-model="llmSettings.base_url"
            :placeholder="t('admin.systemSettings.llmBaseUrlPlaceholder')"
            clearable
            @blur="handleLlmSave"
          />
          <div class="setting-description">
            {{ t('admin.systemSettings.llmBaseUrlDesc') }}
          </div>
        </el-form-item>

        <!-- LLM API Key -->
        <el-form-item :label="t('admin.systemSettings.llmApiKey')">
          <el-input
            v-model="llmSettings.api_key"
            type="password"
            show-password
            :placeholder="llmSettings.has_api_key ? t('admin.systemSettings.llmApiKeyMasked') : t('admin.systemSettings.llmApiKeyPlaceholder')"
            clearable
            @blur="handleLlmSave"
          />
          <div class="setting-description">
            {{ t('admin.systemSettings.llmApiKeyDesc') }}
          </div>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="hover" style="margin-top: 20px;">
      <template #header>
        <div class="card-header">
          <span>{{ t('admin.systemSettings.banner') }}</span>
        </div>
      </template>

      <!-- Every banner in one list, so the page stays the same length however
           many there are; adding and editing happen in a dialog. -->
      <div class="banner-toolbar">
        <el-button type="primary" data-test="banner-add" @click="openEditor()">
          {{ t('admin.systemSettings.bannerAdd') }}
        </el-button>
      </div>

      <el-empty
        v-if="banners.length === 0"
        :description="t('admin.systemSettings.bannerEmpty')"
        :image-size="60"
      />

      <el-table v-else :data="banners" row-key="id">
        <el-table-column :label="t('admin.systemSettings.bannerContent')" min-width="240">
          <template #default="{ row }">
            <span class="banner-content-cell" :title="row.content">{{ row.content }}</span>
          </template>
        </el-table-column>

        <el-table-column :label="t('admin.systemSettings.bannerLevel')" width="110">
          <template #default="{ row }">
            <el-tag size="small" :type="row.level">{{ levelLabel(row.level) }}</el-tag>
          </template>
        </el-table-column>

        <el-table-column :label="t('admin.systemSettings.bannerWindow')" min-width="200">
          <template #default="{ row }">
            <span class="banner-window-text">{{ windowLabel(row) }}</span>
          </template>
        </el-table-column>

        <el-table-column
          :label="t('admin.systemSettings.bannerPriority')"
          width="90"
          align="center"
        >
          <template #default="{ row }">{{ row.priority }}</template>
        </el-table-column>

        <!-- Wide enough for both state labels: a switch shows the one it is in
             beside the track, not inside it. -->
        <el-table-column :label="t('admin.systemSettings.bannerStatus')" width="210">
          <template #default="{ row }">
            <!-- One-way bound on purpose: the switch shows the stored state, so a
                 write that fails leaves it where it was instead of lying. -->
            <el-switch
              :model-value="row.enabled"
              :disabled="bannerSaving"
              :active-text="t('common.enabled')"
              :inactive-text="t('common.disabled')"
              data-test="banner-enabled"
              @change="(value: string | number | boolean) => toggleBannerEnabled(row, value as boolean)"
            />
          </template>
        </el-table-column>

        <el-table-column
          :label="t('admin.systemSettings.bannerActions')"
          width="140"
          align="right"
        >
          <template #default="{ row, $index }">
            <el-button link type="primary" data-test="banner-edit" @click="openEditor(row)">
              {{ t('common.edit') }}
            </el-button>
            <el-button link type="danger" data-test="banner-remove" @click="confirmRemove($index)">
              {{ t('common.delete') }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- Add and edit share one dialog -->
      <el-dialog
        v-model="editorVisible"
        :title="editingId ? t('admin.systemSettings.bannerEdit') : t('admin.systemSettings.bannerAdd')"
        width="560px"
        :close-on-click-modal="false"
      >
        <el-form v-if="editing" label-width="150px">
          <el-form-item :label="t('admin.systemSettings.bannerEnabled')">
            <el-switch
              v-model="editing.enabled"
              :active-text="t('common.enabled')"
              :inactive-text="t('common.disabled')"
            />
          </el-form-item>

          <el-form-item :label="t('admin.systemSettings.bannerContent')" required>
            <el-input
              v-model="editing.content"
              type="textarea"
              :rows="2"
              :placeholder="t('admin.systemSettings.bannerContentPlaceholder')"
              clearable
            />
          </el-form-item>

          <el-form-item :label="t('admin.systemSettings.bannerLevel')">
            <el-radio-group v-model="editing.level">
              <el-radio-button value="info">
                {{ t('admin.systemSettings.bannerLevelInfo') }}
              </el-radio-button>
              <el-radio-button value="warning">
                {{ t('admin.systemSettings.bannerLevelWarning') }}
              </el-radio-button>
              <el-radio-button value="success">
                {{ t('admin.systemSettings.bannerLevelSuccess') }}
              </el-radio-button>
            </el-radio-group>
          </el-form-item>

          <el-form-item :label="t('admin.systemSettings.bannerPriority')">
            <el-input-number v-model="editing.priority" :min="0" :max="99" />
            <div class="setting-description">
              {{ t('admin.systemSettings.bannerPriorityDesc') }}
            </div>
          </el-form-item>

          <el-form-item :label="t('admin.systemSettings.bannerDateRange')">
            <div class="banner-window">
              <el-date-picker
                v-model="editing.start_date"
                type="datetime"
                :placeholder="t('admin.systemSettings.bannerStart')"
                value-format="YYYY-MM-DDTHH:mm:ssZ"
              />
              <span class="banner-window-separator">—</span>
              <el-date-picker
                v-model="editing.end_date"
                type="datetime"
                :placeholder="t('admin.systemSettings.bannerEnd')"
                value-format="YYYY-MM-DDTHH:mm:ssZ"
              />
            </div>
            <div class="setting-description">
              {{ t('admin.systemSettings.bannerDateRangeDesc') }}
            </div>
          </el-form-item>

          <el-form-item :label="t('admin.systemSettings.bannerLink')">
            <el-input
              v-model="editing.link_url"
              :placeholder="t('admin.systemSettings.bannerLinkUrl')"
              clearable
            />
            <el-input
              v-model="editing.link_label"
              class="banner-link-label"
              :placeholder="t('admin.systemSettings.bannerLinkLabel')"
              clearable
            />
            <div class="setting-description">
              {{ t('admin.systemSettings.bannerLinkDesc') }}
            </div>
          </el-form-item>

          <el-form-item
            v-if="editing.content.trim()"
            :label="t('admin.systemSettings.bannerPreview')"
          >
            <div class="banner-preview-box">
              <el-alert
                :title="editing.content"
                :type="editing.level"
                show-icon
                :closable="false"
              />
            </div>
          </el-form-item>
        </el-form>

        <template #footer>
          <el-button @click="editorVisible = false">{{ t('common.cancel') }}</el-button>
          <el-button
            type="primary"
            data-test="banner-save"
            :loading="bannerSaving"
            @click="saveEditor"
          >
            {{ t('common.save') }}
          </el-button>
        </template>
      </el-dialog>
    </el-card>

    <el-card shadow="hover" style="margin-top: 20px;">
      <template #header>
        <div class="card-header">
          <span>{{ t('admin.systemSettings.confluence') }}</span>
        </div>
      </template>

      <!-- Releases are published per repository, so the target is settled the same
           way: a repository, then its project, then the instance. The instance
           values come from the backend's environment and are shown to make the
           fallback visible rather than to be edited here. -->
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item :label="t('admin.systemSettings.confluenceInstance')" :span="2">
          {{ t('admin.systemSettings.confluenceInstanceDesc') }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('admin.systemSettings.confluenceBaseUrl')">
          {{ confluence.instance.base_url || t('admin.systemSettings.confluenceUnset') }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('admin.systemSettings.confluenceSpaceKey')">
          {{ confluence.instance.space_key || t('admin.systemSettings.confluenceUnset') }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('admin.systemSettings.confluenceParentPage')">
          {{ confluence.instance.parent_page_id || t('admin.systemSettings.confluenceUnset') }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('admin.systemSettings.confluenceSync')">
          <el-tag
            size="small"
            :type="confluence.instance.enabled ? 'success' : 'info'"
            effect="plain"
          >
            {{ confluence.instance.enabled ? t('common.enabled') : t('common.disabled') }}
          </el-tag>
          <el-tag
            class="source-tag"
            size="small"
            :type="confluence.instance.has_credentials ? 'success' : 'danger'"
            effect="plain"
          >
            {{
              confluence.instance.has_credentials
                ? t('admin.systemSettings.confluenceCredentialsReady')
                : t('admin.systemSettings.confluenceCredentialsMissing')
            }}
          </el-tag>
        </el-descriptions-item>
      </el-descriptions>

      <!-- Project defaults: what a project's repositories share -->
      <div class="target-section">
        <div class="target-section-head">
          <span class="target-section-title">{{ t('admin.systemSettings.confluenceProjects') }}</span>
          <el-button
            size="small"
            type="primary"
            data-test="confluence-project-add"
            @click="openProjectEditor()"
          >
            {{ t('admin.systemSettings.confluenceTargetAdd') }}
          </el-button>
        </div>
        <div class="setting-description">
          {{ t('admin.systemSettings.confluenceProjectsDesc') }}
        </div>

        <el-table
          v-if="confluence.projects.length"
          :data="confluence.projects"
          size="small"
          data-test="confluence-projects"
        >
          <el-table-column
            :label="t('admin.systemSettings.confluenceTargetProjectKey')"
            min-width="140"
          >
            <template #default="{ row }">{{ row.project_key }}</template>
          </el-table-column>

          <el-table-column :label="t('admin.systemSettings.confluenceSpaceKey')" min-width="140">
            <template #default="{ row }">
              <span v-if="row.space_key">{{ row.space_key }}</span>
              <span v-else class="target-inherited">
                {{ t('admin.systemSettings.confluenceInherit') }}
              </span>
            </template>
          </el-table-column>

          <el-table-column :label="t('admin.systemSettings.confluenceParentPage')" min-width="140">
            <template #default="{ row }">
              <span v-if="row.parent_page_id">{{ row.parent_page_id }}</span>
              <span v-else class="target-inherited">
                {{ t('admin.systemSettings.confluenceInherit') }}
              </span>
            </template>
          </el-table-column>

          <el-table-column :label="t('admin.systemSettings.confluenceSync')" width="130">
            <template #default="{ row }">{{ syncLabel(row.enabled) }}</template>
          </el-table-column>

          <el-table-column
            :label="t('admin.systemSettings.confluenceActions')"
            width="140"
            align="right"
          >
            <template #default="{ row }">
              <el-button
                link
                type="primary"
                data-test="confluence-project-edit"
                @click="openProjectEditor(row)"
              >
                {{ t('common.edit') }}
              </el-button>
              <el-button
                link
                type="danger"
                data-test="confluence-project-remove"
                @click="removeProjectTarget(row)"
              >
                {{ t('common.delete') }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty
          v-else
          :description="t('admin.systemSettings.confluenceProjectsEmpty')"
          :image-size="48"
        />
      </div>

      <!-- What each repository resolves to, and which level decided it -->
      <div class="target-section">
        <div class="target-section-head">
          <span class="target-section-title">
            {{ t('admin.systemSettings.confluenceRepositories') }}
          </span>
          <el-input
            v-model="repositorySearch"
            class="target-search"
            size="small"
            clearable
            :placeholder="t('admin.systemSettings.confluenceSearch')"
          />
        </div>
        <div class="setting-description">
          {{ t('admin.systemSettings.confluenceRepositoriesDesc') }}
        </div>

        <el-table
          :data="filteredRepositories"
          size="small"
          :row-key="repositoryRowKey"
          data-test="confluence-repositories"
        >
          <el-table-column
            :label="t('admin.systemSettings.confluenceRepository')"
            min-width="200"
          >
            <template #default="{ row }">
              <div class="target-repository">
                <span>{{ row.project_key }} / {{ row.repository_slug }}</span>
                <span v-if="row.app_name" class="target-app-name">{{ row.app_name }}</span>
              </div>
            </template>
          </el-table-column>

          <el-table-column
            :label="t('admin.systemSettings.confluenceEffectiveSpace')"
            min-width="170"
          >
            <template #default="{ row }">
              <span v-if="row.space_key">{{ row.space_key }}</span>
              <span v-else class="target-missing">
                {{ t('admin.systemSettings.confluenceNoSpace') }}
              </span>
              <el-tag
                class="source-tag"
                size="small"
                effect="plain"
                :type="sourceTagType(row.space_source)"
              >
                {{ sourceLabel(row.space_source) }}
              </el-tag>
            </template>
          </el-table-column>

          <el-table-column
            :label="t('admin.systemSettings.confluenceEffectiveParent')"
            min-width="170"
          >
            <template #default="{ row }">
              <span v-if="row.parent_page_id">{{ row.parent_page_id }}</span>
              <span v-else class="target-inherited">—</span>
              <el-tag
                v-if="row.parent_page_id"
                class="source-tag"
                size="small"
                effect="plain"
                :type="sourceTagType(row.parent_source)"
              >
                {{ sourceLabel(row.parent_source) }}
              </el-tag>
            </template>
          </el-table-column>

          <el-table-column :label="t('admin.systemSettings.confluenceSync')" width="170">
            <template #default="{ row }">
              <el-tag size="small" :type="row.enabled ? 'success' : 'info'" effect="plain">
                {{ row.enabled ? t('common.enabled') : t('common.disabled') }}
              </el-tag>
              <el-tag
                class="source-tag"
                size="small"
                effect="plain"
                :type="sourceTagType(row.enabled_source)"
              >
                {{ sourceLabel(row.enabled_source) }}
              </el-tag>
            </template>
          </el-table-column>

          <el-table-column
            :label="t('admin.systemSettings.confluenceActions')"
            width="190"
            align="right"
          >
            <template #default="{ row }">
              <el-button
                link
                type="primary"
                data-test="confluence-repository-edit"
                @click="openRepositoryEditor(row)"
              >
                {{ t('admin.systemSettings.confluenceOverride') }}
              </el-button>
              <el-button
                v-if="hasRepositoryTarget(row)"
                link
                type="danger"
                data-test="confluence-repository-clear"
                @click="clearRepositoryTarget(row)"
              >
                {{ t('admin.systemSettings.confluenceClearOverride') }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- One dialog for both levels; which one it edits is what is open -->
      <el-dialog
        v-model="targetEditorVisible"
        :title="
          targetScope === 'project'
            ? t('admin.systemSettings.confluenceProjectTarget')
            : t('admin.systemSettings.confluenceRepositoryTarget')
        "
        width="580px"
        :close-on-click-modal="false"
      >
        <el-form v-if="editingTarget" label-width="170px">
          <el-form-item :label="t('admin.systemSettings.confluenceTargetProjectKey')" required>
            <el-select
              v-model="editingTarget.project_key"
              :disabled="targetIdentityLocked"
              filterable
              allow-create
              default-first-option
              :placeholder="t('admin.systemSettings.confluenceTargetProjectKeyPlaceholder')"
              data-test="confluence-target-project"
            >
              <el-option v-for="project in knownProjects" :key="project" :label="project" :value="project" />
            </el-select>
          </el-form-item>

          <el-form-item
            v-if="targetScope === 'repository'"
            :label="t('admin.systemSettings.confluenceTargetRepositorySlug')"
            required
          >
            <el-select
              v-model="editingTarget.repository_slug"
              :disabled="targetIdentityLocked"
              filterable
              allow-create
              default-first-option
              :placeholder="t('admin.systemSettings.confluenceTargetRepositoryPlaceholder')"
              data-test="confluence-target-repository"
            >
              <el-option
                v-for="repository in knownRepositories"
                :key="repository"
                :label="repository"
                :value="repository"
              />
            </el-select>
          </el-form-item>

          <!-- Each field decides for itself whether it is settled here -->
          <el-form-item :label="t('admin.systemSettings.confluenceSpaceKey')">
            <el-switch
              v-model="targetOverrides.space"
              :active-text="t('admin.systemSettings.confluenceOverride')"
              :inactive-text="t('admin.systemSettings.confluenceInherit')"
              data-test="confluence-target-space-override"
            />
            <el-input
              v-if="targetOverrides.space"
              v-model="editingTarget.space_key"
              class="target-override-input"
              :placeholder="t('admin.systemSettings.confluenceSpaceKeyPlaceholder')"
              data-test="confluence-target-space"
            />
            <div class="setting-description">
              {{ t('admin.systemSettings.confluenceFieldInheritDesc') }}
            </div>
          </el-form-item>

          <el-form-item :label="t('admin.systemSettings.confluenceParentPage')">
            <el-switch
              v-model="targetOverrides.parent"
              :active-text="t('admin.systemSettings.confluenceOverride')"
              :inactive-text="t('admin.systemSettings.confluenceInherit')"
              data-test="confluence-target-parent-override"
            />
            <el-input
              v-if="targetOverrides.parent"
              v-model="editingTarget.parent_page_id"
              class="target-override-input"
              :placeholder="t('admin.systemSettings.confluenceParentPagePlaceholder')"
              data-test="confluence-target-parent"
            />
            <div class="setting-description">
              {{ t('admin.systemSettings.confluenceParentPageDesc') }}
            </div>
          </el-form-item>

          <el-form-item :label="t('admin.systemSettings.confluenceSync')">
            <el-radio-group v-model="editingTarget.sync" data-test="confluence-target-sync">
              <el-radio value="inherit">
                {{ t('admin.systemSettings.confluenceInherit') }}
              </el-radio>
              <el-radio value="on">{{ t('common.enabled') }}</el-radio>
              <el-radio value="off">{{ t('common.disabled') }}</el-radio>
            </el-radio-group>
            <div class="setting-description">
              {{ t('admin.systemSettings.confluenceSyncDesc') }}
            </div>
          </el-form-item>
        </el-form>

        <template #footer>
          <el-button @click="targetEditorVisible = false">{{ t('common.cancel') }}</el-button>
          <el-button
            type="primary"
            data-test="confluence-target-save"
            :loading="confluenceSaving"
            @click="saveTarget"
          >
            {{ t('common.save') }}
          </el-button>
        </template>
      </el-dialog>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useI18n } from 'vue-i18n'
import dayjs from 'dayjs'
import {
  createBanner,
  createProjectTarget,
  createRepositoryTarget,
  emptyConfluenceSettings,
  rbacApi,
  type BannerItem,
  type BannerLevel,
  type ConfluenceProjectTarget,
  type ConfluenceRepositoryTarget,
  type ConfluenceResolvedTarget,
  type ConfluenceSettings,
  type ConfluenceSource,
  type ConfluenceTargetsPayload,
} from '@/api/rbac'

const { t } = useI18n()

const settings = ref({
  registration_enabled: true,
})

const llmSettings = ref({
  enabled: false,
  model: '',
  base_url: '',
  api_key: '',
  has_api_key: false,
})

const saving = ref(false)
const llmSaving = ref(false)

const banners = ref<BannerItem[]>([])
const bannerSaving = ref(false)

// Adding and editing share one dialog, so the list stays the only thing on the page.
const editorVisible = ref(false)
const editing = ref<BannerItem | null>(null)
const editingId = ref<string | null>(null)

const LEVEL_LABEL_KEYS: Record<BannerLevel, string> = {
  info: 'admin.systemSettings.bannerLevelInfo',
  warning: 'admin.systemSettings.bannerLevelWarning',
  success: 'admin.systemSettings.bannerLevelSuccess',
}

const levelLabel = (level: BannerLevel) => t(LEVEL_LABEL_KEYS[level])

/** The window as the list shows it; no bound at all reads as "always". */
function windowLabel(banner: BannerItem): string {
  if (!banner.start_date && !banner.end_date) {
    return t('admin.systemSettings.bannerAlways')
  }
  const bound = (value: string) => (value ? dayjs(value).format('YYYY-MM-DD HH:mm') : '—')
  return `${bound(banner.start_date)} → ${bound(banner.end_date)}`
}

function openEditor(banner?: BannerItem) {
  editingId.value = banner ? banner.id : null
  // Edit a copy: the list must not change until the save goes through.
  editing.value = banner ? { ...banner } : createBanner()
  editorVisible.value = true
}

/** A cleared picker hands back null; the endpoint takes an empty string for that. */
function normalizeBanner(banner: BannerItem): BannerItem {
  return {
    ...banner,
    content: banner.content.trim(),
    start_date: banner.start_date || '',
    end_date: banner.end_date || '',
    link_url: (banner.link_url || '').trim(),
    link_label: (banner.link_label || '').trim(),
  }
}

/**
 * Write the whole collection, which is the shape the endpoint takes.
 *
 * The list on screen is only replaced once the write went through, so a failed
 * save leaves what is shown matching what is stored.
 */
async function persistBanners(next: BannerItem[]): Promise<boolean> {
  bannerSaving.value = true
  try {
    const response = await rbacApi.updateBanner({ banners: next.map(normalizeBanner) })
    banners.value = (response.banners ?? next).map(normalizeBanner)
    return true
  } catch (error: any) {
    console.error('Failed to save banner settings:', error)
    ElMessage.error(error.response?.data?.detail || t('admin.systemSettings.saveFailed'))
    return false
  } finally {
    bannerSaving.value = false
  }
}

async function saveEditor() {
  const banner = editing.value
  if (!banner) return
  if (!banner.content.trim()) {
    ElMessage.warning(t('admin.systemSettings.bannerContentRequired'))
    return
  }

  const edited = normalizeBanner(banner)
  const next = editingId.value
    ? banners.value.map((item) => (item.id === editingId.value ? edited : item))
    : [...banners.value, edited]

  if (await persistBanners(next)) {
    editorVisible.value = false
    ElMessage.success(t('admin.systemSettings.bannerSaveSuccess'))
  }
}

/** Flip one banner on or off from the list, without opening the dialog. */
async function toggleBannerEnabled(banner: BannerItem, enabled: boolean) {
  const next = banners.value.map((item) => (item.id === banner.id ? { ...item, enabled } : item))
  await persistBanners(next)
}

async function confirmRemove(index: number) {
  try {
    await ElMessageBox.confirm(
      t('admin.systemSettings.bannerDeleteConfirm'),
      t('common.delete'),
      {
        type: 'warning',
        confirmButtonText: t('common.confirm'),
        cancelButtonText: t('common.cancel'),
      },
    )
  } catch {
    return // dismissed
  }

  const next = banners.value.filter((_, position) => position !== index)
  if (await persistBanners(next)) {
    ElMessage.success(t('admin.systemSettings.bannerSaveSuccess'))
  }
}

// ===== Confluence publishing targets =====
//
// A release is published per repository, so where it goes is settled the same
// way: the repository says what is particular to it, its project says what the
// repositories of that project share, and the instance supplies what neither
// says. The table shows the value each repository ends up with and which level
// decided it, rather than the three levels that produce it.

const confluence = ref<ConfluenceSettings>(emptyConfluenceSettings())
const confluenceSaving = ref(false)
const repositorySearch = ref('')

/** The sync choice as three states, rather than the null the endpoint takes. */
type SyncChoice = 'inherit' | 'on' | 'off'

interface TargetDraft {
  project_key: string
  repository_slug: string
  space_key: string
  parent_page_id: string
  sync: SyncChoice
}

const targetEditorVisible = ref(false)
const targetScope = ref<'project' | 'repository'>('project')
/** The identity being replaced; empty while a new target has no identity yet. */
const targetEditingKey = ref('')
const editingTarget = ref<TargetDraft | null>(null)
/** Whether the dialog settles each field here or leaves it to the level above. */
const targetOverrides = ref({ space: false, parent: false })

const SOURCE_LABEL_KEYS: Record<ConfluenceSource, string> = {
  instance: 'admin.systemSettings.confluenceSourceInstance',
  project: 'admin.systemSettings.confluenceSourceProject',
  repository: 'admin.systemSettings.confluenceSourceRepository',
}

/** A colour per level, so which one decided a value is readable at a glance. */
const SOURCE_TAG_TYPES: Record<ConfluenceSource, 'info' | 'warning' | 'success'> = {
  instance: 'info',
  project: 'warning',
  repository: 'success',
}

const sourceLabel = (source: ConfluenceSource) => t(SOURCE_LABEL_KEYS[source])
const sourceTagType = (source: ConfluenceSource) => SOURCE_TAG_TYPES[source]

/** What the list shows for a switch that may be settled at another level. */
const syncLabel = (enabled: boolean | null) =>
  enabled === null
    ? t('admin.systemSettings.confluenceInherit')
    : enabled
      ? t('common.enabled')
      : t('common.disabled')

/** Every project that is either registered or already has a target. */
const knownProjects = computed(() => {
  const projects = new Set(confluence.value.resolved.map((row) => row.project_key))
  confluence.value.projects.forEach((target) => projects.add(target.project_key))
  return [...projects].sort()
})

/** The repositories of the project the dialog is editing. */
const knownRepositories = computed(() =>
  confluence.value.resolved
    .filter((row) => row.project_key === editingTarget.value?.project_key)
    .map((row) => row.repository_slug)
)

const filteredRepositories = computed(() => {
  const term = repositorySearch.value.trim().toLowerCase()
  if (!term) {
    return confluence.value.resolved
  }
  return confluence.value.resolved.filter((row) =>
    `${row.project_key}/${row.repository_slug} ${row.app_name ?? ''}`.toLowerCase().includes(term)
  )
})

/** Whether this repository has a target of its own rather than inheriting. */
function hasRepositoryTarget(row: ConfluenceResolvedTarget): boolean {
  return confluence.value.repositories.some(
    (target) =>
      target.project_key === row.project_key && target.repository_slug === row.repository_slug
  )
}

/** A row is one repository of one project; the same slug can sit under several. */
const repositoryRowKey = (row: ConfluenceResolvedTarget) =>
  `${row.project_key}/${row.repository_slug}`

/** Editing an existing target keeps its identity: the key is what it replaces. */
const targetIdentityLocked = computed(() => targetEditingKey.value !== '')

function draftFrom(target: ConfluenceProjectTarget | ConfluenceRepositoryTarget): TargetDraft {
  return {
    project_key: target.project_key,
    repository_slug: 'repository_slug' in target ? target.repository_slug : '',
    space_key: target.space_key,
    parent_page_id: target.parent_page_id,
    sync: target.enabled === null ? 'inherit' : target.enabled ? 'on' : 'off',
  }
}

function openTargetEditor(
  scope: 'project' | 'repository',
  target: ConfluenceProjectTarget | ConfluenceRepositoryTarget
) {
  const identity =
    'repository_slug' in target ? `${target.project_key}/${target.repository_slug}` : ''
  targetScope.value = scope
  targetEditingKey.value = scope === 'repository' ? identity : target.project_key
  editingTarget.value = draftFrom(target)
  // An empty field is one this level says nothing about, which is what the
  // switch reports - so a stored target reopens with its switches where they were.
  targetOverrides.value = {
    space: Boolean(target.space_key),
    parent: Boolean(target.parent_page_id),
  }
  targetEditorVisible.value = true
}

function openProjectEditor(target?: ConfluenceProjectTarget) {
  openTargetEditor('project', target ?? createProjectTarget())
}

function openRepositoryEditor(row: ConfluenceResolvedTarget) {
  const stored = confluence.value.repositories.find(
    (target) =>
      target.project_key === row.project_key && target.repository_slug === row.repository_slug
  )
  openTargetEditor(
    'repository',
    stored ??
      createRepositoryTarget({
        project_key: row.project_key,
        repository_slug: row.repository_slug,
      })
  )
}

/** The draft as the whole collection to write, or null when it is not ready. */
function buildTargets(): ConfluenceTargetsPayload | null {
  const draft = editingTarget.value
  if (!draft) {
    return null
  }

  const projectKey = draft.project_key.trim()
  if (!projectKey) {
    ElMessage.warning(t('admin.systemSettings.confluenceProjectRequired'))
    return null
  }
  const repositorySlug = draft.repository_slug.trim()
  if (targetScope.value === 'repository' && !repositorySlug) {
    ElMessage.warning(t('admin.systemSettings.confluenceRepositoryRequired'))
    return null
  }

  const spaceKey = targetOverrides.value.space ? draft.space_key.trim() : ''
  if (targetOverrides.value.space && !spaceKey) {
    ElMessage.warning(t('admin.systemSettings.confluenceSpaceRequired'))
    return null
  }
  const parentPageId = targetOverrides.value.parent ? draft.parent_page_id.trim() : ''
  if (parentPageId && !/^\d+$/.test(parentPageId)) {
    ElMessage.warning(t('admin.systemSettings.confluenceParentInvalid'))
    return null
  }

  const enabled = draft.sync === 'inherit' ? null : draft.sync === 'on'
  // A level that decides nothing is what its absence already says, so the
  // endpoint refuses it and the dialog says so rather than writing it.
  if (!spaceKey && !parentPageId && enabled === null) {
    ElMessage.warning(t('admin.systemSettings.confluenceTargetEmpty'))
    return null
  }

  const identity = `${projectKey}/${repositorySlug}`

  if (targetScope.value === 'project') {
    const kept = confluence.value.projects.filter(
      (item) => item.project_key !== targetEditingKey.value && item.project_key !== projectKey
    )
    return {
      projects: [
        ...kept,
        { project_key: projectKey, space_key: spaceKey, parent_page_id: parentPageId, enabled },
      ],
      repositories: [...confluence.value.repositories],
    }
  }

  const kept = confluence.value.repositories.filter((item) => {
    const itemIdentity = `${item.project_key}/${item.repository_slug}`
    return itemIdentity !== targetEditingKey.value && itemIdentity !== identity
  })
  return {
    projects: [...confluence.value.projects],
    repositories: [
      ...kept,
      {
        project_key: projectKey,
        repository_slug: repositorySlug,
        space_key: spaceKey,
        parent_page_id: parentPageId,
        enabled,
      },
    ],
  }
}

/**
 * Write the whole configuration, which is the shape the endpoint takes.
 *
 * What is on screen is replaced by what the endpoint answers with, so the table
 * shows the targets as they now resolve rather than as they were asked for.
 */
async function persistConfluence(payload: ConfluenceTargetsPayload): Promise<boolean> {
  confluenceSaving.value = true
  try {
    const response = await rbacApi.updateConfluenceTargets(payload)
    confluence.value = {
      instance: response.instance,
      projects: response.projects,
      repositories: response.repositories,
      resolved: response.resolved,
    }
    return true
  } catch (error: any) {
    console.error('Failed to save Confluence targets:', error)
    ElMessage.error(error.response?.data?.detail || t('admin.systemSettings.saveFailed'))
    return false
  } finally {
    confluenceSaving.value = false
  }
}

async function saveTarget() {
  const payload = buildTargets()
  if (!payload) {
    return
  }

  if (await persistConfluence(payload)) {
    targetEditorVisible.value = false
    ElMessage.success(t('admin.systemSettings.saveSuccess'))
  }
}

async function confirmRemoval(messageKey: string): Promise<boolean> {
  try {
    await ElMessageBox.confirm(t(messageKey), t('common.confirm'), {
      type: 'warning',
      confirmButtonText: t('common.confirm'),
      cancelButtonText: t('common.cancel'),
    })
    return true
  } catch {
    return false // dismissed
  }
}

async function removeProjectTarget(target: ConfluenceProjectTarget) {
  if (!(await confirmRemoval('admin.systemSettings.confluenceProjectDeleteConfirm'))) {
    return
  }

  const payload: ConfluenceTargetsPayload = {
    projects: confluence.value.projects.filter((item) => item.project_key !== target.project_key),
    repositories: [...confluence.value.repositories],
  }
  if (await persistConfluence(payload)) {
    ElMessage.success(t('admin.systemSettings.saveSuccess'))
  }
}

async function clearRepositoryTarget(row: ConfluenceResolvedTarget) {
  if (!(await confirmRemoval('admin.systemSettings.confluenceRepositoryClearConfirm'))) {
    return
  }

  const payload: ConfluenceTargetsPayload = {
    projects: [...confluence.value.projects],
    repositories: confluence.value.repositories.filter(
      (item) =>
        !(item.project_key === row.project_key && item.repository_slug === row.repository_slug)
    ),
  }
  if (await persistConfluence(payload)) {
    ElMessage.success(t('admin.systemSettings.saveSuccess'))
  }
}

// Load settings on mount
onMounted(async () => {
  await Promise.all([
    loadSettings(),
    loadLlmSettings(),
    loadBannerSettings(),
    loadConfluenceSettings(),
  ])
})

const loadSettings = async () => {
  try {
    const response = await rbacApi.getRegistrationEnabled()
    settings.value.registration_enabled = response.registration_enabled
  } catch (error) {
    console.error('Failed to load settings:', error)
    ElMessage.error(t('admin.systemSettings.loadFailed'))
  }
}

const loadLlmSettings = async () => {
  try {
    const response = await rbacApi.getLlmConfig()
    llmSettings.value.enabled = response.enabled
    llmSettings.value.model = response.model
    llmSettings.value.base_url = response.base_url
    llmSettings.value.has_api_key = response.has_api_key
    llmSettings.value.api_key = '' // Never pre-fill the masked key
  } catch (error) {
    console.error('Failed to load LLM settings:', error)
    ElMessage.error(t('admin.systemSettings.loadFailed'))
  }
}

const handleRegistrationToggle = async (value: boolean) => {
  saving.value = true
  try {
    await rbacApi.updateRegistrationEnabled(value)
    ElMessage.success(t('admin.systemSettings.saveSuccess'))
  } catch (error: any) {
    console.error('Failed to save settings:', error)
    ElMessage.error(error.response?.data?.detail || t('admin.systemSettings.saveFailed'))
    // Revert the switch on error
    settings.value.registration_enabled = !value
  } finally {
    saving.value = false
  }
}

const handleLlmSave = async () => {
  llmSaving.value = true
  try {
    const data: Record<string, any> = {
      enabled: llmSettings.value.enabled,
      model: llmSettings.value.model,
      base_url: llmSettings.value.base_url,
    }
    // Only send api_key if user provided a new one
    if (llmSettings.value.api_key) {
      data.api_key = llmSettings.value.api_key
    }
    await rbacApi.updateLlmConfig(data)
    // Reload to get fresh has_api_key status
    await loadLlmSettings()
    // Notify PageAgent composable to re-check config immediately
    window.dispatchEvent(new CustomEvent('pageagent-config-changed'))
    ElMessage.success(t('admin.systemSettings.saveSuccess'))
  } catch (error: any) {
    console.error('Failed to save LLM settings:', error)
    ElMessage.error(error.response?.data?.detail || t('admin.systemSettings.saveFailed'))
    // Reload to revert UI state
    await loadLlmSettings()
  } finally {
    llmSaving.value = false
  }
}

const loadBannerSettings = async () => {
  try {
    const config = await rbacApi.getBanner()
    banners.value = (config.banners ?? []).map(normalizeBanner)
  } catch (error) {
    console.error('Failed to load banner settings:', error)
    ElMessage.error(t('admin.systemSettings.loadFailed'))
  }
}

const loadConfluenceSettings = async () => {
  try {
    confluence.value = await rbacApi.getConfluenceTargets()
  } catch (error) {
    console.error('Failed to load Confluence settings:', error)
    ElMessage.error(t('admin.systemSettings.loadFailed'))
  }
}


</script>

<style scoped>
.system-settings {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 18px;
  font-weight: 600;
}

.setting-description {
  margin-top: 8px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
  line-height: 1.5;
}

.banner-preview-box {
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 100%;
  border: 1px dashed var(--el-border-color);
  border-radius: 4px;
  padding: 8px;
  background: var(--el-fill-color-lighter);
}

.banner-toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 12px;
}

/* Long wording is cut in the cell rather than widening the table. */
.banner-content-cell {
  display: block;
  max-width: 420px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.banner-window-text {
  font-size: 13px;
  color: var(--el-text-color-regular);
}

.banner-window {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.banner-window-separator {
  color: var(--el-text-color-secondary);
}

.banner-link-label {
  margin-top: 8px;
}

/* A table cell breaks words to fit; the switch's state label must stay in one
   piece, since a broken "Enab / led" is what it looks like when it does not. */
:deep(.el-switch__label) {
  white-space: nowrap;
}

/* The three levels are read top to bottom: instance, then project, then what
   each repository ends up with. */
.target-section {
  margin-top: 20px;
}

.target-section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 4px;
}

.target-section-title {
  font-size: 15px;
  font-weight: 600;
}

.target-search {
  max-width: 240px;
}

.target-repository {
  display: flex;
  flex-direction: column;
  line-height: 1.3;
}

.target-app-name {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

/* A value decided elsewhere and a value decided nowhere are both absent from
   the cell, and are not the same thing - hence two states, not one. */
.target-inherited {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.target-missing {
  color: var(--el-color-warning);
  font-size: 13px;
}

.source-tag {
  margin-left: 6px;
}

.target-override-input {
  margin-top: 8px;
}
</style>
