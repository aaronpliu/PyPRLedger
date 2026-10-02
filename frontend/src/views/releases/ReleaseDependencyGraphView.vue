<template>
  <div class="release-dependency-graph-container">
    <el-card shadow="never" class="context-card">
      <template #header>
        <div class="card-header">
          <div>
            <h2>{{ t('releaseDependencyGraph.title') }}</h2>
            <p class="subtitle">
              {{ t('releaseDependencyGraph.subtitle', { version }) }}
              <span v-if="releasedAt" class="released-at">
                {{ t('releaseDependencyGraph.released_at', { date: releasedAt }) }}
              </span>
            </p>
          </div>
          <div class="header-end">
            <!-- One release at a time: the graph of a release is the dependency
                 file it shipped, so the version picks the file -->
            <div class="version-picker">
              <span class="switch-label">{{ t('releaseDependencyGraph.version_label') }}</span>
              <el-select v-model="version" size="small" data-test="version-select">
                <el-option v-for="item in versions" :key="item" :value="item" :label="`v${item}`" />
              </el-select>
            </div>
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

      <ContentLoader
        v-if="loading"
        :rows="8"
        :label="t('releaseDependencyGraph.loading')"
        min-height="480px"
      />

      <el-row v-else :gutter="16">
        <el-col :xs="24" :md="16">
          <ReleaseDependencyGraphChart
            :nodes="viewData.nodes"
            :links="viewData.links"
            :selected-id="selectedId"
            :transitive="transitive"
            :category-names="[
              t('releaseDependencyGraph.category_project'),
              t('releaseDependencyGraph.category_workspace'),
              t('releaseDependencyGraph.category_dependency'),
            ]"
            height="560px"
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

        <el-col :xs="24" :md="8">
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

              <div class="detail-section">
                <h4>{{ t('releaseDependencyGraph.dependencies') }} ({{ directDependencies.length }})</h4>
                <ul v-if="directDependencies.length" class="detail-list">
                  <li v-for="entry in directDependencies" :key="entry.node.id">
                    <button class="detail-link" type="button" @click="selectNode(entry.node.id)">
                      {{ entry.node.name ?? entry.node.id }}
                    </button>
                    <span
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
                <h4>{{ t('releaseDependencyGraph.dependents') }} ({{ directDependents.length }})</h4>
                <ul v-if="directDependents.length" class="detail-list">
                  <li v-for="entry in directDependents" :key="entry.node.id">
                    <button class="detail-link" type="button" @click="selectNode(entry.node.id)">
                      {{ entry.node.name ?? entry.node.id }}
                    </button>
                    <span
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
import { useI18n } from 'vue-i18n'
import ReleaseDependencyGraphChart from '@/components/charts/ReleaseDependencyGraphChart.vue'
import ContentLoader from '@/components/common/ContentLoader.vue'
import { withinDepth } from '@/utils/releaseDependencyGraph'
import type {
  ReleaseDependencyGraphData,
  ReleaseDependencyGraphNode,
} from '@/utils/releaseDependencyGraph'
import { loadMockReleaseDependencyGraph, MOCK_RELEASES } from './releaseDependencyGraphMock'

const { t } = useI18n()

// Newest release first: the picker opens on the version the repository ships.
const versions = MOCK_RELEASES.map((release) => release.version)
const version = ref(versions[0])
const loading = ref(true)
const fullGraph = ref<ReleaseDependencyGraphData>({ nodes: [], links: [] })
const releasedAt = ref('')
// The whole closure from the start: a release's dependency file is its true
// shape, and the cycle inside it is the first thing a reader looks for. The
// depth control exists for the hairball of a big closure, not for the first
// look at a small one.
const depth = ref<'1' | '2' | 'all'>('all')
const transitive = ref(false)
const selectedId = ref<string | null>(null)

/** Reads the dependency file of one release and swaps the canvas onto it. */
async function loadRelease(target: string) {
  loading.value = true
  // Stands in for the endpoint that serves the release's dependency JSON.
  const loaded = await loadMockReleaseDependencyGraph(target)
  fullGraph.value = loaded.data
  releasedAt.value = loaded.releasedAt
  loading.value = false
  // A version change can leave the picked node behind: clear the pick rather
  // than dim a graph against a package the new release does not name.
  if (selectedId.value && !loaded.data.nodes.some((node) => node.id === selectedId.value)) {
    selectedId.value = null
  }
}

onMounted(() => loadRelease(version.value))

watch(version, (target) => loadRelease(target))

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

const categoryNames = [
  'releaseDependencyGraph.category_project',
  'releaseDependencyGraph.category_workspace',
  'releaseDependencyGraph.category_dependency',
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

.version-picker {
  display: flex;
  align-items: center;
  gap: 8px;
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

.detail-section {
  margin-top: 16px;
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
  max-height: 220px;
  overflow-y: auto;
}

.detail-list li {
  display: flex;
  align-items: baseline;
  gap: 6px;
  padding: 3px 0;
  font-size: 13px;
}

.detail-link {
  padding: 0;
  border: none;
  background: none;
  color: var(--el-color-primary);
  cursor: pointer;
  font-size: 13px;
  text-align: left;
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
