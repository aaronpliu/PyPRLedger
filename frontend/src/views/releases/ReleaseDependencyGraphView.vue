<template>
  <div class="release-dependency-graph-container">
    <el-card shadow="never" class="context-card">
      <template #header>
        <div class="card-header">
          <div>
            <h2>{{ t('releaseDependencyGraph.title') }}</h2>
            <p v-if="version" class="subtitle">
              {{ t('releaseDependencyGraph.subtitle', { version }) }}
              <span v-if="releasedAt" class="released-at">
                {{ t('releaseDependencyGraph.released_at', { date: releasedAt }) }}
              </span>
            </p>
          </div>
          <div class="header-end">
            <!-- Depth first: a whole closure reads as a hairball, so the default
                 is what a package.json names on its own -->
            <el-radio-group v-model="depth" size="small" data-test="depth-radio">
              <el-radio-button value="1">{{ t('releaseDependencyGraph.depth_1') }}</el-radio-button>
              <el-radio-button value="2">{{ t('releaseDependencyGraph.depth_2') }}</el-radio-button>
              <el-radio-button value="all">{{ t('releaseDependencyGraph.depth_all') }}</el-radio-button>
            </el-radio-group>
            <el-tooltip
              :content="t('releaseDependencyGraph.transitive_help')"
              placement="bottom-end"
              :show-after="100"
            >
              <span class="switch-label">
                {{ t('releaseDependencyGraph.transitive') }}
                <el-switch v-model="transitive" data-test="transitive-switch" />
              </span>
            </el-tooltip>
          </div>
        </div>
      </template>

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
            <el-form-item :label="t('releaseDependencyGraph.ref_label')">
              <el-select
                v-model="selectedRef"
                filterable
                remote
                clearable
                default-first-option
                :remote-method="onRefSearch"
                :disabled="!hasCoordinates"
                :loading="refsLoading"
                :placeholder="t('releaseDependencyGraph.select_ref')"
                style="width: 100%"
                data-test="ref-select"
                @visible-change="onRefVisibility"
              >
                <el-option-group
                  v-if="visibleTags.length"
                  :label="t('releaseDependencyGraph.tags_group')"
                >
                  <el-option
                    v-for="tag in visibleTags"
                    :key="`tag:${tag}`"
                    :label="tag"
                    :value="tag"
                  />
                </el-option-group>
                <el-option-group
                  v-if="visibleBranches.length"
                  :label="t('releaseDependencyGraph.branches_group')"
                >
                  <el-option
                    v-for="branch in visibleBranches"
                    :key="`branch:${branch}`"
                    :label="branch"
                    :value="branch"
                  />
                </el-option-group>
                <!-- A ref the repository does not report is not offered, and only an
                     offered ref can be picked: a release that does not exist cannot
                     be read. -->
                <template #empty>
                  <p class="ref-empty">{{ t('releaseDependencyGraph.ref_no_match') }}</p>
                </template>
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <!-- The picker offers the recent refs and searches the rest, so it says
           which of the two it is doing rather than leaving a short list to look
           like a short repository. -->
      <p v-if="refsCapped" class="refs-note" data-test="refs-capped">
        {{
          t('releaseDependencyGraph.refs_capped', {
            loaded: loadedRefCount,
            total: totalRefCount,
          })
        }}
      </p>
      <p v-else-if="refsSearchable" class="refs-note" data-test="refs-searchable">
        {{ t('releaseDependencyGraph.refs_searchable', { total: totalRefCount }) }}
      </p>

      <el-empty
        v-if="!hasCoordinates"
        :description="t('releaseDependencyGraph.pick_repository')"
      />

      <!-- The refs are suggestions, not a choice: nothing is read until the reader
           picks the tag or branch they came for -->
      <el-empty
        v-else-if="!selectedRef"
        :description="t('releaseDependencyGraph.pick_ref')"
        data-test="pick-ref"
      />

      <ContentLoader
        v-else-if="loading"
        :rows="8"
        :label="t('releaseDependencyGraph.loading')"
        min-height="480px"
      />

      <el-empty
        v-else-if="!fullGraph.nodes.length"
        :description="t('releaseDependencyGraph.no_data')"
      />

      <el-row v-else :gutter="16">
        <el-col :xs="24" :md="18">
          <!-- The names are indexed by category as the dependency file numbers
               them: 0 the project, 1 a dependency, 2 a package it ships -->
          <ReleaseDependencyGraphChart
            :nodes="viewData.nodes"
            :links="viewData.links"
            :selected-id="selectedId"
            :transitive="transitive"
            :category-names="[
              t('releaseDependencyGraph.category_project'),
              t('releaseDependencyGraph.category_dependency'),
              t('releaseDependencyGraph.category_workspace'),
            ]"
            height="max(560px, calc(100vh - 380px))"
            data-test="release-dependency-graph-chart"
            @node-click="onNodeClick"
          />
          <p class="legend-note">
            <span class="dash-sample" aria-hidden="true" />
            {{ t('releaseDependencyGraph.circular_hint') }}
          </p>
          <p class="legend-note">
            <span class="constraint-sample">@2.0.0</span>
            {{ t('releaseDependencyGraph.constraint_note') }}
          </p>
        </el-col>

        <el-col :xs="24" :md="6">
          <div class="detail-panel" data-test="detail-panel">
            <p class="detail-stats">
              {{ t('releaseDependencyGraph.stats_nodes', { count: viewData.nodes.length }) }}
              &middot;
              {{ t('releaseDependencyGraph.stats_links', { count: viewData.links.length }) }}
            </p>

            <template v-if="selectedNode">
              <h3 class="detail-title">
                {{ selectedNode.name ?? selectedNode.id }}
                <el-tag size="small" :type="tagType(selectedNode.category)" effect="plain">
                  {{ categoryName(selectedNode.category) }}
                </el-tag>
              </h3>
              <p v-if="selectedNode.version" class="detail-version">@{{ selectedNode.version }}</p>

              <el-alert
                v-if="inCycle"
                class="cycle-alert"
                type="warning"
                :closable="false"
                show-icon
                :title="t('releaseDependencyGraph.circular_warning')"
              />

              <!-- Two columns: stacked, a list that outgrows its half of the panel
                   scrolls while the space beside it stands empty, and a package
                   worth reading is one of many -->
              <div class="detail-sections">
                <div class="detail-section">
                  <h4>
                    {{ t('releaseDependencyGraph.dependencies') }} ({{ directDependencies.length }})
                  </h4>
                  <ul v-if="directDependencies.length" class="detail-list">
                    <li v-for="entry in directDependencies" :key="entry.node.id">
                      <button class="detail-link" type="button" @click="selectNode(entry.node.id)">
                        {{ entry.node.name ?? entry.node.id }}
                      </button>
                      <span
                        v-if="entry.constraint"
                        class="detail-constraint"
                        :class="{ 'is-range': !entry.pinned }"
                        :title="entry.constraint"
                      >
                        {{ entry.constraint }}
                      </span>
                    </li>
                  </ul>
                  <p v-else class="detail-empty">{{ t('releaseDependencyGraph.no_dependencies') }}</p>
                </div>

                <div class="detail-section">
                  <h4>
                    {{ t('releaseDependencyGraph.dependents') }} ({{ directDependents.length }})
                  </h4>
                  <ul v-if="directDependents.length" class="detail-list">
                    <li v-for="entry in directDependents" :key="entry.node.id">
                      <button class="detail-link" type="button" @click="selectNode(entry.node.id)">
                        {{ entry.node.name ?? entry.node.id }}
                      </button>
                      <span
                        v-if="entry.constraint"
                        class="detail-constraint"
                        :class="{ 'is-range': !entry.pinned }"
                        :title="entry.constraint"
                      >
                        {{ entry.constraint }}
                      </span>
                    </li>
                  </ul>
                  <p v-else class="detail-empty">{{ t('releaseDependencyGraph.no_dependents') }}</p>
                </div>
              </div>
            </template>

            <p v-else class="detail-hint">{{ t('releaseDependencyGraph.empty_hint') }}</p>
          </div>
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { GIT_PROVIDER_OPTIONS } from '@/constants/gitProvider'
import { useI18n } from 'vue-i18n'
import ReleaseDependencyGraphChart from '@/components/charts/ReleaseDependencyGraphChart.vue'
import ContentLoader from '@/components/common/ContentLoader.vue'
import { dependencyFileToGraph, withinDepth } from '@/utils/releaseDependencyGraph'
import type {
  ReleaseDependencyGraphData,
  ReleaseDependencyGraphNode,
} from '@/utils/releaseDependencyGraph'
import { projectsApi } from '@/api/projects'
import type {
  CloudWorkspaceOption,
  ProjectSummary,
  RepositorySummary,
} from '@/api/projects'
import { releaseDiffApi } from '@/api/releaseDiff'
import { releaseDependencyGraphApi } from '@/api/releaseDependencyGraph'
import { useRefCandidates } from '@/composables/useRefCandidates'

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
const refsLoading = ref(false)
// The provider's whole listing, searched, with the recent refs offered up front
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

