<template>
  <div>
    <el-dropdown @command="handleExportCommand" trigger="click">
      <el-button :size="size" :type="type">
        <el-icon><Download /></el-icon>
        Export
        <el-icon class="el-icon--right"><ArrowDown /></el-icon>
      </el-button>
      <template #dropdown>
        <el-dropdown-menu>
          <el-dropdown-item command="pdf">
            <el-icon><Document /></el-icon>
            Export as PDF
          </el-dropdown-item>
          <el-dropdown-item command="excel">
            <el-icon><Grid /></el-icon>
            Export as Excel
          </el-dropdown-item>
          <el-dropdown-item command="csv">
            <el-icon><Tickets /></el-icon>
            Export as CSV
          </el-dropdown-item>
          <el-dropdown-item command="json">
            <el-icon><Files /></el-icon>
            Export as JSON
          </el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>

    <!-- Export Scope Dialog -->
    <el-dialog
      v-model="showExportDialog"
      title="Export Scope"
      width="500px"
      :close-on-click-modal="false"
      @close="handleDialogClose"
    >
      <div class="export-scope-content">
        <p class="export-scope-label">Select which data to export:</p>
        <el-radio-group v-model="selectedScope" class="export-scope-options">
          <el-radio value="current" border size="large" class="export-scope-option">
            Current Page Only ({{ props.data.length }} items)
          </el-radio>
          <el-radio value="all" border size="large" class="export-scope-option">
            All Filtered Data (across all pages)
          </el-radio>
        </el-radio-group>
      </div>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="handleCancel">Cancel</el-button>
          <el-button type="primary" @click="handleConfirm">Confirm</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Download, ArrowDown, Document, Grid, Tickets, Files } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { Review } from '@/api/reviews'
import { exportSelectedReviews } from '@/utils/export'

interface Props {
  data: Review[]
  selectedIds?: number[]
  size?: 'large' | 'default' | 'small'
  type?: 'primary' | 'success' | 'warning' | 'danger' | 'info'
  // Callback to fetch all data with current filters
  fetchAllData?: () => Promise<Review[]>
}

const props = withDefaults(defineProps<Props>(), {
  size: 'default',
  type: 'primary',
  selectedIds: () => [],
  fetchAllData: undefined,
})

const showExportDialog = ref(false)
const selectedScope = ref<'current' | 'all'>('current')
let pendingFormat: 'pdf' | 'excel' | 'csv' | 'json' | null = null

const handleExportCommand = async (format: 'pdf' | 'excel' | 'csv' | 'json') => {
  if (props.data.length === 0) {
    ElMessage.warning('No data to export')
    return
  }

  // If we have a fetchAllData callback and no specific selection, show dialog
  if ((!props.selectedIds || props.selectedIds.length === 0) && props.fetchAllData) {
    pendingFormat = format
    selectedScope.value = 'current'
    showExportDialog.value = true
  } else {
    // Direct export for selected items or when no fetchAllData callback
    await executeExport(format)
  }
}

const handleConfirm = async () => {
  if (!pendingFormat) return
  
  showExportDialog.value = false
  await executeExport(pendingFormat, selectedScope.value)
  pendingFormat = null
}

const handleCancel = () => {
  showExportDialog.value = false
  pendingFormat = null
}

const handleDialogClose = () => {
  // Dialog closed via X button or Escape - cancel export
  pendingFormat = null
}

const executeExport = async (format: 'pdf' | 'excel' | 'csv' | 'json', scope: 'current' | 'all' = 'current') => {
  try {
    let dataToExport = props.data
    
    if (scope === 'all' && props.fetchAllData) {
      ElMessage.info('Fetching all data for export...')
      dataToExport = await props.fetchAllData()
    } else if (props.selectedIds && props.selectedIds.length > 0) {
      // Filter by selected IDs if provided
      dataToExport = props.data.filter(r => props.selectedIds!.includes(r.id))
    }
    
    if (dataToExport.length === 0) {
      ElMessage.warning('No data to export')
      return
    }

    await exportSelectedReviews(dataToExport, format)
    
    const formatNames: Record<string, string> = {
      pdf: 'PDF',
      excel: 'Excel',
      csv: 'CSV',
      json: 'JSON',
    }
    
    ElMessage.success(`Exported ${dataToExport.length} reviews to ${formatNames[format]}`)
  } catch (error) {
    console.error('Export failed:', error)
    ElMessage.error('Failed to export data')
  }
}
</script>

<style scoped>
.export-scope-content {
  padding: 8px 0;
}

.export-scope-label {
  margin-bottom: 16px;
  color: var(--el-text-color-regular);
  font-size: 14px;
}

.export-scope-options {
  display: flex;
  flex-direction: column;
  gap: 12px;
  width: 100%;
}

.export-scope-option {
  width: 100%;
  margin-right: 0 !important;
  padding: 12px 16px;
  transition: all 0.2s ease;
}

.export-scope-option:hover {
  background: var(--el-fill-color-light);
}

.export-scope-option :deep(.el-radio__label) {
  font-size: 14px;
  color: var(--el-text-color-regular);
  user-select: none;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
