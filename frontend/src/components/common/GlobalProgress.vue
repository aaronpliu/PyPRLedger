<template>
  <!-- A thin bar that states, app-wide, that work is running: a slow call - to
       the git provider above all - stays visible wherever the reader looks,
       without crowding the page with text. The area that is waiting says what
       and how long through its own loader. -->
  <div v-if="visible" class="global-progress" role="status" aria-live="polite">
    <div
      class="global-progress-track"
      role="progressbar"
      :aria-label="t('common.loading')"
      aria-valuetext="in progress"
    >
      <div class="global-progress-fill" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useProgress } from '@/composables/useProgress'

const { t } = useI18n()
const { visible } = useProgress()
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
  background: rgba(var(--el-color-primary-rgb), 0.18);
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

/* The animation is the message; a reader who asked for less of it still gets the
   bar */
@media (prefers-reduced-motion: reduce) {
  .global-progress-fill {
    width: 100%;
    animation: none;
    opacity: 0.7;
  }
}
</style>
