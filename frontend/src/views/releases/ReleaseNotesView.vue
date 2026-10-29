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
          <el-col :xs="24" :sm="12" :md="8">
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
          <el-col :xs="24" :sm="12" :md="8">
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
          <el-col v-if="isCloudProvider" :xs="24" :sm="12" :md="8">
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
        <el-card ref="notesCard" shadow="never" class="notes-card">
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
                   list before it is paged, so a tag is reachable by name. It is the
                   one control of this panel a reader types into, so it is a full-sized
                   field - 40px with 14px text, the height the application's other
                   search field uses - rather than the smallest the component offers,
                   which is where it had been left: 24px with 12px text, under every
                   field around it. The height rides on the input itself, not only in
                   the stylesheet below: see TAG_SEARCH_STYLE. -->
              <el-input
                v-if="tags.length > 0"
                v-model="tagSearch"
                class="nav-search"
                size="large"
                clearable
                :prefix-icon="Search"
                :input-style="TAG_SEARCH_STYLE"
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
        <!-- The commits panel fills the card: the modifier hands the card's height down
             to the table, which is a box of a fixed size otherwise (see
             .detail-card--fills). -->
        <el-card
          shadow="never"
          class="detail-card"
          :class="{ 'detail-card--fills': tabIsTags && !!selectedTag && !editorOpen }"
        >
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
                remote
                clearable
                default-first-option
                :remote-method="onRefSearch"
                :loading="refsLoading"
                :disabled="Boolean(editingId)"
                :placeholder="t('releaseNotes.tag_placeholder')"
                style="width: 100%"
                @change="onEditorScopeChange"
              >
                <el-option v-for="tag in candidateTags" :key="tag" :label="tag" :value="tag" />
                <!-- Only a tag the repository reports can carry a note: a name typed
                     by hand would be a note about a release that does not exist. -->
                <template #empty>
                  <p class="ref-empty">{{ t('releaseNotes.ref_no_match') }}</p>
                </template>
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

              <!-- What the notes are supposed to account for, folded away until it is
                   asked for: a writer reads it while writing, but it must not push the
                   form apart for someone who does not. -->
              <div v-if="hasCoordinates && form.tag_name" class="editor-commits-trigger">
                <el-button
                  link
                  type="primary"
                  size="small"
                  :icon="InfoFilled"
                  data-test="editor-commits-toggle"
                  :aria-expanded="editorCommitsOpen"
                  @click="editorCommitsOpen = !editorCommitsOpen"
                >
                  {{ editorCommitsOpen ? t('releaseNotes.hide_commits') : t('releaseNotes.show_commits') }}
                </el-button>
                <span v-if="!editorCommitsOpen && !editorCommitsLoading && editorCommitCount > 0" class="generated-hint">
                  {{ t('releaseNotes.commit_count', { count: editorCommitCount }) }}
                </span>
              </div>
            </el-form-item>

            <!-- The list opens where the scope is decided - between the tag and its
                 predecessor - and stays open while the notes below are written. -->
            <el-form-item v-if="editorCommitsOpen && form.tag_name">
              <div class="editor-commits" data-test="editor-commits">
                <div class="editor-commits-head">
                  <span class="editor-commits-scope">{{ editorScopeHint }}</span>
                  <span v-if="!editorCommitsLoading" class="generated-hint">
                    · {{ t('releaseNotes.commit_count', { count: editorCommitCount }) }}
                  </span>
                  <el-tooltip :content="t('releaseNotes.commits_refresh')" placement="top">
                    <el-button
                      link
                      type="primary"
                      size="small"
                      :icon="Refresh"
                      :loading="editorCommitsLoading"
                      :aria-label="t('releaseNotes.commits_refresh')"
                      data-test="editor-commits-refresh"
                      @click="loadEditorCommits(true)"
                    />
                  </el-tooltip>
                  <!-- The fold that opened this is above it, which is a scroll away once
                       the panel is tall: this is the same fold, where a reader who has
                       read enough will be looking for it. -->
                  <el-tooltip :content="t('releaseNotes.hide_commits')" placement="top">
                    <el-button
                      link
                      size="small"
                      :icon="ArrowUp"
                      :aria-label="t('releaseNotes.hide_commits')"
                      data-test="editor-commits-hide"
                      @click="editorCommitsOpen = false"
                    />
                  </el-tooltip>
                </div>
                <div class="field-hint">{{ t('releaseNotes.editor_commits_help') }}</div>

                <el-alert
                  v-if="editorScopeInferred"
                  class="status-alert"
                  type="warning"
                  :closable="false"
                  :title="t('releaseNotes.scope_inferred', { from: editorScope?.previous ?? '' })"
                />
                <el-alert
                  v-if="editorScopeTrimmed"
                  class="status-alert"
                  type="warning"
                  :closable="false"
                  :title="editorTrimNotice"
                />

                <ContentLoader
                  v-if="editorCommitsLoading"
                  :rows="3"
                  :label="t('releaseNotes.commits_loading')"
                />
                <!-- No cap inside the panel: a page of rows is read whole, so the pager
                     is the only thing that moves the list (see fill-height). Ten rows is
                     what keeps one page about the height of the notes editor beside it;
                     the pager still offers larger pages for a deliberate read-through. -->
                <commit-table
                  v-else
                  fill-height
                  :page-size="10"
                  :commits="editorCommits"
                  :empty-text="t('releaseNotes.commits_empty')"
                />
              </div>
            </el-form-item>

            <el-form-item :label="t('releaseNotes.previous_tag')">
              <el-select
                v-model="form.previous_tag"
                filterable
                remote
                clearable
                :remote-method="onRefSearch"
                :disabled="Boolean(editingId)"
                :placeholder="t('releaseNotes.previous_tag_placeholder')"
                style="width: 100%"
                @change="onEditorScopeChange"
              >
                <el-option v-for="ref in candidateRefs" :key="ref" :label="ref" :value="ref" />
                <template #empty>
                  <p class="ref-empty">{{ t('releaseNotes.ref_no_match') }}</p>
                </template>
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
                  <!-- The one action that fills the editor, so it is the button of the
                       toolbar rather than one of its trimmings: full size, filled, with
                       the icon that says what it makes - and while it runs it says so in
                       words next to the spinner instead of only spinning. -->
                  <el-button
                    class="generate-notes"
                    type="primary"
                    :icon="MagicStick"
                    :loading="generating"
                    :disabled="!hasCoordinates || !form.tag_name"
                    data-test="generate-notes"
                    @click="generateNotes"
                  >
                    {{
                      generating
                        ? t('releaseNotes.generating_notes')
                        : t('releaseNotes.generate_notes')
                    }}
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
                  <!-- a provider that was busy a moment ago is worth asking again,
                       without regenerating the notes from another button -->
                  <el-button
                    v-if="canRetryAiSummary"
                    link
                    type="primary"
                    size="small"
                    class="ai-summary-retry"
                    :loading="generating"
                    @click="generateNotes()"
                  >
                    {{ t('releaseNotes.retry_ai_summary') }}
                  </el-button>
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
                <!-- Publishing writes the notes out, so the button that does it waits
                     for the editor to hold something: this is the word that says why -->
                <div v-if="canSave && !hasNotes" class="field-hint" data-test="notes-required">
                  {{ t('releaseNotes.notes_required') }}
                </div>
              </div>
            </el-form-item>

            <el-form-item>
              <!-- One line: what the release is, and whether it is also written to
                   Confluence. The write is the automatic path, so it is offered only
                   where the instance syncs by itself - and it is disabled while the
                   release is a pre-release, which is never written by itself. Writing
                   one by hand stays available on the release row. -->
              <div class="release-toggles">
                <el-checkbox v-model="form.is_prerelease" data-test="is-prerelease">
                  {{ t('releaseNotes.prerelease') }}
                </el-checkbox>
                <el-checkbox
                  v-if="confluence.configured && confluence.auto_sync"
                  v-model="form.sync_to_confluence"
                  :disabled="form.is_prerelease"
                  data-test="sync-to-confluence"
                >
                  {{ t('releaseNotes.sync_confluence_label') }}
                </el-checkbox>
              </div>
              <!-- Only the disabled state needs a word: why the switch beside it
                   cannot be turned on while the release is a pre-release. -->
              <div
                v-if="confluence.configured && confluence.auto_sync && form.is_prerelease"
                class="field-hint"
              >
                {{ t('releaseNotes.sync_confluence_prerelease') }}
              </div>
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
                :disabled="!canPublish"
                data-test="publish-release"
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

            <!-- The commits of the tag are the panel here, not a list beside something:
                 the table is given the height the card has, so a page of rows is read
                 in it instead of scrolling inside a box of a fixed size -->
            <commit-table
              v-else
              fill-height
              :commits="tagCommits"
              :empty-text="t('releaseNotes.commits_empty')"
            />
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
                  <!-- The tag the release was cut from, as a badge that leaves the
                       app for the repository - so a release can be traced back to
                       the code it describes without hunting for the tag -->
                  <a
                    v-if="note.tag_url"
                    class="note-entry-tag-badge"
                    :href="note.tag_url"
                    target="_blank"
                    rel="noopener noreferrer"
                    :title="t('releaseNotes.tag_link_hint')"
                  >
                    <el-tag size="small" effect="plain" round>
                      <el-icon class="tag-badge-icon"><Link /></el-icon>
                      {{ note.tag_name }}
                    </el-tag>
                  </a>
                  <el-tag v-else size="small" effect="plain" round>{{ note.tag_name }}</el-tag>
                  <el-tag v-if="note.is_latest" size="small" type="success" round>
                    {{ t('releaseNotes.badge_latest') }}
                  </el-tag>
                  <el-tag v-if="note.is_prerelease" size="small" type="warning" round>
                    {{ t('releaseNotes.badge_prerelease') }}
                  </el-tag>
                  <el-tag v-if="note.status === 'draft'" size="small" type="info" round>
                    {{ t('releaseNotes.badge_draft') }}
                  </el-tag>
                  <!-- The sync is a side errand: when it fails the release is
                       still published, and this is where that reads -->
                  <el-tag
                    v-if="note.confluence_sync_error"
                    size="small"
                    type="danger"
                    effect="plain"
                    round
                    :title="note.confluence_sync_error"
                  >
                    {{ t('releaseNotes.badge_confluence_failed') }}
                  </el-tag>
                </div>

                <!-- The actions belong to the entry they sit on, so a release can
                     be acted on without selecting it first. Only what is reached
                     for constantly stays outside the menu: the page the release is
                     on - or the way to put it there - and copying its notes.
                     Everything else is one menu, one row of icons wide, however
                     many releases the page holds. -->
                <div class="note-entry-actions">
                  <!-- The page it is already on, or the way to put it there -->
                  <el-button
                    v-if="note.confluence_url"
                    link
                    size="small"
                    tag="a"
                    :href="note.confluence_url"
                    target="_blank"
                    rel="noopener"
                    data-test="note-confluence-view"
                  >
                    {{ t('releaseNotes.view_on_confluence') }}
                  </el-button>
                  <el-button
                    v-else-if="confluence.configured && canManage && note.status === 'published'"
                    link
                    size="small"
                    :type="note.confluence_sync_error ? 'warning' : 'primary'"
                    :loading="syncingNoteId === note.id"
                    data-test="note-confluence-sync"
                    @click="syncToConfluence(note)"
                  >
                    {{ t('releaseNotes.sync_to_confluence') }}
                  </el-button>

                  <el-tooltip :content="t('releaseNotes.copy_one')" placement="top">
                    <el-button
                      link
                      size="small"
                      :icon="CopyDocument"
                      :loading="copyingNote"
                      :aria-label="t('releaseNotes.copy_one')"
                      data-test="note-copy"
                      @click="copyNote(note)"
                    />
                  </el-tooltip>

                  <!-- Nothing to offer, nothing to show: a control that opens an
                       empty menu is worse than no control -->
                  <el-dropdown
                    v-if="noteMenuItems(note).length"
                    trigger="click"
                    @command="(command: string) => handleNoteCommand(command, note)"
                  >
                    <el-button
                      link
                      size="small"
                      :icon="MoreFilled"
                      :aria-label="t('releaseNotes.more_actions')"
                      data-test="note-menu"
                    />
                    <template #dropdown>
                      <el-dropdown-menu>
                        <el-dropdown-item
                          v-for="item in noteMenuItems(note)"
                          :key="item.command"
                          :command="item.command"
                          :divided="item.divided"
                          :class="{ 'note-menu-danger': item.danger }"
                          :data-test="`note-menu-${item.command}`"
                        >
                          {{ item.label }}
                        </el-dropdown-item>
                      </el-dropdown-menu>
                    </template>
                  </el-dropdown>
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

              <!-- The people behind the commits, read from the repository rather
                   than written into the notes: a draft has none, a published
                   release is credited however its notes were written -->
              <div
                v-if="note.status === 'published' && contributorsOf(note).length"
                class="release-contributors"
                data-test="note-contributors"
              >
                <span class="contributors-label">{{ t('releaseNotes.contributors') }}</span>
                <ul
                  class="contributor-list"
                  :class="{ 'is-stacked': isCrowded(note) }"
                  data-test="contributor-list"
                >
                  <li
                    v-for="(person, index) in visibleContributors(note)"
                    :key="person.username || person.display_name || index"
                    class="contributor-item"
                  >
                    <!-- A picture over the name, as a face is read before the
                         handle is; hovering it says who the person is without
                         leaving the release -->
                    <el-popover
                      trigger="hover"
                      placement="top"
                      :width="260"
                      :show-after="150"
                      :hide-after="60"
                      :offset="10"
                    >
                      <template #reference>
                        <div class="contributor">
                          <component
                            :is="person.profile_url ? 'a' : 'div'"
                            class="contributor-avatar-frame"
                            :href="person.profile_url ?? undefined"
                            :target="person.profile_url ? '_blank' : undefined"
                            :rel="person.profile_url ? 'noopener' : undefined"
                            @click.stop
                          >
                            <UserAvatar
                              class="contributor-avatar"
                              :username="person.username || person.display_name || '?'"
                              :avatar-url="person.avatar_url"
                              :size="isCrowded(note) ? 32 : 40"
                            />
                          </component>
                          <!-- A crowded release is drawn as one line of faces, so
                               the names are left to the card each picture opens -->
                          <span v-if="!isCrowded(note)" class="contributor-name">
                            {{ contributorLabel(person) }}
                          </span>
                        </div>
                      </template>
                      <ContributorProfileCard
                        :username="person.username"
                        :display-name="person.display_name"
                        :avatar-url="person.avatar_url"
                        :profile-url="person.profile_url"
                        :commit-count="person.commit_count"
                      />
                    </el-popover>
                  </li>

                  <!-- The names not drawn, counted: a release with thirty people
                       in it should still read as one line -->
                  <li
                    v-if="hiddenContributors(note).length"
                    class="contributor-item"
                    data-test="contributor-overflow"
                  >
                    <el-popover
                      trigger="hover"
                      placement="top"
                      :width="220"
                      :show-after="150"
                      :hide-after="60"
                      :offset="10"
                    >
                      <template #reference>
                        <div class="contributor-overflow">
                          <span class="contributor-overflow-count">
                            +{{ hiddenContributors(note).length }}
                          </span>
                        </div>
                      </template>
                      <div class="contributor-overflow-card">
                        <p class="contributor-overflow-title">
                          {{
                            t('releaseNotes.contributor_more', {
                              count: hiddenContributors(note).length,
                            })
                          }}
                        </p>
                        <ul class="contributor-overflow-list">
                          <li
                            v-for="(person, index) in hiddenContributors(note)"
                            :key="person.username || person.display_name || index"
                            class="contributor-overflow-item"
                          >
                            <UserAvatar
                              :username="person.username || person.display_name || '?'"
                              :avatar-url="person.avatar_url"
                              :size="20"
                            />
                            <span class="contributor-overflow-name">
                              {{ contributorLabel(person) }}
                            </span>
                          </li>
                        </ul>
                      </div>
                    </el-popover>
                  </li>
                </ul>
              </div>

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
                  : tabIsTags
                    ? 'releaseNotes.tags_select_hint'
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

    <!-- A page of releases stacks up past the screen, so the list keeps the way back to
         its own head: the arrow appears once the reader has scrolled past it, and it is
         a button, so a keyboard reaches it too. The ring around it is how much of the
         page has been read, so the reader can see where they are without a scrollbar. -->
    <button
      v-if="showBackToTop"
      type="button"
      class="notes-backtop"
      data-test="notes-backtop"
      @click="scrollNotesToTop"
    >
      <svg class="notes-backtop-ring" viewBox="0 0 40 40" aria-hidden="true">
        <circle class="notes-backtop-track" cx="20" cy="20" :r="RING_RADIUS" />
        <circle
          class="notes-backtop-progress"
          data-test="notes-backtop-progress"
          cx="20"
          cy="20"
          :r="RING_RADIUS"
          :stroke-dasharray="RING_LENGTH"
          :stroke-dashoffset="RING_LENGTH * (1 - scrollProgress)"
        />
      </svg>
      <el-icon><ArrowUp /></el-icon>
    </button>
  </div>
