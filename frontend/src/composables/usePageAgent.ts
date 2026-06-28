import { PageAgent } from 'page-agent'
import type { SupportedLanguage } from 'page-agent'
import { ref } from 'vue'
import { llmApi } from '@/api/llm'

export function usePageAgent() {
  const agent = ref<PageAgent | null>(null)
  const initialized = ref(false)
  const visible = ref(false)

  async function init() {
    // Don't re-initialize if already active
    if (initialized.value) return

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
    // Explicit 'auto' overrides the CSS class 'left: 50%'
    wrapper.style.left = 'auto'
    wrapper.style.right = '20px'
    wrapper.style.top = 'unset'
    wrapper.style.bottom = '80px'
    wrapper.style.transform = 'none'

    // Override the built-in X button: hide instead of dispose
    overrideCloseButton(wrapper)

    // Make the panel draggable via its header
    enableDrag(wrapper)

    // Reset state when agent is externally disposed
    agent.value.addEventListener('dispose', () => {
      initialized.value = false
      visible.value = false
      agent.value = null
    })

    initialized.value = true
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
    const headerEl = wrapper.querySelector('[class*="header"]') as HTMLElement | null
    if (!headerEl) return
    const header: HTMLElement = headerEl

    let isDragging = false
    let startX = 0
    let startY = 0
    let origLeft = 0
    let origTop = 0

    function onMouseDown(this: HTMLElement, e: MouseEvent) {
      // Don't start drag if clicking on a button or input
      const target = e.target as HTMLElement
      if (target.tagName === 'BUTTON' || target.tagName === 'INPUT') return

      isDragging = true
      startX = e.clientX
      startY = e.clientY

      // Get current position (fixed positioning)
      const rect = wrapper.getBoundingClientRect()
      origLeft = rect.left
      origTop = rect.top

      // Switch to left/top positioning for drag
      wrapper.style.left = `${rect.left}px`
      wrapper.style.top = `${rect.top}px`
      wrapper.style.right = 'unset'
      wrapper.style.bottom = 'unset'

      this.style.cursor = 'grabbing'
      document.addEventListener('mousemove', onMouseMove)
      document.addEventListener('mouseup', onMouseUp)
    }

    function onMouseMove(e: MouseEvent) {
      if (!isDragging) return
      const dx = e.clientX - startX
      const dy = e.clientY - startY
      wrapper.style.left = `${origLeft + dx}px`
      wrapper.style.top = `${origTop + dy}px`
    }

    function onMouseUp() {
      isDragging = false
      header.style.cursor = ''
      document.removeEventListener('mousemove', onMouseMove)
      document.removeEventListener('mouseup', onMouseUp)
    }

    header.addEventListener('mousedown', onMouseDown)
  }

  /** Show the panel without re-creating the agent */
  function show() {
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

  /** Toggle panel visibility */
  function toggle() {
    if (visible.value) {
      hide()
    } else if (agent.value) {
      show()
    } else {
      init()
    }
  }

  /** Dispose agent and clean up */
  function destroy() {
    agent.value?.dispose()
    initialized.value = false
    visible.value = false
    agent.value = null
  }

  return { agent, initialized, visible, init, show, hide, toggle, destroy }
}

/** Map app locale to PageAgent-supported language */
function getSupportedLanguage(): SupportedLanguage {
  const lang = localStorage.getItem('language') || 'en'
  if (lang === 'zh-CN' || lang === 'zh-TW') return 'zh-CN'
  return 'en-US'
}
