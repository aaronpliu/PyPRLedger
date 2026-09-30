<template>
  <!-- What the app is waiting for, wherever the reader happens to be looking: the
       git provider is asked from the release pages, but the wait outlives a
       change of tab or a scroll. -->
  <div v-if="visible" class="global-progress" role="status" aria-live="polite">
    <div
      class="global-progress-track"
      role="progressbar"
      :aria-label="captionText"
      aria-valuetext="in progress"
    >
      <div class="global-progress-fill" />
    </div>

    <!-- A call that named itself, or one that has run long enough to be worth a
         word: how many seconds is the only honest measure of a wait that has no
         knowable end -->
    <div v-if="captionVisible" class="global-progress-caption" data-test="progress-caption">
      <span class="global-progress-text">{{ captionText }}</span>
      <span v-if="elapsedSeconds >= 1" class="global-progress-elapsed">
        {{ t('common.loading_elapsed', { seconds: elapsedSeconds }) }}
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useProgress } from '@/composables/useProgress'

/** A call with no name of its own gets a caption only once it is worth asking. */
const SLOW_CAPTION_SECONDS = 3

const { t, te } = useI18n()
const { visible, label, elapsedSeconds } = useProgress()

const captionVisible = computed(
  () => Boolean(label.value) || elapsedSeconds.value >= SLOW_CAPTION_SECONDS,
)
const captionText = computed(() => {
  if (!label.value) {
    return t('common.loading')
  }
  return te(label.value) ? t(label.value) : label.value
})
</script>

<style scoped>
.global-progress {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 3000;
  pointer-events: none;
}

.global-progress-track {
  height: 3px;
  overflow: hidden;
  background: rgba(64, 158, 255, 0.18);
}

/* No total is knowable, so the bar states that work is happening rather than how
   much is left */
.global-progress-fill {
  width: 40%;
  height: 100%;
  border-radius: 0 2px 2px 0;
  background: var(--el-color-primary, #409eff);
  animation: global-progress-slide 1.1s ease-in-out infinite;
}

@keyframes global-progress-slide {
  0% {
    transform: translateX(-100%);
  }
  100% {
    transform: translateX(250%);
  }
}

.global-progress-caption {
  display: flex;
  align-items: center;
  gap: 8px;
  float: right;
  max-width: min(90vw, 480px);
  margin: 6px 12px 0 0;
  padding: 4px 10px;
  border: 1px solid var(--el-border-color-lighter, #e4e7ed);
  border-radius: 12px;
  background: var(--el-bg-color-overlay, #ffffff);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
  color: var(--el-text-color-regular, #606266);
  font-size: 12px;
  line-height: 1.6;
}

.global-progress-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.global-progress-elapsed {
  color: var(--el-text-color-secondary, #909399);
  font-variant-numeric: tabular-nums;
}

/* The animation is the message; a reader who asked for less of it still gets the
   bar, the label and the seconds */
@media (prefers-reduced-motion: reduce) {
  .global-progress-fill {
    width: 100%;
    animation: none;
    opacity: 0.7;
  }
}
</style>
