<template>
  <div class="error-boundary">
    <el-result
      icon="error"
      title="Oops! Something went wrong"
      sub-title="An unexpected error occurred. Please try refreshing the page."
    >
      <template #extra>
        <el-button type="primary" @click="handleRefresh">
          Refresh Page
        </el-button>
        <el-button @click="handleGoHome">
          Go to Home
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

const router = useRouter()
const error = ref<string | null>(null)

onErrorCaptured((err) => {
  error.value = err.message || String(err)
  console.error('Error captured by boundary:', err)
  return false // Prevent error from propagating further
})

const handleRefresh = () => {
  window.location.reload()
}

const handleGoHome = () => {
  router.push('/')
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
