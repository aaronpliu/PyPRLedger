<template>
  <div id="app">
    <router-view />
    <PWAInstallPrompt />
  </div>
</template>

<script setup lang="ts">
import PWAInstallPrompt from '@/components/common/PWAInstallPrompt.vue'
// Theme is now managed globally by useTheme composable
// The composable auto-initializes on import
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body, #app {
  height: 100%;
  font-family: 'Helvetica Neue', Helvetica, 'PingFang SC', 'Hiragino Sans GB',
    'Microsoft YaHei', Arial, sans-serif;
}

/* Dark Theme Support */
[data-theme='dark'] {
  --el-bg-color: #1e293b;
  --el-bg-color-page: #0f172a;
  --el-text-color-primary: #f1f5f9;
  --el-text-color-regular: #cbd5e1;
  --el-text-color-secondary: #94a3b8;
  --el-border-color: #334155;
  --el-border-color-lighter: #475569;
  --el-fill-color: #334155;
  --el-fill-color-light: #1e293b;
}

[data-theme='dark'] body {
  background-color: #0f172a;
  color: #f1f5f9;
}

[data-theme='dark'] .el-card {
  background-color: #1e293b;
  border-color: #334155;
}

[data-theme='dark'] .el-descriptions__label,
[data-theme='dark'] .el-descriptions__content {
  border-color: #334155 !important;
}

[data-theme='dark'] .el-table {
  --el-table-bg-color: #1e293b;
  --el-table-tr-bg-color: #1e293b;
  --el-table-header-bg-color: #334155;
  --el-table-row-hover-bg-color: #334155;
  --el-table-border-color: #475569;
}

/* Fix striped table rows in dark mode */
[data-theme='dark'] .el-table--striped .el-table__body tr.el-table__row--striped td.el-table__cell {
  background-color: #263347 !important;
}

[data-theme='dark'] .el-input__wrapper,
[data-theme='dark'] .el-textarea__inner {
  background-color: #334155;
  box-shadow: 0 0 0 1px #475569 inset;
}

[data-theme='dark'] .el-select-dropdown {
  background-color: #1e293b;
  border-color: #334155;
}

[data-theme='dark'] .el-dialog {
  background-color: #1e293b;
}

/* Fix Notification in dark mode */
[data-theme='dark'] .el-notification {
  background-color: #1e293b !important;
  border-color: #334155 !important;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3) !important;
}

[data-theme='dark'] .el-notification__title {
  color: #f1f5f9 !important;
}

[data-theme='dark'] .el-notification__content {
  color: #cbd5e1 !important;
}

/* Fix Message in dark mode */
[data-theme='dark'] .el-message {
  background-color: #1e293b !important;
  border-color: #334155 !important;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3) !important;
}

[data-theme='dark'] .el-message__content {
  color: #f1f5f9 !important;
}

/* Fix MessageBox in dark mode */
[data-theme='dark'] .el-message-box {
  background-color: #1e293b !important;
  border-color: #334155 !important;
}

[data-theme='dark'] .el-message-box__title {
  color: #f1f5f9 !important;
}

[data-theme='dark'] .el-message-box__content {
  color: #cbd5e1 !important;
}
</style>
