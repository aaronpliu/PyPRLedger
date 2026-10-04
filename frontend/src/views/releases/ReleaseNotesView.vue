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
          <div class="header-end">
            <!-- Users who cannot manage releases only get a label: the explanation
                 is kept in the tooltip instead of a banner over the page -->
            <el-tooltip
              v-if="!canManage"
              :content="t('releaseNotes.read_only_help')"
              placement="bottom-end"
              :show-after="100"
            >
              <el-tag class="read-only-tag" type="info" size="small" round effect="plain">
                <el-icon><InfoFilled /></el-icon>
                <span>{{ t('releaseNotes.read_only_title') }}</span>
              </el-tag>
            </el-tooltip>
            <!-- The coordinates fold away: the list and the notes are what the
                 page is opened for -->
            <el-button
              class="panel-toggle"
              :class="{ 'is-collapsed': !coordinatesOpen }"
              text
              :icon="ArrowDown"
              :aria-expanded="coordinatesOpen ? 'true' : 'false'"
              :aria-label="coordinatesOpen ? t('common.collapse') : t('common.expand')"
              data-test="coordinates-toggle"
              @click="coordinatesOpen = !coordinatesOpen"
            />
          </div>
        </div>
      </template>

      <div class="panel-body" :class="{ 'is-collapsed': !coordinatesOpen }">
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
                <el-option
                  v-for="option in GIT_PROVIDER_OPTIONS"
                  :key="option.value"
                  :label="option.label"
                  :value="option.value"
                />
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
      </div>
    </el-card>

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
              <ContentLoader
                v-if="notesLoading"
                :rows="4"
                :label="t('releaseNotes.notes_loading')"
              />

              <el-empty
                v-else-if="notes.length === 0"
                :description="t('releaseNotes.empty')"
                :image-size="60"
              />

              <template v-else>
                <div class="export-bar">
                  <el-checkbox
                    :model-value="exportAll"
                    :indeterminate="!exportAll && exportSelection.size > 0"
                    data-test="export-all"
                    @change="toggleExportAll"
                  >
                    {{ t('releaseNotes.export_all', { count: notesTotal }) }}
                  </el-checkbox>
                  <el-button
                    size="small"
                    type="primary"
                    plain
                    :loading="exportingNotes"
                    :disabled="exportCount === 0"
                    data-test="export-selected"
                    @click="exportNotes()"
                  >
                    {{ t('releaseNotes.export_selected', { count: exportCount }) }}
                  </el-button>
                </div>

                <ul class="nav-list">
                  <li
                    v-for="note in notes"
                    :key="note.id"
                    class="nav-item"
                    :class="{ active: tabIsReleases && selectedNote?.id === note.id && !editorOpen }"
                    @click="selectNote(note)"
                  >
                    <div class="nav-item-main">
                      <el-checkbox
                        class="nav-item-check"
                        :model-value="isExportSelected(note.id)"
                        :aria-label="t('releaseNotes.export_selected', { count: 1 })"
                        @click.stop
                        @change="toggleExportSelection(note.id)"
                      />
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
                      <!-- Profile picture of the author, when the account has one -->
                      <UserAvatar
                        v-if="note.author && note.author_avatar_url"
                        class="nav-item-avatar"
                        :username="note.author"
                        :avatar-url="note.author_avatar_url"
                        :size="16"
                      />
                      <span>{{ formatDate(note.published_date || note.updated_date) }}</span>
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

              <!-- A repository can hold hundreds of tags: the search narrows the
                   list before it is paged, so a tag is reachable by name -->
              <el-input
                v-if="tags.length > 0"
                v-model="tagSearch"
                class="nav-search"
                size="small"
                clearable
                :prefix-icon="Search"
                :placeholder="t('releaseNotes.tags_search_placeholder')"
                data-test="tags-search"
              />

              <!-- a first load is a wait, not an empty repository: show the load
                   instead of a premature "no tags" while the provider is asked -->
              <ContentLoader
                v-if="refsLoading && tags.length === 0"
                :rows="5"
                :label="t('releaseNotes.tags_loading')"
              />
              <el-empty
                v-else-if="tags.length === 0"
                :description="t('releaseNotes.tags_empty')"
                :image-size="60"
              />
              <el-empty
                v-else-if="filteredTags.length === 0"
                :description="t('releaseNotes.tags_no_match')"
                :image-size="60"
              />

              <template v-else>
                <ul ref="tagListRef" class="nav-list">
                  <li
                    v-for="tag in visibleTags"
                    :key="tag"
                    class="nav-item tag-item"
                    :class="{ active: selectedTag === tag && !editorOpen }"
                    :data-tag-name="tag"
                    @click="selectTag(tag)"
                  >
                    <div class="nav-item-main">
                      <span class="nav-item-name">{{ tag }}</span>
                      <!-- A tag can only show a note icon when a release exists for it -->
                      <el-tooltip
                        v-if="tagHasNote(tag)"
                        :content="t('releaseNotes.open_note')"
                        placement="top"
                        :show-after="100"
                      >
                        <el-button
                          link
                          type="primary"
                          size="small"
                          class="tag-note-link"
                          :icon="Document"
                          :aria-label="t('releaseNotes.open_note')"
                          @click.stop="openNoteForTag(tag)"
                        />
                      </el-tooltip>
                    </div>
                  </li>
                </ul>

                <el-pagination
                  v-if="filteredTags.length > tagPageSize"
                  v-model:current-page="tagPage"
                  v-model:page-size="tagPageSize"
                  class="nav-pagination"
                  size="small"
                  background
                  :page-sizes="[10, 20, 50, 100]"
                  :total="filteredTags.length"
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
                <!-- The badges and the actions now live on each entry, so the
                     header describes the page (or the tag) and not a selection. -->
                <el-tag
                  v-if="tabIsReleases && !editorOpen && notesTotal"
                  size="small"
                  type="info"
                  round
                  data-test="page-count"
                >
                  {{ notesTotal }}
                </el-tag>
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
                <el-option v-for="tag in sortedTags" :key="tag" :label="tag" :value="tag" />
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
                  <el-checkbox
                    v-if="llmEnabled"
                    v-model="aiSummary"
                    size="small"
                    style="margin-left: 8px"
                  >
                    {{ t('releaseNotes.ai_summary') }}
                  </el-checkbox>
                  <span v-if="generatedCount !== null" class="generated-hint">
                    {{ t('releaseNotes.generated', { count: generatedCount }) }}
                  </span>
                  <span v-if="summarizedByAi" class="generated-hint">
                    · {{ t('releaseNotes.generated_with_ai') }}
                  </span>
                </div>
                <div v-if="!llmEnabled" class="field-hint">
                  {{ t('releaseNotes.ai_summary_unavailable') }}
                </div>
                <!-- the pass was asked for and could not be made: the notes on
                     screen came from the commit subjects, and this says why -->
                <div v-else-if="aiFallback" class="field-hint ai-summary-fallback">
                  <span>{{ aiFallbackMessage }}</span>
                  <!-- the provider's own message, which is what can be acted on -->
                  <code v-if="summaryError" class="ai-summary-error">{{ summaryError }}</code>
                </div>
                <div v-else-if="aiSummary" class="field-hint">
                  {{ t('releaseNotes.ai_summary_help') }}
                </div>
                <MdEditor
                  v-model="form.body"
                  :toolbars="toolbars"
                  :theme="mdTheme"
                  :language="mdLanguage"
                  preview-theme="github"
                  :style="{ height: '420px' }"
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
              <span>{{ tagScopeHint }}</span>
              <span v-if="!tagCommitsLoading"> · {{ t('releaseNotes.commit_count', { count: tagCommitCount }) }}</span>
            </div>

            <el-alert
              v-if="tagScopeInferred"
              class="status-alert"
              type="warning"
              :closable="false"
              :title="t('releaseNotes.scope_inferred', { from: tagScope?.previous ?? '' })"
            />

            <el-alert
              v-if="tagScopeTrimmed"
              class="status-alert"
              type="warning"
              :closable="false"
              :title="tagTrimNotice"
            />

            <ContentLoader
              v-if="tagCommitsLoading"
              :rows="5"
              :label="t('releaseNotes.commits_loading')"
            />

            <commit-table v-else :commits="tagCommits" :empty-text="t('releaseNotes.commits_empty')" />
          </template>

          <!-- Every release of the current page, one entry each -->
          <template v-else-if="tabIsReleases && notes.length">
            <article
              v-for="note in notes"
              :key="note.id"
              class="note-entry"
              :class="{ focused: selectedNote?.id === note.id }"
              :data-note-id="note.id"
            >
              <header class="note-entry-header">
                <div class="note-entry-title">
                  <h4 class="note-entry-name">
                    <!-- The title links back to the tag the release was cut from:
                         the mirror of the note icon in the tag navigator -->
                    <a
                      class="note-entry-tag-link"
                      href="#"
                      @click.prevent="openTagForNote(note.tag_name)"
                    >
                      {{ note.name }}
                    </a>
                  </h4>
                  <!-- the tag is the version's identity: it reads at the same
                       weight as the title, while the status badges stay small -->
                  <el-tag effect="plain">{{ note.tag_name }}</el-tag>
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

                <!-- The actions belong to the entry they sit on, so a release can
                     be acted on without selecting it first -->
                <div class="note-entry-actions">
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
                  <el-button
                    link
                    type="primary"
                    size="small"
                    :loading="exportingNotes"
                    @click="exportNotes([note.id])"
                  >
                    {{ t('releaseNotes.export_one') }}
                  </el-button>
                  <el-button
                    link
                    type="primary"
                    size="small"
                    :loading="copyingNote"
                    @click="copyNote(note)"
                  >
                    {{ t('releaseNotes.copy_one') }}
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
              </header>

              <div class="release-meta">
                <span v-if="note.author" class="release-author">
                  <UserAvatar
                    v-if="note.author_avatar_url"
                    class="release-author-avatar"
                    :username="note.author"
                    :avatar-url="note.author_avatar_url"
                    :size="22"
                  />
                  {{ t('releaseNotes.released_by', { author: note.author }) }}
                </span>
                <span v-if="note.published_date">
                  · {{ formatDate(note.published_date) }}
                </span>
                <span v-else-if="note.updated_date">
                  · {{ t('releaseNotes.updated_at', { date: formatDate(note.updated_date) }) }}
                </span>
                <span v-if="note.previous_tag" class="release-range">
                  ·
                  {{
                    t('releaseNotes.range', {
                      from: note.previous_tag,
                      to: note.tag_name,
                    })
                  }}
                </span>
              </div>

              <div
                v-if="note.body"
                class="release-body"
                :class="{ collapsed: isNoteCollapsed(note) }"
                @click="openNoteLink"
              >
                <MdPreview :model-value="noteBody(note.body)" :theme="mdTheme" preview-theme="github" />
                <div v-if="isNoteCollapsed(note)" class="note-fade" />
              </div>
              <p v-else class="muted">{{ t('releaseNotes.notes_empty') }}</p>

              <!-- Collapsing is a reading aid: the notes stay whole in the release
                   and in an export -->
              <el-button
                v-if="isLongNote(note)"
                link
                type="primary"
                size="small"
                class="note-expand"
                @click="toggleNoteExpanded(note.id)"
              >
                {{
                  isNoteCollapsed(note)
                    ? t('releaseNotes.show_more')
                    : t('releaseNotes.show_less')
                }}
              </el-button>
            </article>

            <el-pagination
              v-if="notesTotal > notesPageSize"
              v-model:current-page="notesPage"
              v-model:page-size="notesPageSize"
              class="detail-pagination"
              :page-sizes="[5, 10, 20, 50]"
              :total="notesTotal"
              layout="total, sizes, prev, pager, next"
              background
            />
          </template>

          <ContentLoader
            v-else-if="notesLoading"
            :rows="6"
            :label="t('releaseNotes.notes_loading')"
          />

          <el-empty
            v-else
            :description="
              t(
                !hasCoordinates
                  ? 'releaseNotes.needs_repository'
                  : notesTotal === 0
                    ? 'releaseNotes.empty'
                    : 'releaseNotes.select_hint',
              )
            "
          />
        </el-card>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { GIT_PROVIDER_OPTIONS } from '@/constants/gitProvider'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowDown, Close, Document, InfoFilled, Refresh, Search } from '@element-plus/icons-vue'
