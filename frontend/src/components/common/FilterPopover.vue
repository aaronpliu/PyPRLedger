<template>
  <div class="filter-popover-wrapper">
    <!-- Search Input with Filter Badge -->
    <el-popover
      v-model:visible="popoverVisible"
      :width="650"
      placement="bottom-start"
      trigger="click"
      :hide-after="0"
      :popper-options="{
        modifiers: [
          {
            name: 'offset',
            options: {
              offset: [0, 8],
            },
          },
        ],
      }"
      @hide="handlePopoverHide"
    >
      <template #reference>
        <el-input
          ref="searchInputRef"
          v-model="localSearchQuery"
          :placeholder="placeholder"
          clearable
          :style="{ width: searchWidth }"
          @input="handleSearchInput"
          @keyup.enter="handleEnter"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
          <template #suffix>
            <el-badge
              v-if="activeFilterCount > 0"
              :value="activeFilterCount"
              :max="99"
              type="primary"
            >
              <el-icon class="filter-icon"><Filter /></el-icon>
            </el-badge>
            <el-icon v-else class="filter-icon"><Filter /></el-icon>
          </template>
        </el-input>
      </template>

      <!-- Filter Panel Content -->
      <div class="filter-panel" @click.stop>
        <div class="filter-panel-header">
          <h4>{{ panelTitle }}</h4>
          <el-button link @click="handleReset">
            <el-icon><RefreshLeft /></el-icon>
            Reset All
          </el-button>
        </div>

        <div class="filter-grid">
          <!-- App Name (Multi-select) -->
          <div v-if="showAppFilter" class="filter-item">
            <label class="filter-label">App Name</label>
            <el-select
              v-model="localAppFilter"
              placeholder="Select apps"
              clearable
              multiple
              collapse-tags
              collapse-tags-tooltip
              style="width: 100%"
            >
              <el-option
                v-for="app in appOptions"
                :key="typeof app === 'string' ? app : app.app_name"
                :label="typeof app === 'string' ? app : app.app_name"
                :value="typeof app === 'string' ? app : app.app_name"
              />
            </el-select>
          </div>

          <!-- Project Filter -->
          <div v-if="showProjectFilter" class="filter-item">
            <label class="filter-label">Project</label>
            <el-select
              v-model="localProjectFilter"
              placeholder="Select project"
              clearable
              filterable
              style="width: 100%"
            >
              <el-option
                v-for="project in projectOptions"
                :key="project.project_key"
                :label="`${project.name || project.project_name || 'Unknown'} (${project.project_key})`"
                :value="project.project_key"
              >
                <span>{{ project.name || project.project_name || 'Unknown' }}</span>
                <span class="text-secondary" style="margin-left: 8px; font-size: 0.85em">
                  ({{ project.project_key }})
                </span>
              </el-option>
            </el-select>
          </div>

          <!-- PR User (Remote Search) -->
          <div v-if="showPRUserFilter" class="filter-item">
            <label class="filter-label">PR User</label>
            <el-select
              v-model="localPRUserFilter"
              placeholder="Select or type name"
              clearable
              filterable
              remote
              :remote-method="searchPRUsers"
              :loading="prUsersLoading"
              style="width: 100%"
            >
              <el-option
                v-for="user in prUserOptions"
                :key="user.username"
                :label="user.display_name || user.username"
                :value="user.username"
              >
                <span>{{ user.display_name }}</span>
                <span class="text-secondary" style="margin-left: 8px; font-size: 0.85em">
                  ({{ user.username }})
                </span>
              </el-option>
            </el-select>
          </div>

          <!-- Reviewer (Remote Search with Unassigned) -->
          <div v-if="showReviewerFilter" class="filter-item">
            <label class="filter-label">Reviewer</label>
            <el-select
              v-model="localReviewerFilter"
              placeholder="Select or type name"
              clearable
              filterable
              remote
              :remote-method="searchReviewers"
              :loading="reviewersLoading"
              style="width: 100%"
            >
              <el-option
                v-for="user in reviewerOptions"
                :key="user.username"
                :label="user.display_name || user.username"
                :value="user.username"
              >
                <span>{{ user.display_name }}</span>
                <span class="text-secondary" style="margin-left: 8px; font-size: 0.85em">
                  ({{ user.username }})
                </span>
              </el-option>
              <el-option
                key="__unassigned__"
                label="⚠️ Unassigned"
                value="__unassigned__"
              >
                <span style="color: #e6a23c; font-weight: 600">⚠️ Unassigned</span>
              </el-option>
            </el-select>
          </div>

          <!-- Scored Filter -->
          <div v-if="showScoredFilter" class="filter-item">
            <label class="filter-label">Scored</label>
            <el-select
              v-model="localScoredFilter"
              placeholder="All"
              clearable
              style="width: 100%"
            >
              <el-option label="Scored" value="yes" />
              <el-option label="Not Scored" value="no" />
            </el-select>
          </div>

          <!-- Severity Filter -->
          <div v-if="showSeverityFilter" class="filter-item">
            <label class="filter-label">Severity</label>
            <el-select
              v-model="localSeverityFilter"
              placeholder="All"
              clearable
              style="width: 100%"
            >
              <el-option label="Critical" value="critical" />
              <el-option label="High" value="high" />
              <el-option label="Medium" value="medium" />
              <el-option label="Low" value="low" />
            </el-select>
          </div>

          <!-- PR Status Filter -->
          <div v-if="showStatusFilter" class="filter-item">
            <label class="filter-label">PR Status</label>
            <el-select
              v-model="localStatusFilter"
              placeholder="All Status"
              clearable
              style="width: 100%"
            >
              <el-option label="Open" value="open" />
              <el-option label="Merged" value="merged" />
              <el-option label="Closed" value="closed" />
              <el-option label="Draft" value="draft" />
            </el-select>
          </div>
        </div>

        <!-- Action Buttons -->
        <div class="filter-actions">
          <el-button @click="handleCancel">Cancel</el-button>
          <el-button type="primary" @click="handleConfirm">
            <el-icon><Check /></el-icon>
            Confirm
          </el-button>
        </div>
      </div>
    </el-popover>

    <!-- Active Filter Tags (shown when popover is closed) -->
    <div v-if="activeFilterCount > 0 && !popoverVisible" class="active-filters-bar">
      <el-tag
        v-for="tag in activeFilterTags"
        :key="tag.key"
        closable
        @close="handleRemoveFilter(tag.key)"
        size="small"
        style="margin-right: 8px; margin-bottom: 8px"
      >
        {{ tag.label }}: {{ tag.value }}
      </el-tag>
      <el-button link type="primary" size="small" @click="handleReset">
        Clear All
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { Search, Filter, RefreshLeft, Check } from '@element-plus/icons-vue'
import type { AppInfo } from '@/api/projectRegistry'
import type { ReviewerUser } from '@/api/users'