</template>

<script setup lang="ts">
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
  type ComponentPublicInstance,
} from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ArrowDown,
  ArrowUp,
  Close,
  CopyDocument,
  Document,
  InfoFilled,
  Link,
  MagicStick,
  MoreFilled,
  Refresh,
  Search,
} from '@element-plus/icons-vue'
import { MdEditor, MdPreview, type ToolbarNames } from 'md-editor-v3'
import 'md-editor-v3/lib/style.css'
import { projectsApi } from '@/api/projects'
import type { CloudWorkspaceOption, ProjectSummary, RepositorySummary } from '@/api/projects'
import { releaseDiffApi } from '@/api/releaseDiff'
import type { CommitInfo } from '@/api/releaseDiff'
import CommitTable from '@/components/release/CommitTable.vue'
import ContentLoader from '@/components/common/ContentLoader.vue'
import ContributorProfileCard from '@/components/release/ContributorProfileCard.vue'
import UserAvatar from '@/components/user/UserAvatar.vue'
import { useJira } from '@/composables/useJira'
import { searchCandidates } from '@/composables/useRefCandidates'
import { linkifyJiraMarkdown } from '@/utils/jira'
import {
  releaseNotesApi,
  type ReleaseNote,
  type ReleaseNoteContributor,
} from '@/api/releaseNotes'
import type {
  ReleaseNoteExportRequest,
  ReleaseNotePreviewResponse,
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

/**
 * The height of the tag search, written on the input itself.
 *
 * The size prop alone sets this - an input's height comes from the size variable the
 * class carries (40px and 14px text for the large one) - and this field was reported
 * as staying at the small size (24px, 12px text) however it was set. A style on the
 * element is the one thing that cannot be lost on the way to the browser, so the
 * height of this field is stated here and not only in the stylesheet.
 */
const TAG_SEARCH_STYLE = 'height: 38px; line-height: 38px; font-size: 14px'

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
// The pickers hold the provider's whole listing - they offer part of it and search
// the rest. Which part is offered is this page's own call: its tags are read in
// version order rather than in the order the provider happens to return them.
const refSearch = ref('')

/** What the reader typed: it searches the whole listing, not the offered page. */
function onRefSearch(query: string) {
  refSearch.value = query ?? ''
}

// The coordinate panel is open on arrival: it is what a first visit fills in
const coordinatesOpen = ref(true)
// The tag navigator is searched by name, not paged through
const tagSearch = ref('')

const notes = ref<ReleaseNote[]>([])
const notesTotal = ref(0)
const notesLoading = ref(false)
/**
 * Credits of the notes being written, as the generator returned them.
 *
 * The commits are read once, when the notes are generated, so the people behind
 * them are known then: deduplicated by person and matched to the account that
 * carries a picture. Saving the notes stores them with the release, and the
 * release page reads them from there - nobody asks the git provider again.
 */
const previewContributors = ref<ReleaseNoteContributor[] | null>(null)
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
/**
 * A release scope as the server resolved it: the predecessor it found, the
 * revisions the comparison was pinned to, and whether the answer was proven (an
 * ancestor) or inferred from the tag order.
 */
interface ScopeState {
  previous: string | null
  previousSha: string | null
  versionSha: string | null
  source: ReleaseScopeSource
  verified: boolean
  reason: ReleaseScopeReason
}

// Commits covered by the selected tag (the tag -> commits mapping)
const tagCommits = ref<CommitInfo[]>([])
const tagCommitCount = ref(0)
const tagCommitsLoading = ref(false)
const tagTruncated = ref(false)
const tagScope = ref<ScopeState | null>(null)

// The same scope, for the release being written: the notes are meant to account for
// these commits, and the writer can see them while doing it. Folded away until it is
// asked for, and kept open once it has been - it is read, not passed through.
const editorCommitsOpen = ref(false)
const editorCommits = ref<CommitInfo[]>([])
const editorCommitCount = ref(0)
const editorCommitsLoading = ref(false)
const editorTruncated = ref(false)
const editorScope = ref<ScopeState | null>(null)
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
// A retry can only help where the failure was about the answer itself: a deployment
// with no LLM configured says the same thing however often it is asked
const canRetryAiSummary = computed(
  () => Boolean(aiFallback.value) && aiFallback.value !== 'not_configured' && llmEnabled.value,
)

/**
 * The AI notice describes the notes it was generated with.
 *
 * Anything that puts different notes on screen - another tag, another scope, a closed
 * editor - leaves it describing text that is no longer there, which is how a failure
 * on one release stayed on screen over the next one.
 */
function clearSummaryState() {
  summarizedByAi.value = false
  summaryNotice.value = null
  summaryError.value = null
}

// The switch is about the next pass: what it says now belongs to the previous one
watch(aiSummary, clearSummaryState)

const formCard = ref<HTMLElement | null>(null)

/**
 * The head of the list of releases, which the arrow over a long page returns to.
 *
 * The list, not the document: a page of releases is read as a list, so the way back
 * should land on the list itself rather than on the filters above it. The card is a
 * component, so its element is read from the instance.
 */
const notesCard = ref<ComponentPublicInstance | null>(null)

/** Whether the head of the list has been scrolled past, which is when the way back is
 *  offered. Measured from the card itself, so it holds whatever the page above it does. */
const showBackToTop = ref(false)

/** How much of the page has been read, from 0 to 1: the ring drawn around the arrow.
 *  The page is measured rather than the list, so the ring keeps moving wherever the
 *  reader is on it, and empties again on the way back up. */
const scrollProgress = ref(0)

/** The ring as the geometry of a 40px button: its circumference is what the dash of the
 *  progress arc covers, so a share of the page is a share of that length. */
const RING_RADIUS = 18
const RING_LENGTH = 2 * Math.PI * RING_RADIUS

function trackScroll() {
  const top = (notesCard.value?.$el as HTMLElement | undefined)?.getBoundingClientRect().top
  showBackToTop.value = typeof top === 'number' && top < 16

  const scrollable = document.documentElement.scrollHeight - window.innerHeight
  scrollProgress.value =
    scrollable > 0 ? Math.min(1, Math.max(0, window.scrollY / scrollable)) : 0
}

function scrollNotesToTop() {
  const element = notesCard.value?.$el as HTMLElement | undefined
  element?.scrollIntoView?.({ behavior: 'smooth', block: 'start' })
}

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
  sync_to_confluence: true,
})