import { MdEditor, MdPreview, type ToolbarNames } from 'md-editor-v3'
import 'md-editor-v3/lib/style.css'
import { projectsApi } from '@/api/projects'
import type { CloudWorkspaceOption, ProjectSummary, RepositorySummary } from '@/api/projects'
import { releaseDiffApi } from '@/api/releaseDiff'
import type { CommitInfo } from '@/api/releaseDiff'
import CommitTable from '@/components/release/CommitTable.vue'
import ContentLoader from '@/components/common/ContentLoader.vue'
import UserAvatar from '@/components/user/UserAvatar.vue'
import { useJira } from '@/composables/useJira'
import { linkifyJiraMarkdown } from '@/utils/jira'
import { releaseNotesApi, type ReleaseNote } from '@/api/releaseNotes'
import type {
  ReleaseNoteExportRequest,
  ReleaseScopeReason,
  ReleaseScopeSource,
} from '@/api/releaseNotes'
import { copyTextToClipboard, downloadMarkdown } from '@/utils/export/markdown'
import { llmApi } from '@/api/llm'
import { useAuthStore } from '@/stores/auth'

type NavigatorTab = 'releases' | 'tags'

const { t, locale } = useI18n()
const authStore = useAuthStore()
// JIRA link settings: also used to link the ticket keys of hand written notes
const { jiraSettings, loadJiraSettings } = useJira()