interface Props {
  // Search configuration
  searchQuery?: string
  placeholder?: string
  searchWidth?: string

  // Filter values
  appFilter?: string[]
  projectFilter?: string
  prUserFilter?: string
  reviewerFilter?: string
  scoredFilter?: string
  severityFilter?: string
  statusFilter?: string

  // Filter visibility flags
  showAppFilter?: boolean
  showProjectFilter?: boolean
  showPRUserFilter?: boolean
  showReviewerFilter?: boolean
  showScoredFilter?: boolean
  showSeverityFilter?: boolean
  showStatusFilter?: boolean

  // Options for dropdowns
  appOptions?: AppInfo[] | string[]
  projectOptions?: Array<{ project_key: string; name?: string; project_name?: string }>
  prUserOptions?: ReviewerUser[]
  reviewerOptions?: ReviewerUser[]

  // Loading states
  prUsersLoading?: boolean
  reviewersLoading?: boolean

  // Customization
  panelTitle?: string
}

const props = withDefaults(defineProps<Props>(), {
  searchQuery: '',
  placeholder: 'Search... (Click for more filters)',
  searchWidth: '350px',
  appFilter: () => [],
  projectFilter: '',
  prUserFilter: '',
  reviewerFilter: '',
  scoredFilter: '',
  severityFilter: '',
  statusFilter: '',
  showAppFilter: true,
  showProjectFilter: false,
  showPRUserFilter: true,
  showReviewerFilter: true,
  showScoredFilter: true,
  showSeverityFilter: true,
  showStatusFilter: true,
  appOptions: () => [],
  projectOptions: () => [],
  prUserOptions: () => [],
  reviewerOptions: () => [],
  prUsersLoading: false,
  reviewersLoading: false,
  panelTitle: 'Advanced Filters',
})

const emit = defineEmits<{
  'update:searchQuery': [value: string]
  'update:appFilter': [value: string[]]
  'update:projectFilter': [value: string]
  'update:prUserFilter': [value: string]
  'update:reviewerFilter': [value: string]
  'update:scoredFilter': [value: string]
  'update:severityFilter': [value: string]
  'update:statusFilter': [value: string]
  apply: []
  reset: []
  searchPRUsers: [query: string]
  searchReviewers: [query: string]
}>()

// Local state for two-way binding
const popoverVisible = ref(false)
const searchInputRef = ref()

