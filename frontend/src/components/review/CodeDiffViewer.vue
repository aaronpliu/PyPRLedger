<template>
  <div class="code-diff-viewer">
    <div ref="diffContainer" class="diff-container"></div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import * as Diff2Html from 'diff2html'
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

onMounted(() => {
  renderDiff()
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

  const configuration = {
    drawFileList: false,
    matching: 'lines' as const,
    outputFormat: currentFormat.value,
    synchronisedScroll: true,
    highlight: true,
    renderNothingWhenEmpty: false,
  }

  try {
    // Use Diff2Html.html() instead of Diff2HtmlUI
    const html = Diff2Html.html(processedDiff, configuration)
    diffContainer.value.innerHTML = html
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
}

.diff-container {
  /* Let diff2html handle its own scrolling */
  background: #fafafa;
}

[data-theme='dark'] .diff-container {
  background: #0f172a;
}

/* Diff2Html Custom Styles - Match web/index.html exactly */
:deep(.d2h-wrapper) {
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Fira Mono', monospace;
}

/* Dark theme for entire diff2html container */
[data-theme='dark'] :deep(.d2h-wrapper) {
  background-color: #0f172a !important;
  color: #e2e8f0 !important;
}

[data-theme='dark'] :deep(.d2h-file-diff) {
  background-color: #0f172a !important;
}

:deep(.d2h-file-header) {
  background: #f8fafc !important;
  border-bottom: 2px solid var(--el-border-color) !important;
  padding: 12px 16px !important;
}

[data-theme='dark'] :deep(.d2h-file-header) {
  background: #1e293b !important;
  border-bottom-color: #334155 !important;
}

:deep(.d2h-file-name) {
  color: var(--el-text-color-primary) !important;
  font-weight: 700 !important;
  font-size: 0.95rem !important;
}

:deep(.d2h-file-stats) {
  color: var(--el-text-color-secondary) !important;
  font-size: 0.85rem !important;
}

/* Line numbers */
:deep(.d2h-code-linenumber) {
  color: #94a3b8 !important;
  background-color: #f8fafc !important;
  border-right: 1px solid var(--el-border-color) !important;
  font-size: 0.8rem !important;
  padding: 0 8px !important;
}

[data-theme='dark'] :deep(.d2h-code-linenumber) {
  background-color: #0f172a !important;
  border-right-color: #334155 !important;
}

/* Added lines */
:deep(.d2h-ins) {
  background-color: #dcfce7 !important;
}

[data-theme='dark'] :deep(.d2h-ins) {
  background-color: #064e3b !important;
}

:deep(.d2h-ins .d2h-code-line-ctn) {
  color: #166534 !important;
}

[data-theme='dark'] :deep(.d2h-ins .d2h-code-line-ctn) {
  color: #6ee7b7 !important;
}

/* Deleted lines */
:deep(.d2h-del) {
  background-color: #fee2e2 !important;
}

[data-theme='dark'] :deep(.d2h-del) {
  background-color: #7f1d1d !important;
}

:deep(.d2h-del .d2h-code-line-ctn) {
  color: #991b1b !important;
}

[data-theme='dark'] :deep(.d2h-del .d2h-code-line-ctn) {
  color: #fecaca !important;
}

/* Context lines */
:deep(.d2h-cntx .d2h-code-line-ctn) {
  color: var(--el-text-color-secondary) !important;
}

[data-theme='dark'] :deep(.d2h-cntx .d2h-code-line-ctn) {
  color: #94a3b8 !important;
}

/* Dark theme for code content */
[data-theme='dark'] :deep(.d2h-code-line-ctn) {
  color: #e2e8f0 !important;
}

/* Code content */
:deep(.d2h-code-line-ctn) {
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Fira Mono', monospace !important;
  font-size: 0.85rem !important;
  line-height: 1.6 !important;
  padding: 2px 8px !important;
}

/* Dark theme for code content */
[data-theme='dark'] :deep(.d2h-code-line-ctn) {
  color: #e2e8f0 !important;
}

/* Side-by-side layout */
:deep(.d2h-files-diff.d2h-view-side-by-side .d2h-file-diff) {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0;
}

/* Disable ALL sticky/fixed positioning in diff2html */
:deep(.d2h-gutter),
:deep(.d2h-code-linenumber),
:deep(.d2h-code-line-prefix),
:deep([class*="line-numbers"]) {
  position: static !important;
}

/* Fix side-by-side mode specifically */
:deep(.d2h-view-side-by-side .d2h-code-side-line),
:deep(.d2h-view-side-by-side .d2h-code-wrapper) {
  position: static !important;
}

/* File list toggle */
:deep(.d2h-file-list-wrapper) {
  background: #f8fafc !important;
  border-bottom: 2px solid var(--el-border-color) !important;
}

[data-theme='dark'] :deep(.d2h-file-list-wrapper) {
  background: #1e293b !important;
  border-bottom-color: #334155 !important;
}

:deep(.d2h-file-list) {
  max-height: 200px;
  overflow-y: auto;
}

:deep(.d2h-file-switch) {
  cursor: pointer;
  padding: 8px 12px !important;
  transition: background 0.2s ease;
}

:deep(.d2h-file-switch:hover) {
  background: rgba(102, 126, 234, 0.1) !important;
}
</style>