// Confluence is an optional integration. The server says whether it is set up
// here, and the page only offers what a sync could actually do.
const confluence = ref({ configured: false, auto_sync: false })
const syncingNoteId = ref<number | null>(null)

// Whether the form may ask for the automatic path: it is the switch in the
// environment that turns that off for every repository at once, so where it is off
// there is nothing to ask for - a release is written by hand from the release itself.
// A pre-release is the same kind of nothing-to-ask-for, which is what the disabled
// switch beside it says.
const asksForConfluenceSync = computed(
  () =>
    form.value.sync_to_confluence && confluence.value.auto_sync && !form.value.is_prerelease
)

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
// A release is published with its notes, so an empty body would publish a version
// that says nothing. A draft is not that case: it is where the notes are still
// being written, which is why only publishing waits for them.
const hasNotes = computed(() => Boolean(form.value.body.trim()))
const canPublish = computed(() => canSave.value && hasNotes.value)

// The tags are shown in the order the provider lists them, which is the order
// Bitbucket lists tags in: most recently created first. This page used to re-sort
// them by version instead, so that a release line read top-down, and paid for it
// with the tag that matters most: the one just cut. A version sort buries it - a tag
// that does not read as a version at all, or a patch cut for an older line, falls
// below everything, past the first page of the list.
//
// What the two ref pickers offer: the newest part of the whole listing, narrowed by
// what the reader typed - the rest is still reachable by searching it.
const candidateTags = computed(() => searchCandidates(tags.value, refSearch.value))
const candidateRefs = computed(() =>
  searchCandidates([...tags.value, ...branches.value], refSearch.value),
)