/** A picker that has just closed goes back to offering the recent refs. */
function onRefVisibility(visible: boolean) {
  if (!visible) {
    refSearch.value = ''
  }
}

const selectedProjectKey = computed(() => (repo.value.project_key ?? '').trim())
const selectedRepositorySlug = computed(() => (repo.value.repository_slug ?? '').trim())
const isCloudProvider = computed(() => repo.value.git_provider === 'bitbucket_cloud')
const selectedWorkspaceSlug = computed(() =>
  isCloudProvider.value ? (repo.value.workspace_slug ?? '').trim() : '',
)
const hasCoordinates = computed(
  () => Boolean(selectedProjectKey.value) && Boolean(selectedRepositorySlug.value),
)

// The ref picks the dependency file: a tag ships one, a branch carries whatever
// the walk produces at its tip today.
const selectedRef = ref('')
const loading = ref(false)
const fullGraph = ref<ReleaseDependencyGraphData>({ nodes: [], links: [] })
const renderedRef = ref('')
const releasedAt = ref('')
// The whole closure from the start: a release's dependency file is its true
// shape, and the cycle inside it is the first thing a reader looks for. The
// depth control exists for the hairball of a big closure, not for the first
// look at a small one.
const depth = ref<'1' | '2' | 'all'>('all')
const transitive = ref(false)
const selectedId = ref<string | null>(null)