// Release notes are manageable by review administrators (RBAC: release_note.manage)
const MANAGE_ROLES = ['review_admin', 'system_admin']

const PREVIEW_MAX_COMMITS = 500
// GET /release/notes accepts at most 200 rows per call (backend cap)
const NOTE_LOOKUP_PAGE_SIZE = 200
// Safety bound when indexing the released tags of a repository
const NOTE_LOOKUP_MAX = 2000

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
  '-',
  // reading the note as it will be published, next to the markdown being typed
  'preview',
  'previewOnly',
  'catalog',
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

// The coordinate panel is open on arrival: it is what a first visit fills in
const coordinatesOpen = ref(true)
// The tag navigator is searched by name, not paged through
const tagSearch = ref('')

const notes = ref<ReleaseNote[]>([])
const notesTotal = ref(0)
const notesLoading = ref(false)
// Export selection: either the releases ticked in the list, or every release of
// the repository - the latter covers releases the paginated list has not loaded,
// which is what "export the change log" means. The two are exclusive: ticking a
// release after selecting all narrows the export down to what was ticked.
const exportSelection = ref<Set<number>>(new Set())
const exportAll = ref(false)
const exportingNotes = ref(false)
const copyingNote = ref(false)

// How many releases the export would write: everything, or what is ticked
const exportCount = computed(() =>
  exportAll.value ? notesTotal.value : exportSelection.value.size,
)

// Notes long enough to be collapsed are expanded one entry at a time; the state
// is dropped when the page changes.
const NOTE_COLLAPSE_LINES = 20
const NOTE_COLLAPSE_CHARS = 1500
const expandedNotes = ref<Set<number>>(new Set())

/**
 * Whether the notes of a release are long enough to be worth collapsing.
 *
 * The decision is taken from the text rather than from the rendered height: the
 * test environment has no layout engine, so a measured overflow check could never
 * be asserted, and it would also depend on the renderer and the font.
 */
