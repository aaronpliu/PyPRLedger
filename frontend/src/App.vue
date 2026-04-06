<template>
  <div id="app">
    <router-view />
    <PWAInstallPrompt />
  </div>
</template>

<script setup lang="ts">
import PWAInstallPrompt from '@/components/common/PWAInstallPrompt.vue'
// Root component - just renders the router view
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
</style>
