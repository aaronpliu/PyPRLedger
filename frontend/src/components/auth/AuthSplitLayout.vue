<template>
  <div class="auth-split">
    <!-- One continuous brand canvas: the aurora and grid span the whole page,
         so there is no left/right seam to read - the form simply floats on
         the same backdrop the story sits on -->
    <div class="aurora" aria-hidden="true">
      <span class="aurora-blob aurora-blob-sky"></span>
      <span class="aurora-blob aurora-blob-teal"></span>
      <span class="aurora-blob aurora-blob-cyan"></span>
    </div>
    <div class="brand-grid" aria-hidden="true"></div>

    <!-- Star dust: three layers of tiny drifting specks, each with its own
         twinkle rhythm - near-field depth in front of the aurora -->
    <div class="starfield" aria-hidden="true">
      <span class="dust dust-1"></span>
      <span class="dust dust-2"></span>
      <span class="dust dust-3"></span>
    </div>

    <!-- Form panel: the half that asks for input, first in reading order.
         Clean, theme-aware card on the canvas - readability is structural
         here, not a shadow. -->
    <main class="form-panel">
      <div class="form-content">
        <slot />
      </div>
      <div class="form-switchers">
        <ThemeSwitcher />
        <LanguageSwitcher />
      </div>
    </main>

    <!-- Brand column: the half that tells what the product is -->
    <aside class="brand-panel">
      <div class="brand-content">
        <h1 class="brand-title">
          <BrandLogo variant="full-light" alt="PR Ledger" />
        </h1>
        <p class="brand-tagline">{{ t('auth.brand_tagline') }}</p>
        <div class="brand-line"></div>

        <ul class="brand-points">
          <li v-for="point in brandPoints" :key="point.key" class="brand-point">
            <span class="brand-point-icon">
              <el-icon><component :is="point.icon" /></el-icon>
            </span>
            <span class="brand-point-text">
              <b>{{ point.title }}</b>
              <small>{{ point.description }}</small>
            </span>
          </li>
        </ul>
      </div>
    </aside>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { MagicStick, Collection, DataAnalysis } from '@element-plus/icons-vue'
import ThemeSwitcher from '@/components/common/ThemeSwitcher.vue'
import LanguageSwitcher from '@/components/common/LanguageSwitcher.vue'
import BrandLogo from '@/components/common/BrandLogo.vue'

const { t } = useI18n()

// What the product actually does, as three lines a first-time visitor can
// read in one breath - the same story the pages behind the login tell.
const brandPoints = computed(() => [
  {
    key: 'review',
    icon: MagicStick,
    title: t('auth.brand_point_review_title'),
    description: t('auth.brand_point_review_desc'),
  },
  {
    key: 'release',
    icon: Collection,
    title: t('auth.brand_point_release_title'),
    description: t('auth.brand_point_release_desc'),
  },
  {
    key: 'insight',
    icon: DataAnalysis,
    title: t('auth.brand_point_insight_title'),
    description: t('auth.brand_point_insight_desc'),
  },
])
</script>

