<template>
  <!-- The wait for one area of the page: what it is, and - for a call to the git
       provider that has no knowable end - how long it has been. -->
  <div
    v-if="loading"
    class="content-loader"
    :class="{ 'is-inline': inline }"
    :style="minHeight ? { minHeight } : undefined"
    role="status"
    aria-live="polite"
    :aria-label="labelText"
  >
    <el-skeleton v-if="rows > 0" :rows="rows" animated />

    <div class="content-loader-caption">
      <span class="content-loader-spinner" aria-hidden="true" />
      <span class="content-loader-text">{{ labelText }}</span>
      <span v-if="showElapsed && elapsedSeconds >= 1" class="content-loader-elapsed">
        {{ t('common.loading_elapsed', { seconds: elapsedSeconds }) }}
      </span>
      <span v-if="showElapsed && elapsedSeconds >= slowAfter" class="content-loader-slow">
        {{ t('common.loading_slow') }}
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

interface Props {
  loading?: boolean
  /** What is loading: a translation key, or plain text that renders as given. */
  label?: string
  /** Skeleton rows; 0 renders the spinner alone. */
  rows?: number
  /** Sit in a line of text instead of taking the block. */
  inline?: boolean
  /** Count the seconds, for calls that can take a while. */
  showElapsed?: boolean
  /** After how many seconds the "taking a while" note appears. */
  slowAfter?: number
  minHeight?: string
}

const props = withDefaults(defineProps<Props>(), {
  loading: true,
  label: '',
  rows: 0,
  inline: false,
  showElapsed: false,
  slowAfter: 10,
  minHeight: '',
})

const { t, te } = useI18n()
const labelText = computed(() => {
  if (!props.label) {
    return t('common.loading')
  }
  // a key is translated; anything else - a caller's own words - renders as given
  return te(props.label) ? t(props.label) : props.label
})

const startedAt = ref<number | null>(null)
const elapsedSeconds = ref(0)
let timer: ReturnType<typeof setInterval> | undefined

function stopTimer(): void {
  if (timer !== undefined) {
    clearInterval(timer)
    timer = undefined
  }
}

function resetTimer(): void {
  stopTimer()
  elapsedSeconds.value = 0
  if (!props.loading) {
    startedAt.value = null
    return
  }
  startedAt.value = Date.now()
  timer = setInterval(() => {
    elapsedSeconds.value = Math.floor((Date.now() - (startedAt.value ?? Date.now())) / 1000)
  }, 1000)
}

watch(() => props.loading, resetTimer, { immediate: true })
onBeforeUnmount(stopTimer)
</script>

<style scoped>
.content-loader {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
}

.content-loader.is-inline {
  display: inline-flex;
  flex-direction: row;
  align-items: center;
  gap: 8px;
  padding: 0;
}

.content-loader-caption {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 20px;
  color: var(--el-text-color-secondary, #909399);
  font-size: 13px;
  line-height: 1.6;
}

.content-loader-spinner {
  width: 14px;
  height: 14px;
  flex: none;
  border: 2px solid var(--el-border-color, #dcdfe6);
  border-top-color: var(--el-color-primary, #409eff);
  border-radius: 50%;
  animation: content-loader-spin 0.8s linear infinite;
}

.content-loader-text {
  white-space: nowrap;
}

.content-loader-elapsed {
  font-variant-numeric: tabular-nums;
}

.content-loader-slow {
  color: var(--el-color-warning, #e6a23c);
}

@keyframes content-loader-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .content-loader-spinner {
    animation-duration: 2s;
  }
}
</style>