function isLongNote(note: ReleaseNote): boolean {
  const body = note.body ?? ''
  return body.length > NOTE_COLLAPSE_CHARS || body.split('\n').length > NOTE_COLLAPSE_LINES
}

/** Whether the notes are rendered collapsed (long, and not expanded by hand). */
function isNoteCollapsed(note: ReleaseNote): boolean {
  return isLongNote(note) && !expandedNotes.value.has(note.id)
}

function toggleNoteExpanded(noteId: number) {
  const next = new Set(expandedNotes.value)
  if (next.has(noteId)) {
    next.delete(noteId)
  } else {
    next.add(noteId)
  }
  expandedNotes.value = next
}

function isExportSelected(noteId: number): boolean {
  return exportAll.value || exportSelection.value.has(noteId)
}

/** Tick or untick one release. Ticking one leaves the "all releases" mode. */
function toggleExportSelection(noteId: number) {
  if (exportAll.value) {
    exportAll.value = false
    exportSelection.value = new Set([noteId])
    return
  }

  const next = new Set(exportSelection.value)
  if (next.has(noteId)) {
    next.delete(noteId)
  } else {
    next.add(noteId)
  }
  exportSelection.value = next
}

/** Switch between every release of the repository and the ticked ones. */
function toggleExportAll(checked: unknown) {
  exportAll.value = Boolean(checked)
  if (exportAll.value) {
    exportSelection.value = new Set()
  }
}

function clearExportSelection() {
  exportAll.value = false
  exportSelection.value = new Set()
}
// Column 1 is a navigator with two tabs: stored releases and repository tags
const activeTab = ref<NavigatorTab>('releases')
const tabIsReleases = computed(() => activeTab.value === 'releases')
const tabIsTags = computed(() => activeTab.value === 'tags')
// Releases are paginated by the backend, tags are paginated in the browser
const notesPage = ref(1)
const notesPageSize = ref(10)
const tagPage = ref(1)
const tagPageSize = ref(20)
// the rendered page of the tag navigator, used to bring a tag into view
const tagListRef = ref<HTMLElement | null>(null)
// Either a stored release or a tag is selected, depending on the active tab
const selectedId = ref<number | null>(null)
const selectedTag = ref<string | null>(null)
const selectedNote = computed(() => notes.value.find((note) => note.id === selectedId.value) ?? null)
// Commits covered by the selected tag (the tag -> commits mapping)
const tagCommits = ref<CommitInfo[]>([])
const tagCommitCount = ref(0)
const tagCommitsLoading = ref(false)
const tagTruncated = ref(false)
// Release scope of the selected tag as the server resolved it: the predecessor it
// found, the revisions the comparison was pinned to, and whether the answer was
// proven (an ancestor) or inferred from the tag order
const tagScope = ref<{
  previous: string | null
  previousSha: string | null
  versionSha: string | null
  source: ReleaseScopeSource
  verified: boolean
  reason: ReleaseScopeReason
} | null>(null)
// tag name -> release (id + position in the full list), loaded for the tags tab
const releaseTagIndex = ref<Map<string, { id: number; position: number }>>(new Map())
const releaseTagIndexLoaded = ref(false)
const releaseTagIndexLoading = ref(false)

const saving = ref(false)
const importing = ref(false)
const generating = ref(false)
const generatedCount = ref<number | null>(null)
// The AI pass is optional and server-side: the switch is only offered when the
// deployment has an LLM configured (System Settings -> LLM).
type SummaryNotice = 'not_configured' | 'provider_error' | 'unreadable_answer' | 'failed'

const llmEnabled = ref(false)
const aiSummary = ref(false)
const summarizedByAi = ref(false)
const summaryNotice = ref<SummaryNotice | null>(null)
// What the provider said when it refused the call, when it said anything: the
// one thing that tells an administrator what to change.
const summaryError = ref<string | null>(null)

// A pass that was asked for and could not be made is answered with the
// deterministic notes, so say which one is on screen instead of leaving the
// reader to guess whether the sections came from the AI or from the subjects.
const aiFallback = computed<SummaryNotice | null>(() =>
  aiSummary.value && !summarizedByAi.value ? summaryNotice.value : null,
)
const aiFallbackMessage = computed(() => {
  switch (aiFallback.value) {
    case 'not_configured':
      return t('releaseNotes.ai_summary_fallback_not_configured')
    case 'provider_error':
      return t('releaseNotes.ai_summary_fallback_provider_error')
    case 'unreadable_answer':
      return t('releaseNotes.ai_summary_fallback_unreadable_answer')
    case 'failed':
      return t('releaseNotes.ai_summary_fallback_failed')
    default:
      return ''
  }
})
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
// The library only ships zh-CN and en-US tooltips, and answers an unknown
// language with English - closer to zh-CN than that for a Chinese UI
const mdLanguage = computed(() => (locale.value.startsWith('zh') ? 'zh-CN' : 'en-US'))

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

// Newest first: versions compare numerically so v1.10.0 sorts above v1.9.0.
// The provider returns the tags in its own order (Bitbucket Cloud lists them
// alphabetically, i.e. oldest first), so every tag picker uses this order.
const sortedTags = computed(() =>
  [...tags.value].sort((a, b) => b.localeCompare(a, undefined, { numeric: true })),
)
const selectableRefs = computed(() => [...sortedTags.value, ...branches.value])

