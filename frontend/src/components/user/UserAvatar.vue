<template>
  <div class="user-avatar" :style="{ width: size + 'px', height: size + 'px' }">
    <img 
      v-if="avatarUrl && !showFallback" 
      :src="avatarUrl" 
      :alt="username"
      class="avatar-img"
      @error="handleImageError"
    />
    <!-- The hue is a class, not a colour: it is the stylesheet that knows which
         set of tones the theme on screen calls for -->
    <div v-else class="avatar-fallback" :class="hueClass(username)">
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

// One class per tone the initial can be drawn in; the colour itself is in the
// stylesheet, which holds a light tone and a dark one for each
const HUE_COUNT = 12

/**
 * The tone a name is drawn in - the same one every time, so a reader learns to
 * know a person by the colour of their initial.
 */
const hueClass = (name: string) => `avatar-hue-${(name ? name.charCodeAt(0) : 0) % HUE_COUNT}`

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
  font-weight: bold;
  font-size: calc(v-bind(size) * 0.4px);
  user-select: none;
}

/* The initial sits on a pale tone of one hue and is drawn in the deeper tone of
   that same hue: 22px avatars leave a 9px letter, which needs 4.5:1 to be read,
   and these pairs give 6:1 or better. A pastel with white on it was what made
   letters unreadable before, so the text is never white here.

   Each hue is named twice: the tone for the light theme, and the one for the
   dark theme, where a pale block would be the brightest thing on the page. */
.avatar-hue-0 { background: #fee2e2; color: #991b1b; } /* red */
.avatar-hue-1 { background: #ffedd5; color: #9a3412; } /* orange */
.avatar-hue-2 { background: #fef3c7; color: #92400e; } /* amber */
.avatar-hue-3 { background: #dcfce7; color: #166534; } /* green */
.avatar-hue-4 { background: #cffafe; color: #155e75; } /* cyan */
.avatar-hue-5 { background: #dbeafe; color: #1d4ed8; } /* blue */
.avatar-hue-6 { background: #e0e7ff; color: #3730a3; } /* indigo */
.avatar-hue-7 { background: #ede9fe; color: #5b21b6; } /* violet */
.avatar-hue-8 { background: #fce7f3; color: #9d174d; } /* pink */
.avatar-hue-9 { background: #ccfbf1; color: #115e59; } /* teal */
.avatar-hue-10 { background: #fae8ff; color: #86198f; } /* fuchsia */
.avatar-hue-11 { background: #e2e8f0; color: #334155; } /* slate */

[data-theme='dark'] .avatar-hue-0 { background: #4c1d1d; color: #fca5a5; }
[data-theme='dark'] .avatar-hue-1 { background: #431407; color: #fdba74; }
[data-theme='dark'] .avatar-hue-2 { background: #451a03; color: #fcd34d; }
[data-theme='dark'] .avatar-hue-3 { background: #052e16; color: #86efac; }
[data-theme='dark'] .avatar-hue-4 { background: #083344; color: #67e8f9; }
[data-theme='dark'] .avatar-hue-5 { background: #172554; color: #93c5fd; }
[data-theme='dark'] .avatar-hue-6 { background: #1e1b4b; color: #a5b4fc; }
[data-theme='dark'] .avatar-hue-7 { background: #2e1065; color: #c4b5fd; }
[data-theme='dark'] .avatar-hue-8 { background: #500724; color: #f9a8d4; }
[data-theme='dark'] .avatar-hue-9 { background: #042f2e; color: #5eead4; }
[data-theme='dark'] .avatar-hue-10 { background: #4a044e; color: #f0abfc; }
[data-theme='dark'] .avatar-hue-11 { background: #1e293b; color: #cbd5e1; }
</style>
