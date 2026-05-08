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
  const colors = [
    '#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A',
    '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E2',
    '#F38181', '#AA96DA', '#FCBAD3', '#FFFFD2'
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
