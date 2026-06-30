<template>
  <div v-if="showBanner" class="reviews-banner">
    <div class="banner-inner">
      <span class="banner-icon">
        <svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor">
          <path d="M8 1a7 7 0 1 0 0 14A7 7 0 0 0 8 1zM7 5h2v1H7V5zm0 2h2v4H7V7z"/>
        </svg>
      </span>
      <span class="banner-text">{{ banner.content }}</span>
      <button class="banner-close" @click="handleClose" :title="t('common.close')">
        <svg viewBox="0 0 16 16" width="12" height="12" fill="currentColor">
          <path d="M4.646 4.646a.5.5 0 0 1 .708 0L8 7.293l2.646-2.647a.5.5 0 0 1 .708.708L8.707 8l2.647 2.646a.5.5 0 0 1-.708.708L8 8.707l-2.646 2.647a.5.5 0 0 1-.708-.708L7.293 8 4.646 5.354a.5.5 0 0 1 0-.708z"/>
        </svg>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { rbacApi, type BannerConfig } from '@/api/rbac'

const { t } = useI18n()

const DISMISSED_KEY = 'banner_dismissed_id'

function getBannerId(): string {
  return `${banner.value.content}||${banner.value.start_date}||${banner.value.end_date}`
}

const banner = ref<BannerConfig>({
  enabled: false,
  content: '',
  start_date: '',
  end_date: '',
})
const showBanner = ref(false)

function isWithinDateRange(): boolean {
  const now = Date.now()
  if (banner.value.start_date) {
    const start = new Date(banner.value.start_date).getTime()
    if (now < start) return false
  }
  if (banner.value.end_date) {
    const end = new Date(banner.value.end_date).getTime()
    if (now > end) return false
  }
  return true
}

function evaluateBanner() {
  const dismissedId = localStorage.getItem(DISMISSED_KEY)
  const currentId = getBannerId()
  showBanner.value =
    banner.value.enabled &&
    dismissedId !== currentId &&
    banner.value.content.length > 0 &&
    isWithinDateRange()
}

function handleClose() {
  localStorage.setItem(DISMISSED_KEY, getBannerId())
  showBanner.value = false
}

onMounted(async () => {
  try {
    const config = await rbacApi.getBanner()
    banner.value = config
    evaluateBanner()
  } catch {
    // Silently fail — banner simply won't show
  }
})
</script>

<style scoped>
.reviews-banner {
  position: sticky;
  top: 0;
  z-index: 10;
  flex-shrink: 0;
  height: 28px;
  background: linear-gradient(135deg, var(--el-color-primary), #6366f1);
  color: #fff;
  font-size: 13px;
  line-height: 28px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.18);
  border-bottom: 1px solid rgba(255, 255, 255, 0.15);
  padding: 0 20px;
}

/* Dark theme adjustment for the gradient */
[data-theme="dark"] .reviews-banner {
  background: linear-gradient(135deg, #4f46e5, #6366f1);
  box-shadow: 0 2px 12px rgba(79, 70, 229, 0.35);
  border-bottom-color: rgba(255, 255, 255, 0.08);
}

.banner-inner {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 100%;
}

.banner-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  opacity: 0.9;
}

.banner-text {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-weight: 500;
  letter-spacing: 0.02em;
}

.banner-close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border: none;
  background: rgba(255, 255, 255, 0.15);
  color: inherit;
  border-radius: 4px;
  cursor: pointer;
  flex-shrink: 0;
  transition: background 0.2s;
  padding: 0;
}

.banner-close:hover {
  background: rgba(255, 255, 255, 0.3);
}
</style>
