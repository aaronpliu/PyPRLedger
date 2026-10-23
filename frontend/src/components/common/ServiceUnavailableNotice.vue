<template>
  <!-- Confirmed: the service cannot be reached. Drawn over the page rather than in
       place of it, because a probe can be wrong and a page that was unmounted has
       taken whatever was being written on it with it. -->
  <div v-if="confirmed" class="outage" role="alertdialog" aria-modal="true">
    <div class="outage__panel">
      <el-result
        icon="error"
        :title="t('errors.service_unavailable')"
        :sub-title="t('errors.service_unavailable_desc')"
      >
        <template #extra>
          <el-button type="primary" :loading="checking" @click="retry">
            {{ t('errors.retry') }}
          </el-button>
          <!-- Said here rather than in a toast: a toast is timed, and the one thing
               the reader needs after pressing Retry is that it is still not back. -->
          <div v-if="failed" class="outage__failure" role="status">
            {{ t('errors.service_unavailable_retry_failed') }}
          </div>
        </template>
      </el-result>
    </div>
  </div>

  <!-- In doubt: one probe failed, which is not yet an answer. Out of the way, with
       the reason a slow page is slow - and it goes away on its own. -->
  <div v-else class="outage__banner" role="status" aria-live="polite">
    <el-icon class="is-loading"><Loading /></el-icon>
    <span>{{ t('errors.connection_lost') }}</span>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loading } from '@element-plus/icons-vue'
import { checkBackend } from '@/composables/useBackendAvailability'

defineProps<{ confirmed: boolean }>()

const { t } = useI18n()
const checking = ref(false)
const failed = ref(false)

async function retry() {
  checking.value = true
  failed.value = false
  const healthy = await checkBackend()
  checking.value = false
  failed.value = !healthy
}
</script>

<style scoped>
/* Above the application and below nothing: the page underneath keeps its state
   while the reader waits, and comes back exactly as it was. */
.outage {
  position: fixed;
  inset: 0;
  z-index: 3000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
  background: var(--el-bg-color-page, #f5f7fa);
}

.outage__panel {
  width: min(560px, 100%);
  background: var(--el-bg-color);
  border-radius: 8px;
  box-shadow: var(--el-box-shadow-light);
}

.outage__failure {
  margin-top: 12px;
  font-size: 13px;
  color: var(--el-color-danger);
}

.outage__banner {
  position: fixed;
  top: 0;
  right: 0;
  left: 0;
  z-index: 2999;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 8px 16px;
  font-size: 13px;
  color: var(--el-color-warning-dark-2, #b88230);
  background: var(--el-color-warning-light-9, #fdf6ec);
  border-bottom: 1px solid var(--el-color-warning-light-5, #f5dab1);
}
</style>