/** Whether a tag survives the search box, by a plain substring of its name. */
function tagMatchesQuery(tag: string): boolean {
  const query = tagSearch.value.trim().toLowerCase()
  return !query || tag.toLowerCase().includes(query)
}

// The search narrows the list before it is paged, so a match is on the first
// page of the result rather than on whichever page its position falls on
const filteredTags = computed(() => tags.value.filter(tagMatchesQuery))
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

/**
 * The range a scope covers, with the revisions it was pinned to.
 *
 * A predecessor is a predecessor however it was arrived at: supplied by the reader
 * (a previous version picked in the form), proven by ancestry, or inferred from the
 * tag order. All of them read as a range - only a scope without one has nothing to
 * show, and those are labelled by reason before this is reached.
 */
function scopeRangeLabel(scope: ScopeState | null, tag: string): string | null {
  if (!scope?.previous) return null
  return t('releaseNotes.range', {
    from: labelWithRevision(scope.previous, scope.previousSha),
    to: labelWithRevision(tag, scope.versionSha),
  })
}

// A scope inferred from the tag order is a legitimate answer, just not a proven one
function scopeIsInferred(scope: ScopeState | null): boolean {
  return Boolean(scope?.previous) && !scope?.verified
}

// A capped listing borrows its meaning from the scope: for a scoped release it is
// a display limit, and the panel must not present it as a repository limit
function scopeIsTrimmed(scope: ScopeState | null, truncated: boolean): boolean {
  return truncated && Boolean(scope?.previous)
}

