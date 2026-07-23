<template>
  <div class="auth-background">
    <transition-group name="background-fade" tag="div" class="background-slider">
      <div
        v-for="(bg, index) in backgrounds"
        :key="bg.id"
        v-show="currentBgIndex === index"
        class="background-wrapper"
      >
        <img
          :src="bg.url"
          :alt="bg.title"
          class="background-image"
          loading="eager"
          decoding="async"
        />
        <div class="background-overlay"></div>
      </div>
    </transition-group>
    
    <!-- Background Controls -->
    <div class="background-controls">
      <!-- Indicators -->
      <div class="bg-indicators">
        <button
          v-for="(bg, index) in backgrounds"
          :key="bg.id"
          class="indicator"
          :class="{ active: currentBgIndex === index }"
          @click="setBg(index)"
          :title="bg.title"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { ArrowLeft, ArrowRight } from '@element-plus/icons-vue'

interface BackgroundImage {
  id: string
  url: string
  title: string
}

// Automatically load all images from /public/auth-bg/ directory
// This uses Vite's import.meta.glob to discover images at build time
const loadBackgroundImages = (): BackgroundImage[] => {
  const backgrounds: BackgroundImage[] = []

  const imageModules = import.meta.glob('/public/auth-bg/*.{jpg,jpeg,png,gif,webp,svg}')
  
  Object.keys(imageModules).forEach((path) => {
    // Extract filename from path
    const filename = path.split('/').pop() || ''
    if (!filename) return
    
    // Generate ID from filename (remove extension)
    const id = filename.replace(/\.[^/.]+$/, '')
    
    // Generate title from filename (convert kebab-case to Title Case)
    const title = id
      .split('-')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ')
    
    backgrounds.push({
      id,
      url: `/auth-bg/${filename}`,
      title,
    })
  })

  return backgrounds
}

const backgrounds = loadBackgroundImages()

const currentBgIndex = ref(0)
let autoRotateTimer: number | null = null

const nextBg = () => {
  currentBgIndex.value = (currentBgIndex.value + 1) % backgrounds.length
}

const previousBg = () => {
  currentBgIndex.value = (currentBgIndex.value - 1 + backgrounds.length) % backgrounds.length
}

const setBg = (index: number) => {
  currentBgIndex.value = index
  resetAutoRotate()
}

const startAutoRotate = () => {
  autoRotateTimer = window.setInterval(() => {
    nextBg()
  }, 8000)
}

const resetAutoRotate = () => {
  if (autoRotateTimer) {
    clearInterval(autoRotateTimer)
  }
  startAutoRotate()
}

onMounted(() => {
  startAutoRotate()
})

onUnmounted(() => {
  if (autoRotateTimer) {
    clearInterval(autoRotateTimer)
  }
})
</script>

<style scoped>
.auth-background {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 0;
  overflow: hidden;
}

.background-slider {
  position: relative;
  width: 100%;
  height: 100%;
}

.background-wrapper {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  overflow: hidden;
}

.background-image {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: center;
  image-rendering: -webkit-optimize-contrast !important;
  image-rendering: crisp-edges !important;
  image-rendering: high-quality !important;
  image-rendering: pixelated !important;
  -webkit-backface-visibility: hidden;
  backface-visibility: hidden;
  transform: translateZ(0);
  will-change: transform;
  transition: transform 8s ease-out;
  min-width: 100%;
  min-height: 100%;
}

.background-wrapper[style*="display: block"] .background-image {
  transform: scale(1.05);
}

.background-overlay {
  position: absolute;
  width: 100%;
  height: 100%;
  /* Reduced blur to maintain image sharpness */
  background: linear-gradient(
    135deg,
    rgba(0, 0, 0, 0.3) 0%,
    rgba(0, 0, 0, 0.15) 50%,
    rgba(0, 0, 0, 0.3) 100%
  );
  /* Remove backdrop-filter blur - it makes images fuzzy */
  /* backdrop-filter: blur(2px); */
}

[data-theme='dark'] .background-overlay {
  background: linear-gradient(
    135deg,
    rgba(0, 0, 0, 0.5) 0%,
    rgba(0, 0, 0, 0.3) 50%,
    rgba(0, 0, 0, 0.5) 100%
  );
  /* No blur in dark mode either */
}

/* Background Fade Transition */
.background-fade-enter-active,
.background-fade-leave-active {
  transition: opacity 1.5s ease;
}

.background-fade-enter-from,
.background-fade-leave-to {
  opacity: 0;
}

/* Background Controls */
.background-controls {
  position: absolute;
  bottom: 40px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 10;
  display: flex;
  align-items: center;
  gap: 10px;
}

.bg-indicators {
  display: flex;
  gap: 10px;
  align-items: center;
}

.indicator {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.4);
  border: 2px solid rgba(255, 255, 255, 0.6);
  cursor: pointer;
  transition: all 0.3s ease;
  padding: 0;
}

.indicator:hover {
  background: rgba(255, 255, 255, 0.6);
  transform: scale(1.2);
}

.indicator.active {
  background: white;
  border-color: white;
  transform: scale(1.3);
  box-shadow: 0 0 12px rgba(255, 255, 255, 0.8);
}

/* Responsive Design */
@media (max-width: 768px) {
  .background-controls {
    bottom: 20px;
  }
  
  .indicator {
    width: 8px;
    height: 8px;
  }
}

@media (max-width: 480px) {
  .background-controls {
    bottom: 16px;
  }
  
  .indicator {
    width: 6px;
    height: 6px;
  }
}
</style>