// Local copies of filter values
const localSearchQuery = ref(props.searchQuery)
const localAppFilter = ref([...(props.appFilter || [])])
const localProjectFilter = ref(props.projectFilter || '')
const localPRUserFilter = ref(props.prUserFilter || '')
const localReviewerFilter = ref(props.reviewerFilter || '')
const localScoredFilter = ref(props.scoredFilter || '')
const localSeverityFilter = ref(props.severityFilter || '')
const localStatusFilter = ref(props.statusFilter || '')

// Sync local values with props
watch(
  () => props.searchQuery,
  (val) => {
    localSearchQuery.value = val
  }
)

watch(
  () => props.appFilter,
  (val) => {
    localAppFilter.value = [...(val || [])]
  },
  { deep: true }
)

watch(() => props.projectFilter, (val) => {
  localProjectFilter.value = val || ''
})

watch(() => props.prUserFilter, (val) => {
  localPRUserFilter.value = val || ''
})

watch(() => props.reviewerFilter, (val) => {
  localReviewerFilter.value = val || ''
})

watch(() => props.scoredFilter, (val) => {
  localScoredFilter.value = val || ''
})

watch(() => props.severityFilter, (val) => {
  localSeverityFilter.value = val || ''
})

watch(() => props.statusFilter, (val) => {
  localStatusFilter.value = val || ''
})

// Computed: Active filter count
const activeFilterCount = computed(() => {
  let count = 0
  if (localSearchQuery.value) count++
  if (localAppFilter.value && localAppFilter.value.length > 0) count++
  if (localProjectFilter.value) count++
  if (localPRUserFilter.value) count++
  if (localReviewerFilter.value) count++
  if (localScoredFilter.value) count++
  if (localSeverityFilter.value) count++
  if (localStatusFilter.value) count++
  return count
})

// Computed: Active filter tags for display
const activeFilterTags = computed(() => {
  const tags = []

  if (localAppFilter.value && localAppFilter.value.length > 0) {
    tags.push({
      key: 'app',
      label: 'App',
      value: localAppFilter.value.join(', '),
    })
  }

  if (localProjectFilter.value) {
    const project = props.projectOptions.find(p => p.project_key === localProjectFilter.value)
    const projectName = project?.name || project?.project_name || localProjectFilter.value
    tags.push({
      key: 'project',
      label: 'Project',
      value: `${projectName} (${localProjectFilter.value})`,
    })
  }

  if (localPRUserFilter.value) {
    tags.push({
      key: 'prUser',
      label: 'PR User',
      value: localPRUserFilter.value,
    })
  }

  if (localReviewerFilter.value) {
    tags.push({
      key: 'reviewer',
      label: 'Reviewer',
      value:
        localReviewerFilter.value === '__unassigned__'
          ? 'Unassigned'
          : localReviewerFilter.value,
    })
  }

  if (localScoredFilter.value) {
    tags.push({
      key: 'scored',
      label: 'Scored',
      value: localScoredFilter.value === 'yes' ? 'Yes' : 'No',
    })
  }

  if (localSeverityFilter.value) {
    tags.push({
      key: 'severity',
      label: 'Severity',
      value: localSeverityFilter.value.charAt(0).toUpperCase() + localSeverityFilter.value.slice(1),
    })
  }

  if (localStatusFilter.value) {
    tags.push({
      key: 'status',
      label: 'Status',
      value: localStatusFilter.value.charAt(0).toUpperCase() + localStatusFilter.value.slice(1),
    })
  }

  return tags
})

// Event handlers
const handleSearchInput = (value: string) => {
  emit('update:searchQuery', value)
}

const handleEnter = () => {
  // Optional: Auto-apply on Enter key
  // handleApply()
}

const handleConfirm = () => {
  // Sync all local values to parent
  emit('update:searchQuery', localSearchQuery.value)
  emit('update:appFilter', localAppFilter.value)
  emit('update:projectFilter', localProjectFilter.value)
  emit('update:prUserFilter', localPRUserFilter.value)
  emit('update:reviewerFilter', localReviewerFilter.value)
  emit('update:scoredFilter', localScoredFilter.value)
  emit('update:severityFilter', localSeverityFilter.value)
  emit('update:statusFilter', localStatusFilter.value)
  
  // Close popover and trigger data reload
  popoverVisible.value = false
  emit('apply')
}