/** What a capped listing means: a display limit, or a capped scan that cut nothing. */
function trimNotice(shown: number, count: number): string {
  return shown < count
    ? t('releaseNotes.commits_trimmed', { shown, count })
    : t('releaseNotes.commits_scan_capped')
}

/**
 * Scope line of a commits panel: the range when resolved, why otherwise.
 *
 * `guess` is only a placeholder for the moment before the server answers - the
 * local tag order cannot know what lies beyond the page of tags the browser holds.
 */
function scopeHint(scope: ScopeState | null, tag: string, guess: string | null): string {
  if (scope?.reason === 'first_release') {
    return t('releaseNotes.scope_first_release', { tag })
  }
  if (scope?.reason === 'unresolved') {
    return t('releaseNotes.scope_unresolved', { tag })
  }
  if (scope) {
    return scopeRangeLabel(scope, tag) ?? t('releaseNotes.full_history', { tag })
  }
  return guess
    ? t('releaseNotes.range', { from: guess, to: tag })
    : t('releaseNotes.full_history', { tag })
}

const tagScopeInferred = computed(() => scopeIsInferred(tagScope.value))
const tagScopeTrimmed = computed(() => scopeIsTrimmed(tagScope.value, tagTruncated.value))
const tagTrimNotice = computed(() =>
  trimNotice(tagCommits.value.length, tagCommitCount.value),
)
const tagScopeHint = computed(() =>
  scopeHint(tagScope.value, selectedTag.value ?? '', previousTagFor(selectedTag.value ?? '')),
)

