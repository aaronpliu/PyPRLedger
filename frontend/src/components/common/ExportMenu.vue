<template>
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
</template>

<script setup lang="ts">
import { Download, ArrowDown, Document, Grid, Tickets, Files } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { Review } from '@/api/reviews'
import { exportSelectedReviews } from '@/utils/export'

interface Props {
  data: Review[]
  selectedIds?: number[]
  size?: 'large' | 'default' | 'small'
  type?: 'primary' | 'success' | 'warning' | 'danger' | 'info'
}

const props = withDefaults(defineProps<Props>(), {
  size: 'default',
  type: 'primary',
  selectedIds: () => [],
})

const handleExportCommand = (format: 'pdf' | 'excel' | 'csv' | 'json') => {
  if (props.data.length === 0) {
    ElMessage.warning('No data to export')
    return
  }

  try {
    const selectedIds = props.selectedIds.length > 0 ? props.selectedIds : undefined
    exportSelectedReviews(props.data, format, selectedIds)
    
    const formatNames: Record<string, string> = {
      pdf: 'PDF',
      excel: 'Excel',
      csv: 'CSV',
      json: 'JSON',
    }
    
    const count = selectedIds?.length || props.data.length
    ElMessage.success(`Exported ${count} reviews to ${formatNames[format]}`)
  } catch (error) {
    console.error('Export failed:', error)
    ElMessage.error('Failed to export data')
  }
}
</script>

<style scoped>
/* No additional styles needed */
</style>
