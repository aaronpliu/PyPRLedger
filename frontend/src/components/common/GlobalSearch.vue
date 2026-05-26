<template>
  <div class="global-search">
    <!-- Search Trigger Button -->
    <el-button
      :icon="Search"
      @click="openSearch"
      class="search-trigger"
    >
      <span class="search-hint">Search...</span>
      <kbd class="shortcut">Ctrl+K</kbd>
    </el-button>

    <!-- Search Dialog -->
    <el-dialog
      v-model="dialogVisible"
      width="600px"
      :show-close="false"
      class="search-dialog"
      append-to-body
    >
      <template #header>
        <div class="dialog-header">
          <el-input
            ref="searchInputRef"
            v-model="searchQuery"
            placeholder="Search reviews, scores, users..."
            :prefix-icon="Search"
            clearable
            size="large"
            @input="handleSearch"
            @keyup.enter="handleEnterKey"
            @keydown.up.prevent="navigateResults(-1)"
            @keydown.down.prevent="navigateResults(1)"
            @keydown.esc="closeSearch"
          />
        </div>
      </template>

      <!-- Search Results -->
      <div class="search-results" v-loading="loading">
        <!-- Recent Searches -->
        <div v-if="!searchQuery && recentSearches.length > 0" class="recent-section">
          <div class="section-title">
            <el-icon><Clock /></el-icon>
            <span>Recent Searches</span>
            <el-button link size="small" @click="clearRecentSearches">Clear</el-button>
          </div>
          <div
            v-for="(search, index) in recentSearches"
            :key="index"
            class="recent-item"
            @click="applyRecentSearch(search)"
          >
            <el-icon><Search /></el-icon>
            <span>{{ search }}</span>
          </div>
        </div>

        <!-- Search Suggestions -->
        <div v-else-if="!searchQuery" class="suggestions-section">
          <div class="section-title">
            <el-icon><Guide /></el-icon>
            <span>Search Tips</span>
          </div>
          <div class="suggestion-list">
            <div class="suggestion-item">
              <strong>Reviews:</strong> Search by PR ID, project key, or repository
            </div>
            <div class="suggestion-item">
              <strong>Users:</strong> Search by username or display name
            </div>
            <div class="suggestion-item">
              <strong>Projects:</strong> Search by project name, key, or app name
            </div>
          </div>
        </div>

        <!-- Press Enter Hint -->
        <div v-else-if="searchQuery.length >= 2 && !hasSearched && !loading" class="enter-hint-section">
          <div class="enter-hint">
            <kbd>Enter</kbd>
            <span>to search for &quot;{{ searchQuery }}&quot;</span>
          </div>
        </div>

        <!-- Search Results List -->
        <div v-else-if="searchResults.length > 0" class="results-section">
          <div class="results-count">{{ searchResults.length }} results found</div>
          <div
            v-for="(result, index) in searchResults"
            :key="result.id"
            class="result-item"
            :class="{ active: selectedIndex === index }"
            @click="handleResultClick(result)"
            @mouseenter="selectedIndex = index"
          >
            <div class="result-icon">
              <el-icon :color="getResultColor(result.type)">
                <component :is="getResultIcon(result.type)" />
              </el-icon>
            </div>
            <div class="result-content">
              <div class="result-title">
                <span v-html="highlightMatch(result.title, searchQuery)"></span>
              </div>
              <div class="result-description">{{ result.description }}</div>
              <div class="result-meta">
                <el-tag size="small" :type="getTypeTagType(result.type)">
                  {{ result.type }}
                </el-tag>
                <span class="result-date">{{ formatDate(result.created_at) }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- No Results -->
        <el-empty
          v-else-if="searchQuery && !loading"
          description="No results found"
          :image-size="100"
        >
          <template #description>
            <p>Try different keywords or filters</p>
          </template>
        </el-empty>
      </div>

      <!-- Footer -->
      <template #footer>
        <div class="dialog-footer">
          <span class="footer-hints">
            <kbd>↑↓</kbd> Navigate
            <kbd>↵</kbd> Search / Select
            <kbd>Esc</kbd> Close
          </span>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { Search, Clock, Guide, Document, Star, User, Folder } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import dayjs from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'
import { globalSearch, type SearchResult } from '@/api/search'

// Extend dayjs with relativeTime plugin
dayjs.extend(relativeTime)

const router = useRouter()

// State
const dialogVisible = ref(false)
const searchQuery = ref('')
const searchResults = ref<SearchResult[]>([])
const selectedIndex = ref(0)
const loading = ref(false)
const searchInputRef = ref()
let searchTimeout: ReturnType<typeof setTimeout> | null = null

// Track whether a search has been performed for the current query
let hasSearched = false

// Recent searches from localStorage
const recentSearches = ref<string[]>([])

onMounted(() => {
  loadRecentSearches()
  // Register keyboard shortcut
  document.addEventListener('keydown', handleKeyboardShortcut)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeyboardShortcut)
})

