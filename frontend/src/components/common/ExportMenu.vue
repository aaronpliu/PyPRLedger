<template>
  <div>
    <el-dropdown @command="handleExportCommand" trigger="click">
      <el-button :size="size" :type="type">
        <el-icon><Download /></el-icon>
        {{ t('export.button') }}
        <el-icon class="el-icon--right"><ArrowDown /></el-icon>
      </el-button>
      <template #dropdown>
        <el-dropdown-menu>
          <el-dropdown-item command="pdf">
            <el-icon><Document /></el-icon>
            {{ t('export.as_pdf') }}
          </el-dropdown-item>
          <el-dropdown-item command="excel">
            <el-icon><Grid /></el-icon>
            {{ t('export.as_excel') }}
          </el-dropdown-item>
          <el-dropdown-item command="csv">
            <el-icon><Tickets /></el-icon>
            {{ t('export.as_csv') }}
          </el-dropdown-item>
          <el-dropdown-item command="json">
            <el-icon><Files /></el-icon>
            {{ t('export.as_json') }}
          </el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>

    <!-- Export Scope Dialog -->
    <el-dialog
      v-model="showExportDialog"
      :title="t('export.scope_title')"
      width="500px"
      :close-on-click-modal="false"
      @close="handleDialogClose"
    >
      <div class="export-scope-content">
        <p class="export-scope-label">{{ t('export.scope_label') }}</p>
        <el-radio-group v-model="selectedScope" class="export-scope-options">
          <el-radio value="current" border size="large" class="export-scope-option">
            {{ t('export.current_page_only', { count: props.data.length }) }}
          </el-radio>
          <el-radio value="all" border size="large" class="export-scope-option">
            {{ t('export.all_filtered_data') }}
          </el-radio>
        </el-radio-group>
      </div>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="handleCancel">{{ t('common.cancel') }}</el-button>
          <el-button type="primary" @click="handleConfirm">{{ t('common.confirm') }}</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
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

const { t } = useI18n()

const showExportDialog = ref(false)
const selectedScope = ref<'current' | 'all'>('current')
let pendingFormat: 'pdf' | 'excel' | 'csv' | 'json' | null = null

const handleExportCommand = async (format: 'pdf' | 'excel' | 'csv' | 'json') => {
  if (props.data.length === 0) {
    ElMessage.warning(t('export.no_data'))
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
      ElMessage.info(t('export.fetching_all'))
      dataToExport = await props.fetchAllData()
    } else if (props.selectedIds && props.selectedIds.length > 0) {
      // Filter by selected IDs if provided
      dataToExport = props.data.filter(r => props.selectedIds!.includes(r.id))
    }
    
    if (dataToExport.length === 0) {
      ElMessage.warning(t('export.no_data'))
      return
    }

    await exportSelectedReviews(dataToExport, format)
    
    const formatNames: Record<string, string> = {
      pdf: 'PDF',
      excel: 'Excel',
      csv: 'CSV',
      json: 'JSON',
    }
    
    ElMessage.success(t('export.success_message', { count: dataToExport.length, format: formatNames[format] }))
  } catch (error) {
    console.error('Export failed:', error)
    ElMessage.error(t('export.failed_message'))
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