const handleCancel = () => {
  // Reset local values to current prop values
  localSearchQuery.value = props.searchQuery
  localAppFilter.value = [...(props.appFilter || [])]
  localProjectFilter.value = props.projectFilter || ''
  localPRUserFilter.value = props.prUserFilter || ''
  localReviewerFilter.value = props.reviewerFilter || ''
  localScoredFilter.value = props.scoredFilter || ''
  localSeverityFilter.value = props.severityFilter || ''
  localStatusFilter.value = props.statusFilter || ''
  
  popoverVisible.value = false
}

const handleReset = () => {
  // Clear all filters (watchers will emit updates automatically)
  localSearchQuery.value = ''
  localAppFilter.value = []
  localProjectFilter.value = ''
  localPRUserFilter.value = ''
  localReviewerFilter.value = ''
  localScoredFilter.value = ''
  localSeverityFilter.value = ''
  localStatusFilter.value = ''
  
  emit('reset')
  popoverVisible.value = false
}

const handleRemoveFilter = (key: string) => {
  switch (key) {
    case 'app':
      localAppFilter.value = []
      break
    case 'project':
      localProjectFilter.value = ''
      break
    case 'prUser':
      localPRUserFilter.value = ''
      break
    case 'reviewer':
      localReviewerFilter.value = ''
      break
    case 'scored':
      localScoredFilter.value = ''
      break
    case 'severity':
      localSeverityFilter.value = ''
      break
    case 'status':
      localStatusFilter.value = ''
      break
  }
  // Updates will be synced when popover closes or confirm is clicked
  // But we trigger apply to refresh data immediately if needed, 
  // relying on parent to read current prop values which might need explicit update if not using v-model sync on close
  
  // To ensure consistency with "Apply on Confirm/Hide", we should probably just update local state here.
  // If immediate update is required for tag removal UX, parent must handle it.
  // However, strictly following "only apply on Confirm or hide", we just update local state.
  // The tags will re-render based on local state anyway.
  
  // If the parent needs to know about the change immediately to update the list, 
  // we might need to call handleConfirm logic or similar. 
  // But usually removing a tag implies applying the filter.
  // Let's trigger a confirm-like update to ensure parent state matches.
  
  emit('update:searchQuery', localSearchQuery.value)
  emit('update:appFilter', [...localAppFilter.value])
  emit('update:projectFilter', localProjectFilter.value)
  emit('update:prUserFilter', localPRUserFilter.value)
  emit('update:reviewerFilter', localReviewerFilter.value)
  emit('update:scoredFilter', localScoredFilter.value)
  emit('update:severityFilter', localSeverityFilter.value)
  emit('update:statusFilter', localStatusFilter.value)
  
  emit('apply')
}

const searchPRUsers = (query: string) => {
  emit('searchPRUsers', query)
}

const searchReviewers = (query: string) => {
  emit('searchReviewers', query)
}

const handlePopoverHide = () => {
  // When popover hides (clicking outside or pressing Escape),
  // sync current local values to parent so filters persist
  emit('update:searchQuery', localSearchQuery.value)
  emit('update:appFilter', localAppFilter.value)
  emit('update:projectFilter', localProjectFilter.value)
  emit('update:prUserFilter', localPRUserFilter.value)
  emit('update:reviewerFilter', localReviewerFilter.value)
  emit('update:scoredFilter', localScoredFilter.value)
  emit('update:severityFilter', localSeverityFilter.value)
  emit('update:statusFilter', localStatusFilter.value)
}

</script>

<style scoped>
.filter-popover-wrapper {
  margin-bottom: 16px;
}

.filter-icon {
  color: var(--el-text-color-secondary);
  transition: color 0.2s;
}

.filter-icon:hover {
  color: var(--el-color-primary);
}

.filter-panel {
  padding: 8px 0;
}

.filter-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.filter-panel-header h4 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.filter-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 20px;
  padding: 4px 0;
}

.filter-item {
  display: flex;
  flex-direction: column;
  transition: all 0.2s ease;
}

.filter-item:hover {
  transform: translateY(-1px);
}

.filter-label {
  margin-bottom: 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-regular);
  letter-spacing: 0.3px;
}

.filter-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  width: 100%;
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid var(--el-border-color-lighter);
}

.active-filters-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  min-height: 32px;
  animation: fadeIn 0.2s ease-in;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(-4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.text-secondary {
  color: var(--el-text-color-secondary);
}

/* Responsive adjustments */
@media (max-width: 768px) {
  .filter-grid {
    grid-template-columns: 1fr;
    gap: 16px;
  }
  
  .filter-panel {
    max-width: 100vw;
  }
}

/* Dark mode adjustments */
[data-theme='dark'] .filter-panel-header {
  border-bottom-color: var(--el-border-color-dark);
}

[data-theme='dark'] .filter-actions {
  border-top-color: var(--el-border-color-dark);
}
</style>
