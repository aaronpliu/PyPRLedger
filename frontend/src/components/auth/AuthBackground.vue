<template>
  <div class="auth-background">
    <transition-group name="background-fade" tag="div" class="background-slider">
      <div
        v-for="(bg, index) in backgrounds"
        :key="bg.id"
        v-show="currentBgIndex === index"
        class="background-image"
        :class="{ 'background-gradient': bg.isGradient }"
        :style="bg.isGradient ? {} : { backgroundImage: `url(${bg.url})` }"
      >
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
  isGradient?: boolean
}

// Automatically load all images from /public/auth-bg/ directory
// This uses Vite's import.meta.glob to discover images at build time
const loadBackgroundImages = (): BackgroundImage[] => {
  const backgrounds: BackgroundImage[] = [
    {
      id: 'abstract-gradient',
      url: '',
      title: 'Abstract Gradient',
      isGradient: true,
    },
  ]

  // Import all image files from /public/auth-bg/ directory
  // Supported formats: jpg, jpeg, png, gif, webp, svg
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

.background-image {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-size: cover;
  background-position: center;
  background-repeat: no-repeat;
  /* Ensure full resolution - no compression or quality loss */
  image-rendering: -webkit-optimize-contrast;
  image-rendering: crisp-edges;
  transition: transform 8s ease-out;
}

.background-gradient {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
  background-size: 400% 400%;
  animation: gradient-shift 15s ease infinite;
}

@keyframes gradient-shift {
  0% {
    background-position: 0% 50%;
  }
  50% {
    background-position: 100% 50%;
  }
  100% {
    background-position: 0% 50%;
  }
}

.background-image[style*="display: block"] {
  transform: scale(1.05);
}

.background-overlay {
  position: absolute;
  width: 100%;
  height: 100%;
  background: linear-gradient(
    135deg,
    rgba(0, 0, 0, 0.4) 0%,
    rgba(0, 0, 0, 0.2) 50%,
    rgba(0, 0, 0, 0.4) 100%
  );
  backdrop-filter: blur(2px);
}

[data-theme='dark'] .background-overlay {
  background: linear-gradient(
    135deg,
    rgba(0, 0, 0, 0.6) 0%,
    rgba(0, 0, 0, 0.4) 50%,
    rgba(0, 0, 0, 0.6) 100%
  );
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