const editorScopeInferred = computed(() => scopeIsInferred(editorScope.value))
const editorScopeTrimmed = computed(() => scopeIsTrimmed(editorScope.value, editorTruncated.value))
const editorTrimNotice = computed(() =>
  trimNotice(editorCommits.value.length, editorCommitCount.value),
)
const editorScopeHint = computed(() =>
  scopeHint(
    editorScope.value,
    form.value.tag_name.trim(),
    form.value.previous_tag.trim() || previousTagFor(form.value.tag_name.trim()),
  ),
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

/**
 * The tag released just before ``tag``, which is the base of its release scope.
 *
 * Read off the listing, which is in the order the tags were released in: the entry
 * after a tag is the one that came before it.
 */
function previousTagFor(tag: string): string | null {
  const index = tags.value.indexOf(tag)
  return index >= 0 ? (tags.value[index + 1] ?? null) : null
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
    // derived rather than chosen: the registry decides where a repository lives, and
    // this stands only for one it says nothing about
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
    // No `limit`: the API answers with the repository's whole listing (up to its
    // safety ceiling), because a tag the picker never received is a tag this page
    // cannot record a note for.
    const response = await releaseDiffApi.listRefs({
      ...coordinates(),
      refresh: force,
    })
    const tagNames = uniqueRefs(response.tags)
    const branchNames = uniqueRefs(response.branches)
    tags.value = tagNames
    branches.value = branchNames
    tagPage.value = 1
    // No tag is selected on arrival: the commits of a tag can be a whole release
    // worth of history, and loading the newest one was a wait nobody asked for.
    // The list reads as a list until a tag is picked.
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
    // Left empty: the pickers offer nothing and the note keeps its own tag
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
 * The credits stored with a release.
 *
 * A release that was never generated - written by hand or imported - carries none.
 */
function contributorsOf(note: ReleaseNote): ReleaseNoteContributor[] {
  return note.contributors ?? []
}

/** The login a release is credited under, or the name when the commits carry none. */
function contributorLabel(person: ReleaseNoteContributor): string {
  return person.username ? `@${person.username}` : person.display_name || ''
}

/**
 * Whether the credits no longer fit one row of names.
 *
 * Up to six people are drawn as a face over a handle each; past that the faces
 * overlap in a single line and the rest are counted, so a release written by a
 * whole team takes no more room than one written by a few.
 */
const CROWDED_CONTRIBUTORS = 6

function isCrowded(note: ReleaseNote): boolean {
  return contributorsOf(note).length > CROWDED_CONTRIBUTORS
}

/** The credits drawn on the release: everyone, or the first faces of a crowd. */
function visibleContributors(note: ReleaseNote): ReleaseNoteContributor[] {
  const people = contributorsOf(note)
  return isCrowded(note) ? people.slice(0, CROWDED_CONTRIBUTORS) : people
}

/** The credits a crowded release only counts; empty for everyone else. */
function hiddenContributors(note: ReleaseNote): ReleaseNoteContributor[] {
  return isCrowded(note) ? contributorsOf(note).slice(CROWDED_CONTRIBUTORS) : []
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
    tagScope.value = toScope(response)
  } catch {
    ElMessage.error(t('releaseNotes.commits_load_failed'))
  } finally {
    tagCommitsLoading.value = false
  }
}

/** Read the scope fields of a preview answer into the shape both panels render. */
function toScope(response: ReleaseNotePreviewResponse): ScopeState {
  return {
    previous: response.previous_version ?? null,
    previousSha: response.previous_sha ?? null,
    versionSha: response.version_sha ?? null,
    source: response.previous_source ?? 'none',
    verified: Boolean(response.previous_verified),
    reason: response.scope_reason ?? 'unresolved',
  }
}

/** Drop what the editor panel holds, so a closed form cannot show a stale scope. */
function clearEditorScope() {
  editorCommits.value = []
  editorCommitCount.value = 0
  editorTruncated.value = false
  editorScope.value = null
}

/**
 * Load the commits of the release the editor is writing.
 *
 * The notes are meant to account for the commits of the scope, so the writer is
 * given the same list the tags panel shows - resolved by the same server call, with
 * the predecessor the form holds (or the one the server resolves when it is empty).
 * Nothing new is asked of the backend: the preview answer already carries the
 * commits it built the notes from.
 */
async function loadEditorCommits(refresh = false) {
  const tag = form.value.tag_name.trim()
  if (!editorOpen.value || !hasCoordinates.value || !tag) {
    clearEditorScope()
    return
  }

  const previous = form.value.previous_tag.trim() || undefined
  editorCommitsLoading.value = true
  try {
    const response = await releaseNotesApi.preview({
      ...coordinates(),
      version: tag,
      previous_version: previous,
      max_commits: PREVIEW_MAX_COMMITS,
      refresh,
    })
    // the form may have moved on while this was in flight
    if (!editorOpen.value || form.value.tag_name.trim() !== tag) return
    applyEditorScope(response.commits, response)
  } catch {
    ElMessage.error(t('releaseNotes.commits_load_failed'))
  } finally {
    editorCommitsLoading.value = false
  }
}

/** Show a preview answer (its commits and its scope) in the editor panel. */
function applyEditorScope(
  commits: CommitInfo[] | undefined,
  response: ReleaseNotePreviewResponse,
) {
  editorCommits.value = commits ?? []
  editorCommitCount.value = response.commit_count ?? editorCommits.value.length
  editorTruncated.value = Boolean(response.truncated)
  editorScope.value = toScope(response)
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
  previewContributors.value = null
  clearSummaryState()
  clearEditorScope()
  form.value = {
    tag_name: '',
    previous_tag: '',
    name: '',
    body: '',
    is_prerelease: false,
    push_to_provider: false,
    target_commitish: '',
    sync_to_confluence: true,
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
  //   3. the newest tag, which is where the listing starts
  const selected = tabIsTags.value ? selectedTag.value : null
  const initial = tag ?? selected ?? tags.value[0]
  if (initial) {
    form.value.tag_name = initial
    // The draft inherits the scope the server resolved for that tag, so the editor
    // generates the same commit set the tags panel shows. The local tag order is
    // only a fallback for a tag the resolver has not looked at.
    const scope = initial === selectedTag.value ? tagScope.value : null
    form.value.previous_tag = (scope ? scope.previous : previousTagFor(initial)) ?? ''
    // The commits of that scope are usually already on screen - the draft is opened
    // from the tag they belong to - so they are carried over rather than asked for
    // again. Anything else (another tag, a page just opened) is read from the server.
    if (scope && tagCommits.value.length > 0) {
      editorCommits.value = [...tagCommits.value]
      editorCommitCount.value = tagCommitCount.value
      editorTruncated.value = tagTruncated.value
      editorScope.value = scope
    } else {
      void loadEditorCommits()
    }
  }
  formCard.value?.scrollIntoView?.({ behavior: 'smooth', block: 'start' })
}

/** The tag or the predecessor of a draft changed: its commits changed with it. */
function onEditorScopeChange() {
  // The notes on screen were generated for the previous scope, and so was whatever
  // the AI pass said about them
  clearSummaryState()
  generatedCount.value = null
  void loadEditorCommits()
}

/** What one release's overflow menu can be asked to do. */
type NoteCommand = 'provider' | 'sync' | 'edit' | 'publish' | 'push' | 'delete'

interface NoteMenuItem {
  command: NoteCommand
  label: string
  divided?: boolean
  danger?: boolean
}

/**
 * The actions of one release, in the order they are shown; empty means no menu.
 *
 * What is left here is either rare or destructive - the entry keeps the page the
 * release is on and copying its notes outside, and everything else inside, so a
 * page full of releases reads as one row of controls each rather than a wall of
 * text buttons repeated for every version.
 */
function noteMenuItems(note: ReleaseNote): NoteMenuItem[] {
  const items: NoteMenuItem[] = []

  if (note.external_url) {
    items.push({ command: 'provider', label: t('releaseNotes.view_on_provider') })
  }
  // Writing it again is only needed once a page exists: before that the control
  // beside the release offers it, and that control gives way to the page link
  // afterwards - which is when this becomes the only way back in.
  if (
    note.confluence_url &&
    confluence.value.configured &&
    canManage.value &&
    note.status === 'published'
  ) {
    items.push({
      command: 'sync',
      label: note.confluence_sync_error
        ? t('releaseNotes.sync_confluence_retry')
        : t('releaseNotes.sync_to_confluence'),
    })
  }
  if (canManage.value) {
    items.push({ command: 'edit', label: t('releaseNotes.edit_release') })
  }
  if (canManage.value && note.status === 'draft') {
    items.push({ command: 'publish', label: t('releaseNotes.publish') })
  }
  if (canImportFromProvider.value) {
    items.push({ command: 'push', label: t('releaseNotes.push_to_provider') })
  }
  if (canManage.value) {
    // Set apart and last: it is the one action here that cannot be undone.
    items.push({
      command: 'delete',
      label: t('releaseNotes.delete'),
      divided: true,
      danger: true,
    })
  }

  return items
}

/** Carry out what the menu was asked to do, for the release it was opened on. */
function handleNoteCommand(command: string, note: ReleaseNote) {
  switch (command) {
    case 'provider':
      // A menu item is not a link, so the release is opened the way the link
      // that used to sit here would have opened it.
      if (note.external_url) {
        window.open(note.external_url, '_blank', 'noopener')
      }
      break
    case 'sync':
      syncToConfluence(note)
      break
    case 'edit':
      editNote(note)
      break
    case 'publish':
      publishNote(note)
      break
    case 'push':
      pushNote(note)
      break
    case 'delete':
      confirmDelete(note)
      break
  }
}

function editNote(note: ReleaseNote) {
  selectedId.value = note.id
  selectedTag.value = null
  editingId.value = note.id
  editingStatus.value = note.status
  generatedCount.value = null
  // The stored credits stay as they are until the notes are generated again
  previewContributors.value = null
  clearSummaryState()
  editorOpen.value = true
  form.value = {
    tag_name: note.tag_name,
    previous_tag: note.previous_tag ?? '',
    name: note.name,
    body: note.body ?? '',
    is_prerelease: note.is_prerelease,
    push_to_provider: false,
    target_commitish: '',
    sync_to_confluence: true,
  }
  // What the notes of this release are supposed to cover, so an edit can check that
  // nothing the release brought is missing from them
  void loadEditorCommits()
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

  // Whatever the previous pass said is about notes that are about to be replaced
  clearSummaryState()
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
    // The people behind those commits came back with them, so the credits are saved
    // with the notes instead of being read again when the release is shown
    previewContributors.value = preview.contributors ?? []
    // The notes and the commits they were built from come out of the same answer, so
    // the panel beside them is what the body was made of - not a second reading of
    // the repository that could disagree with it.
    applyEditorScope(preview.commits as CommitInfo[], preview)
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
  if (status === 'published' && !hasNotes.value) {
    ElMessage.warning(t('releaseNotes.notes_required'))
    return
  }

  // Read before the form is reset: whether this save asked to write to Confluence.
  const willSyncToConfluence = asksForConfluenceSync.value
  // Only notes generated in this session carry credits; an edit that changes the
  // wording leaves the credits already stored with the release alone
  const contributors = previewContributors.value ?? undefined
  saving.value = true
  let saved: ReleaseNote
  try {
    if (editingId.value) {
      saved = await releaseNotesApi.update(editingId.value, {
        name: form.value.name.trim() || form.value.tag_name.trim(),
        body: form.value.body,
        previous_tag: form.value.previous_tag.trim() || null,
        is_prerelease: form.value.is_prerelease,
        status,
        contributors,
        sync_to_confluence: asksForConfluenceSync.value,
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
        contributors,
        sync_to_confluence: asksForConfluenceSync.value,
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
    return
  } finally {
    saving.value = false
  }

  // The Confluence write runs in the background after this response, so the list
  // has not seen it yet. Poll the release until it shows its page (or its failure)
  // and refresh, instead of leaving "Sync to Confluence" on the screen.
  if (status === 'published' && willSyncToConfluence) {
    void pollForConfluenceSync(saved.id)
  }
}

/** Re-read one release until its background Confluence write has landed. */
async function pollForConfluenceSync(noteId: number) {
  for (let attempt = 0; attempt < 8; attempt += 1) {
    await new Promise((resolve) => setTimeout(resolve, 750))
    const note = await releaseNotesApi.get(noteId).catch(() => null)
    if (note?.confluence_url || note?.confluence_sync_error) {
      // The release that was just written from here is the row on screen, so it is
      // put back in place - reading the list again would blank the panel for a change
      // to one row. Only a release older than the page on screen needs the list.
      if (!replaceNoteInList(note)) {
        await loadNotes()
      }
      return
    }
  }
}

/** Ask whether this instance syncs releases to Confluence. */
async function loadConfluenceStatus() {
  try {
    // No answer means not available, which is also what an instance without the
    // integration says - the controls that need it stay out of the way either way.
    const status = await releaseNotesApi.confluenceStatus()
    confluence.value = status ?? { configured: false, auto_sync: false }
  } catch {
    // Whatever went wrong, the controls that need it stay out of the way.
  }
}

/**
 * Put one release back in the list where it already sits.
 *
 * Reading the whole list again for a single row is what this page used to do, and it
 * is a flash: the panel empties, the scroll is lost and the notes that were open fold
 * away. The row that changed is all the reader needs, so it is swapped in place.
 */
function replaceNoteInList(updated: ReleaseNote): boolean {
  const index = notes.value.findIndex((note) => note.id === updated.id)
  if (index === -1) return false
  notes.value[index] = updated
  return true
}

/**
 * Write one release to Confluence, or try again after a failure.
 *
 * Failing here is not a failed release: the response says what happened, and the
 * release keeps whatever it had.
 */
async function syncToConfluence(note: ReleaseNote) {
  syncingNoteId.value = note.id
  try {
    const result = await releaseNotesApi.syncToConfluence(note.id)
    if (result.synced) {
      ElMessage.success(t('releaseNotes.sync_confluence_ok'))
    } else {
      ElMessage.warning(result.message)
    }
    // The page url, or the reason it failed, is on the release: that one release is
    // read back so the row can answer - the page link replaces the button, or the
    // failure shows - without the list being read again around it.
    try {
      replaceNoteInList(await releaseNotesApi.get(note.id))
    } catch {
      // The toast already said what happened. A row that could not be read back keeps
      // the state it had rather than taking the page down with it.
    }
  } catch {
    ElMessage.error(t('releaseNotes.sync_confluence_failed'))
  } finally {
    syncingNoteId.value = null
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

// The tags tab maps a tag to the commits it released: opening it reads which tags
// have a release, so their note icon can be shown. Nothing is selected for the
// reader - the commits of the newest tag are a whole release worth of history, and
// were a wait on every visit to a tab that is often just being browsed.
watch(activeTab, (tab) => {
  if (tab !== 'tags') {
    return
  }
  void loadReleaseTagIndex()
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
  void loadConfluenceStatus()
  // Where the head of the list sits is only known once the card is on the page
  window.addEventListener('scroll', trackScroll, { passive: true })
  trackScroll()
})

onBeforeUnmount(() => {
  themeObserver?.disconnect()
  themeObserver = null
  window.removeEventListener('scroll', trackScroll)
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

/*
 * The way back to the head of a long page of releases: the round button Element Plus
 * draws for its own back-to-top, so it reads as part of the application, and a button
 * rather than a clickable div so a keyboard reaches it. The ring is the page's own
 * progress - the track it runs along, and the arc that fills as the reader goes down.
 */
.notes-backtop {
  position: fixed;
  right: 32px;
  bottom: 32px;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--el-bg-color);
  color: var(--el-text-color-primary);
  box-shadow: var(--el-box-shadow-light);
  cursor: pointer;
}

.notes-backtop-ring {
  position: absolute;
  inset: 0;
  /* The arc starts at the top of the button and runs clockwise, as a progress ring does */
  transform: rotate(-90deg);
}

.notes-backtop-track,
.notes-backtop-progress {
  fill: none;
  stroke-width: 2;
}

.notes-backtop-track {
  stroke: var(--el-border-color-lighter);
}

.notes-backtop-progress {
  stroke: var(--el-color-primary);
  stroke-linecap: round;
  transition: stroke-dashoffset 0.1s linear;
}

.notes-backtop:hover {
  background: var(--el-fill-color-light);
  color: var(--el-color-primary);
}

.notes-backtop:focus-visible {
  outline: 2px solid var(--el-color-primary);
  outline-offset: 2px;
}

/*
 * The commits panel holds a table that is as tall as the rows of the page it shows.
 *
 * So the card is at least the height the row gives it - the panel is filled, not a box
 * drawn around the table - and as tall as the table when the page needs more, which is
 * what keeps every row of the page in the page instead of behind a scrollbar inside a
 * box of a fixed size. Nothing here may cap the body: a body told to take only the
 * card's height would clip the rows past it.
 */
.detail-card--fills {
  height: auto;
  min-height: 100%;
  display: flex;
  flex-direction: column;
}

.detail-card--fills :deep(.el-card__body) {
  display: flex;
  flex-direction: column;
  flex: 1;
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

/*
 * The tag search, whose height is written out rather than left to the component's
 * size.
 *
 * The size prop decides nothing here on its own: the height of an input comes from
 * --el-input-inner-height, which the size class sets, and this field kept coming out
 * small however that prop was set - the small size (24px, 12px text) and the large one
 * (40px, 14px) were reported as reading the same. So the height is stated here, on the
 * one control of this panel a reader types into, and it holds whatever the variable
 * resolves to.
 */
.nav-search {
  margin-bottom: 8px;
}

.nav-search :deep(.el-input__wrapper) {
  min-height: 40px;
  padding: 0 12px;
}

.nav-search :deep(.el-input__inner) {
  height: 38px;
  line-height: 38px;
  font-size: 14px;
}

/*
 * The list is paginated, so a page has to be visible in full: no height clamp and
 * no scrolling of its own. The clamp used to cut the list off after about seven
 * releases and scroll the rest, which contradicted the page size the pagination
 * offers and left two ways to move through the same list.
 */
.nav-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin: 0;
  padding: 0;
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

/* Reading column: one sheet per release of the page.
   The gap groups them and the border gives each one its own edge, so no rule has
   to divide one release from the next. */
.note-entry {
  padding: 20px 22px 22px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 12px;
  /* The colour of the card it sits on: in dark mode Element Plus paints the card
     with --el-bg-color-overlay, so --el-bg-color would cut a darker hole */
  background: var(--el-card-bg-color, var(--el-bg-color));
  scroll-margin-top: 16px;
}

.note-entry + .note-entry {
  margin-top: 16px;
}

/* Hover is a hint that the sheet has reachable controls, not that the sheet
   itself opens: the border deepens, nothing moves and nothing lifts. */
.note-entry:not(.focused):hover {
  border-color: var(--el-border-color);
}

/* The release the navigator points at. A ring, in place of the rail the list
   layout drew in the margin. */
.note-entry.focused {
  border-color: var(--el-color-primary);
  box-shadow: 0 0 0 1px var(--el-color-primary);
}

.note-entry-header {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}

/* Inside a sheet the metadata line is separated from the title rather than
   hanging under it. Scoped to the sheet: the tag tab keeps its own meta line. */
.note-entry .release-meta {
  margin-top: 8px;
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
  font-size: 28px;
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

/* The tag badge points out of the app, to the code the release was cut from. It
   sits beside the name so a release and its tag read as one line. */
.note-entry-tag-badge {
  display: inline-flex;
  align-items: center;
  text-decoration: none;
}

.tag-badge-icon {
  margin-right: 4px;
  vertical-align: -2px;
}

.note-entry-tag-badge:hover .el-tag {
  color: var(--el-color-primary);
  border-color: var(--el-color-primary);
}

.note-entry-tag-badge:focus-visible {
  outline: 2px solid var(--el-color-primary);
  outline-offset: 2px;
  border-radius: 6px;
}

.note-entry-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  /* Fewer controls than there used to be, and further apart: an icon needs more
     room around it than a word does. */
  gap: 6px;
}

/* The one action in a release menu that cannot be undone */
.note-menu-danger {
  color: var(--el-color-danger);
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
  /* Ends on the sheet's own colour, not the page's: the fade is drawn over the
     notes, and the two differ in dark mode */
  background: linear-gradient(transparent, var(--el-card-bg-color, var(--el-bg-color)));
  pointer-events: none;
}

.note-expand {
  margin-top: 8px;
}

/* The credits sit under the notes and quieter than them: they are a reading of
   the release, not part of what was written */
.release-contributors {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid var(--el-border-color-lighter);
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.contributors-label {
  font-weight: 600;
}

.contributor-list {
  display: flex;
  flex-wrap: wrap;
  gap: 14px 18px;
  margin: 0;
  padding: 0;
  list-style: none;
}

/* A face over the handle, one person per column: the picture is read first, the
   name says who it is */
.contributor {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  width: 76px;
  text-decoration: none;
}

/* The frame is a link when the platform has a profile page: an underlined link
   over a picture whose line box is collapsed draws a line across the avatar, so
   the underline is dropped and the hover ring says the picture is clickable */
.contributor-avatar-frame {
  display: inline-flex;
  border-radius: 50%;
  line-height: 0;
  text-decoration: none;
}

.contributor-avatar {
  box-sizing: border-box;
  border: 1px solid var(--el-border-color-lighter);
  transition: box-shadow 0.15s ease;
}

.contributor:hover .contributor-avatar {
  box-shadow: 0 0 0 2px var(--el-color-primary-light-5);
}

.contributor-name {
  max-width: 100%;
  overflow: hidden;
  color: var(--el-text-color-regular);
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.contributor:hover .contributor-name {
  color: var(--el-color-primary);
}

/* More people than one row of handles holds: the faces overlap in a single line
   and the rest are counted, the way a team is drawn beside a repository. The ring
   is the colour of the sheet, so the circles read as separate faces */
.contributor-list.is-stacked {
  flex-wrap: nowrap;
  align-items: center;
  gap: 0;
}

.contributor-list.is-stacked .contributor-item + .contributor-item {
  margin-left: -10px;
}

/* The face under the pointer comes forward, so its ring is not covered by the
   neighbour drawn over it */
.contributor-list.is-stacked .contributor-item {
  position: relative;
}

.contributor-list.is-stacked .contributor-item:hover {
  z-index: 1;
}

.contributor-list.is-stacked .contributor {
  width: 32px;
}

.contributor-list.is-stacked .contributor-avatar {
  border: 2px solid var(--el-card-bg-color, var(--el-bg-color));
}

.contributor-overflow {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
  width: 32px;
  height: 32px;
  border: 2px solid var(--el-card-bg-color, var(--el-bg-color));
  border-radius: 50%;
  background: var(--el-fill-color);
  color: var(--el-text-color-secondary);
  font-size: 11px;
  font-weight: 600;
  cursor: default;
}

.contributor-overflow:hover {
  background: var(--el-fill-color-darker);
  color: var(--el-color-primary);
}

.contributor-overflow-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.contributor-overflow-title {
  margin: 0;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  font-weight: 600;
}

.contributor-overflow-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 220px;
  margin: 0;
  padding: 0;
  overflow-y: auto;
  list-style: none;
}

.contributor-overflow-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.contributor-overflow-name {
  overflow: hidden;
  color: var(--el-text-color-regular);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.detail-pagination {
  margin-top: 20px;
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

/* The rendered notes must not outrank the release name (28px).
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

/* Wide enough for the label it carries while it works, so generating does not
   resize the button under the pointer that just pressed it */
.generate-notes {
  min-width: 152px;
}

/* The commits of the release being written, folded away until they are asked for */
.editor-commits-trigger {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-basis: 100%;
  margin-top: 2px;
}

/* A panel of its own, because it is one: the commits are read while the notes are
   written, and a block drawn like the rest of the form is one a reader takes for a
   piece of it and forgets is open. The border is what says it folds away again. */
.editor-commits {
  width: 100%;
  padding: 12px;
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  background: var(--el-fill-color-lighter);
}

.editor-commits-head {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.editor-commits-scope {
  color: var(--el-text-color-regular);
  font-size: 13px;
}

.editor-commits-head .el-button {
  margin-left: auto;
}

.generated-hint {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.field-hint {
  /* The form item content is a flex row; forcing the hint to its own line keeps it
     from crowding a checkbox it explains (the checkbox is narrower than the row). */
  flex-basis: 100%;
  margin-top: 4px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

/* What the release is, and whether it is written to Confluence: one line. */
.release-toggles {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
}

.ref-empty {
  margin: 0;
  padding: 8px 0;
  text-align: center;
  font-size: 13px;
  color: var(--el-text-color-secondary);
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

.ai-summary-retry {
  margin-top: 2px;
  padding: 0;
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

/* The reading column on a narrow screen: the sheet keeps its edge, with the
   padding and the title brought down so a release still fits a phone. */
@media (max-width: 768px) {
  .note-entry {
    padding: 16px;
    border-radius: 10px;
  }

  .note-entry + .note-entry {
    margin-top: 12px;
  }

  .note-entry-name {
    font-size: 22px;
  }
}
</style>
