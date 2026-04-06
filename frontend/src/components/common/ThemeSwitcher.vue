<template>
  <el-dropdown @command="handleThemeChange" trigger="click">
    <el-button :icon="currentThemeIcon" circle size="small">
      <el-icon><component :is="currentThemeIcon" /></el-icon>
    </el-button>
    <template #dropdown>
      <el-dropdown-menu>
        <el-dropdown-item command="light">
          <el-icon><Sunny /></el-icon>
          Light Mode
        </el-dropdown-item>
        <el-dropdown-item command="dark">
          <el-icon><Moon /></el-icon>
          Dark Mode
        </el-dropdown-item>
        <el-dropdown-item command="auto">
          <el-icon><Monitor /></el-icon>
          Auto (System)
        </el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { Sunny, Moon, Monitor } from '@element-plus/icons-vue'

const currentTheme = ref<'light' | 'dark' | 'auto'>('auto')

const themeIcons = {
  light: Sunny,
  dark: Moon,
  auto: Monitor,
}

const currentThemeIcon = themeIcons[currentTheme.value]

onMounted(() => {
  // Load saved theme preference
  const savedTheme = localStorage.getItem('theme') as 'light' | 'dark' | 'auto'
  if (savedTheme) {
    currentTheme.value = savedTheme
  }
  
  applyTheme(currentTheme.value)
})

watch(currentTheme, (newTheme) => {
  applyTheme(newTheme)
  localStorage.setItem('theme', newTheme)
})

const handleThemeChange = (command: 'light' | 'dark' | 'auto') => {
  currentTheme.value = command
}

const applyTheme = (theme: 'light' | 'dark' | 'auto') => {
  const root = document.documentElement
  
  if (theme === 'auto') {
    // Check system preference
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
    const actualTheme = prefersDark ? 'dark' : 'light'
    
    root.setAttribute('data-theme', actualTheme)
    
    // Listen for system theme changes
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
      if (currentTheme.value === 'auto') {
        root.setAttribute('data-theme', e.matches ? 'dark' : 'light')
      }
    })
  } else {
    root.setAttribute('data-theme', theme)
  }
  
  // Update Element Plus theme
  updateElementPlusTheme(theme === 'dark' || (theme === 'auto' && window.matchMedia('(prefers-color-scheme: dark)').matches))
}

const updateElementPlusTheme = (isDark: boolean) => {
  // Element Plus dark mode class
  if (isDark) {
    document.documentElement.classList.add('dark')
  } else {
    document.documentElement.classList.remove('dark')
  }
}
</script>

<style scoped>
.el-dropdown-menu__item {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
