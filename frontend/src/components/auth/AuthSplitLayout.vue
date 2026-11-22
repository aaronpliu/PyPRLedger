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
     not a painted boundary */
  overflow: hidden;
  background: linear-gradient(160deg, #0a1628 0%, #102a43 55%, #0a1628 100%);
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
  filter: blur(90px);
  opacity: 0.5;
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

@media (prefers-reduced-motion: reduce) {
  .aurora-blob {
    animation: none;
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

.form-switchers :deep(.language-mark__glyph) {
  color: rgba(226, 232, 240, 0.55);
}

.form-switchers :deep(.language-mark__glyph.is-current) {
  color: #ffffff;
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
