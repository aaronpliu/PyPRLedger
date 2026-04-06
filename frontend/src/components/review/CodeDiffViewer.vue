<template>
  <div class="code-diff-viewer">
    <div ref="diffContainer" class="diff-container"></div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { Diff2HtmlUI } from 'diff2html/lib/ui/js/diff2html-ui-slim.js'
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

watch(() => [props.diff, currentFormat.value], () => {
  renderDiff()
})

const toggleView = (format: 'line-by-line' | 'side-by-side') => {
  currentFormat.value = format
  emit('update:outputFormat', format)
  renderDiff()
}

const renderDiff = () => {
  if (!diffContainer.value || !props.diff) return

  // Clear previous content
  diffContainer.value.innerHTML = ''

  const configuration = {
    drawFileList: true,
    fileListToggle: true,
    fileListStartVisible: false,
    fileContentToggle: true,
    matching: 'lines' as const,
    outputFormat: currentFormat.value,
    synchronisedScroll: true,
    highlight: true,
    renderNothingWhenEmpty: false,
  }

  try {
    const diff2htmlUi = new Diff2HtmlUI(diffContainer.value, props.diff, configuration)
    diff2htmlUi.draw()
    diff2htmlUi.highlightCode()
  } catch (error) {
    console.error('Failed to render diff:', error)
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
  max-height: 600px;
  overflow: auto;
  background: #fafafa;
}

[data-theme='dark'] .diff-container {
  background: #0f172a;
}

/* Diff2Html Custom Styles - Match web/index.html exactly */
:deep(.d2h-wrapper) {
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Fira Mono', monospace;
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

/* Code content */
:deep(.d2h-code-line-ctn) {
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Fira Mono', monospace !important;
  font-size: 0.85rem !important;
  line-height: 1.6 !important;
  padding: 2px 8px !important;
}

/* Side-by-side layout */
:deep(.d2h-files-diff.d2h-view-side-by-side .d2h-file-diff) {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0;
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