/** Whether a tag survives the search box, by a plain substring of its name. */
function tagMatchesQuery(tag: string): boolean {
  const query = tagSearch.value.trim().toLowerCase()
  return !query || tag.toLowerCase().includes(query)
}

// The search narrows the list before it is paged, so a match is on the first
// page of the result rather than on whichever page its position falls on
const filteredTags = computed(() => sortedTags.value.filter(tagMatchesQuery))
const visibleTags = computed(() => {
  const start = (tagPage.value - 1) * tagPageSize.value
  return filteredTags.value.slice(start, start + tagPageSize.value)
})
/** Short revision, or an empty string when the server resolved none. */
function shortRevision(sha?: string | null): string {
  return (sha ?? '').trim().slice(0, 7)
}

/** A ref with its revision when one is known: ``v1.0.0 (3f2a1b)``. */
function labelWithRevision(ref: string, sha?: string | null): string {
  const short = shortRevision(sha)
  return short ? `${ref} (${short})` : ref
}

// The release scope of a tag is resolved by the server: the browser only holds a
// page of tags, so guessing the predecessor here used to lose the scope of every
// tag beyond that page and list the whole history instead.
const tagScopeResolved = computed(() => tagScope.value?.reason === 'resolved')

const tagScopeRange = computed(() => {
  const scope = tagScope.value
  if (!scope || !scope.previous || !tagScopeResolved.value) return null
  return t('releaseNotes.range', {
    from: labelWithRevision(scope.previous, scope.previousSha),
    to: labelWithRevision(selectedTag.value ?? '', scope.versionSha),
  })
})

// A scope inferred from the tag order is a legitimate answer, just not a proven one
const tagScopeInferred = computed(
  () => Boolean(tagScope.value) && tagScopeResolved.value && !tagScope.value?.verified,
)

// A capped listing borrows its meaning from the scope: for a resolved scope it is
// a display limit, and the panel must not present it as a repository limit
const tagScopeTrimmed = computed(() => tagTruncated.value && tagScopeResolved.value)

const tagTrimNotice = computed(() =>
  tagCommits.value.length < tagCommitCount.value
    ? t('releaseNotes.commits_trimmed', {
        shown: tagCommits.value.length,
        count: tagCommitCount.value,
      })
    : t('releaseNotes.commits_scan_capped'),
)

/** Scope line of the tags panel: the range when resolved, why otherwise. */
const tagScopeHint = computed(() => {
  const tag = selectedTag.value ?? ''
  const scope = tagScope.value

  if (scope?.reason === 'first_release') {
    return t('releaseNotes.scope_first_release', { tag })
  }
  if (scope?.reason === 'unresolved') {
    return t('releaseNotes.scope_unresolved', { tag })
  }
  if (scope) {
    return tagScopeRange.value ?? t('releaseNotes.full_history', { tag })
  }
  // no answer yet: the local tag order is only a placeholder for the label
  const guess = previousTagFor(tag)
  return guess
    ? t('releaseNotes.range', { from: guess, to: tag })
    : t('releaseNotes.full_history', { tag })
})

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
  // The column holds a page of releases, so its title describes the list rather
  // than one selection (the badges and the actions moved into the entries).
  return t('releaseNotes.list_title')
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

/**
 * Clean the ref names of the provider response.
 *
 * A repeated entry would otherwise render one identical row per occurrence in
 * the tag / branch pickers, so the list is de-duplicated (and blanks dropped).
 */
function uniqueRefs(values: string[] | null | undefined): string[] {
  return [...new Set((values ?? []).map((value) => value.trim()).filter(Boolean))]
}

/** Select a stored release and show its notes. */
function selectNote(note: ReleaseNote) {
  closeForm()
  selectedId.value = note.id
  void scrollToNoteEntry(note.id)
}

/**
 * Bring the entry of a release into view in the reading column.
 *
 * The column lists the whole page, so picking a release scrolls to it instead of
 * replacing what is rendered. The wait is bounded and repeated: jumping from the
 * tags tab can change the page first, and that reload is started by a watcher
 * rather than awaited here.
 */
async function scrollToNoteEntry(noteId: number) {
  for (let attempt = 0; attempt < 10; attempt += 1) {
    await nextTick()
    const target = document.querySelector(`[data-note-id="${noteId}"]`)
    if (target) {
      target.scrollIntoView?.({ behavior: 'smooth', block: 'start' })
      return
    }
    await new Promise((resolve) => setTimeout(resolve, 50))
  }
}

/** Scroll the tag of the navigator into view (the list is paginated). */
async function scrollToTagItem(tag: string) {
  for (let attempt = 0; attempt < 10; attempt += 1) {
    await nextTick()
    const items = tagListRef.value?.querySelectorAll<HTMLElement>('.tag-item') ?? []
    const target = Array.from(items).find((item) => item.dataset.tagName === tag)
    if (target) {
      target.scrollIntoView?.({ behavior: 'smooth', block: 'nearest' })
      return
    }
    await new Promise((resolve) => setTimeout(resolve, 50))
  }
}

/** Select a tag and show the commits it released. */
function selectTag(tag: string) {
  closeForm()
  selectedTag.value = tag
  void loadTagCommits(tag)
}