const loadRecentSearches = () => {
  try {
    const stored = localStorage.getItem('recentSearches')
    if (stored) {
      recentSearches.value = JSON.parse(stored)
    }
  } catch (error) {
    console.error('Failed to load recent searches:', error)
  }
}

const saveRecentSearch = (query: string) => {
  if (!query.trim()) return
  
  // Add to beginning, remove duplicates
  const searches = [query, ...recentSearches.value.filter(s => s !== query)].slice(0, 10)
  recentSearches.value = searches
  
  try {
    localStorage.setItem('recentSearches', JSON.stringify(searches))
  } catch (error) {
    console.error('Failed to save recent search:', error)
  }
}

const clearRecentSearches = () => {
  recentSearches.value = []
  localStorage.removeItem('recentSearches')
}

const handleKeyboardShortcut = (e: KeyboardEvent) => {
  // Ctrl+K or Cmd+K
  if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
    e.preventDefault()
    openSearch()
  }
}

const openSearch = async () => {
  dialogVisible.value = true
  searchQuery.value = ''
  searchResults.value = []
  selectedIndex.value = 0
  hasSearched = false
  
  // Focus input after dialog opens
  await nextTick()
  searchInputRef.value?.focus()
}

const closeSearch = () => {
  dialogVisible.value = false
  searchQuery.value = ''
  searchResults.value = []
  hasSearched = false

  // Clear any pending search timeout
  if (searchTimeout) {
    clearTimeout(searchTimeout)
    searchTimeout = null
  }
}

const handleSearch = () => {
  const query = searchQuery.value.trim()

  if (!query) {
    searchResults.value = []
    hasSearched = false
    return
  }

  // Clear results and reset search flag when query changes
  if (searchTimeout) {
    clearTimeout(searchTimeout)
    searchTimeout = null
  }
  hasSearched = false
  searchResults.value = []
}

// Handle Enter key: search if no results, select first result if results exist
const handleEnterKey = () => {
  if (searchResults.value.length > 0) {
    selectFirstResult()
  } else {
    triggerSearch()
  }
}

// Trigger search explicitly (on Enter key press)
const triggerSearch = async () => {
  const query = searchQuery.value.trim()

  if (!query || query.length < 2) {
    searchResults.value = []
    return
  }

  // Prevent duplicate search for the same query
  if (hasSearched) return

  hasSearched = true
  loading.value = true

  try {
    const response = await globalSearch(query, undefined, 10)

    // Discard response if query changed while loading
    if (searchQuery.value.trim() !== query) return

    const allResults: SearchResult[] = [
      ...response.reviews,
      ...response.users,
      ...response.projects,
    ]

    searchResults.value = allResults
    selectedIndex.value = 0

    saveRecentSearch(query)
  } catch (error: any) {
    console.error('Search failed:', error)
    searchResults.value = []
  } finally {
    loading.value = false
  }
}

const navigateResults = (direction: number) => {
  if (searchResults.value.length === 0) return
  
  selectedIndex.value = Math.max(0, Math.min(
    searchResults.value.length - 1,
    selectedIndex.value + direction
  ))
}

const selectFirstResult = () => {
  if (searchResults.value.length > 0) {
    handleResultClick(searchResults.value[selectedIndex.value])
  }
}

const handleResultClick = async (result: SearchResult) => {
  closeSearch()
  
  try {
    // Check if route exists before navigating
    const resolved = router.resolve(result.url)
    
    // If route doesn't exist, show error
    if (!resolved || !resolved.matched || resolved.matched.length === 0) {
      ElMessage.warning('This page is not available')
      return
    }
    
    // Navigate to the result
    await router.push(result.url)
  } catch (error: any) {
    console.error('Navigation failed:', error)
    
    // Handle navigation errors gracefully
    if (error?.message?.includes('Redirected')) {
      // Redirect is normal, ignore
      return
    }
    
    ElMessage.error('Failed to navigate to this page')
  }
}

