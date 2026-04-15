import { ref, watch } from 'vue'

const currentTheme = ref<'light' | 'dark' | 'auto'>('auto')

// Initialize theme on module load
const initTheme = () => {
  const savedTheme = localStorage.getItem('theme') as 'light' | 'dark' | 'auto'
  if (savedTheme) {
    currentTheme.value = savedTheme
  }
  applyTheme(currentTheme.value)
}

// Watch for theme changes and apply them
watch(currentTheme, (newTheme) => {
  applyTheme(newTheme)
  localStorage.setItem('theme', newTheme)
})

const applyTheme = (theme: 'light' | 'dark' | 'auto') => {
  const root = document.documentElement
  
  let actualTheme: 'light' | 'dark'
  
  if (theme === 'auto') {
    // Check system preference
    actualTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
    
    // Listen for system theme changes
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
      if (currentTheme.value === 'auto') {
        const newActualTheme = e.matches ? 'dark' : 'light'
        root.setAttribute('data-theme', newActualTheme)
        updateElementPlusTheme(e.matches)
      }
    })
  } else {
    actualTheme = theme
  }
  
  root.setAttribute('data-theme', actualTheme)
  updateElementPlusTheme(actualTheme === 'dark')
}

const updateElementPlusTheme = (isDark: boolean) => {
  if (isDark) {
    document.documentElement.classList.add('dark')
    // Also set data-theme for custom styles
    document.documentElement.setAttribute('data-theme', 'dark')
  } else {
    document.documentElement.classList.remove('dark')
    document.documentElement.setAttribute('data-theme', 'light')
  }
}

export const useTheme = () => {
  return {
    currentTheme,
    setTheme: (theme: 'light' | 'dark' | 'auto') => {
      currentTheme.value = theme
    },
  }
}

// Auto-initialize
initTheme()
