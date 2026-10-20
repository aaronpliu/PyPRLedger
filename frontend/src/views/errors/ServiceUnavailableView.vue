<template>
  <div class="service-unavailable">
    <el-result
      icon="error"
      :title="t('errors.service_unavailable')"
      :sub-title="t('errors.service_unavailable_desc')"
    >
      <template #extra>
        <el-button type="primary" :loading="checking" @click="retry">
          {{ t('errors.retry') }}
        </el-button>
      </template>
    </el-result>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { checkBackend, markBackendAvailable } from '@/composables/useBackendAvailability'

const { t } = useI18n()
const router = useRouter()
const route = useRoute()
const checking = ref(false)

async function retry() {
  checking.value = true
  const healthy = await checkBackend()
  checking.value = false

  if (healthy) {
    markBackendAvailable()
    // Back to where the reader was headed, or home when that is unknown.
    const from = typeof route.query.from === 'string' ? route.query.from : '/'
    await router.replace(from)
  } else {
    ElMessage.error(t('errors.service_unavailable_retry_failed'))
  }
}
</script>

<style scoped>
.service-unavailable {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: 40px;
}
</style>