const applyRecentSearch = (search: string) => {
  searchQuery.value = search
  handleSearch()
}

const getResultIcon = (type: string) => {
  const icons: Record<string, any> = {
    review: Document,
    user: User,
    project: Folder,
  }
  return icons[type] || Search
}

const getResultColor = (type: string) => {
  const colors: Record<string, string> = {
    review: '#409eff',
    user: '#e6a23c',
    project: '#67c23a',
  }
  return colors[type] || '#909399'
}

const getTypeTagType = (type: string) => {
  const types: Record<string, any> = {
    review: 'primary',
    user: 'warning',
    project: 'success',
  }
  return types[type] || 'info'
}

const highlightMatch = (text: string, query: string) => {
  if (!query) return text
  
  const regex = new RegExp(`(${query})`, 'gi')
  return text.replace(regex, '<mark>$1</mark>')
}

const formatDate = (dateStr: string) => {
  return dayjs(dateStr).fromNow()
}
</script>

<style scoped>
.global-search {
  display: inline-block;
}

.search-trigger {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--el-fill-color-light);
  border: 1px solid var(--el-border-color);
  color: var(--el-text-color-primary);
}

.search-trigger:hover {
  background: var(--el-fill-color);
  border-color: var(--el-border-color-hover);
}

.search-hint {
  opacity: 0.8;
}

.shortcut {
  padding: 2px 6px;
  background: var(--el-fill-color);
  border-radius: 4px;
  font-size: 11px;
  font-family: monospace;
  color: var(--el-text-color-regular);
}

.search-dialog :deep(.el-dialog__header) {
  padding: 16px 20px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  margin: 0;
}

.dialog-header {
  width: 100%;
}

.search-results {
  max-height: 400px;
  overflow-y: auto;
  padding: 0 20px;
}

.recent-section,
.suggestions-section,
.results-section {
  padding: 16px 0;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 12px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.section-title .el-button {
  margin-left: auto;
}

.recent-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: background-color 0.2s;
  color: var(--el-text-color-regular);
}

.recent-item:hover {
  background-color: var(--el-fill-color-light);
}

.suggestion-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.suggestion-item {
  padding: 8px 12px;
  background: var(--el-fill-color-light);
  border-radius: 6px;
  font-size: 13px;
  color: var(--el-text-color-regular);
}

.suggestion-item kbd {
  padding: 2px 6px;
  background: var(--el-fill-color);
  border-radius: 4px;
  font-family: monospace;
  font-size: 12px;
  margin-right: 8px;
  color: var(--el-text-color-primary);
}

.results-count {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.enter-hint-section {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 0;
}

.enter-hint {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 24px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
  font-size: 14px;
  color: var(--el-text-color-secondary);
}

.enter-hint kbd {
  padding: 4px 10px;
  background: var(--el-fill-color);
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
  font-family: monospace;
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.enter-hint span {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 300px;
}

.result-item {
  display: flex;
  gap: 12px;
  padding: 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: background-color 0.2s;
  margin-bottom: 8px;
}

.result-item:hover,
.result-item.active {
  background-color: var(--el-fill-color-light);
}

.result-icon {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  border-radius: 6px;
  background: var(--el-fill-color-light);
  display: flex;
  align-items: center;
  justify-content: center;
}

.result-content {
  flex: 1;
  min-width: 0;
}

.result-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--el-text-color-primary);
  margin-bottom: 4px;
}

.result-title :deep(mark) {
  background: #ffd700;
  padding: 0 2px;
  border-radius: 2px;
  color: #000;
}

[data-theme='dark'] .result-title :deep(mark) {
  background: #b8860b;
  color: #fff;
}

.result-description {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 6px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.result-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.result-date {
  font-size: 11px;
  color: var(--el-text-color-placeholder);
}

.dialog-footer {
  display: flex;
  justify-content: center;
  padding-top: 8px;
  border-top: 1px solid var(--el-border-color-lighter);
}

.footer-hints {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.footer-hints kbd {
  padding: 2px 6px;
  background: var(--el-fill-color-light);
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
  font-family: monospace;
  font-size: 11px;
  margin-right: 4px;
  color: var(--el-text-color-regular);
}
</style>
