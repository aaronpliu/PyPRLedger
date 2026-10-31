<template>
  <div class="user-avatar" :style="{ width: size + 'px', height: size + 'px' }">
    <img 
      v-if="avatarUrl && !showFallback" 
      :src="avatarUrl" 
      :alt="username"
      class="avatar-img"
      @error="handleImageError"
    />
    <div 
      v-else 
      class="avatar-fallback"
      :style="{ backgroundColor: getColorFromName(username) }"
    >
      {{ getInitials(username) }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{
  username: string
  avatarUrl?: string | null
  size?: number
}>()

const showFallback = ref(!props.avatarUrl)

// Watch for avatar URL changes
watch(() => props.avatarUrl, (newUrl) => {
  showFallback.value = !newUrl
})

const getInitials = (name: string) => {
  if (!name) return '?'
  return name.charAt(0).toUpperCase()
}

const getColorFromName = (name: string) => {
  // Every tone is dark enough for the white initial to read on it: the earlier
  // pastels put white on #F7DC6F (yellow) or #FFFFD2 (near white) at under
  // 1.4:1 contrast, which is what made some letters hard to see. These all
  // sit at 5:1 or better against white.
  const colors = [
    '#B91C1C', // red
    '#C2410C', // orange
    '#B45309', // amber
    '#15803D', // green
    '#0E7490', // cyan
    '#1D4ED8', // blue
    '#4338CA', // indigo
    '#6D28D9', // violet
    '#BE185D', // pink
    '#0F766E', // teal
    '#A21CAF', // fuchsia
    '#475569', // slate
  ]
  const index = name.charCodeAt(0) % colors.length
  return colors[index]
}

const handleImageError = () => {
  showFallback.value = true
}
</script>

<style scoped>
.user-avatar {
  border-radius: 50%;
  overflow: hidden;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: center;
}

.avatar-fallback {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-weight: bold;
  font-size: calc(v-bind(size) * 0.4px);
  user-select: none;
}
</style>
