<template>
  <!-- Several banners can be within their window at once, so they take turns in
       the bar rather than stacking and pushing the page down. -->
  <div
    v-if="currentBanner"
    class="reviews-banner"
    :class="`reviews-banner--${currentBanner.level}`"
    @mouseenter="interacting = true"
    @mouseleave="interacting = false"
    @focusin="interacting = true"
    @focusout="interacting = false"
  >
    <div class="banner-inner">
      <span class="banner-icon">
        <svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor">
          <path d="M8 1a7 7 0 1 0 0 14A7 7 0 0 0 8 1zM7 5h2v1H7V5zm0 2h2v4H7V7z"/>
        </svg>
      </span>

      <!-- Keyed per banner, so the entrance animation replays on each turn -->
      <div :key="dismissalKey(currentBanner)" class="banner-content">
        <span class="banner-text">{{ currentBanner.content }}</span>
        <!-- A site-relative link is a route, so it navigates instead of reloading -->
        <router-link
          v-if="currentBanner.link_url && isInternalLink(currentBanner.link_url)"
          class="banner-link"
          :to="currentBanner.link_url"
        >
          {{ linkLabel(currentBanner) }}
        </router-link>
        <a
          v-else-if="currentBanner.link_url"
          class="banner-link"
          :href="currentBanner.link_url"
          target="_blank"
          rel="noopener noreferrer"
        >
          {{ linkLabel(currentBanner) }}
        </a>
      </div>

      <!-- Which banner is on show, and a way to pick one -->
      <div v-if="visibleBanners.length > 1" class="banner-dots">
        <button
          v-for="(banner, index) in visibleBanners"
          :key="dismissalKey(banner)"
          type="button"
          class="banner-dot"
          :class="{ 'is-active': index === currentIndex }"
          :title="banner.content"
          :aria-label="banner.content"
          :aria-current="index === currentIndex"
          data-test="banner-dot"
          @click="showBanner(index)"
        ></button>
      </div>

      <button class="banner-close" @click="dismiss(currentBanner)" :title="t('common.close')">
        <svg viewBox="0 0 16 16" width="12" height="12" fill="currentColor">
          <path d="M4.646 4.646a.5.5 0 0 1 .708 0L8 7.293l2.646-2.647a.5.5 0 0 1 .708.708L8.707 8l2.647 2.646a.5.5 0 0 1-.708.708L8 8.707l-2.646 2.647a.5.5 0 0 1-.708-.708L7.293 8 4.646 5.354a.5.5 0 0 1 0-.708z"/>
        </svg>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { rbacApi, type BannerItem } from '@/api/rbac'

const { t } = useI18n()

const DISMISSED_KEY = 'banner_dismissed_ids'
// The slot this used to be, from when there was only ever one banner.
const LEGACY_DISMISSED_KEY = 'banner_dismissed_id'

/** How long each banner holds the bar before the next one takes its turn. */
const ROTATE_INTERVAL_MS = 6000

const banners = ref<BannerItem[]>([])
const dismissed = ref<Set<string>>(new Set())

/**
 * What identifies a banner for a dismissal.
 *
 * It includes the wording, so a banner that is edited reads as a new one and is
 * shown again, while re-saving it unchanged keeps it dismissed.
 */
function dismissalKey(banner: BannerItem): string {
  return [banner.id, banner.content, banner.start_date, banner.end_date].join('||')
}

function readDismissed(): Set<string> {
  try {
    const raw = localStorage.getItem(DISMISSED_KEY)
    const parsed = raw ? JSON.parse(raw) : []
    return new Set(
      Array.isArray(parsed) ? parsed.filter((entry): entry is string => typeof entry === 'string') : [],
    )
  } catch {
    // Unreadable storage just means nothing has been dismissed.
    return new Set()
  }
}

/** Drop the keys of banners that no longer exist, so the list cannot grow forever. */
function pruneDismissed(keys: Set<string>): string[] {
  const live = new Set(banners.value.map((banner) => dismissalKey(banner)))
  return [...keys].filter((key) => live.has(key))
}

function isWithinWindow(banner: BannerItem): boolean {
  const now = Date.now()
  if (banner.start_date && now < new Date(banner.start_date).getTime()) return false
  if (banner.end_date && now > new Date(banner.end_date).getTime()) return false
  return true
}

/** Highest priority first; equal priorities keep the order the server returned. */
const visibleBanners = computed(() =>
  banners.value
    .filter(
      (banner) =>
        banner.enabled &&
        banner.content.trim().length > 0 &&
        isWithinWindow(banner) &&
        !dismissed.value.has(dismissalKey(banner)),
    )
    .sort((a, b) => b.priority - a.priority),
)

