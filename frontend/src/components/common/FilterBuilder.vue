<template>
  <div class="filter-builder">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span>Advanced Filters</span>
          <div class="header-actions">
            <el-button size="small" @click="showSaveDialog = true" :disabled="filters.length === 0">
              <el-icon><Folder /></el-icon>
              Save Preset
            </el-button>
            <el-button size="small" @click="resetFilters">Reset</el-button>
          </div>
        </div>
      </template>

      <!-- Active Filters -->
      <div class="active-filters" v-if="filters.length > 0">
        <el-tag
          v-for="(filter, index) in filters"
          :key="index"
          closable
          @close="removeFilter(index)"
          class="filter-tag"
          :type="getFilterTagType(filter.operator)"
        >
          {{ formatFilter(filter) }}
        </el-tag>
      </div>

      <!-- Add Filter Form -->
      <el-form :inline="true" class="filter-form">
        <el-form-item label="Field">
          <el-select v-model="newFilter.field" placeholder="Select field" style="width: 150px">
            <el-option
              v-for="field in availableFields"
              :key="field.value"
              :label="field.label"
              :value="field.value"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="Operator">
          <el-select v-model="newFilter.operator" placeholder="Operator" style="width: 120px">
            <el-option label="Equals" value="eq" />
            <el-option label="Not Equals" value="neq" />
            <el-option label="Contains" value="contains" />
            <el-option label="Greater Than" value="gt" />
            <el-option label="Less Than" value="lt" />
            <el-option label="In Range" value="in" />
          </el-select>
        </el-form-item>

        <el-form-item label="Value">
          <el-input
            v-model="newFilter.value"
            placeholder="Enter value"
            style="width: 200px"
            clearable
            @keyup.enter="addFilter"
          />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="addFilter" :disabled="!canAddFilter">
            <el-icon><Plus /></el-icon>
            Add Filter
          </el-button>
        </el-form-item>
      </el-form>

      <!-- Saved Presets -->
      <div v-if="savedPresets.length > 0" class="saved-presets">
        <div class="presets-title">Saved Presets:</div>
        <el-space wrap>
          <el-button
            v-for="preset in savedPresets"
            :key="preset.id"
            size="small"
            @click="applyPreset(preset)"
          >
            {{ preset.name }}
          </el-button>
        </el-space>
      </div>
    </el-card>

    <!-- Save Preset Dialog -->
    <el-dialog v-model="showSaveDialog" title="Save Filter Preset" width="400px">
      <el-form label-width="80px">
        <el-form-item label="Name">
          <el-input v-model="presetName" placeholder="Enter preset name" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showSaveDialog = false">Cancel</el-button>
        <el-button type="primary" @click="savePreset">Save</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Folder, Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

interface Filter {
  field: string
  operator: string
  value: string
}

interface FilterPreset {
  id: string
  name: string
  filters: Filter[]
}

interface FieldOption {
  label: string
  value: string
}

const props = defineProps<{
  availableFields: FieldOption[]
}>()

const emit = defineEmits<{
  (e: 'filters-change', filters: Filter[]): void
  (e: 'apply-preset', preset: FilterPreset): void
}>()

// State
const filters = ref<Filter[]>([])
const newFilter = ref<Filter>({ field: '', operator: '', value: '' })
const savedPresets = ref<FilterPreset[]>([])
const showSaveDialog = ref(false)
const presetName = ref('')

const canAddFilter = computed(() => {
  return newFilter.value.field && newFilter.value.operator && newFilter.value.value
})

const addFilter = () => {
  if (!canAddFilter.value) return

  filters.value.push({ ...newFilter.value })
  newFilter.value = { field: '', operator: '', value: '' }
  
  emitFiltersChange()
  ElMessage.success('Filter added')
}

const removeFilter = (index: number) => {
  filters.value.splice(index, 1)
  emitFiltersChange()
}

const resetFilters = () => {
  filters.value = []
  emitFiltersChange()
  ElMessage.info('Filters cleared')
}

const emitFiltersChange = () => {
  emit('filters-change', filters.value)
}

const formatFilter = (filter: Filter) => {
  const fieldLabel = props.availableFields.find(f => f.value === filter.field)?.label || filter.field
  return `${fieldLabel} ${filter.operator} ${filter.value}`
}

const getFilterTagType = (operator: string) => {
  const types: Record<string, any> = {
    eq: 'success',
    neq: 'warning',
    contains: 'primary',
    gt: 'info',
    lt: 'info',
    in: '',
  }
  return types[operator] || ''
}

// Preset management
const savePreset = () => {
  if (!presetName.value.trim()) {
    ElMessage.warning('Please enter a preset name')
    return
  }

  const preset: FilterPreset = {
    id: Date.now().toString(),
    name: presetName.value,
    filters: [...filters.value],
  }

  savedPresets.value.push(preset)
  savePresetsToStorage()
  
  showSaveDialog.value = false
  presetName.value = ''
  
  ElMessage.success(`Preset "${preset.name}" saved`)
}

const applyPreset = (preset: FilterPreset) => {
  filters.value = [...preset.filters]
  emit('apply-preset', preset)
  emitFiltersChange()
  ElMessage.success(`Applied preset: ${preset.name}`)
}

const savePresetsToStorage = () => {
  try {
    localStorage.setItem('filterPresets', JSON.stringify(savedPresets.value))
  } catch (error) {
    console.error('Failed to save presets:', error)
  }
}

const loadPresetsFromStorage = () => {
  try {
    const stored = localStorage.getItem('filterPresets')
    if (stored) {
      savedPresets.value = JSON.parse(stored)
    }
  } catch (error) {
    console.error('Failed to load presets:', error)
  }
}

// Initialize
loadPresetsFromStorage()

// Expose methods for parent component
defineExpose({
  filters,
  resetFilters,
})
</script>

<style scoped>
.filter-builder {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.active-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
  min-height: 32px;
}

.filter-tag {
  margin: 0;
}

.filter-form {
  margin-bottom: 16px;
}

.saved-presets {
  padding-top: 16px;
  border-top: 1px solid #e4e7ed;
}

.presets-title {
  font-size: 12px;
  color: #909399;
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
</style>
