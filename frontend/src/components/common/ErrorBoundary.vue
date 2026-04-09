<template>
  <div class="error-boundary" role="alert" aria-live="assertive">
    <el-result
      icon="error"
      title="Oops! Something went wrong"
      sub-title="An unexpected error occurred. Please try refreshing the page."
    >
      <template #extra>
        <el-button type="primary" @click="handleRefresh" aria-label="Refresh page">
          Refresh Page
        </el-button>
        <el-button @click="handleGoHome" aria-label="Go to homepage">
          Go to Home
        </el-button>
        <el-button @click="handleReportError" aria-label="Report this error">
          Report Error
        </el-button>
      </template>
    </el-result>
    
    <!-- Error details (only in development) -->
    <el-card v-if="error && import.meta.env.DEV" class="error-details">
      <template #header>
        <span>Error Details (Development Only)</span>
      </template>
      <pre>{{ error }}</pre>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onErrorCaptured } from 'vue'
import { useRouter } from 'vue-router'
import { ElNotification } from 'element-plus'

const router = useRouter()
const error = ref<string | null>(null)
const errorInfo = ref<any>(null)

onErrorCaptured((err, instance, info) => {
  error.value = err.message || String(err)
  errorInfo.value = { component: instance?.$options?.name, info }
  console.error('Error captured by boundary:', err, info)
  
  // Log to error tracking service in production
  if (import.meta.env.PROD) {
    // TODO: Integrate with Sentry or similar
    console.error('Production error:', { message: err.message, stack: err.stack })
  }
  
  return false // Prevent error from propagating further
})

const handleRefresh = () => {
  window.location.reload()
}

const handleGoHome = () => {
  router.push('/')
}

const handleReportError = () => {
  // Copy error details to clipboard
  const errorText = `Error: ${error.value}\nComponent: ${errorInfo.value?.component}\nInfo: ${errorInfo.value?.info}`
  navigator.clipboard.writeText(errorText).then(() => {
    ElNotification({
      title: 'Error Copied',
      message: 'Error details have been copied to clipboard. Please report this to support.',
      type: 'success',
      duration: 5000,
    })
  }).catch(() => {
    ElNotification({
      title: 'Copy Failed',
      message: 'Failed to copy error details. Please take a screenshot.',
      type: 'warning',
    })
  })
}
</script>

<style scoped>
.error-boundary {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: 40px;
}

.error-details {
  margin-top: 20px;
  max-width: 800px;
  width: 100%;
}

.error-details pre {
  background: #f5f7fa;
  padding: 16px;
  border-radius: 4px;
  overflow-x: auto;
  max-height: 400px;
  font-size: 12px;
  line-height: 1.5;
}
</style>
