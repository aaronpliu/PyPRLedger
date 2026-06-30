import { PageAgent } from 'page-agent'
import type { SupportedLanguage } from 'page-agent'
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { llmApi } from '@/api/llm'

export function usePageAgent() {
  const { locale } = useI18n()
  const agent = ref<PageAgent | null>(null)
  const initialized = ref(false)
  const initializing = ref(false)
  const visible = ref(false)

  // Re-init with new language when user switches locale
  watch(locale, async () => {
    if (initialized.value) {
      const wasVisible = visible.value
      destroy()
      await init()
      if (wasVisible) {
        show()
      }
    }
  })

  // Watch for admin config changes — immediately show/hide the launcher
  window.addEventListener('pageagent-config-changed', () => {
    refresh()
  })

  async function init() {
    // Guard against re-init and concurrent init calls
    if (initialized.value || initializing.value) return
    initializing.value = true

    try {
      // Fetch LLM config from backend (no apiKey exposed to frontend)
      const config = await llmApi.getConfig()
      if (!config.enabled) return

      // Initialize PageAgent with backend proxy baseURL
      // Panel stays hidden — launcher icon controls visibility
      agent.value = new PageAgent({
        model: config.model,
        baseURL: '/api/v1/llm/proxy', // Backend proxy handles auth
        apiKey: 'proxy',               // Dummy key, backend adds real key
        language: getSupportedLanguage(),
      })

      const wrapper = agent.value.panel.wrapper

      // Position as a floating dialog (remove default centering transform)
      wrapper.style.left = 'auto'
      wrapper.style.right = '20px'
      wrapper.style.top = 'unset'
      wrapper.style.bottom = '80px'
      wrapper.style.transform = 'none'

      // Prevent wrapper-level transition from animating our position
      wrapper.style.transition = 'none'

      // Enlarge the task input for better usability
      const taskInput = wrapper.querySelector('input') as HTMLElement | null
      if (taskInput) {
        taskInput.style.height = '36px'
        taskInput.style.fontSize = '14px'
        taskInput.style.paddingInline = '12px'
      }

      // Override the built-in X button: hide instead of dispose
      overrideCloseButton(wrapper)

      // Make the whole wrapper draggable (not just the header)
      enableDrag(wrapper)

      // Listen for status changes — library calls panel.show() on 'running'
      // which sets transform: translateX(-50%), so we revert it
      agent.value.addEventListener('statuschange', () => {
        const w = agent.value?.panel.wrapper
        if (w) {
          w.style.transform = 'none'
        }
      })

      // Reset state when agent is externally disposed
      agent.value.addEventListener('dispose', () => {
        initialized.value = false
        visible.value = false
        agent.value = null
      })

      initialized.value = true
    } finally {
      initializing.value = false
    }
    // Panel stays hidden — user clicks launcher to open
  }

  function overrideCloseButton(wrapper: HTMLElement) {
    const actionButton = wrapper.querySelector('[class*="stopButton"]') as HTMLElement | null
    if (!actionButton) return
    // Clone to remove all existing event listeners (built-in dispose handler)
    const newButton = actionButton.cloneNode(true) as HTMLElement
    actionButton.parentNode?.replaceChild(newButton, actionButton)
    newButton.addEventListener('click', (e) => {
      e.stopPropagation()
      // Stop the agent if running, then just hide
      if (agent.value && agent.value.status === 'running') {
        agent.value.stop()
      }
      hide()
    })
  }

  function enableDrag(wrapper: HTMLElement) {
    let isDragging = false
    let hasMoved = false
    let startX = 0
    let startY = 0
    let origLeft = 0
    let origTop = 0

    function startDrag(clientX: number, clientY: number) {
      isDragging = true
      hasMoved = false
      startX = clientX
      startY = clientY

      const rect = wrapper.getBoundingClientRect()
      origLeft = rect.left
      origTop = rect.top

      wrapper.style.cursor = 'grabbing'
    }

    function moveDrag(clientX: number, clientY: number) {
      if (!isDragging) return
      const dx = clientX - startX
      const dy = clientY - startY

      // Only switch to absolute positioning after meaningful movement (threshold 5px)
      // This prevents position shift on simple clicks (expand/collapse)
      if (!hasMoved && (Math.abs(dx) > 5 || Math.abs(dy) > 5)) {
        hasMoved = true
        wrapper.style.left = `${origLeft}px`
        wrapper.style.top = `${origTop}px`
        wrapper.style.right = 'unset'
        wrapper.style.bottom = 'unset'
      }

      if (hasMoved) {
        wrapper.style.left = `${origLeft + dx}px`
        wrapper.style.top = `${origTop + dy}px`
      }
    }

    function endDrag() {
      if (!isDragging) return
      isDragging = false
      wrapper.style.cursor = ''
      document.removeEventListener('mousemove', onMouseMove)
      document.removeEventListener('mouseup', onMouseUp)
      document.removeEventListener('touchmove', onTouchMove)
      document.removeEventListener('touchend', onTouchEnd)
    }

    function onMouseDown(this: HTMLElement, e: MouseEvent) {
      const target = e.target as HTMLElement
      if (target.tagName === 'BUTTON' || target.tagName === 'INPUT') return
      e.preventDefault()
      startDrag(e.clientX, e.clientY)
      document.addEventListener('mousemove', onMouseMove)
      document.addEventListener('mouseup', onMouseUp)
    }

    function onMouseMove(e: MouseEvent) {
      moveDrag(e.clientX, e.clientY)
    }

    function onMouseUp() {
      endDrag()
    }

    function onTouchStart(e: TouchEvent) {
      const target = e.target as HTMLElement
      if (target.tagName === 'BUTTON' || target.tagName === 'INPUT') return
      const touch = e.touches[0]
      if (!touch) return
      startDrag(touch.clientX, touch.clientY)
      document.addEventListener('touchmove', onTouchMove, { passive: false })
      document.addEventListener('touchend', onTouchEnd)
    }

    function onTouchMove(e: TouchEvent) {
      e.preventDefault()
      const touch = e.touches[0]
      if (!touch) return
      moveDrag(touch.clientX, touch.clientY)
    }

    function onTouchEnd() {
      endDrag()
    }

    wrapper.addEventListener('mousedown', onMouseDown)
    wrapper.addEventListener('touchstart', onTouchStart, { passive: false })
  }

  /** Show the panel — re-check config first in case admin toggled it */
  async function show() {
    await refresh()
    if (!agent.value) return
    const wrapper = agent.value.panel.wrapper
    agent.value.panel.show()
    // Re-apply positioning — panel.show() sets transform: translateX(-50%)
    wrapper.style.transform = 'none'
    visible.value = true
  }

  /** Hide the panel without destroying the agent */
  function hide() {
    if (!agent.value) return
    const wrapper = agent.value.panel.wrapper
    agent.value.panel.hide()
    // Re-apply positioning — panel.hide() sets transform: translateX(-50%)
    wrapper.style.transform = 'none'
    visible.value = false
  }

  /** Toggle panel visibility — re-check config first */
  async function toggle() {
    await refresh()
    if (visible.value) {
      hide()
    } else if (agent.value) {
      await show()
    } else {
      await init()
    }
  }

  /** Dispose agent and clean up */
  function destroy() {
    agent.value?.dispose()
    initialized.value = false
    visible.value = false
    agent.value = null
  }

  /** Re-check LLM config and sync agent state (enabled ↔ disabled) */
  async function refresh() {
    try {
      const config = await llmApi.getConfig()
      if (!config.enabled && initialized.value) {
        destroy()
      } else if (config.enabled && !initialized.value) {
        await init()
      }
    } catch {
      // Silently fail — next interaction will retry
    }
  }

  return { agent, initialized, visible, init, refresh, show, hide, toggle, destroy }
}

/** Map app locale to PageAgent-supported language */
function getSupportedLanguage(): SupportedLanguage {
  const lang = localStorage.getItem('language') || 'en'
  if (lang === 'zh-CN' || lang === 'zh-TW') return 'zh-CN'
  return 'en-US'
}