/** Whether a release note exists for a tag (independent of the current page). */
function tagHasNote(tag: string): boolean {
  return releaseTagIndex.value.has(tag)
}

/**
 * Build the tag -> release index once per repository.
 *
 * The navigator only holds the current page of releases, but a tag has to show
 * its note icon (and jump to the note) no matter which page that release is on.
 */
async function loadReleaseTagIndex(force = false) {
  if (!hasCoordinates.value || releaseTagIndexLoading.value) {
    return
  }
  if (releaseTagIndexLoaded.value && !force) {
    return
  }

  const projectKey = selectedProjectKey.value
  const repositorySlug = selectedRepositorySlug.value

  releaseTagIndexLoading.value = true
  try {
    const index = new Map<string, { id: number; position: number }>()
    let position = 0
    let total = Number.POSITIVE_INFINITY

    // A page holds at most 200 rows, so walk the pages to cover every release and
    // keep the positions aligned with the paginated list of the releases tab.
    while (position < total && position < NOTE_LOOKUP_MAX) {
      const response = await releaseNotesApi.list({
        project_key: projectKey,
        repository_slug: repositorySlug,
        limit: NOTE_LOOKUP_PAGE_SIZE,
        offset: position,
      })
      const items: ReleaseNote[] = response.items ?? []
      items.forEach((note, indexInPage) => {
        if (!index.has(note.tag_name)) {
          index.set(note.tag_name, { id: note.id, position: position + indexInPage })
        }
      })
      total = response.total ?? position + items.length
      if (items.length === 0) {
        break
      }
      position += items.length
    }

    // another repository may have been selected while the pages were loading
    if (
      projectKey !== selectedProjectKey.value ||
      repositorySlug !== selectedRepositorySlug.value
    ) {
      return
    }

    releaseTagIndex.value = index
    releaseTagIndexLoaded.value = true
  } catch {
    // the tags tab stays usable, only the note icons are missing
    ElMessage.error(t('releaseNotes.load_failed'))
  } finally {
    releaseTagIndexLoading.value = false
  }
}

function invalidateReleaseTagIndex() {
  releaseTagIndex.value = new Map()
  releaseTagIndexLoaded.value = false
}

/** Releases changed: drop the tag icons and reload them when they are on screen. */
function refreshReleaseTagIndex() {
  invalidateReleaseTagIndex()
  if (tabIsTags.value) {
    void loadReleaseTagIndex()
  }
}

/** Jump from a tag to its release note (the note icon in the tags tab). */
async function openNoteForTag(tag: string) {
  closeForm()
  await loadReleaseTagIndex()

  const entry = releaseTagIndex.value.get(tag)
  if (!entry) {
    return
  }

  activeTab.value = 'releases'
  // Select before paging: the reload keeps a selection that is on the new page
  selectedId.value = entry.id
  const page = Math.floor(entry.position / notesPageSize.value) + 1
  if (page !== notesPage.value) {
    notesPage.value = page
  }
  // the entry may only exist once the page it belongs to has loaded
  void scrollToNoteEntry(entry.id)
}

/**
 * Mirror of openNoteForTag: from a release to the tag it was cut from.
 *
 * The tag navigator is paginated in the browser, so the page holding the tag is
 * opened before the item is scrolled to; selecting it also loads the commits it
 * released, which is where the release's scope can be inspected.
 */
