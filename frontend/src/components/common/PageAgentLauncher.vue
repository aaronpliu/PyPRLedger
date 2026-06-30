<template>
  <div
    class="page-agent-launcher"
    :class="{
      'is-active': visible,
      'is-entered': entryDone,
    }"
    :title="visible ? t('admin.systemSettings.llmHide') : t('admin.systemSettings.llmShow')"
    @click="handleClick"
  >
    <div v-if="!visible" class="horse-wrapper">
      <!-- Speed lines (appear during run-in, before entryDone) -->
      <svg v-if="!entryDone" class="speed-lines" viewBox="0 0 30 30" fill="none" stroke="currentColor">
        <line class="sl sl1" x1="2" y1="8" x2="8" y2="8" stroke-width="0.8" stroke-linecap="round" />
        <line class="sl sl2" x1="1" y1="14" x2="7" y2="14" stroke-width="1" stroke-linecap="round" />
        <line class="sl sl3" x1="3" y1="20" x2="9" y2="20" stroke-width="0.7" stroke-linecap="round" />
        <line class="sl sl4" x1="22" y1="6" x2="28" y2="6" stroke-width="0.8" stroke-linecap="round" />
        <line class="sl sl5" x1="23" y1="12" x2="29" y2="12" stroke-width="0.6" stroke-linecap="round" />
      </svg>

      <!-- Impact ring (bursts when horse arrives) -->
      <svg v-if="!entryDone" class="impact-ring" viewBox="0 0 30 30" fill="none" stroke="currentColor">
        <circle cx="15" cy="15" r="12" stroke-width="0.8" opacity="0.6" />
      </svg>

      <!-- Sparkle particles (only after entry) -->
      <svg v-if="entryDone" class="sparkle s1" viewBox="0 0 12 12" fill="currentColor">
        <path d="M6 0 L7 4 L11 5 L7 6 L6 10 L5 6 L1 5 L5 4 Z" />
      </svg>
      <svg v-if="entryDone" class="sparkle s2" viewBox="0 0 12 12" fill="currentColor">
        <path d="M6 0 L7 4 L11 5 L7 6 L6 10 L5 6 L1 5 L5 4 Z" />
      </svg>
      <svg v-if="entryDone" class="sparkle s3" viewBox="0 0 12 12" fill="currentColor">
        <path d="M6 0 L7 4 L11 5 L7 6 L6 10 L5 6 L1 5 L5 4 Z" />
      </svg>

      <!-- Horse head silhouette, facing right -->
      <!-- Gallops while scaling up (run-in), then settles into breathing -->
      <svg
        class="horse-icon"
        :class="{ 'is-running': !entryDone }"
        viewBox="0 0 30 30"
        fill="none"
        stroke="currentColor"
        stroke-width="1.3"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <!-- Filled head silhouette -->
        <path
          d="M 7 24 C 4 19, 5 11, 9 8 L 11 4.5 L 13.5 7.5 C 17 8, 20.5 10, 23 13 C 25 15.5, 25.5 18.5, 23.5 20.5 C 21.5 22.5, 17 23.5, 13 22.5 C 10.5 22, 8.5 23.5, 7 24 Z"
          fill="currentColor"
          fill-opacity="0.18"
          stroke="currentColor"
          stroke-width="1.3"
        />
        <!-- Ear outline -->
        <path d="M 11 4.5 L 13.5 7.5" stroke-width="1.3" />
        <!-- Ear inner -->
        <path d="M 11.5 5.5 L 12.5 7" stroke-width="0.7" opacity="0.5" />
        <!-- Eye -->
        <ellipse cx="15.5" cy="11" rx="1.4" ry="1.1" fill="currentColor" stroke="none" />
        <circle cx="15.8" cy="10.8" r="0.4" fill="white" stroke="none" opacity="0.8" />
        <!-- Nostril -->
        <path d="M 22.5 16 C 23.5 15.5, 24 16.5, 23 17" stroke-width="0.9" fill="none" />
        <!-- Mouth -->
        <path d="M 21 18.5 C 20 19.5, 18 19.5, 16 19" stroke-width="0.8" opacity="0.7" />
        <!-- Cheek/jaw detail -->
        <path d="M 17.5 17 C 19 16.5, 20.5 17.5, 20 19" stroke-width="0.5" opacity="0.3" />
        <!-- Mane strand 1 (main) -->
        <path d="M 9 8 C 5.5 10, 4 14, 4.5 18" stroke-width="1.2" />
        <!-- Mane strand 2 -->
        <path d="M 8.5 9 C 5 11.5, 3.5 15.5, 4 20" stroke-width="1" opacity="0.7" />
        <!-- Mane strand 3 -->
        <path d="M 8 11 C 5 13.5, 4 17, 4.5 21" stroke-width="0.8" opacity="0.5" />
        <!-- Mane strand 4 (short, top) -->
        <path d="M 10 6 C 8 7.5, 7 9.5, 7.5 12" stroke-width="0.7" opacity="0.4" />
      </svg>
    </div>

    <!-- Close X when panel is visible -->
    <svg
      v-else
      class="launcher-icon"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
    >
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  toggle: []
}>()

