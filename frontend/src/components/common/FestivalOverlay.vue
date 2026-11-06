<template>
  <div>
    <transition name="festival-fade">
      <canvas v-if="playing" ref="canvasRef" class="festival-overlay" aria-hidden="true" />
    </transition>
    <transition name="festival-greeting">
      <div
        v-if="playing && greeting"
        class="festival-greeting"
        :class="`festival-greeting--${greetingEffect}`"
        aria-hidden="true"
      >
        <span class="festival-greeting-deco">{{ decoEmoji }}</span>
        <span class="festival-greeting-text">{{ greeting }}</span>
        <span class="festival-greeting-deco">{{ decoEmoji }}</span>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { rbacApi } from '@/api/rbac'
import type { FestivalConfig, FestivalEffect } from '@/api/rbac'
import { useTheme } from '@/composables/useTheme'

const { t } = useI18n()
const canvasRef = ref<HTMLCanvasElement | null>(null)
const playing = ref(false)
const greeting = ref('')
const greetingEffect = ref<FestivalEffect>('christmas')

/** The emoji that frames the greeting, per festival. */
const DECO_EMOJI: Record<FestivalEffect, string> = {
  christmas: '❄️',
  spring_festival: '🏮',
  mid_autumn: '🌕',
  new_year: '🎊',
  custom: '✨',
}
const decoEmoji = computed(() => DECO_EMOJI[greetingEffect.value])

/** Every festival pops its own greeting; the custom effect uses the admin's text. */
const DEFAULT_GREETINGS: Record<FestivalEffect, string> = {
  christmas: 'festival.greeting_christmas',
  spring_festival: 'festival.greeting_spring_festival',
  mid_autumn: 'festival.greeting_mid_autumn',
  new_year: 'festival.greeting_new_year',
  custom: '',
}

const { isDark } = useTheme()

const DEFAULT_DURATION_SECONDS = 15
const DEFAULT_SPEED = 1.0
const SESSION_KEY = 'festival_overlay_played'
const FESTIVAL_PREVIEW_EVENT = 'festival-preview'
const GREETING_MS = 6000

interface Particle {
  kind: 'flake' | 'emoji' | 'confetti' | 'petal'
  x: number
  y: number
  size: number
  speed: number
  sway: number
  swaySpeed: number
  phase: number
  opacity: number
  color: string
  rotation: number
  rotationSpeed: number
}

let particles: Particle[] = []
let rafId = 0
let stopTimer: ReturnType<typeof setTimeout> | null = null
let greetingTimer: ReturnType<typeof setTimeout> | null = null
let resizeHandler: (() => void) | null = null
let speedMultiplier = DEFAULT_SPEED
let currentEffect: FestivalEffect = 'christmas'
let currentConfig: FestivalConfig | null = null

const CONFETTI_DEFAULTS = ['#ef4444', '#f59e0b', '#3b82f6', '#10b981', '#e5e7eb']

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
    config.custom_name,
    config.custom_emoji,
    ...(config.custom_colors ?? []),
  ].join('|')
}

function baseParticle(kind: Particle['kind'], width: number, height: number): Particle {
  return {
    kind,
    x: Math.random() * width,
    y: Math.random() * height,
    size: 1,
    // Base velocities are gentle on purpose: a particle takes roughly ten
    // seconds to cross the screen at speed 1, and the admin's multiplier scales it.
    speed: (0.03 + Math.random() * 0.035) * speedMultiplier,
    sway: 12 + Math.random() * 24,
    swaySpeed: 0.001 + Math.random() * 0.002,
    phase: Math.random() * Math.PI * 2,
    opacity: 0.5 + Math.random() * 0.5,
    color: '#ffffff',
    rotation: Math.random() * Math.PI * 2,
    rotationSpeed: (Math.random() - 0.5) * 0.004,
  }
}

