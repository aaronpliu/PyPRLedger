<template>
  <div class="audit-log-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <h2>{{ t('admin.audit_logs') }}</h2>
          <el-button type="success" @click="exportLogs">
            <el-icon><Download /></el-icon>
            Export
          </el-button>
        </div>
      </template>

      <!-- Filters -->
      <el-form :inline="true" class="filter-form">
        <el-form-item label="Username">
          <el-input v-model="filters.username" placeholder="Search by username" clearable style="width: 200px" />
        </el-form-item>
        
        <el-form-item label="Action">
          <el-select v-model="filters.action" placeholder="All Actions" clearable style="width: 180px">
            <el-option label="CREATE" value="CREATE" />
            <el-option label="UPDATE" value="UPDATE" />
            <el-option label="DELETE" value="DELETE" />
            <el-option label="LOGIN" value="LOGIN" />
            <el-option label="LOGOUT" value="LOGOUT" />
          </el-select>
        </el-form-item>
        
        <el-form-item label="Resource Type">
          <el-select v-model="filters.resource_type" placeholder="All Types" clearable style="width: 180px">
            <el-option label="Review" value="review" />
            <el-option label="Score" value="score" />
            <el-option label="User" value="user" />
            <el-option label="Role" value="role" />
          </el-select>
        </el-form-item>
        
        <el-form-item label="Status">
          <el-select v-model="filters.response_status" placeholder="All Status" clearable style="width: 150px">
            <el-option label="Success (2xx)" :value="200" />
            <el-option label="Client Error (4xx)" :value="400" />
            <el-option label="Server Error (5xx)" :value="500" />
          </el-select>
        </el-form-item>
        
        <el-form-item label="Date Range">
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            range-separator="to"
            start-placeholder="Start date"
            end-placeholder="End date"
            style="width: 240px"
          />
        </el-form-item>
        
        <el-form-item>
          <el-button type="primary" @click="loadAuditLogs">
            <el-icon><Search /></el-icon>
            Search
          </el-button>
          <el-button @click="resetFilters">Reset</el-button>
        </el-form-item>
      </el-form>

      <!-- Statistics -->
      <el-row :gutter="20" class="stats-row" v-if="stats">
        <el-col :span="6">
          <el-statistic title="Total Actions" :value="stats.total_actions" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="Period (Days)" :value="stats.period_days" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="Unique Users" :value="stats.top_actors?.length || 0" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="Success Rate" :value="getSuccessRate()" suffix="%" :precision="1" />
        </el-col>
      </el-row>

      <!-- Audit Logs Table -->
      <el-table :data="logs" v-loading="loading" stripe style="width: 100%; margin-top: 20px">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="auth_user_id" label="User ID" width="100" />
        <el-table-column prop="action" label="Action" width="120">
          <template #default="{ row }">
            <el-tag :type="getActionType(row.action)">{{ row.action }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="resource_type" label="Resource" width="120" />
        <el-table-column prop="resource_id" label="Resource ID" width="120" />
        <el-table-column prop="request_method" label="Method" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="getMethodType(row.request_method)">
              {{ row.request_method }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="response_status" label="Status" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.response_status)">
              {{ row.response_status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="ip_address" label="IP Address" width="140" />
        <el-table-column prop="execution_time_ms" label="Exec Time" width="120">
          <template #default="{ row }">
            {{ row.execution_time_ms }}ms
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="Timestamp" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="Actions" width="100" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="viewDetails(row)">
              Details
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- Pagination -->
      <div class="pagination-container">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[20, 50, 100, 200]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="loadAuditLogs"
          @current-change="loadAuditLogs"
        />
      </div>
    </el-card>

    <!-- Details Dialog -->
    <el-dialog v-model="showDetailsDialog" title="Audit Log Details" width="700px">
      <el-descriptions :column="1" border v-if="selectedLog">
        <el-descriptions-item label="ID">{{ selectedLog.id }}</el-descriptions-item>
        <el-descriptions-item label="User ID">{{ selectedLog.auth_user_id }}</el-descriptions-item>
        <el-descriptions-item label="Action">{{ selectedLog.action }}</el-descriptions-item>
        <el-descriptions-item label="Resource Type">{{ selectedLog.resource_type }}</el-descriptions-item>
        <el-descriptions-item label="Resource ID">{{ selectedLog.resource_id }}</el-descriptions-item>
        <el-descriptions-item label="Request Method">{{ selectedLog.request_method }}</el-descriptions-item>
        <el-descriptions-item label="Request Path">{{ selectedLog.request_path }}</el-descriptions-item>
        <el-descriptions-item label="Response Status">{{ selectedLog.response_status }}</el-descriptions-item>
        <el-descriptions-item label="IP Address">{{ selectedLog.ip_address }}</el-descriptions-item>
        <el-descriptions-item label="User Agent">{{ selectedLog.user_agent }}</el-descriptions-item>
        <el-descriptions-item label="Execution Time">{{ selectedLog.execution_time_ms }}ms</el-descriptions-item>
        <el-descriptions-item label="Error Message" v-if="selectedLog.error_message">
          {{ selectedLog.error_message }}
        </el-descriptions-item>
        <el-descriptions-item label="Old Values" v-if="selectedLog.old_values">
          <pre>{{ JSON.stringify(selectedLog.old_values, null, 2) }}</pre>
        </el-descriptions-item>
        <el-descriptions-item label="New Values" v-if="selectedLog.new_values">
          <pre>{{ JSON.stringify(selectedLog.new_values, null, 2) }}</pre>
        </el-descriptions-item>
        <el-descriptions-item label="Created At">{{ formatDate(selectedLog.created_at) }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { Download, Search } from '@element-plus/icons-vue'
import { auditApi } from '@/api/audit'
import type { AuditLog, AuditStats } from '@/types'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import dayjs from 'dayjs'

const { t } = useI18n()
const loading = ref(false)
const logs = ref<AuditLog[]>([])
const stats = ref<AuditStats | null>(null)
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(50)
const showDetailsDialog = ref(false)
const selectedLog = ref<AuditLog | null>(null)
const dateRange = ref<[Date, Date] | null>(null)

const filters = reactive({
  username: null as string | null,
  action: null as string | null,
  resource_type: null as string | null,
  response_status: null as number | null,
})

const formatDate = (dateStr: string) => {
  return dayjs(dateStr).format('YYYY-MM-DD HH:mm:ss')
}

const getActionType = (action: string) => {
  const types: Record<string, any> = {
    CREATE: 'success',
    UPDATE: 'warning',
    DELETE: 'danger',
    LOGIN: 'info',
    LOGOUT: 'info',
  }
  return types[action] || 'info'
}

const getMethodType = (method: string | null) => {
  if (!method) return 'info'
  const types: Record<string, any> = {
    GET: '',
    POST: 'success',
    PUT: 'warning',
    DELETE: 'danger',
  }
  return types[method] || 'info'
}

const getStatusType = (status: number | null) => {
  if (!status) return 'info'
  if (status >= 200 && status < 300) return 'success'
  if (status >= 400 && status < 500) return 'warning'
  if (status >= 500) return 'danger'
  return 'info'
}

const getSuccessRate = () => {
  if (!stats.value || stats.value.total_actions === 0) return 0
  const successCount = Object.entries(stats.value.actions_by_status || {})
    .filter(([status]) => parseInt(status) >= 200 && parseInt(status) < 400)
    .reduce((sum, [, count]) => sum + count, 0)
  return (successCount / stats.value.total_actions) * 100
}

const loadAuditLogs = async () => {
  loading.value = true
  try {
    const params: any = {
      limit: pageSize.value,
      offset: (currentPage.value - 1) * pageSize.value,
    }

    // Add filters only if they have values
    if (filters.username) {
      params.username = filters.username
    }
    if (filters.action) {
      params.action = filters.action
    }
    if (filters.resource_type) {
      params.resource_type = filters.resource_type
    }
    if (filters.response_status) {
      params.status = filters.response_status.toString()
    }

    if (dateRange.value && dateRange.value.length === 2) {
      params.start_date = dayjs(dateRange.value[0]).format('YYYY-MM-DD')
      params.end_date = dayjs(dateRange.value[1]).format('YYYY-MM-DD')
    }

    const data = await auditApi.getLogs(params)
    logs.value = data.logs
    total.value = data.total

    // Load stats
    stats.value = await auditApi.getStats(30)
  } catch (error) {
    ElMessage.error('Failed to load audit logs')
  } finally {
    loading.value = false
  }
}

const resetFilters = () => {
  filters.auth_user_id = null
  filters.action = null
  filters.resource_type = null
  filters.response_status = null
  dateRange.value = null
  currentPage.value = 1
  loadAuditLogs()
}

const viewDetails = (log: AuditLog) => {
  selectedLog.value = log
  showDetailsDialog.value = true
}

const exportLogs = async () => {
  try {
    const blob = await auditApi.exportLogs({
      ...filters,
      format: 'csv',
    })
    
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `audit-logs-${dayjs().format('YYYY-MM-DD')}.csv`
    document.body.appendChild(a)
    a.click()
    window.URL.revokeObjectURL(url)
    document.body.removeChild(a)
    
    ElMessage.success('Audit logs exported successfully')
  } catch (error) {
    ElMessage.error('Failed to export audit logs')
  }
}

onMounted(() => {
  loadAuditLogs()
})
</script>

<style scoped>
.audit-log-container {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header h2 {
  margin: 0;
  font-size: 20px;
}

.filter-form {
  margin-bottom: 20px;
}

.stats-row {
  margin-bottom: 20px;
}

.pagination-container {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

pre {
  background: #f5f7fa;
  padding: 12px;
  border-radius: 4px;
  max-height: 200px;
  overflow-y: auto;
}
</style>
