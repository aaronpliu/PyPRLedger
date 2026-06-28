<template>
  <div
    class="page-agent-launcher"
    :class="{ 'is-active': visible }"
    :title="visible ? t('admin.systemSettings.llmHide') : t('admin.systemSettings.llmShow')"
    @click="handleClick"
  >
    <svg
      v-if="!visible"
      class="launcher-icon"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
    >
      <path d="M12 2a10 10 0 0 1 10 10c0 4.5-3.5 8.5-8 9.5V22l-4-3h-1a10 10 0 0 1-7-9.5A10 10 0 0 1 12 2z" />
      <line x1="9" y1="10" x2="15" y2="10" />
      <line x1="12" y1="7" x2="12" y2="13" />
    </svg>
    <svg
      v-else
      class="launcher-icon"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
    >
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  toggle: []
}>()

function handleClick() {
  emit('toggle')
}
</script>

<style scoped>
.page-agent-launcher {
  position: fixed;
  bottom: 24px;
  right: 24px;
  z-index: 2147483641;
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: linear-gradient(135deg, #409eff, #6366f1);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.4);
  transition: all 0.25s ease;
  user-select: none;
}

.page-agent-launcher:hover {
  transform: scale(1.1);
  box-shadow: 0 6px 20px rgba(64, 158, 255, 0.5);
}

.page-agent-launcher.is-active {
  background: linear-gradient(135deg, #f56c6c, #e6a23c);
  box-shadow: 0 4px 12px rgba(245, 108, 108, 0.4);
}

.launcher-icon {
  width: 24px;
  height: 24px;
}
</style>
