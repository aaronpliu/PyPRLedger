import { ref } from 'vue'

/**
 * One search dialog, whoever asks for it: the toolbar button, Ctrl+K, or the "/"
 * shortcut. Module-level state so asking costs nothing more than a function call.
 */
const isOpen = ref(false)

export function useGlobalSearch() {
  const open = () => {
    isOpen.value = true
  }

  const close = () => {
    isOpen.value = false
  }

  return { isOpen, open, close }
}
