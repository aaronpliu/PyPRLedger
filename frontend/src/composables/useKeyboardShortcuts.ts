import { onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { useGlobalSearch } from '@/composables/useGlobalSearch'

interface ShortcutConfig {
  key: string
  ctrl?: boolean
  shift?: boolean
  alt?: boolean
  handler: () => void
  descriptionKey: string
}

/**
 * Composable for keyboard shortcuts
 */
export function useKeyboardShortcuts() {
  const router = useRouter()
  const { t } = useI18n()
  const { open: openGlobalSearch } = useGlobalSearch()

  const shortcuts: ShortcutConfig[] = [
    {
      key: 'g',
      handler: () => {
        router.push('/')
      },
      descriptionKey: 'shortcuts.go_dashboard',
    },
    {
      key: 'r',
      handler: () => {
        router.push('/reviews')
      },
      descriptionKey: 'shortcuts.go_reviews',
    },
    {
      key: 's',
      handler: () => {
        router.push('/scores')
      },
      descriptionKey: 'shortcuts.go_scores',
    },
    {
      key: '/',
      handler: () => {
        openGlobalSearch()
      },
      descriptionKey: 'shortcuts.open_search',
    },
    {
      key: '?',
      shift: true,
      handler: () => {
        showShortcutsHelp()
      },
      descriptionKey: 'shortcuts.show_help',
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
      descriptionKey: 'shortcuts.close_dialog',
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
      return `${modifiers.join('+')} - ${t(s.descriptionKey)}`
    }).join('\n')

    ElMessage({
      message: `${t('shortcuts.title')}\n\n${helpText}`,
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