const version = computed(() => renderedRef.value)

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
 * its safety ceiling) because a ref a picker never received is a release the
 * reader cannot choose. Nothing is picked for them either - the graph is read
 * when they choose a ref.
 */
async function loadRefs() {
  clearRefCandidates()
  selectedRef.value = ''
  if (!hasCoordinates.value) return

  refsLoading.value = true
  try {
    const response = await releaseDiffApi.listRefs(coordinates())
    setRefCandidates(response)
  } catch {
    // Left empty: the picker stays empty and the canvas stays blank.
  } finally {
    refsLoading.value = false
  }
}

/** Reads the dependency graph of one ref and swaps the canvas onto it. */
async function loadGraph(target: string) {
  loading.value = true
  try {
    const file = await releaseDependencyGraphApi.read({ ...coordinates(), ref: target })
    const graph = dependencyFileToGraph(file)
    fullGraph.value = graph.data
    renderedRef.value = graph.ref.name
    releasedAt.value = graph.generated_at ?? ''
    // A ref change can leave the picked node behind: clear the pick rather than
    // dim a graph against a package the new file does not name.
    if (selectedId.value && !graph.data.nodes.some((node) => node.id === selectedId.value)) {
      selectedId.value = null
    }
  } catch {
    fullGraph.value = { nodes: [], links: [] }
    renderedRef.value = ''
    releasedAt.value = ''
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void loadProjects()
})

