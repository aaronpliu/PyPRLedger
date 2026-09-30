<template>
  <!-- The wait for one area of the page, named so the reader knows what is asked.
       A skeleton marks the areas that render lists, a small spinner the inline
       waits - never both: the skeleton is already the signal. -->
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
      <span v-if="rows === 0" class="content-loader-spinner" aria-hidden="true" />
      <span class="content-loader-text">{{ labelText }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

interface Props {
  loading?: boolean
  /** What is loading: a translation key, or plain text that renders as given. */
  label?: string
  /** Skeleton rows; 0 renders a spinner instead. */
  rows?: number
  /** Sit in a line of text instead of taking the block. */
  inline?: boolean
  minHeight?: string
}

const props = withDefaults(defineProps<Props>(), {
  loading: true,
  label: '',
  rows: 0,
  inline: false,
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
