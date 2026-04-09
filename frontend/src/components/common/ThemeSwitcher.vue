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
import { computed } from 'vue'
import { Sunny, Moon, Monitor } from '@element-plus/icons-vue'
import { useTheme } from '@/composables/useTheme'

const { currentTheme, setTheme } = useTheme()

const themeIcons = {
  light: Sunny,
  dark: Moon,
  auto: Monitor,
}

const currentThemeIcon = computed(() => themeIcons[currentTheme.value])

const handleThemeChange = (command: 'light' | 'dark' | 'auto') => {
  setTheme(command)
}
</script>

<style scoped>
.el-dropdown-menu__item {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
