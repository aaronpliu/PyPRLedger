<template>
  <div class="code-diff-viewer">
    <div ref="diffContainer" class="diff-container"></div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { Diff2HtmlUI } from 'diff2html/lib/ui/js/diff2html-ui-base.js'
import hljs from 'highlight.js'
import 'diff2html/bundles/css/diff2html.min.css'

const props = withDefaults(defineProps<{
  diff: string
  outputFormat?: 'line-by-line' | 'side-by-side'
}>(), {
  outputFormat: 'line-by-line',
})

const emit = defineEmits<{
  'update:outputFormat': [value: 'line-by-line' | 'side-by-side']
}>()

const diffContainer = ref<HTMLElement | null>(null)
const currentFormat = ref(props.outputFormat)
let diff2htmlUi: any = null
let processedDiffCache: string = ''

onMounted(() => {
  renderDiff()
  
  // Watch for theme changes and re-render
  const observer = new MutationObserver(() => {
    // Re-render with new theme
    if (processedDiffCache) {
      renderDiff()
    }
  })
  
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['data-theme']
  })
  
  onUnmounted(() => {
    observer.disconnect()
  })
})

// Watch for prop changes from parent
watch(() => props.outputFormat, (newFormat) => {
  if (newFormat && newFormat !== currentFormat.value) {
    currentFormat.value = newFormat
    renderDiff()
  }
})

watch(() => [props.diff, currentFormat.value], () => {
  renderDiff()
})

const toggleView = (format: 'line-by-line' | 'side-by-side') => {
  currentFormat.value = format
  emit('update:outputFormat', format)
  renderDiff()
}

/**
 * Check if a string is base64 encoded
 */
const isBase64 = (str: string): boolean => {
  if (!str || typeof str !== 'string') return false
  
  // Base64 regex pattern
  const base64Regex = /^[A-Za-z0-9+/]*={0,2}$/
  
  // Check if it matches base64 pattern and length is multiple of 4
  return base64Regex.test(str) && str.length % 4 === 0 && str.length > 0
}

/**
 * Decode base64 string to UTF-8
 */
const decodeBase64 = (base64Str: string): string => {
  try {
    // Browser environment - use atob
    const binaryString = atob(base64Str)
    const bytes = new Uint8Array(binaryString.length)
    for (let i = 0; i < binaryString.length; i++) {
      bytes[i] = binaryString.charCodeAt(i)
    }
    return new TextDecoder('utf-8').decode(bytes)
  } catch (error) {
    console.error('Failed to decode base64:', error)
    throw error
  }
}

const renderDiff = () => {
  if (!diffContainer.value || !props.diff) return

  // Clear previous content
  diffContainer.value.innerHTML = ''

  let processedDiff = props.diff
  
  // Check if diff is base64 encoded
  if (isBase64(props.diff)) {
    console.log('Detected base64 encoded diff, decoding...')
    try {
      processedDiff = decodeBase64(props.diff)
      console.log('Successfully decoded base64 diff')
    } catch (decodeError) {
      console.warn('Failed to decode as base64, treating as plain text:', decodeError)
      // If decoding fails, continue with original diff
    }
  }
  
  // Cache the processed diff for theme switching
  processedDiffCache = processedDiff
  
  // Normalize diff format - ensure proper line breaks
  const hasNewlines = processedDiff.includes('\n') || processedDiff.includes('\r')
  
  if (!hasNewlines) {
    console.log('Normalizing diff format (adding newlines)')
    // More comprehensive normalization
    processedDiff = processedDiff
      // Add newline before hunk headers (@@ ... @@)
      .replace(/(@@[^@]*@@)/g, '\n$1')
      // Add newline before added lines (+ at start, but not +++ )
      .replace(/(^|\n)(\+[^+])/g, '$1\n$2')
      // Add newline before removed lines (- at start, but not --- )
      .replace(/(^|\n)(-[^-])/g, '$1\n$2')
      // Add newline before context lines (space at start after @@)
      .replace(/(@@[^@]*@@)( )/g, '$1\n ')
      .trim()
    
    // Ensure "diff --git" is at the very beginning (no leading whitespace/newlines)
    if (processedDiff.startsWith('\n') || processedDiff.startsWith('\r')) {
      processedDiff = processedDiff.trimStart()
    }
    
    console.log('Normalized diff preview:', processedDiff.substring(0, 300))
  }

  const isDark = document.documentElement.getAttribute('data-theme') === 'dark'
  
  const configuration = {
    drawFileList: true,
    fileListToggle: true,
    fileListStartVisible: true,
    fileContentToggle: true,
    matching: 'lines' as const,
    outputFormat: currentFormat.value,
    synchronisedScroll: true,
    highlight: true,
    renderNothingWhenEmpty: false,
    stickyFileHeaders: true,
    colorScheme: isDark ? ('dark' as const) : ('light' as const),
  }

  try {
    diffContainer.value.innerHTML = ''
    diff2htmlUi = new Diff2HtmlUI(diffContainer.value, processedDiff, configuration, hljs)
    diff2htmlUi.draw()
  } catch (error) {
    console.error('Failed to render diff:', error)
    console.error('Diff that caused error:', props.diff.substring(0, 500))
    diffContainer.value.innerHTML = '<div class="diff-error">Failed to render code diff</div>'
  }
}
</script>

<style scoped>
.code-diff-viewer {
  border-radius: 8px;
  overflow: hidden;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.diff-container {
  flex: 1;
  overflow: auto;
}

/* Fix line number positioning */
:deep(.d2h-code-linenumber),
:deep(.d2h-code-side-linenumber) {
  position: relative !important;
}

:deep(.d2h-gutter) {
  position: relative !important;
}
</style>