const currentIndex = ref(0)
const interacting = ref(false)
const pageHidden = ref(false)

let rotationTimer: ReturnType<typeof setInterval> | null = null

/** The banner on show: with several taking turns, only one is in the bar. */
const currentBanner = computed(() => visibleBanners.value[currentIndex.value] ?? null)

/** Nobody wants a banner to change under the pointer, or in a tab nobody is looking at. */
const isPaused = computed(() => interacting.value || pageHidden.value)

function stopRotation() {
  if (rotationTimer !== null) {
    clearInterval(rotationTimer)
    rotationTimer = null
  }
}

function startRotation() {
  stopRotation()
  if (visibleBanners.value.length < 2) {
    return
  }
  rotationTimer = setInterval(() => {
    if (isPaused.value) {
      return
    }
    currentIndex.value = (currentIndex.value + 1) % visibleBanners.value.length
  }, ROTATE_INTERVAL_MS)
}

function showBanner(index: number) {
  currentIndex.value = index
  // Picking one by hand earns it a full interval before the next takes over.
  startRotation()
}

function onVisibilityChange() {
  pageHidden.value = document.visibilityState === 'hidden'
}

// Dismissing one, or the list arriving, changes what there is to show: keep the
// position in range — the banner after the one that went is what slides in.
watch(
  () => visibleBanners.value.length,
  (length) => {
    currentIndex.value = Math.min(currentIndex.value, Math.max(length - 1, 0))
    startRotation()
  },
)

function isInternalLink(url: string): boolean {
  return url.startsWith('/')
}

function linkLabel(banner: BannerItem): string {
  return banner.link_label || t('common.more')
}

function dismiss(banner: BannerItem) {
  const next = new Set(dismissed.value)
  next.add(dismissalKey(banner))
  dismissed.value = next
  localStorage.setItem(DISMISSED_KEY, JSON.stringify(pruneDismissed(next)))
}

onMounted(async () => {
  localStorage.removeItem(LEGACY_DISMISSED_KEY)
  dismissed.value = readDismissed()
  document.addEventListener('visibilitychange', onVisibilityChange)
  try {
    const config = await rbacApi.getBanner()
    // The length watcher starts the rotation from here.
    banners.value = config.banners ?? []
    localStorage.setItem(DISMISSED_KEY, JSON.stringify(pruneDismissed(dismissed.value)))
  } catch {
    // Silently fail — banner simply won't show
  }
})

onUnmounted(() => {
  stopRotation()
  document.removeEventListener('visibilitychange', onVisibilityChange)
})
</script>

<style scoped>
/*
 * One row per banner: several can be within their window at the same time, so the
 * container stacks them. The level picks the colour; `info` keeps the accent the
 * banner has always used.
 */
.reviews-banner {
  --banner-accent: var(--el-color-primary);
  --banner-accent-dark: var(--el-color-primary-dark-2);
  flex-shrink: 0;
  height: 28px;
  background: linear-gradient(135deg, var(--banner-accent), var(--banner-accent-dark));
  color: #fff;
  font-size: 13px;
  line-height: 28px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.18);
  border-bottom: 1px solid rgba(255, 255, 255, 0.15);
  padding: 0 20px;
}

.reviews-banner--warning {
  --banner-accent: var(--el-color-warning);
  --banner-accent-dark: var(--el-color-warning-dark-2);
}

.reviews-banner--success {
  --banner-accent: var(--el-color-success);
  --banner-accent-dark: var(--el-color-success-dark-2);
}

/* Dark theme adjustment — the gradient is the level colour in both modes */
[data-theme="dark"] .reviews-banner {
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.35);
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

.banner-content {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
  /* The element is keyed per banner, so this replays on every turn. */
  animation: banner-swap 0.28s ease;
}

@keyframes banner-swap {
  from {
    opacity: 0;
    transform: translateY(4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (prefers-reduced-motion: reduce) {
  .banner-content {
    animation: none;
  }
}

.banner-text {
  flex: 1;
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-weight: 500;
  letter-spacing: 0.02em;
}

.banner-dots {
  display: flex;
  align-items: center;
  gap: 5px;
  flex-shrink: 0;
}

.banner-dot {
  width: 6px;
  height: 6px;
  padding: 0;
  border: none;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.45);
  cursor: pointer;
  transition: background 0.2s, transform 0.2s;
}

.banner-dot:hover {
  background: rgba(255, 255, 255, 0.75);
}

.banner-dot.is-active {
  background: #fff;
  transform: scale(1.25);
}

.banner-link {
  flex-shrink: 0;
  color: inherit;
  font-weight: 600;
  text-decoration: underline;
  text-underline-offset: 2px;
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
