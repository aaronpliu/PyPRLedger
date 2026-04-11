<template>
  <div class="review-detail" v-loading="loading">
    <el-page-header @back="$router.back()" title="Back">
      <template #content>
        <span class="page-title">Review Details</span>
      </template>
    </el-page-header>

    <el-row :gutter="20" class="content-row" v-if="review">
      <!-- Main Content -->
      <el-col :span="24">
        <!-- Review Info Card -->
        <el-card class="info-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <span class="card-title">📋 Review Information</span>
              <el-space>
                <el-button type="success" size="small" @click="showScoreDialog = true">
                  <el-icon><Plus /></el-icon>
                  Add Score
                </el-button>
                <el-button type="danger" size="small" @click="confirmDelete">
                  <el-icon><Delete /></el-icon>
                  Delete
                </el-button>
              </el-space>
            </div>
          </template>

          <el-descriptions :column="3" border size="default">
            <el-descriptions-item label="PR ID" label-align="right">
              <el-tag type="info" size="small">{{ review.pull_request_id }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="Commit ID" v-if="review.pull_request_commit_id" label-align="right">
              <el-tag type="success" size="small">{{ review.pull_request_commit_id.substring(0, 8) }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="Project" label-align="right">
              <strong>{{ review.project_key }}</strong> / {{ review.repository_slug }}
            </el-descriptions-item>
            <el-descriptions-item label="Reviewer" label-align="right">
              <el-avatar :size="24" style="vertical-align: middle; margin-right: 8px;">{{ getInitials(review.reviewer_info?.display_name || review.reviewer) }}</el-avatar>
              {{ review.reviewer_info?.display_name || review.reviewer }}
            </el-descriptions-item>
            <el-descriptions-item label="Status" label-align="right">
              <el-tag :type="getStatusType(review.pull_request_status)" effect="dark">
                {{ review.pull_request_status }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="Level" label-align="right">
              <el-tag :type="review.source_filename ? 'warning' : 'success'" size="small">
                {{ review.source_filename ? '📄 File-Level' : '📋 PR-Level' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="Summary" :span="3" label-align="right">
              <div class="summary-text">{{ review.reviewer_comments || 'No summary provided' }}</div>
            </el-descriptions-item>
            <el-descriptions-item label="Created" label-align="right">
              <el-icon><Clock /></el-icon> {{ formatDate(review.created_date || '') }}
            </el-descriptions-item>
            <el-descriptions-item label="Updated" label-align="right">
              <el-icon><Clock /></el-icon> {{ formatDate(review.updated_date || '') }}
            </el-descriptions-item>
          </el-descriptions>
        </el-card>

        <!-- Dual Column Layout: Code Diff + AI Review -->
        <el-row :gutter="16" style="margin-top: 16px" v-if="review.git_code_diff || review.ai_suggestions">
          <!-- Code Diff Column -->
          <el-col :span="review.ai_suggestions ? 12 : 24">
            <div class="analysis-column">
              <div class="analysis-column-header">
                <span>📝 Code Changes</span>
                <el-radio-group v-model="diffFormat" size="small">
                  <el-radio-button value="line-by-line">📄 Unified</el-radio-button>
                  <el-radio-button value="side-by-side">↔️ Side by Side</el-radio-button>
                </el-radio-group>
              </div>
              <div class="analysis-column-body">
                <CodeDiffViewer
                  v-if="review.diff_content || review.git_code_diff"
                  :diff="review.diff_content || review.git_code_diff || ''"
                  v-model:output-format="diffFormat"
                />
              </div>
            </div>
          </el-col>

          <!-- AI Review Column -->
          <el-col :span="review.ai_suggestions ? 12 : 0" v-if="review.ai_suggestions">
            <div class="analysis-column">
              <div class="analysis-column-header">
                🤖 AI Review Results
              </div>
              <div class="analysis-column-body">
                <AIReviewResults :suggestions="review.ai_suggestions" />
              </div>
            </div>
          </el-col>
        </el-row>

        <!-- Scores Section -->
        <el-card class="scores-card" style="margin-top: 20px">
          <template #header>
            <div class="card-header">
              <span class="card-title">📊 Scores ({{ scores.length }})</span>
              <el-button type="primary" size="small" @click="showScoreDialog = true">
                <el-icon><Plus /></el-icon>
                Add Score
              </el-button>
            </div>
          </template>

          <el-table :data="scores" stripe>
            <el-table-column prop="reviewer" label="Reviewer" width="150">
              <template #default="{ row }">
                {{ row.reviewer_info?.display_name || row.reviewer }}
              </template>
            </el-table-column>
            <el-table-column prop="score" label="Score" width="120">
              <template #default="{ row }">
                <span class="score-value">{{ row.score }}</span>
                <span v-if="row.max_score" class="score-max"> / {{ row.max_score }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="reviewer_comments" label="Comments" min-width="200" show-overflow-tooltip />
            <el-table-column prop="created_date" label="Created" width="160">
              <template #default="{ row }">
                {{ formatDate(row.created_date || '') }}
              </template>
            </el-table-column>
            <el-table-column prop="updated_date" label="Updated" width="160">
              <template #default="{ row }">
                {{ row.updated_date ? formatDate(row.updated_date) : '-' }}
              </template>
            </el-table-column>
            <el-table-column label="Actions" width="180">
              <template #default="{ row }">
                <el-button 
                  size="small" 
                  type="primary" 
                  @click="editScore(row)"
                  :disabled="!canEditScore(row)"
                >
                  Update
                </el-button>
                <el-button 
                  size="small" 
                  type="danger" 
                  @click="deleteScore(row)"
                  :disabled="!canDeleteScore(row)"
                >
                  Delete
                </el-button>
              </template>
            </el-table-column>
          </el-table>

          <el-empty v-if="scores.length === 0" description="No scores yet" />
        </el-card>
      </el-col>
    </el-row>

    <!-- Add Score Dialog -->
    <el-dialog v-model="showScoreDialog" :title="editingScore ? 'Update Score' : 'Add Score'" width="700px">
      <!-- Quick Score Buttons -->
      <QuickScoreButtons @select="handleQuickScoreSelect" />
      
      <!-- Score Range Guide -->
      <ScoreRangeGuide />
      
      <el-form :model="scoreForm" :rules="scoreRules" ref="scoreFormRef" label-width="120px">
        <el-form-item label="Reviewer">
          <el-input 
            v-model="scoreForm.reviewer" 
            disabled
            placeholder="Current user"
          >
            <template #prefix>
              <el-icon><User /></el-icon>
            </template>
          </el-input>
          <div style="font-size: 0.8rem; color: var(--el-text-color-secondary); margin-top: 4px;">
            Score will be attributed to your account
          </div>
        </el-form-item>
        
        <el-form-item label="Score" prop="score">
          <div class="score-input-container">
            <el-slider 
              v-model="scoreForm.score" 
              :min="0" 
              :max="10" 
              :step="0.5"
              :marks="{ 0: '0', 2: '2', 4: '4', 6: '6', 8: '8', 10: '10' }"
              show-input
              style="width: 100%"
            />
            <div class="score-value-display">{{ scoreForm.score.toFixed(1) }}</div>
          </div>
        </el-form-item>
        
        <el-form-item label="Comments">
          <div class="comment-editor">
            <!-- Toolbar -->
            <div class="editor-toolbar">
              <el-tooltip content="Bold" placement="top">
                <el-button size="small" text @click="insertMarkdown('**', '**')">
                  <strong>B</strong>
                </el-button>
              </el-tooltip>
              <el-tooltip content="Italic" placement="top">
                <el-button size="small" text @click="insertMarkdown('*', '*')">
                  <em>I</em>
                </el-button>
              </el-tooltip>
              <el-tooltip content="Code" placement="top">
                <el-button size="small" text @click="insertMarkdown('`', '`')">
                  <code>&lt;/&gt;</code>
                </el-button>
              </el-tooltip>
              <el-tooltip content="Link" placement="top">
                <el-button size="small" text @click="insertLink">
                  🔗
                </el-button>
              </el-tooltip>
              <el-divider direction="vertical" />
              <el-tooltip content="Emoji Picker" placement="top">
                <el-popover
                  v-model:visible="showEmojiPicker"
                  placement="bottom-start"
                  :width="320"
                  trigger="click"
                >
                  <template #reference>
                    <el-button size="small" text>😊</el-button>
                  </template>
                  <div class="emoji-picker">
                    <div class="emoji-grid">
                      <button
                        v-for="emoji in commonEmojis"
                        :key="emoji"
                        class="emoji-btn"
                        @click="insertEmoji(emoji)"
                      >
                        {{ emoji }}
                      </button>
                    </div>
                  </div>
                </el-popover>
              </el-tooltip>
              <el-divider direction="vertical" />
              <el-tooltip content="Toggle Preview" placement="top">
                <el-button 
                  size="small" 
                  :type="showPreview ? 'primary' : ''"
                  text 
                  @click="showPreview = !showPreview"
                >
                  👁️ Preview
                </el-button>
              </el-tooltip>
            </div>
            
            <!-- Editor Area -->
            <div class="editor-content">
              <el-input
                v-if="!showPreview"
                v-model="scoreForm.reviewer_comments"
                type="textarea"
                :rows="6"
                placeholder="Add comments... (supports Markdown)"
                maxlength="1000"
                show-word-limit
                @keydown.ctrl.enter="handleAddScore"
              />
              <div v-else class="markdown-preview">
                <div v-if="!scoreForm.reviewer_comments" class="preview-empty">
                  No content to preview
                </div>
                <div v-else v-html="renderMarkdown(scoreForm.reviewer_comments)"></div>
              </div>
            </div>
            
            <!-- Helper Text -->
            <div class="editor-hint">
              💡 Tip: Use **bold**, *italic*, `code`, [link](url). Press Ctrl+Enter to submit.
            </div>
          </div>
        </el-form-item>
      </el-form>
      
      <template #footer>
        <el-button @click="showScoreDialog = false">Cancel</el-button>
        <el-button type="primary" :loading="addingScore" @click="handleAddScore">
          {{ editingScore ? 'Update' : 'Add' }} Score
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Clock, Plus, Delete, User } from '@element-plus/icons-vue'
import { reviewsApi } from '@/api/reviews'
import { scoresApi } from '@/api/scores'
import type { Review } from '@/api/reviews'
import type { Score, ScoreCreate } from '@/api/scores'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import dayjs from 'dayjs'
import CodeDiffViewer from '@/components/review/CodeDiffViewer.vue'
import QuickScoreButtons from '@/components/review/QuickScoreButtons.vue'
import ScoreRangeGuide from '@/components/review/ScoreRangeGuide.vue'
import AIReviewResults from '@/components/review/AIReviewResults.vue'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const loading = ref(false)
const addingScore = ref(false)
const review = ref<Review | null>(null)
const scores = ref<Score[]>([])
const showScoreDialog = ref(false)
const editingScore = ref<Score | null>(null)
const scoreFormRef = ref<FormInstance>()
const diffFormat = ref<'line-by-line' | 'side-by-side'>('line-by-line')
const showEmojiPicker = ref(false)
const showPreview = ref(false)

const scoreForm = reactive<ScoreCreate>({
  pull_request_id: '',
  pull_request_commit_id: '',
  project_key: '',
  repository_slug: '',
  reviewer: '',
  score: 0,
  reviewer_comments: null,
  source_filename: null,
})

const scoreRules: FormRules = {
  score: [
    { required: true, message: 'Please input score', trigger: 'blur' },
  ],
}

const formatDate = (dateStr: string) => {
  return dayjs(dateStr).format('YYYY-MM-DD HH:mm:ss')
}

const getStatusType = (status: string) => {
  const types: Record<string, any> = {
    open: 'success',
    merged: 'primary',
    closed: 'info',
    draft: 'warning',
    completed: 'success',
    in_progress: 'warning',
    pending: 'info',
  }
  return types[status] || 'info'
}

const getInitials = (name: string) => {
  if (!name) return '?'
  return name
    .split(' ')
    .map(n => n[0])
    .join('')
    .toUpperCase()
    .substring(0, 2)
}

const loadReview = async () => {
  const id = Number(route.params.id)
  if (!id) return

  loading.value = true
  try {
    // Get review by ID (fetches from list)
    review.value = await reviewsApi.getReviewById(id)
    
    if (!review.value) {
      throw new Error('Review not found')
    }
    
    // Load scores using composite key (match the review's level)
    scores.value = await scoresApi.getScoresByReview(
      review.value.pull_request_id,
      review.value.project_key,
      review.value.repository_slug,
      review.value.source_filename || null  // null for PR-level, filename for file-level
    )
    
    // Debug info
    ElMessage.info(`Loaded ${scores.value.length} score(s) for ${review.value.source_filename ? 'file-level' : 'PR-level'} review`)
    
    // Set score form defaults
    scoreForm.pull_request_id = review.value.pull_request_id
    scoreForm.pull_request_commit_id = review.value.pull_request_commit_id || ''
    scoreForm.project_key = review.value.project_key
    scoreForm.repository_slug = review.value.repository_slug
    scoreForm.reviewer = authStore.currentUser?.username || ''
    scoreForm.source_filename = review.value.source_filename || null
  } catch (error) {
    console.error('Failed to load review:', error)
    ElMessage.error('Failed to load review')
    router.push('/reviews')
  } finally {
    loading.value = false
  }
}

const handleAddScore = async () => {
  if (!scoreFormRef.value) return
  
  await scoreFormRef.value.validate(async (valid) => {
    if (valid) {
      addingScore.value = true
      try {
        await scoresApi.createScore(scoreForm)
        ElMessage.success(editingScore.value ? 'Score updated successfully' : 'Score added successfully')
        showScoreDialog.value = false
        editingScore.value = null
        // Reset form
        scoreForm.score = 0
        scoreForm.reviewer_comments = null
        loadReview()
      } catch (error) {
        ElMessage.error(editingScore.value ? 'Failed to update score' : 'Failed to add score')
      } finally {
        addingScore.value = false
      }
    }
  })
}

const editScore = (score: Score) => {
  editingScore.value = score
  scoreForm.score = score.score
  scoreForm.reviewer_comments = score.reviewer_comments || null
  showScoreDialog.value = true
}

const canEditScore = (score: Score): boolean => {
  const currentUsername = authStore.currentUser?.username
  return currentUsername === score.reviewer
}

const canDeleteScore = (score: Score): boolean => {
  const currentUsername = authStore.currentUser?.username
  return currentUsername === score.reviewer
}

const deleteScore = async (score: Score) => {
  if (!review.value) return
  
  try {
    await ElMessageBox.confirm('Are you sure you want to delete this score?', 'Confirm', {
      type: 'warning',
    })
    
    await scoresApi.deleteScore(
      score.reviewer,
      review.value.pull_request_id,
      review.value.project_key,
      review.value.repository_slug,
      score.source_filename || null
    )
    ElMessage.success('Score deleted successfully')
    loadReview()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('Failed to delete score')
    }
  }
}

const confirmDelete = async () => {
  if (!review.value) return
  
  try {
    await ElMessageBox.confirm(
      `Are you sure you want to delete review #${review.value.id}?`,
      'Confirm Delete',
      {
        type: 'warning',
      }
    )
    
    await reviewsApi.deleteReview(
      review.value.project_key,
      review.value.repository_slug,
      review.value.pull_request_id
    )
    ElMessage.success('Review deleted successfully')
    router.push('/reviews')
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('Failed to delete review')
    }
  }
}

const handleQuickScoreSelect = (value: number) => {
  scoreForm.score = value
}

// Common emojis for quick insertion
const commonEmojis = [
  '👍', '👎', '✅', '❌', '⭐', '💡', '🔥', '🎉',
  '👀', '💬', '📝', '🚀', '⚠️', '🐛', '✨', '💯',
  '😊', '😄', '🤔', '👏', '🙏', '❤️', '💪', '🎯',
]

// Insert markdown syntax at cursor position
const insertMarkdown = (before: string, after: string) => {
  const textarea = document.querySelector('.comment-editor textarea') as HTMLTextAreaElement
  if (!textarea) return
  
  const start = textarea.selectionStart
  const end = textarea.selectionEnd
  const text = scoreForm.reviewer_comments || ''
  const selectedText = text.substring(start, end)
  
  const newText = text.substring(0, start) + before + selectedText + after + text.substring(end)
  scoreForm.reviewer_comments = newText
  
  // Restore cursor position
  setTimeout(() => {
    textarea.focus()
    textarea.setSelectionRange(start + before.length, end + before.length)
  }, 0)
}

// Insert link
const insertLink = () => {
  const url = prompt('Enter URL:')
  if (url) {
    const text = prompt('Enter link text:', url)
    if (text) {
      insertMarkdown('[', `](${url})`)
      // Replace placeholder with actual text
      const textarea = document.querySelector('.comment-editor textarea') as HTMLTextAreaElement
      if (textarea) {
        const currentText = scoreForm.reviewer_comments || ''
        const lastBracket = currentText.lastIndexOf('[')
        if (lastBracket !== -1) {
          const newText = currentText.substring(0, lastBracket + 1) + text + currentText.substring(lastBracket + 1)
          scoreForm.reviewer_comments = newText
        }
      }
    }
  }
}

// Insert emoji
const insertEmoji = (emoji: string) => {
  const textarea = document.querySelector('.comment-editor textarea') as HTMLTextAreaElement
  if (!textarea) return
  
  const start = textarea.selectionStart
  const text = scoreForm.reviewer_comments || ''
  const newText = text.substring(0, start) + emoji + text.substring(start)
  scoreForm.reviewer_comments = newText
  showEmojiPicker.value = false
  
  setTimeout(() => {
    textarea.focus()
    textarea.setSelectionRange(start + emoji.length, start + emoji.length)
  }, 0)
}

// Simple markdown renderer
const renderMarkdown = (text: string): string => {
  if (!text) return ''
  
  let html = text
    // Escape HTML
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    // Bold
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    // Italic
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    // Code
    .replace(/`(.+?)`/g, '<code style="background: #f1f5f9; padding: 2px 6px; border-radius: 3px; font-family: monospace;">$1</code>')
    // Links
    .replace(/\[(.+?)\]\((.+?)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" style="color: #3b82f6; text-decoration: underline;">$1</a>')
    // Line breaks
    .replace(/\n/g, '<br>')
  
  return html
}

// Watch for dialog open to set reviewer
watch(showScoreDialog, (isOpen) => {
  if (isOpen && review.value) {
    // Always set reviewer to current user
    scoreForm.reviewer = authStore.currentUser?.username || ''
    
    // If not editing, reset other fields
    if (!editingScore.value) {
      scoreForm.score = 0
      scoreForm.reviewer_comments = null
    }
  }
})

onMounted(() => {
  loadReview()
})
</script>

<style scoped>
.review-detail {
  padding: 20px;
  background: var(--el-bg-color-page);
  min-height: calc(100vh - 60px);
}

.page-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.content-row {
  margin-top: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.summary-text {
  line-height: 1.6;
  color: var(--el-text-color-regular);
  white-space: pre-wrap;
  word-break: break-word;
}

.actions-card {
  position: sticky;
  top: 20px;
}

/* Analysis Column - Match web/index.html */
.analysis-column {
  border: 2px solid var(--el-border-color);
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.06);
  background: white;
  height: 600px; /* Fixed height for the entire column */
  display: flex;
  flex-direction: column;
}

[data-theme='dark'] .analysis-column {
  background: #1e293b;
  border-color: #334155;
}

.analysis-column-header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 12px 16px;
  font-weight: 700;
  font-size: 0.95rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-shrink: 0; /* Prevent header from shrinking */
  overflow: hidden; /* Ensure no scrollbar in header */
}

.analysis-column-body {
  padding: 0;
  flex: 1;
  overflow: auto; /* Enable both vertical and horizontal scrolling */
  min-height: 0;
}

/* Custom scrollbar styling */
.analysis-column-body::-webkit-scrollbar {
  width: 8px;
}

.analysis-column-body::-webkit-scrollbar-track {
  background: transparent;
}

.analysis-column-body::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 4px;
}

.analysis-column-body::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}

[data-theme='dark'] .analysis-column-body::-webkit-scrollbar-thumb {
  background: #475569;
}

[data-theme='dark'] .analysis-column-body::-webkit-scrollbar-thumb:hover {
  background: #64748b;
}

.score-value {
  font-size: 1.2rem;
  font-weight: 700;
  color: var(--el-color-success);
}

.score-max {
  font-size: 0.9rem;
  color: var(--el-text-color-secondary);
}

.score-input-container {
  width: 100%;
}

.score-value-display {
  text-align: center;
  font-size: 2rem;
  font-weight: 800;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin-top: 12px;
  text-shadow: 0 2px 4px rgba(102, 126, 234, 0.2);
}

/* Element Plus enhancements */
:deep(.el-descriptions__label) {
  font-weight: 500;
  width: 120px;
  color: var(--el-text-color-primary);
}

:deep(.el-descriptions__content) {
  color: var(--el-text-color-regular);
}

/* Dark theme for descriptions */
[data-theme='dark'] :deep(.el-descriptions) {
  --el-descriptions-bg-color: #1e293b;
  --el-descriptions-border-color: #334155;
}

[data-theme='dark'] :deep(.el-descriptions__label) {
  background-color: #1e293b !important;
  color: #f1f5f9 !important;
  border-color: #334155 !important;
}

[data-theme='dark'] :deep(.el-descriptions__content) {
  background-color: #0f172a !important;
  color: #cbd5e1 !important;
  border-color: #334155 !important;
}

/* Force text nodes and all child elements to use correct color */
[data-theme='dark'] :deep(.el-descriptions__cell.is-bordered-content) {
  color: #cbd5e1 !important;
}

:deep(.el-table) {
  --el-table-border-color: var(--el-border-color-lighter);
}

:deep(.el-button) {
  border-radius: 6px;
  transition: all 0.3s ease;
}

:deep(.el-button:hover) {
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

:deep(.el-card) {
  border-radius: 8px;
  transition: all 0.3s ease;
}

:deep(.el-card:hover) {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

/* Comment Editor Styles */
.comment-editor {
  border: 1px solid var(--el-border-color);
  border-radius: 6px;
  overflow: hidden;
}

.editor-toolbar {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px;
  background: var(--el-fill-color-light);
  border-bottom: 1px solid var(--el-border-color);
  flex-wrap: wrap;
}

.editor-toolbar :deep(.el-button) {
  min-width: 32px;
  height: 32px;
  padding: 0;
}

.editor-content {
  position: relative;
}

.markdown-preview {
  min-height: 150px;
  max-height: 400px;
  overflow-y: auto;
  padding: 12px;
  background: white;
  font-size: 0.9rem;
  line-height: 1.6;
  color: var(--el-text-color-primary);
}

[data-theme='dark'] .markdown-preview {
  background: #1e293b;
  color: #cbd5e1;
}

.preview-empty {
  color: var(--el-text-color-secondary);
  font-style: italic;
  text-align: center;
  padding: 40px 0;
}

.editor-hint {
  padding: 6px 12px;
  background: var(--el-fill-color-lighter);
  font-size: 0.75rem;
  color: var(--el-text-color-secondary);
  border-top: 1px solid var(--el-border-color);
}

/* Emoji Picker */
.emoji-picker {
  max-height: 200px;
  overflow-y: auto;
}

.emoji-grid {
  display: grid;
  grid-template-columns: repeat(8, 1fr);
  gap: 4px;
  padding: 8px;
}

.emoji-btn {
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  border-radius: 4px;
  cursor: pointer;
  font-size: 1.2rem;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.emoji-btn:hover {
  background: var(--el-fill-color);
  transform: scale(1.2);
}

/* Markdown Preview Styles */
.markdown-preview :deep(strong) {
  font-weight: 700;
  color: var(--el-text-color-primary);
}

.markdown-preview :deep(em) {
  font-style: italic;
}

.markdown-preview :deep(code) {
  background: var(--el-fill-color-light);
  padding: 2px 6px;
  border-radius: 3px;
  font-family: 'SF Mono', Monaco, monospace;
  font-size: 0.85em;
}

.markdown-preview :deep(a) {
  color: #3b82f6;
  text-decoration: underline;
}

.markdown-preview :deep(a:hover) {
  color: #2563eb;
}
</style>

<style>
/* Global styles for dark mode descriptions - must be non-scoped */
[data-theme='dark'] .el-descriptions__cell.is-bordered-content {
  color: #cbd5e1 !important;
}

[data-theme='dark'] .el-descriptions__cell.is-bordered-content strong,
[data-theme='dark'] .el-descriptions__cell.is-bordered-content span:not(.el-tag):not(.el-avatar),
[data-theme='dark'] .el-descriptions__cell.is-bordered-content div:not([class*="el-"]) {
  color: #cbd5e1 !important;
}

[data-theme='dark'] .summary-text {
  color: #cbd5e1 !important;
}

/* Force all text nodes to be visible */
[data-theme='dark'] td.el-descriptions__content {
  color: #cbd5e1 !important;
}

/* Ultimate fallback - target everything */
[data-theme='dark'] .el-descriptions table tbody tr td {
  color: #cbd5e1 !important;
  background-color: #0f172a !important;
}

[data-theme='dark'] .el-descriptions table tbody tr td * {
  color: inherit !important;
}
</style>
