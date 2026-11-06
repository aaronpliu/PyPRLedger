<template>
  <transition name="festival-fade">
    <canvas v-if="playing" ref="canvasRef" class="festival-overlay" aria-hidden="true" />
  </transition>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { rbacApi } from '@/api/rbac'
import type { FestivalConfig } from '@/api/rbac'
import { useTheme } from '@/composables/useTheme'

const canvasRef = ref<HTMLCanvasElement | null>(null)
const playing = ref(false)

const { isDark } = useTheme()

const DEFAULT_DURATION_SECONDS = 15
const DEFAULT_SPEED = 1.0
const SESSION_KEY = 'festival_overlay_played'
const FESTIVAL_PREVIEW_EVENT = 'festival-preview'
const FLAKE_COUNT = 140

interface Flake {
  x: number
  y: number
  r: number
  speed: number
  sway: number
  swaySpeed: number
  phase: number
  opacity: number
}

let flakes: Flake[] = []
let rafId = 0
let stopTimer: ReturnType<typeof setTimeout> | null = null
let resizeHandler: (() => void) | null = null
let speedMultiplier = DEFAULT_SPEED

function todayIso(): string {
  const now = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}

/** Within the admin window; an empty bound means "no bound". */
function withinWindow(config: FestivalConfig): boolean {
  const today = todayIso()
  if (config.start_date && today < config.start_date) return false
  if (config.end_date && today > config.end_date) return false
  return true
}

function clamp(value: number | undefined, low: number, high: number, fallback: number): number {
  if (typeof value !== 'number' || Number.isNaN(value)) return fallback
  return Math.max(low, Math.min(high, value))
}

/** What defines one play: a changed config reads as a play the visitor has not seen. */
function fingerprint(config: FestivalConfig): string {
  return [
    config.effect,
    config.start_date,
    config.end_date,
    config.duration_seconds,
    config.speed,
  ].join('|')
}

function play(config: FestivalConfig): void {
  cleanup()
  const durationSeconds = clamp(config.duration_seconds, 5, 120, DEFAULT_DURATION_SECONDS)
  speedMultiplier = clamp(config.speed, 0.2, 3, DEFAULT_SPEED)
  playing.value = true
  // The canvas mounts with the v-if before the paint, so the first frame is ready.
  requestAnimationFrame(() => startSnow(durationSeconds * 1000))
}

function spawnFlakes(width: number, height: number): Flake[] {
  // Base velocities are gentle on purpose: a flake takes roughly ten seconds
  // to cross the screen at speed 1, and the admin's multiplier scales it.
  return Array.from({ length: FLAKE_COUNT }, () => ({
    x: Math.random() * width,
    y: Math.random() * height,
    r: 1 + Math.random() * 2.6,
    speed: (0.03 + Math.random() * 0.035) * speedMultiplier,
    sway: 12 + Math.random() * 24,
    swaySpeed: 0.001 + Math.random() * 0.002,
    phase: Math.random() * Math.PI * 2,
    opacity: 0.5 + Math.random() * 0.5,
  }))
}

function startSnow(durationMs: number): void {
  const canvas = canvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  const resize = () => {
    canvas.width = window.innerWidth * dpr
    canvas.height = window.innerHeight * dpr
    canvas.style.width = `${window.innerWidth}px`
    canvas.style.height = `${window.innerHeight}px`
    flakes = spawnFlakes(canvas.width, canvas.height)
  }
  resize()
  resizeHandler = resize
  window.addEventListener('resize', resize)

  let last = performance.now()
  const draw = (now: number) => {
    const dt = Math.min(now - last, 50)
    last = now
    const { width, height } = canvas
    ctx.clearRect(0, 0, width, height)
    // White reads on the dark background; on the light one the flakes go
    // pale blue so they do not vanish against the page.
    ctx.fillStyle = isDark.value ? 'rgba(255, 255, 255, 0.85)' : 'rgba(148, 178, 215, 0.8)'
    for (const flake of flakes) {
      flake.phase += flake.swaySpeed * dt
      flake.y += flake.speed * dt
      flake.x += Math.sin(flake.phase) * (flake.sway / 1000) * dt
      if (flake.y > height + flake.r * 2) {
        flake.y = -flake.r * 2
        flake.x = Math.random() * width
      }
      ctx.globalAlpha = flake.opacity
      ctx.beginPath()
      ctx.arc(flake.x, flake.y, flake.r * dpr, 0, Math.PI * 2)
      ctx.fill()
    }
    ctx.globalAlpha = 1
    rafId = requestAnimationFrame(draw)
  }
  rafId = requestAnimationFrame(draw)

  stopTimer = setTimeout(stop, durationMs)
}

function stop(): void {
  playing.value = false
  cleanup()
}

function cleanup(): void {
  if (rafId) cancelAnimationFrame(rafId)
  rafId = 0
  if (stopTimer) clearTimeout(stopTimer)
  stopTimer = null
  if (resizeHandler) window.removeEventListener('resize', resizeHandler)
  resizeHandler = null
  flakes = []
}

onMounted(async () => {
  // The settings card previews through this event, bypassing the session mark.
  const onPreview = (event: Event) => {
    const detail = (event as CustomEvent).detail as FestivalConfig | undefined
    if (detail) play(detail)
  }
  window.addEventListener(FESTIVAL_PREVIEW_EVENT, onPreview)
  onBeforeUnmount(() => window.removeEventListener(FESTIVAL_PREVIEW_EVENT, onPreview))

  // One play per browser session per config: reopening a tab replays it,
  // navigating does not, and a changed config plays again.
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return

  let config: FestivalConfig | null = null
  try {
    config = (await rbacApi.getFestivalAnimation()).festival
  } catch {
    return
  }
  if (!config?.enabled || config.effect !== 'christmas' || !withinWindow(config)) return

  const mark = `${todayIso()}|${fingerprint(config)}`
  if (sessionStorage.getItem(SESSION_KEY) === mark) return
  sessionStorage.setItem(SESSION_KEY, mark)
  play(config)
})

onBeforeUnmount(cleanup)
</script>

<style scoped>
.festival-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  pointer-events: none;
}

.festival-fade-enter-active,
.festival-fade-leave-active {
  transition: opacity 1.2s ease;
}

.festival-fade-enter-from,
.festival-fade-leave-to {
  opacity: 0;
}
</style>
