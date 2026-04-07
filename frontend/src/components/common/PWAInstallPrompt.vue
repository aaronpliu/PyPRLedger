<template>
  <transition name="slide-up">
    <div v-if="showInstallPrompt" class="install-prompt">
      <el-card shadow="always" class="prompt-card">
        <div class="prompt-content">
          <div class="prompt-icon">
            <el-icon :size="48" color="#409eff"><Download /></el-icon>
          </div>
          <div class="prompt-text">
            <h3>Install PR Ledger</h3>
            <p>Install this app on your device for quick access and offline support</p>
          </div>
          <div class="prompt-actions">
            <el-button type="primary" @click="installApp">
              Install
            </el-button>
            <el-button @click="dismissPrompt">
              Later
            </el-button>
          </div>
        </div>
      </el-card>
    </div>
  </transition>

  <!-- Offline Indicator -->
  <transition name="fade">
    <div v-if="isOffline" class="offline-indicator">
      <el-alert
        title="You are offline"
        type="warning"
        :closable="false"
        show-icon
      >
        <template #default>
          Some features may be limited. Your changes will sync when you're back online.
        </template>
      </el-alert>
    </div>
  </transition>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { Download } from '@element-plus/icons-vue'
import { ElNotification } from 'element-plus'

const showInstallPrompt = ref(false)
const isOffline = ref(false)
let deferredPrompt: any = null

// Check if user has dismissed the prompt before
const hasDismissedPrompt = () => {
  const dismissed = localStorage.getItem('pwa-prompt-dismissed')
  if (dismissed) {
    const dismissedTime = parseInt(dismissed, 10)
    const now = Date.now()
    const daysSinceDismissed = (now - dismissedTime) / (1000 * 60 * 60 * 24)
    // Only show again after 30 days
    return daysSinceDismissed < 30
  }
  return false
}

onMounted(() => {
  // Listen for beforeinstallprompt event
  window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt)
  
  // Listen for app installed event
  window.addEventListener('appinstalled', handleAppInstalled)
  
  // Listen for online/offline status
  window.addEventListener('online', handleOnlineStatus)
  window.addEventListener('offline', handleOnlineStatus)
  
  // Check initial status
  handleOnlineStatus()
})

onUnmounted(() => {
  window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt)
  window.removeEventListener('appinstalled', handleAppInstalled)
  window.removeEventListener('online', handleOnlineStatus)
  window.removeEventListener('offline', handleOnlineStatus)
})

const handleBeforeInstallPrompt = (e: Event) => {
  // Don't show if user has dismissed before
  if (hasDismissedPrompt()) {
    console.log('User previously dismissed PWA prompt, not showing again')
    return
  }
  
  e.preventDefault()
  deferredPrompt = e
  showInstallPrompt.value = true
  
  // Auto-hide after 10 seconds if not dismissed
  setTimeout(() => {
    if (showInstallPrompt.value) {
      dismissPrompt()
    }
  }, 10000)
}

const handleAppInstalled = () => {
  console.log('PWA was installed')
  showInstallPrompt.value = false
  deferredPrompt = null
  
  ElNotification({
    title: 'Success',
    message: 'PR Ledger has been installed on your device!',
    type: 'success',
    duration: 3000,
  })
}

const handleOnlineStatus = () => {
  isOffline.value = !navigator.onLine
  
  if (!isOffline.value) {
    ElNotification({
      title: 'Back Online',
      message: 'You are now connected to the internet',
      type: 'success',
      duration: 2000,
    })
  }
}

const installApp = async () => {
  if (!deferredPrompt) {
    console.warn('No install prompt available')
    return
  }

  try {
    await deferredPrompt.prompt()
    const choiceResult = await deferredPrompt.userChoice
    
    if (choiceResult.outcome === 'accepted') {
      console.log('User accepted the install prompt')
    } else {
      console.log('User dismissed the install prompt')
    }
    
    deferredPrompt = null
    showInstallPrompt.value = false
  } catch (error) {
    console.error('Install failed:', error)
    ElNotification({
      title: 'Error',
      message: 'Failed to install app',
      type: 'error',
    })
  }
}

const dismissPrompt = () => {
  showInstallPrompt.value = false
  // Save dismissal time to localStorage
  localStorage.setItem('pwa-prompt-dismissed', Date.now().toString())
  // Don't clear deferredPrompt - user can still install from browser menu
}
</script>

<style scoped>
.install-prompt {
  position: fixed;
  bottom: 20px;
  right: 20px;
  z-index: 9999;
  max-width: 400px;
}

.prompt-card {
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
}

.prompt-content {
  display: flex;
  align-items: center;
  gap: 16px;
}

.prompt-icon {
  flex-shrink: 0;
}

.prompt-text {
  flex: 1;
}

.prompt-text h3 {
  margin: 0 0 4px 0;
  font-size: 16px;
  color: #303133;
}

.prompt-text p {
  margin: 0;
  font-size: 13px;
  color: #909399;
  line-height: 1.4;
}

.prompt-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.offline-indicator {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 9998;
}

.offline-indicator :deep(.el-alert) {
  border-radius: 0;
  margin: 0;
}

/* Transitions */
.slide-up-enter-active,
.slide-up-leave-active {
  transition: all 0.3s ease;
}

.slide-up-enter-from {
  opacity: 0;
  transform: translateY(20px);
}

.slide-up-leave-to {
  opacity: 0;
  transform: translateY(20px);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
