<template>
  <el-popover placement="bottom-end" :width="264" trigger="click">
    <template #reference>
      <el-button :icon="currentThemeIcon" circle size="small" title="Appearance" />
    </template>

    <div class="theme-panel">
      <div class="theme-panel__section">
        <span class="theme-panel__label">Appearance</span>
        <el-radio-group v-model="themeMode" size="small">
          <el-radio-button value="light">Light</el-radio-button>
          <el-radio-button value="dark">Dark</el-radio-button>
          <el-radio-button value="auto">Auto</el-radio-button>
        </el-radio-group>
      </div>

      <div class="theme-panel__section">
        <span class="theme-panel__label">Accent color</span>
        <div class="theme-swatches">
          <button
            v-for="preset in THEME_COLOR_PRESETS"
            :key="preset.key"
            type="button"
            class="theme-swatch"
            :class="{ 'is-active': primaryColor === preset.value }"
            :style="{ backgroundColor: preset.value }"
            :title="preset.label"
            :aria-label="preset.label"
            :aria-pressed="primaryColor === preset.value"
            @click="setPrimaryColor(preset.value)"
          />
          <el-color-picker
            :model-value="primaryColor"
            size="small"
            :predefine="presetValues"
            @change="onCustomColor"
          />
        </div>
        <el-button
          v-if="isCustomPrimaryColor"
          link
          type="primary"
          size="small"
          class="theme-panel__reset"
          @click="resetPrimaryColor"
        >
          Reset to default
        </el-button>
      </div>
    </div>
  </el-popover>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Sunny, Moon, Monitor } from '@element-plus/icons-vue'
import { useTheme } from '@/composables/useTheme'
import { THEME_COLOR_PRESETS } from '@/utils/themeColor'

const {
  currentTheme,
  primaryColor,
  isCustomPrimaryColor,
  setTheme,
  setPrimaryColor,
  resetPrimaryColor,
} = useTheme()

const presetValues = THEME_COLOR_PRESETS.map((preset) => preset.value)

const themeMode = computed({
  get: () => currentTheme.value,
  set: (value: 'light' | 'dark' | 'auto') => setTheme(value),
})

const themeIcons = {
  light: Sunny,
  dark: Moon,
  auto: Monitor,
}

const currentThemeIcon = computed(() => themeIcons[currentTheme.value])

const onCustomColor = (value: string | null) => {
  if (value) {
    setPrimaryColor(value)
  }
}
</script>

<style scoped>
.theme-panel {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.theme-panel__section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.theme-panel__label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.theme-panel__reset {
  align-self: flex-start;
}

.theme-swatches {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.theme-swatch {
  width: 22px;
  height: 22px;
  border: none;
  border-radius: 50%;
  cursor: pointer;
  padding: 0;
  /* A ring rather than a border, so the swatch keeps its exact colour. */
  box-shadow: 0 0 0 2px var(--el-bg-color-overlay);
  outline: 1px solid var(--el-border-color);
  outline-offset: 1px;
  transition: transform 0.15s ease;
}

.theme-swatch:hover {
  transform: scale(1.1);
}

.theme-swatch.is-active {
  outline: 2px solid var(--el-text-color-primary);
  outline-offset: 2px;
}
</style>