// The project catalog carries the provider each repository lives on, so picking
// a project fills it in - the reader never has to know which one it is.
watch(selectedProjectKey, async (projectKey) => {
  const project = projects.value.find((item) => item.project_key === projectKey)

  repo.value.repository_slug = ''
  repo.value.git_provider = project?.git_provider || null
  clearRefCandidates()
  selectedRef.value = ''

  // Unknown project keys (typed manually) have no local repository catalog
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

watch(selectedRef, (target) => {
  if (target) void loadGraph(target)
})

const viewData = computed(() =>
  withinDepth(fullGraph.value, depth.value === 'all' ? Infinity : Number(depth.value)),
)

// A depth change can leave the picked node outside the picture: a stale
// selection would dim a graph against a package nobody can see.
watch(depth, () => {
  if (selectedId.value && !viewData.value.nodes.some((node) => node.id === selectedId.value)) {
    selectedId.value = null
  }
})

const selectedNode = computed<ReleaseDependencyGraphNode | null>(
  () => viewData.value.nodes.find((node) => node.id === selectedId.value) ?? null,
)

/** One row of the panel: a package plus the constraint that points at it. */
interface DependencyEntry {
  node: ReleaseDependencyGraphNode
  constraint: string
  pinned: boolean
}

// The panel describes the package, not the slice the canvas shows: its
// dependencies are the ones its dependency file holds, at any depth.
const directDependencies = computed<DependencyEntry[]>(() => {
  const entries: DependencyEntry[] = []
  for (const link of fullGraph.value.links) {
    if (link.source !== selectedId.value) continue
    const node = fullGraph.value.nodes.find((item) => item.id === link.target)
    if (node) {
      entries.push({ node, constraint: link.constraint ?? '', pinned: link.pinned ?? true })
    }
  }
  return entries
})

const directDependents = computed<DependencyEntry[]>(() => {
  const entries: DependencyEntry[] = []
  for (const link of fullGraph.value.links) {
    if (link.target !== selectedId.value) continue
    const node = fullGraph.value.nodes.find((item) => item.id === link.source)
    if (node) {
      entries.push({ node, constraint: link.constraint ?? '', pinned: link.pinned ?? true })
    }
  }
  return entries
})

const inCycle = computed(() =>
  fullGraph.value.links.some(
    (link) =>
      link.circular && (link.source === selectedId.value || link.target === selectedId.value),
  ),
)

// Indexed by category as the dependency file numbers them: 0 the project,
// 1 a dependency, 2 a package the application ships.
const categoryNames = [
  'releaseDependencyGraph.category_project',
  'releaseDependencyGraph.category_dependency',
  'releaseDependencyGraph.category_workspace',
]

function categoryName(category: number): string {
  return t(categoryNames[category] ?? 'releaseDependencyGraph.category_dependency')
}

function tagType(category: number): 'primary' | 'success' | 'info' {
  return category === 0 ? 'primary' : category === 2 ? 'success' : 'info'
}

function onNodeClick(id: string) {
  // A second click on the picked node clears it: the whole graph lights again.
  if (selectedId.value === id) {
    selectedId.value = null
    return
  }
  selectNode(id)
}

/** Pick a node, deepening the view when the depth leaves it off the canvas. */
function selectNode(id: string) {
  selectedId.value = id
  if (!viewData.value.nodes.some((node) => node.id === id)) {
    depth.value = 'all'
  }
}

/** A key reads better with the name the provider holds beside it. */
function secondaryName(value: string, name?: string | null): string | undefined {
  return name && name !== value ? name : undefined
}
</script>

<style scoped>
.release-dependency-graph-container {
  padding: 4px 0 24px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
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

.released-at {
  margin-left: 8px;
}

.coordinates {
  margin-bottom: 8px;
}

.option-key {
  font-weight: 600;
}

.option-name {
  margin-left: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.header-end {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.switch-label {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--el-text-color-regular);
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

.legend-note {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.dash-sample {
  display: inline-block;
  width: 28px;
  border-top: 2px dashed #f56c6c;
}

.detail-panel {
  padding: 4px 4px 4px 8px;
}

.detail-stats {
  margin: 0 0 12px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.detail-title {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin: 0 0 4px;
  font-size: 16px;
  font-weight: 600;
}

.detail-version {
  margin: 0 0 12px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.cycle-alert {
  margin-bottom: 12px;
}

/* The two lists share the panel's height instead of splitting it in half */
.detail-sections {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.detail-section {
  margin-top: 16px;
  min-width: 0;
}

.detail-section h4 {
  margin: 0 0 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-regular);
}

.detail-list {
  margin: 0;
  padding: 0;
  list-style: none;
  /* The chart sets the page's height; a list reads down it rather than stopping
     at a fixed one and scrolling while the space beside it stands empty. The cap
     stays as a backstop for a package nothing should have that many of. */
  max-height: max(240px, calc(100vh - 460px));
  overflow-y: auto;
}

.detail-list li {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 6px;
  padding: 3px 0;
  font-size: 13px;
  min-width: 0;
}

.detail-link {
  padding: 0;
  border: none;
  background: none;
  color: var(--el-color-primary);
  cursor: pointer;
  font-size: 13px;
  text-align: left;
  /* half the panel's width, so a long package name wraps rather than spills */
  min-width: 0;
  overflow-wrap: anywhere;
}

.detail-link:hover {
  text-decoration: underline;
}

/* A range is the loose one: it reads as an open question, a pinned version as
   settled. */
.constraint-sample,
.detail-constraint {
  font-family: var(--el-font-family-mono, monospace);
  font-size: 11px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
}

.detail-constraint.is-range {
  color: var(--el-color-warning);
}

.detail-empty,
.detail-hint {
  margin: 0;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
</style>
