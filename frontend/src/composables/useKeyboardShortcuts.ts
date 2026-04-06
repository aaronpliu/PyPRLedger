import { onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

interface ShortcutConfig {
  key: string
  ctrl?: boolean
  shift?: boolean
  alt?: boolean
  handler: () => void
  description: string
}

/**
 * Composable for keyboard shortcuts
 */
export function useKeyboardShortcuts() {
  const router = useRouter()

  const shortcuts: ShortcutConfig[] = [
    {
      key: 'g',
      handler: () => {
        router.push('/')
        ElMessage.success('Navigated to Dashboard')
      },
      description: 'Go to Dashboard',
    },
    {
      key: 'r',
      handler: () => {
        router.push('/reviews')
        ElMessage.success('Navigated to Reviews')
      },
      description: 'Go to Reviews',
    },
    {
      key: 's',
      handler: () => {
        router.push('/scores')
        ElMessage.success('Navigated to Scores')
      },
      description: 'Go to Scores',
    },
    {
      key: '/',
      handler: () => {
        // Focus search input
        const searchInput = document.querySelector('input[placeholder*="Search"]') as HTMLInputElement
        if (searchInput) {
          searchInput.focus()
          ElMessage.success('Search focused')
        }
      },
      description: 'Focus Search',
    },
    {
      key: '?',
      shift: true,
      handler: () => {
        showShortcutsHelp()
      },
      description: 'Show Keyboard Shortcuts',
    },
    {
      key: 'Escape',
      handler: () => {
        // Close any open dialogs/dropdowns
        const activeElement = document.activeElement as HTMLElement
        if (activeElement) {
          activeElement.blur()
        }
      },
      description: 'Close Dialog/Focus',
    },
  ]

  const handleKeydown = (event: KeyboardEvent) => {
    // Ignore if typing in input/textarea
    const target = event.target as HTMLElement
    if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable) {
      return
    }

    const shortcut = shortcuts.find(s => {
      const keyMatch = event.key.toLowerCase() === s.key.toLowerCase()
      const ctrlMatch = s.ctrl ? event.ctrlKey || event.metaKey : !event.ctrlKey && !event.metaKey
      const shiftMatch = s.shift ? event.shiftKey : !event.shiftKey
      const altMatch = s.alt ? event.altKey : !event.altKey
      
      return keyMatch && ctrlMatch && shiftMatch && altMatch
    })

    if (shortcut) {
      event.preventDefault()
      shortcut.handler()
    }
  }

  const showShortcutsHelp = () => {
    const helpText = shortcuts.map(s => {
      const modifiers = []
      if (s.ctrl) modifiers.push('Ctrl')
      if (s.shift) modifiers.push('Shift')
      if (s.alt) modifiers.push('Alt')
      modifiers.push(s.key.toUpperCase())
      return `${modifiers.join('+')} - ${s.description}`
    }).join('\n')

    ElMessage({
      message: `Keyboard Shortcuts:\n\n${helpText}`,
      type: 'info',
      duration: 10000,
      showClose: true,
    })
  }

  onMounted(() => {
    window.addEventListener('keydown', handleKeydown)
  })

  onUnmounted(() => {
    window.removeEventListener('keydown', handleKeydown)
  })

  return {
    shortcuts,
    showShortcutsHelp,
  }
}