const entryDone = ref(false)

onMounted(() => {
  // Entry animation: horse runs in for ~2s, then settles
  setTimeout(() => {
    entryDone.value = true
  }, 2200)
})

function handleClick() {
  emit('toggle')
}
</script>

<style scoped>
.page-agent-launcher {
  position: fixed;
  bottom: 24px;
  right: 24px;
  z-index: 2147483641;
  width: 54px;
  height: 54px;
  border-radius: 50%;
  background: linear-gradient(135deg, #409eff, #6366f1);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 4px 14px rgba(64, 158, 255, 0.4);
  transition: box-shadow 0.3s ease, transform 0.2s ease;
  user-select: none;
  overflow: hidden;
}

.page-agent-launcher:hover {
  transform: scale(1.12);
  box-shadow: 0 6px 24px rgba(64, 158, 255, 0.55),
    0 0 40px rgba(99, 102, 241, 0.25);
}

.page-agent-launcher.is-active {
  background: linear-gradient(135deg, #f56c6c, #e6a23c);
  box-shadow: 0 4px 14px rgba(245, 108, 108, 0.4);
}

/* ── Horse Wrapper ── */
.horse-wrapper {
  position: relative;
  width: 30px;
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* ── Run-in animation: horse gallops from far to near ── */
.horse-icon {
  width: 28px;
  height: 28px;
  /* Run-in (galloping + scaling), then settle into breathing */
  animation: horse-run-in 2s ease-out forwards,
             horse-breathe 3s ease-in-out 2s infinite;
}

/* After entry settled, explicitly use breathing */
.is-entered .horse-icon {
  animation: horse-breathe 3s ease-in-out infinite;
}

.is-entered:hover .horse-icon {
  animation: horse-gallop 0.6s ease-in-out infinite;
}

/* ── Speed Lines (visible during run-in only) ── */
.speed-lines {
  position: absolute;
  width: 100%;
  height: 100%;
  animation: speed-lines-fx 1.8s ease-out forwards;
  pointer-events: none;
}

@keyframes speed-lines-fx {
  0% { opacity: 0; }
  15% { opacity: 0.5; }
  50% { opacity: 0.25; }
  100% { opacity: 0; }
}

.sl {
  stroke-dasharray: 6;
}
.sl1 { animation: speed-streak 0.5s 0.3s ease-out forwards; }
.sl2 { animation: speed-streak 0.5s 0.5s ease-out forwards; }
.sl3 { animation: speed-streak 0.5s 0.7s ease-out forwards; }
.sl4 { animation: speed-streak 0.5s 0.4s ease-out forwards; }
.sl5 { animation: speed-streak 0.5s 0.6s ease-out forwards; }

@keyframes speed-streak {
  0% { opacity: 0; transform: translateX(0); }
  25% { opacity: 0.6; }
  100% { opacity: 0; transform: translateX(-8px); }
}

/* ── Impact Ring (bursts when horse arrives) ── */
.impact-ring {
  position: absolute;
  width: 100%;
  height: 100%;
  animation: impact-burst 0.5s 1.85s ease-out forwards;
  pointer-events: none;
}

@keyframes impact-burst {
  0% { transform: scale(0.5); opacity: 0.5; }
  60% { transform: scale(1.3); opacity: 0.15; }
  100% { transform: scale(1.5); opacity: 0; }
}

/* ── Mane Animation ── */
.horse-icon > :nth-child(9) {
  animation: mane-sway 2.5s ease-in-out infinite;
  transform-origin: 6px 14px;
}
.horse-icon > :nth-child(10) {
  animation: mane-sway 2.5s ease-in-out 0.3s infinite;
  transform-origin: 5px 15px;
}
.horse-icon > :nth-child(11) {
  animation: mane-sway 2.5s ease-in-out 0.6s infinite;
  transform-origin: 5px 16px;
}
.horse-icon > :nth-child(12) {
  animation: mane-sway 2.5s ease-in-out 0.15s infinite;
  transform-origin: 8px 10px;
}

.is-entered:hover .horse-icon > :nth-child(9),
.is-entered:hover .horse-icon > :nth-child(10),
.is-entered:hover .horse-icon > :nth-child(11),
.is-entered:hover .horse-icon > :nth-child(12) {
  animation-duration: 0.5s;
}

/* ── Sparkle Particles (after entry) ── */
.sparkle {
  position: absolute;
  width: 8px;
  height: 8px;
  opacity: 0;
  animation: sparkle-pop 2.5s ease-in-out infinite;
}

.s1 {
  top: -4px;
  right: -2px;
  animation-delay: 0s;
}

.s2 {
  bottom: -2px;
  left: -3px;
  animation-delay: 0.8s;
}

.s3 {
  top: 2px;
  left: -5px;
  animation-delay: 1.6s;
}

.is-entered:hover .sparkle {
  animation-duration: 1s;
}

/* ── Keyframes ── */

/* Run-in: horse gallops from far (tiny) to near (full size), stays visible */
@keyframes horse-run-in {
  0% {
    transform: scale(0.15) translateY(5px);
    opacity: 0.4;
    filter: blur(1.5px);
  }
  10% {
    opacity: 0.8;
  }
  25% {
    transform: scale(0.4) translateY(-1px) rotate(-5deg);
    opacity: 1;
    filter: blur(0);
  }
  40% {
    transform: scale(0.6) translateY(2px) rotate(4deg);
  }
  55% {
    transform: scale(0.78) translateY(-1px) rotate(-3deg);
  }
  70% {
    transform: scale(0.9) translateY(1px) rotate(2deg);
  }
  85% {
    transform: scale(0.98) translateY(-0.5px) rotate(-1deg);
  }
  93% {
    transform: scale(1.04) translateY(0.5px);
  }
  100% {
    transform: scale(1) translateY(0) rotate(0deg);
    opacity: 1;
    filter: blur(0);
  }
}

/* Gentle breathing */
@keyframes horse-breathe {
  0%, 100% { transform: translateY(0) scaleY(1); }
  46% { transform: translateY(-0.5px) scaleY(1.03); }
  50% { transform: translateY(-0.8px) scaleY(1.05); }
  54% { transform: translateY(-0.5px) scaleY(1.03); }
}

/* Lively gallop on hover */
@keyframes horse-gallop {
  0%, 100% { transform: rotate(0deg) translateY(0); }
  20% { transform: rotate(-3deg) translateY(-1px); }
  40% { transform: rotate(2deg) translateY(0px); }
  60% { transform: rotate(-2deg) translateY(-1.5px); }
  80% { transform: rotate(3deg) translateY(0px); }
}

/* Mane sway */
@keyframes mane-sway {
  0%, 100% { transform: translateX(0); }
  25% { transform: translateX(-0.8px); }
  75% { transform: translateX(0.6px); }
}

/* Sparkle pop */
@keyframes sparkle-pop {
  0%, 100% { opacity: 0; transform: scale(0) rotate(0deg); }
  15% { opacity: 1; transform: scale(1) rotate(180deg); }
  30% { opacity: 0.8; transform: scale(0.9) rotate(360deg); }
  50%, 100% { opacity: 0; transform: scale(0) rotate(360deg); }
}

.launcher-icon {
  width: 24px;
  height: 24px;
}
</style>