function buildParticles(width: number, height: number): Particle[] {
  const list: Particle[] = []
  const push = (count: number, build: (p: Particle) => void) => {
    for (let i = 0; i < count; i++) {
      const p = baseParticle('flake', width, height)
      build(p)
      list.push(p)
    }
  }

  if (currentEffect === 'christmas') {
    // Snow: white on the dark background, pale blue where it would vanish
    // against the light page.
    const color = isDark.value ? 'rgba(255, 255, 255, 0.85)' : 'rgba(148, 178, 215, 0.8)'
    push(140, (p) => {
      p.size = 1 + Math.random() * 2.6
      p.color = color
    })
  } else if (currentEffect === 'spring_festival') {
    push(10, (p) => {
      p.kind = 'emoji'
      p.color = '🏮'
      p.size = 24 + Math.random() * 20
      p.speed = 0.02 * speedMultiplier
      p.sway = 30 + Math.random() * 30
      p.opacity = 0.85
    })
    push(60, (p) => {
      p.size = 1.5 + Math.random() * 2.4
      p.color = Math.random() > 0.5 ? '#fbbf24' : '#fde68a'
    })
  } else if (currentEffect === 'mid_autumn') {
    push(90, (p) => {
      p.kind = 'petal'
      p.size = 3 + Math.random() * 4
      p.color = Math.random() > 0.4 ? '#fcd34d' : '#fef3c7'
      p.rotationSpeed = (Math.random() - 0.5) * 0.003
    })
  } else {
    // new_year and custom share the confetti read; custom adds emoji particles
    // in the shape the administrator picked.
    const colors =
      currentEffect === 'custom' && currentConfig?.custom_colors?.length
        ? currentConfig.custom_colors
        : CONFETTI_DEFAULTS
    push(120, (p) => {
      p.kind = 'confetti'
      p.size = 4 + Math.random() * 5
      p.color = colors[Math.floor(Math.random() * colors.length)]
    })
    if (currentEffect === 'custom') {
      const emoji = currentConfig?.custom_emoji || '🎉'
      push(30, (p) => {
        p.kind = 'emoji'
        p.size = 16 + Math.random() * 16
        p.speed = 0.025 * speedMultiplier
        p.opacity = 0.9
        p.color = emoji
      })
    }
  }
  return list
}

function drawParticle(ctx: CanvasRenderingContext2D, p: Particle): void {
  ctx.globalAlpha = p.opacity
  if (p.kind === 'emoji') {
    ctx.font = `${p.size}px "Segoe UI Emoji", "Apple Color Emoji", "Noto Color Emoji", serif`
    ctx.textBaseline = 'middle'
    ctx.fillText(p.color, p.x, p.y)
    return
  }
  if (p.kind === 'confetti' || p.kind === 'petal') {
    ctx.save()
    ctx.translate(p.x, p.y)
    ctx.rotate(p.rotation)
    ctx.fillStyle = p.color
    if (p.kind === 'confetti') {
      ctx.fillRect(-p.size / 2, -p.size / 4, p.size, p.size / 2)
    } else {
      ctx.beginPath()
      ctx.ellipse(0, 0, p.size, p.size * 0.55, 0, 0, Math.PI * 2)
      ctx.fill()
    }
    ctx.restore()
    return
  }
  ctx.fillStyle = p.color
  ctx.beginPath()
  ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2)
  ctx.fill()
}

/** A soft moon in the upper corner anchors the Mid-Autumn read. */
function drawMoon(ctx: CanvasRenderingContext2D, width: number): void {
  const cx = width * 0.86
  const cy = Math.min(width, 900) * 0.16
  const r = Math.max(48, Math.min(width, 900) * 0.07)
  const glow = ctx.createRadialGradient(cx, cy, r * 0.4, cx, cy, r * 2.4)
  glow.addColorStop(0, 'rgba(253, 244, 214, 0.35)')
  glow.addColorStop(1, 'rgba(253, 244, 214, 0)')
  ctx.globalAlpha = 1
  ctx.fillStyle = glow
  ctx.beginPath()
  ctx.arc(cx, cy, r * 2.4, 0, Math.PI * 2)
  ctx.fill()

  const body = ctx.createRadialGradient(cx - r * 0.3, cy - r * 0.3, r * 0.2, cx, cy, r)
  body.addColorStop(0, '#fffbeb')
  body.addColorStop(1, '#fde68a')
  ctx.fillStyle = body
  ctx.beginPath()
  ctx.arc(cx, cy, r, 0, Math.PI * 2)
  ctx.fill()
}

function start(durationMs: number): void {
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
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    particles = buildParticles(window.innerWidth, window.innerHeight)
  }
  resize()
  resizeHandler = resize
  window.addEventListener('resize', resize)

  let last = performance.now()
  const frame = (now: number) => {
    const dt = Math.min(now - last, 50)
    last = now
    const width = window.innerWidth
    const height = window.innerHeight
    ctx.clearRect(0, 0, width, height)
    if (currentEffect === 'mid_autumn') drawMoon(ctx, width)
    for (const p of particles) {
      p.phase += p.swaySpeed * dt
      p.y += p.speed * dt
      p.x += Math.sin(p.phase) * (p.sway / 1000) * dt
      p.rotation += p.rotationSpeed * dt
      if (p.y > height + p.size * 2) {
        p.y = -p.size * 2
        p.x = Math.random() * width
      }
      drawParticle(ctx, p)
    }
    ctx.globalAlpha = 1
    rafId = requestAnimationFrame(frame)
  }
  rafId = requestAnimationFrame(frame)

  stopTimer = setTimeout(stop, durationMs)
}