<style scoped>
.auth-split {
  position: relative;
  display: flex;
  min-height: 100vh;
  /* One navy canvas carries both halves: whatever divides them is content,
     not a painted boundary. Two steps lighter than the old near-black so
     the page reads deep blue rather than charcoal */
  overflow: hidden;
  background: linear-gradient(160deg, #14304a 0%, #1f4266 55%, #14304a 100%);
  color: #ffffff;
}

/* ---- Brand column ---- */
.brand-panel {
  /* Roughly half the screen, but never wider than the story it tells: past
     640px the extra room goes to the form, where the user actually works */
  width: clamp(320px, 46%, 680px);
  flex-shrink: 0;
  display: flex;
  align-items: center;
  padding: 48px clamp(32px, 5vw, 72px);
}

/* The aurora: three soft blobs of the brand palette drifting slowly across
   the whole canvas. Animations are decoration only - a reader who prefers
   stillness gets the same page without the drift. */
.aurora {
  position: absolute;
  inset: 0;
  /* the blobs sit at full brand saturation; the layer opacity is the single
     dial that keeps their glow from dazzling against the lighter canvas */
  filter: blur(110px);
  opacity: 0.25;
  pointer-events: none;
}

.aurora-blob {
  position: absolute;
  border-radius: 50%;
  will-change: transform;
}

.aurora-blob-sky {
  width: 620px;
  height: 620px;
  top: -180px;
  right: -120px;
  background: #0ea5e9;
  animation: aurora-drift 26s ease-in-out infinite alternate;
}

.aurora-blob-teal {
  width: 540px;
  height: 540px;
  bottom: -180px;
  right: 30%;
  background: #14b8a6;
  animation: aurora-drift 32s ease-in-out infinite alternate-reverse;
}

.aurora-blob-cyan {
  width: 480px;
  height: 480px;
  top: 26%;
  left: -160px;
  background: #22d3ee;
  animation: aurora-drift 24s ease-in-out infinite alternate;
}

@keyframes aurora-drift {
  from {
    transform: translate(0, 0) scale(1);
  }
  to {
    transform: translate(40px, -30px) scale(1.12);
  }
}

/* ---- Star dust ---- */
/* Three layers of specks: each layer is a single element whose box-shadow
   paints ~10 dots across the canvas (vw/vh keeps the spread responsive at
   any window size). Layers differ in size, tint and rhythm so the twinkle
   never syncs into a blink. Slow alternating drift, no loop jump. */
.starfield {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.dust {
  position: absolute;
  top: 0;
  left: 0;
  width: 1px;
  height: 1px;
  border-radius: 50%;
  background: transparent;
  animation:
    dust-twinkle 9s ease-in-out infinite,
    dust-drift 70s ease-in-out infinite alternate;
}

.dust-1 {
  /* warm white pinpricks */
  box-shadow:
    8vw 12vh 0 0 rgba(255, 255, 255, 0.7),
    22vw 68vh 0 0 rgba(255, 255, 255, 0.45),
    35vw 30vh 0 0 rgba(255, 255, 255, 0.6),
    47vw 82vh 0 0 rgba(255, 255, 255, 0.5),
    58vw 18vh 0 0 rgba(255, 255, 255, 0.55),
    66vw 55vh 0 0 rgba(255, 255, 255, 0.4),
    74vw 40vh 0 0 rgba(255, 255, 255, 0.6),
    88vw 25vh 0 0 rgba(255, 255, 255, 0.5),
    92vw 72vh 0 0 rgba(255, 255, 255, 0.45),
    15vw 88vh 0 0 rgba(255, 255, 255, 0.35);
  animation-duration: 9s, 70s;
}

.dust-2 {
  /* cool sky-tinted grains, a beat slower */
  box-shadow:
    5vw 45vh 0 0 rgba(148, 197, 233, 0.55),
    18vw 22vh 0 0 rgba(148, 197, 233, 0.4),
    28vw 76vh 0 0 rgba(148, 197, 233, 0.5),
    41vw 58vh 0 0 rgba(148, 197, 233, 0.35),
    52vw 8vh 0 0 rgba(148, 197, 233, 0.5),
    63vw 90vh 0 0 rgba(148, 197, 233, 0.4),
    78vw 62vh 0 0 rgba(148, 197, 233, 0.45),
    85vw 12vh 0 0 rgba(148, 197, 233, 0.5),
    96vw 48vh 0 0 rgba(148, 197, 233, 0.4),
    33vw 92vh 0 0 rgba(148, 197, 233, 0.35);
  animation-duration: 13s, 85s;
  animation-delay: -4s, -20s;
}

.dust-3 {
  /* a few larger sparkles that carry their own halo */
  width: 2px;
  height: 2px;
  box-shadow:
    12vw 35vh 0 1px rgba(125, 211, 252, 0.7),
    12vw 35vh 0 5px rgba(125, 211, 252, 0.12),
    44vw 15vh 0 1px rgba(255, 255, 255, 0.65),
    44vw 15vh 0 5px rgba(255, 255, 255, 0.1),
    57vw 66vh 0 1px rgba(125, 211, 252, 0.6),
    57vw 66vh 0 5px rgba(125, 211, 252, 0.1),
    81vw 34vh 0 1px rgba(255, 255, 255, 0.6),
    81vw 34vh 0 5px rgba(255, 255, 255, 0.09),
    91vw 82vh 0 1px rgba(125, 211, 252, 0.6),
    91vw 82vh 0 5px rgba(125, 211, 252, 0.1);
  animation-duration: 17s, 100s;
  animation-delay: -8s, -40s;
}

@keyframes dust-twinkle {
  0%,
  100% {
    opacity: 0.25;
  }
  50% {
    opacity: 0.9;
  }
}

@keyframes dust-drift {
  from {
    transform: translateY(0);
  }
  to {
    transform: translateY(46px);
  }
}

@media (prefers-reduced-motion: reduce) {
  .aurora-blob {
    animation: none;
  }

  /* stillness keeps the specks, drops the twinkle and the drift */
  .dust {
    animation: none;
    opacity: 0.5;
  }
}

/* A whisper of a grid over the aurora: just enough structure to read as an
   engineered product rather than a wallpaper */
.brand-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.04) 1px, transparent 1px);
  background-size: 44px 44px;
  mask-image: radial-gradient(ellipse at 30% 40%, black 0%, transparent 75%);
}