function openTagForNote(tag: string) {
  activeTab.value = 'tags'

  // a search that hides the tag would leave the jump pointing at nothing
  if (!tagMatchesQuery(tag)) {
    tagSearch.value = ''
  }

  const position = filteredTags.value.indexOf(tag)
  if (position >= 0) {
    const page = Math.floor(position / tagPageSize.value) + 1
    if (page !== tagPage.value) {
      tagPage.value = page
    }
  }

  // selects the tag (and closes an open editor) and loads its commits
  selectTag(tag)
  void scrollToTagItem(tag)
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
    tags.value = uniqueRefs(response.tags)
    branches.value = uniqueRefs(response.branches)
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
      // A refreshed tag list is the moment a new tag may exist or an old one may
      // have been moved, so the scope of the current selection is re-resolved
      // instead of being served from the cache.
      if (selectedTag.value) {
        void loadTagCommits(selectedTag.value, true)
      }
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
  // an expanded note belongs to the page it was expanded on
  expandedNotes.value = new Set()
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
async function loadTagCommits(tag: string, refresh = false) {
  tagCommits.value = []
  tagCommitCount.value = 0
  tagTruncated.value = false
  tagScope.value = null
  if (!hasCoordinates.value) return

  tagCommitsLoading.value = true
  try {
    // The predecessor is resolved on the server: the browser only holds a page of
    // tags, and guessing it here used to lose the scope of every tag beyond that
    // page (the whole history was listed instead).
    const response = await releaseNotesApi.preview({
      ...coordinates(),
      version: tag,
      max_commits: PREVIEW_MAX_COMMITS,
      refresh,
    })
    // a newer click may have overtaken this response
    if (selectedTag.value !== tag) return
    tagCommits.value = (response.commits ?? []) as CommitInfo[]
    tagCommitCount.value = response.commit_count ?? tagCommits.value.length
    tagTruncated.value = Boolean(response.truncated)
    tagScope.value = {
      previous: response.previous_version ?? null,
      previousSha: response.previous_sha ?? null,
      versionSha: response.version_sha ?? null,
      source: response.previous_source ?? 'none',
      verified: Boolean(response.previous_verified),
      reason: response.scope_reason ?? 'unresolved',
    }
  } catch {
    ElMessage.error(t('releaseNotes.commits_load_failed'))
  } finally {
    tagCommitsLoading.value = false
  }
}

// ------------------------------------------------------------------ #
// Export
// ------------------------------------------------------------------ #

/**
 * Export releases as one markdown document.
 *
 * The document is assembled by the backend: the page holds one page of releases,
 * and a text document has to read the same whoever asked for it. Passing `ids`
 * exports exactly those releases (the detail header does that for one release);
 * otherwise the current selection decides - every release of the repository, or
 * the ticked ones.
 */
async function exportNotes(ids?: number[]) {
  if (!hasCoordinates.value) return

  const payload: ReleaseNoteExportRequest = ids
    ? { ...coordinates(), ids }
    : exportAll.value
      ? { ...coordinates(), select_all: true }
      : { ...coordinates(), ids: [...exportSelection.value] }

  if (!payload.ids?.length && !payload.select_all) return

  exportingNotes.value = true
  try {
    const exported = await releaseNotesApi.exportNotes(payload)
    downloadMarkdown(exported.content, exported.filename)
    ElMessage.success(t('releaseNotes.exported_ok', { count: exported.count }))
    if (exported.truncated) {
      ElMessage.warning(t('releaseNotes.exported_truncated', { count: exported.count }))
    }
    if (exported.skipped_ids.length > 0) {
      ElMessage.warning(
        t('releaseNotes.exported_skipped', { count: exported.skipped_ids.length }),
      )
    }
  } catch {
    ElMessage.error(t('releaseNotes.export_failed'))
  } finally {
    exportingNotes.value = false
  }
}

/**
 * Put the open release on the clipboard.
 *
 * The same document the download would produce, so the two cannot disagree; a
 * refused clipboard (a non-secure context, a denied permission) is reported so a
 * copy that did nothing is never mistaken for one that worked.
 */
async function copyNote(note: ReleaseNote) {
  if (!hasCoordinates.value) return

  copyingNote.value = true
  try {
    const exported = await releaseNotesApi.exportNotes({
      ...coordinates(),
      ids: [note.id],
    })
    const copied = await copyTextToClipboard(exported.content)
    if (copied) {
      ElMessage.success(t('releaseNotes.copied_ok'))
    } else {
      ElMessage.warning(t('releaseNotes.copy_failed'))
    }
  } catch {
    ElMessage.error(t('releaseNotes.export_failed'))
  } finally {
    copyingNote.value = false
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
/**
 * Note body as it is rendered.
 *
 * The backend links the JIRA tickets of the notes it generates itself; a body
 * written or imported by hand keeps its plain text, so the ticket keys are
 * linked here as well (code blocks and existing links stay untouched).
 */
function noteBody(body?: string | null): string {
  return linkifyJiraMarkdown(body, jiraSettings.value)
}

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
  // The tag the release is being drafted for, in order of preference:
  //   1. the tag that was clicked next to the draft button,
  //   2. the tag selected in the tags navigator (the draft button of the list
  //      header must not fall back to another version while a tag is active),
  //   3. the newest tag - the provider order hands out the oldest one (v0.1.0)
  const selected = tabIsTags.value ? selectedTag.value : null
  const initial = tag ?? selected ?? sortedTags.value[0] ?? tags.value[0]
  if (initial) {
    form.value.tag_name = initial
    // The draft inherits the scope the server resolved for that tag, so the editor
    // generates the same commit set the tags panel shows. The local tag order is
    // only a fallback for a tag the resolver has not looked at.
    const scope = initial === selectedTag.value ? tagScope.value : null
    form.value.previous_tag = (scope ? scope.previous : previousTagFor(initial)) ?? ''
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

async function loadLlmConfig() {
  try {
    const config = await llmApi.getConfig()
    llmEnabled.value = Boolean(config.enabled)
  } catch {
    // an unconfigured LLM simply means the deterministic notes are the only option
    llmEnabled.value = false
  }
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
      language: locale.value,
      summarize: aiSummary.value && llmEnabled.value,
    })
    form.value.body = preview.body
    if (!form.value.name.trim()) {
      form.value.name = preview.suggested_name
    }
    generatedCount.value = preview.commit_count
    // The server falls back to the deterministic notes when the LLM call fails,
    // so the answer says which one is on screen rather than assuming the switch
    summarizedByAi.value = preview.summary_source === 'llm'
    summaryNotice.value = preview.summary_notice ?? null
    summaryError.value = preview.summary_error ?? null
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
    refreshReleaseTagIndex()
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
    refreshReleaseTagIndex()
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
    // This page may have held nothing but the release just deleted: step back on
    // to the last page that still has releases instead of showing an empty list.
    if (notes.value.length <= 1 && notesPage.value > 1) {
      notesPage.value -= 1
    } else {
      await loadNotes()
    }
    refreshReleaseTagIndex()
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
    // an export selection belongs to the releases it was made from
    clearExportSelection()
    selectedId.value = null
    selectedTag.value = null
    tagCommits.value = []
    tagCommitCount.value = 0
    notesPage.value = 1
    tagPage.value = 1
    // a search for a tag of the previous repository means nothing here
    tagSearch.value = ''
    invalidateReleaseTagIndex()
    void loadRefs()
    void loadNotes()
    if (tabIsTags.value) {
      void loadReleaseTagIndex()
    }
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

// A narrower search has a result of its own: start it from its first page
watch(tagSearch, () => {
  tagPage.value = 1
})

// The tags tab maps a tag to the commits it released: pick the newest tag when
// the tab is opened without an explicit selection, and know which tags have a
// release so their note icon can be shown
watch(activeTab, (tab) => {
  if (tab !== 'tags') {
    return
  }
  void loadReleaseTagIndex()
  if (!selectedTag.value) {
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
  void loadJiraSettings()
  void loadLlmConfig()
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

.card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.card-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

/* The read-only label and the fold toggle sit together at the end of the header */
.header-end {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* The chevron points at the closed panel once the body is folded away */
.panel-toggle :deep(.el-icon) {
  transition: transform 0.2s ease;
}

.panel-toggle.is-collapsed :deep(.el-icon) {
  transform: rotate(-90deg);
}

/* Folded away rather than unmounted: the repository that was picked stays
   picked, and the panel comes back exactly as it was left */
.panel-body.is-collapsed {
  display: none;
}

/* Read-only label of a user without the release administrator role: the label
   states the limitation, the tooltip explains it */
.read-only-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  cursor: help;
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

.export-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}

.nav-item-check {
  height: auto;
  margin-right: 0;
}

.nav-search {
  margin-bottom: 8px;
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
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.nav-item-avatar {
  /* keep the requested size: the border must not grow the icon */
  box-sizing: border-box;
  border: 1px solid var(--el-border-color-lighter);
}

.tag-item .nav-item-main {
  justify-content: space-between;
}

/* Note icon of a tag that already has a release */
.tag-note-link {
  height: auto;
  padding: 2px;
}

.detail-card .release-meta {
  margin-top: 0;
}

.detail-card .release-body {
  margin-top: 12px;
}

/* Reading column: one entry per release of the page */
.note-entry {
  padding: 16px 0 20px;
  border-bottom: 1px solid var(--el-border-color);
}

.note-entry:last-of-type {
  border-bottom: 0;
}

.note-entry.focused {
  margin-left: -12px;
  padding-left: 10px;
  border-left: 2px solid var(--el-color-primary);
}

.note-entry-header {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}

.note-entry-title {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

/* The release name is the line that identifies a version on a page holding
   several of them, so nothing inside the notes may compete with it. */
.note-entry-name {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  line-height: 1.3;
  color: var(--el-text-color-primary);
}

/* The title is the anchor onto the tag it was cut from, so it keeps the weight of
   the entry while behaving like a link on hover and on focus. */
.note-entry-tag-link {
  color: inherit;
  text-decoration: none;
}

.note-entry-tag-link:hover,
.note-entry-tag-link:focus-visible {
  color: var(--el-color-primary);
  text-decoration: underline;
  text-underline-offset: 3px;
}

.note-entry-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 2px;
}

/* A long note is clamped with a fade; the expand control follows it */
.release-body.collapsed {
  max-height: 24rem;
  overflow: hidden;
}

.note-fade {
  position: absolute;
  inset-inline: 0;
  bottom: 0;
  height: 3rem;
  background: linear-gradient(transparent, var(--el-bg-color));
  pointer-events: none;
}

.note-expand {
  margin-top: 4px;
}

.detail-pagination {
  margin-top: 12px;
  justify-content: flex-end;
}

.detail-pagination :deep(.el-pagination__total),
.detail-pagination :deep(.el-pagination__sizes) {
  margin-right: auto;
}

.release-meta {
  margin-top: 6px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.release-author {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  vertical-align: middle;
}

.release-author-avatar {
  box-sizing: border-box;
  border: 1px solid var(--el-border-color-lighter);
  vertical-align: middle;
}

.release-body {
  position: relative;
  margin-top: 12px;
}

/* The rendered notes must not outrank the release name (20px).
   md-editor's github theme renders a level-2 heading - which is what a generated
   body opens with ("## What's Changed") - at 1.5em with 24px/16px block margins,
   and inherits its base size from the page. The scale is therefore pinned here
   instead of being left to the ambient font size: the notes are the content of a
   release, so 14px text with a 16px top heading, below the release name. */
.release-body :deep(.github-theme) {
  font-size: 14px;
}

.release-body :deep(h1),
.release-body :deep(h2) {
  font-size: 16px;
}

.release-body :deep(h3) {
  font-size: 15px;
}

.release-body :deep(h4),
.release-body :deep(h5),
.release-body :deep(h6) {
  font-size: 14px;
}

.release-body :deep(h1),
.release-body :deep(h2),
.release-body :deep(h3),
.release-body :deep(h4),
.release-body :deep(h5),
.release-body :deep(h6) {
  margin-block: 14px 8px;
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

/* a summary that was asked for and could not be made is not a help text */
.ai-summary-fallback {
  color: var(--el-color-warning);
}

.ai-summary-error {
  display: block;
  margin-top: 2px;
  font-family: var(--el-font-family-mono, monospace);
  opacity: 0.85;
  word-break: break-word;
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