function play(config: FestivalConfig): void {
  cleanup()
  currentEffect = config.effect
  currentConfig = config
  greetingEffect.value = config.effect
  const durationSeconds = clamp(config.duration_seconds, 5, 120, DEFAULT_DURATION_SECONDS)
  speedMultiplier = clamp(config.speed, 0.2, 3, DEFAULT_SPEED)
  const greetingText =
    config.effect === 'custom' ? config.custom_name : t(DEFAULT_GREETINGS[config.effect])
  if (greetingText) {
    greeting.value = greetingText
    greetingTimer = setTimeout(() => {
      greeting.value = ''
    }, Math.min(GREETING_MS, durationSeconds * 1000))
  }
  playing.value = true
  // The canvas mounts with the v-if before the paint, so the first frame is ready.
  requestAnimationFrame(() => start(durationSeconds * 1000))
}

function stop(): void {
  playing.value = false
  greeting.value = ''
  cleanup()
}

function cleanup(): void {
  if (rafId) cancelAnimationFrame(rafId)
  rafId = 0
  if (stopTimer) clearTimeout(stopTimer)
  stopTimer = null
  if (greetingTimer) clearTimeout(greetingTimer)
  greetingTimer = null
  if (resizeHandler) window.removeEventListener('resize', resizeHandler)
  resizeHandler = null
  particles = []
  currentConfig = null
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
  if (!config?.enabled || !withinWindow(config)) return

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

.festival-greeting {
  position: fixed;
  top: 48px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 10000;
  pointer-events: none;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 32px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.35);
  background-size: 200% 200%;
  animation: festival-greeting-shift 6s ease-in-out infinite,
    festival-greeting-float 3s ease-in-out infinite;
  color: #fff;
  font-size: 20px;
  font-weight: 600;
  letter-spacing: 2px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
}

.festival-greeting-deco {
  font-size: 22px;
  animation: festival-greeting-spin 4s ease-in-out infinite;
}

.festival-greeting-text {
  text-shadow: 0 1px 6px rgba(0, 0, 0, 0.35);
}

@keyframes festival-greeting-shift {
  0%,
  100% {
    background-position: 0% 50%;
  }
  50% {
    background-position: 100% 50%;
  }
}

@keyframes festival-greeting-float {
  0%,
  100% {
    transform: translateX(-50%) translateY(0);
  }
  50% {
    transform: translateX(-50%) translateY(-5px);
  }
}

@keyframes festival-greeting-spin {
  0%,
  100% {
    transform: rotate(-12deg) scale(1);
  }
  50% {
    transform: rotate(12deg) scale(1.15);
  }
}

/* One palette per festival, matching the particles that fall behind it. */
.festival-greeting--christmas {
  background-image: linear-gradient(120deg, #b91c1c, #166534, #14532d);
}

.festival-greeting--spring_festival {
  background-image: linear-gradient(120deg, #dc2626, #ea580c, #b45309);
  border-color: #fbbf24;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25), 0 0 18px rgba(251, 191, 36, 0.45);
}

.festival-greeting--spring_festival .festival-greeting-text {
  text-shadow: 0 0 10px rgba(253, 230, 138, 0.9), 0 1px 4px rgba(0, 0, 0, 0.4);
}

.festival-greeting--mid_autumn {
  background-image: linear-gradient(120deg, #1e3a8a, #3730a3, #4338ca);
  border-color: rgba(253, 230, 138, 0.6);
  color: #fef3c7;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25), 0 0 18px rgba(253, 230, 138, 0.35);
}

.festival-greeting--new_year {
  background-image: linear-gradient(120deg, #7c3aed, #db2777, #e11d48);
}

.festival-greeting--custom {
  background-image: linear-gradient(120deg, #dc2626, #ef4444, #f59e0b);
}

.festival-fade-enter-active,
.festival-fade-leave-active {
  transition: opacity 1.2s ease;
}

.festival-fade-enter-from,
.festival-fade-leave-to {
  opacity: 0;
}

.festival-greeting-enter-active {
  transition: opacity 0.8s ease, transform 0.8s ease;
}

.festival-greeting-leave-active {
  transition: opacity 1s ease;
}

.festival-greeting-enter-from {
  opacity: 0;
  transform: translateX(-50%) translateY(-16px);
}

.festival-greeting-leave-to {
  opacity: 0;
}
</style>