.brand-content {
  position: relative;
  z-index: 1;
  max-width: 420px;
}

.brand-title {
  --brand-logo-height: 160px;
  margin: 0 0 6px 0;
  line-height: 0;
}

.brand-tagline {
  font-size: 1.05rem;
  color: rgba(255, 255, 255, 0.78);
  margin: 0 0 20px 0;
  line-height: 1.6;
}

.brand-line {
  width: 64px;
  height: 3px;
  border-radius: 2px;
  margin-bottom: 40px;
  background: linear-gradient(
    90deg,
    rgba(14, 165, 233, 0.9),
    rgba(20, 184, 166, 0.9),
    rgba(34, 211, 238, 0.9)
  );
}

.brand-points {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.brand-point {
  display: flex;
  align-items: flex-start;
  gap: 14px;
}

.brand-point-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  flex-shrink: 0;
  border-radius: 10px;
  font-size: 20px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.12);
  color: #7dd3fc;
}

.brand-point-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.brand-point-text b {
  font-size: 0.95rem;
  font-weight: 600;
}

.brand-point-text small {
  font-size: 0.85rem;
  color: rgba(255, 255, 255, 0.65);
  line-height: 1.5;
}

/* ---- Form panel ---- */
.form-panel {
  position: relative;
  z-index: 1;
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px 24px;
}

.form-content {
  width: 100%;
  max-width: 480px;
}

/* The switchers live on the navy canvas now, so they get a glass tile of
   their own instead of relying on a light surface behind them */
.form-switchers {
  position: fixed;
  top: 16px;
  right: 16px;
  z-index: 1000;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 10px;
  border-radius: 14px;
  background: rgba(10, 22, 40, 0.55);
  border: 1px solid rgba(148, 197, 233, 0.22);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
}

.form-switchers :deep(.el-button) {
  border-color: rgba(148, 197, 233, 0.3);
  background: rgba(255, 255, 255, 0.08);
  color: #e2e8f0;
}

.form-switchers :deep(.el-button:hover) {
  background: rgba(255, 255, 255, 0.16);
  color: #ffffff;
}

/* the switcher paints its glyphs in theme text colour; on the navy glass tile
   that would be black on dark, so invert here - and compensate the inactive
   glyph's opacity step so both stay legible */
.form-switchers :deep(.language-mark__glyph) {
  color: #e2e8f0;
  opacity: 0.55;
}

.form-switchers :deep(.language-mark__glyph.is-current) {
  color: #ffffff;
  opacity: 1;
}

/* ---- Responsive ---- */
/* A short viewport has to fit the lockup, the story and the three points:
   shrink the lockup before anything else gets clipped by the panel */
@media (max-height: 720px) and (min-width: 961px) {
  .brand-title {
    --brand-logo-height: 108px;
  }

  .brand-line {
    margin-bottom: 24px;
  }

  .brand-points {
    gap: 16px;
  }
}

@media (max-width: 960px) {
  .auth-split {
    flex-direction: column;
  }

  .brand-panel {
    /* Stacked, the brand band reads first again: the form panel follows it in
       the DOM, so the order is put back explicitly here */
    order: -1;
    width: auto;
    padding: 32px 24px;
  }

  .brand-content {
    max-width: none;
  }

  /* the compact header band has no room for a full-height lockup */
  .brand-title {
    --brand-logo-height: 76px;
  }

  .brand-points {
    display: none;
  }

  .brand-tagline {
    margin-bottom: 14px;
  }

  .brand-line {
    margin-bottom: 0;
  }

  .form-panel {
    padding: 32px 20px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .auth-split {
    min-height: 100dvh;
  }
}
</style>
