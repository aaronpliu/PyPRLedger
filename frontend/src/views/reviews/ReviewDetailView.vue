<template>
  <div class="review-detail" v-loading="loading">
    <el-page-header @back="$router.back()" title="Back">
      <template #content>
        <span class="page-title">Review Details</span>
      </template>
      <template #extra>
        <div class="detail-navigation-actions">
          <span v-if="currentReviewIndex >= 0" class="detail-navigation-position">
            {{ currentReviewIndex + 1 }} / {{ reviewNavigationStore.total }}
          </span>
          <el-button class="detail-navigation-button" :disabled="!previousReview" @click="goToPreviousReview">
            <el-icon><ArrowLeft /></el-icon>
            Previous
          </el-button>
          <el-button class="detail-navigation-button" type="primary" :disabled="!nextReview" @click="goToNextReview">
            Next
            <el-icon class="el-icon--right"><ArrowRight /></el-icon>
          </el-button>
        </div>
      </template>
    </el-page-header>

    <el-row :gutter="20" class="content-row" v-if="review">
      <!-- Main Content -->
      <el-col :span="24">
        <!-- Review Info Card (Collapsible) -->
        <el-card class="info-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <div class="card-title-wrapper" @click="toggleInfoCollapse" style="cursor: pointer; flex: 1;">
                <el-icon 
                  :class="['collapse-icon', { 'is-collapsed': !isInfoExpanded }]" 
                  style="margin-right: 8px; transition: transform 0.3s;"
                >
                  <ArrowDown />
                </el-icon>
                <span class="card-title">📋 Review Information (#{{ review.pull_request_id }})</span>
              </div>
              <el-space>
                <!-- Add Score Button - Only show if user has permission -->
                <template v-if="hasScorePermissionRole">
                  <el-tooltip
                    v-if="currentUserHasScore"
                    content="You already have a score. Use the 'Update' button in the Scores table below to modify it."
                    placement="top"
                  >
                    <span>
                      <el-button type="success" size="small" disabled>
                        <el-icon><Plus /></el-icon>
                        Add Score
                      </el-button>
                    </span>
                  </el-tooltip>
                  <el-tooltip v-else-if="!canCreateScore" :content="scoreActionDisabledReason" placement="top">
                    <span>
                      <el-button type="success" size="small" disabled>
                        <el-icon><Plus /></el-icon>
                        Add Score
                      </el-button>
                    </span>
                  </el-tooltip>
                  <el-button v-else type="success" size="small" @click="showScoreDialog = true">
                    <el-icon><Plus /></el-icon>
                    Add Score
                  </el-button>
                </template>
                
                <!-- Delete Review Button - Only show if user has permission -->
                <el-button 
                  v-if="canDeleteReview"
                  type="danger" 
                  size="small" 
                  @click="confirmDelete"
                >
                  <el-icon><Delete /></el-icon>
                  Delete
                </el-button>
              </el-space>
            </div>
          </template>

          <el-collapse-transition>
            <el-descriptions v-if="isInfoExpanded" :column="3" border size="default">
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
                <el-avatar :size="24" class="reviewer-avatar">{{ getInitials(getReviewerDisplayName(review)) }}</el-avatar>
                {{ getReviewerDisplayName(review) }}
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
          </el-collapse-transition>
        </el-card>

        <!-- Dual Column Layout: Code Diff + AI Review -->
        <el-row :gutter="16" style="margin-top: 16px" v-if="review.git_code_diff || review.ai_suggestions">
          <!-- Code Diff Column -->
          <el-col :xs="24" :sm="24" :md="review.ai_suggestions ? 14 : 24" :lg="review.ai_suggestions ? 14 : 24" :xl="review.ai_suggestions ? 15 : 24">
            <div class="analysis-column">
              <div class="analysis-column-header">
                <span>📝 Code Changes</span>
                <el-radio-group v-model="diffFormat" size="small" class="diff-format-toggle">
                  <el-radio-button value="line-by-line">Line by Line</el-radio-button>
                  <el-radio-button value="side-by-side">Side by Side</el-radio-button>
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
          <el-col :xs="24" :sm="24" :md="review.ai_suggestions ? 10 : 0" :lg="review.ai_suggestions ? 10 : 0" :xl="review.ai_suggestions ? 9 : 0" v-if="review.ai_suggestions">
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
              <!-- Add Score Button - Only show if user has permission -->
              <template v-if="hasScorePermissionRole">
                <el-tooltip
                  v-if="currentUserHasScore"
                  content="You already have a score. Use the 'Update' button in the table to modify it."
                  placement="top"
                >
                  <span>
                    <el-button type="primary" size="small" disabled>
                      <el-icon><Plus /></el-icon>
                      Add Score
                    </el-button>
                  </span>
                </el-tooltip>
                <el-tooltip v-else-if="!canCreateScore" :content="scoreActionDisabledReason" placement="top">
                  <span>
                    <el-button type="primary" size="small" disabled>
                      <el-icon><Plus /></el-icon>
                      Add Score
                    </el-button>
                  </span>
                </el-tooltip>
                <el-button v-else type="primary" size="small" @click="showScoreDialog = true">
                  <el-icon><Plus /></el-icon>
                  Add Score
                </el-button>
              </template>
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
                <!-- Update button: 
                     - review_admin+: can update any score
                     - reviewer: can only update their own score (hide others')
                -->
                <el-button 
                  v-if="canDeleteAnyScore || (hasScorePermissionRole && canEditScore(row))"
                  size="small" 
                  type="primary" 
                  @click="editScore(row)"
                >
                  Update
                </el-button>
                <!-- Delete button: 
                     - review_admin+: can delete any score
                     - reviewer: can only delete their own score
                -->
                <el-button 
                  v-if="canDeleteAnyScore || (hasScorePermissionRole && canEditScore(row))"
                  size="small" 
                  type="danger" 
                  @click="deleteScore(row)"
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
    <el-dialog 
      v-model="showScoreDialog" 
      :title="editingScore ? 'Update Score' : 'Add Score'" 
      width="900px"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
      show-close
    >
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
          <MdEditor
            v-model="scoreForm.reviewer_comments"
            :toolbars="toolbars"
            :theme="isDarkTheme ? 'dark' : 'light'"
            language="en-US"
            preview-theme="vuepress"
            code-theme="atom"
            style="height: 400px; border-radius: 6px; overflow: hidden;"
            placeholder="Add your comments here... (supports Markdown)"
          />
          <div class="editor-hint" style="margin-top: 8px;">
            💡 Supports Markdown formatting. Use the toolbar above or type directly.
          </div>
        </el-form-item>
      </el-form>
      
      <template #footer>
        <el-button @click="handleCloseDialog">Cancel</el-button>
        <el-button type="primary" :loading="addingScore" @click="handleAddScore">
          {{ editingScore ? 'Update' : 'Add' }} Score
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, watch, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Clock, Plus, Delete, User, ArrowDown, ArrowLeft, ArrowRight } from '@element-plus/icons-vue'
import { MdEditor, type ToolbarNames, config } from 'md-editor-v3'
import 'md-editor-v3/lib/style.css'
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
import { useReviewNavigationStore, type ReviewNavigationItem } from '@/stores/reviewNavigation'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const reviewNavigationStore = useReviewNavigationStore()
const loading = ref(false)
const addingScore = ref(false)
const review = ref<Review | null>(null)
const scores = ref<Score[]>([])
const showScoreDialog = ref(false)
const editingScore = ref<Score | null>(null)
const scoreFormRef = ref<FormInstance>()
const diffFormat = ref<'line-by-line' | 'side-by-side'>('line-by-line')
const isInfoExpanded = ref(false)

// Detect current theme
const isDarkTheme = computed(() => {
  return document.documentElement.getAttribute('data-theme') === 'dark'
})

// Check if current user already has a score
const currentUserHasScore = computed(() => {
  if (!effectiveReviewerUsername.value || !review.value) return false
  return scores.value.some(s => s.reviewer === effectiveReviewerUsername.value)
})

// Check if current user has permission to create/update scores
// Requires 'reviewer' role or higher (has 'create' permission on 'scores')
const hasScorePermissionRole = computed(() => {
  const roles = authStore.user?.roles || []
  return roles.includes('reviewer') || roles.includes('review_admin') || roles.includes('system_admin')
})

const effectiveReviewerUsername = computed(() => {
  return authStore.currentUser?.git_username || null
})

const canCreateScore = computed(() => {
  return hasScorePermissionRole.value && !!effectiveReviewerUsername.value && isCurrentReviewAssignedToUser.value
})

const isCurrentReviewAssignedToUser = computed(() => {
  if (!review.value || !effectiveReviewerUsername.value) {
    return false
  }

  return review.value.reviewer === effectiveReviewerUsername.value
})

const scoreActionDisabledReason = computed(() => {
  if (!hasScorePermissionRole.value) {
    return 'You do not have permission to submit scores.'
  }

  if (!effectiveReviewerUsername.value) {
    return 'Link your account to a Bitbucket user before submitting scores.'
  }

  if (!review.value?.reviewer) {
    return 'This review is visible because you raised the PR, but scoring is only allowed after review admin assigns it to you.'
  }

  return 'You can only score reviews that are assigned to your linked Bitbucket user.'
})

// Check if current user has permission to delete scores
// Requires 'review_admin' role or higher (has 'delete' permission on 'scores')
const canDeleteAnyScore = computed(() => {
  const roles = authStore.user?.roles || []
  // Only review_admin and system_admin have delete permission
  return roles.includes('review_admin') || roles.includes('system_admin')
})

// Check if current user has permission to delete reviews
// Requires 'review_admin' role or higher (has 'delete' permission on 'reviews')
const canDeleteReview = computed(() => {
  const roles = authStore.user?.roles || []
  // Only review_admin and system_admin can delete reviews
  return roles.includes('review_admin') || roles.includes('system_admin')
})

// Configure MdEditor to use English
config({
  editorConfig: {
    languageUserDefined: {
      'en-US': {
        toolbarTips: {
          bold: 'Bold',
          underline: 'Underline',
          italic: 'Italic',
          strikeThrough: 'Strikethrough',
          title: 'Title',
          sub: 'Subscript',
          sup: 'Superscript',
          quote: 'Quote',
          unorderedList: 'Unordered List',
          orderedList: 'Ordered List',
          codeRow: 'Inline Code',
          code: 'Code Block',
          link: 'Link',
          image: 'Image',
          table: 'Table',
          revoke: 'Undo',
          next: 'Redo',
          save: 'Save',
          prettier: 'Format',
          pageFullscreen: 'Page Fullscreen',
          fullscreen: 'Fullscreen',
          preview: 'Preview',
          htmlPreview: 'HTML Preview',
          catalog: 'Catalog',
        },
        titleItem: {
          h1: 'Heading 1',
          h2: 'Heading 2',
          h3: 'Heading 3',
          h4: 'Heading 4',
          h5: 'Heading 5',
          h6: 'Heading 6',
        },
        imgTitleItem: {
          link: 'Add Image Link',
          upload: 'Upload Image',
          clip2upload: 'Clip and Upload',
        },
        linkModalTips: {
          linkTitle: 'Add Link',
          imageTitle: 'Add Image',
          descLabel: 'Description:',
          descLabelPlaceHolder: 'Enter description...',
          urlLabel: 'Link URL:',
          urlLabelPlaceHolder: 'Enter URL...',
          buttonOK: 'OK',
        },
        clipModalTips: {
          title: 'Crop Image',
          buttonUpload: 'Upload',
        },
        copyCode: {
          text: 'Copy',
          successTips: 'Copied!',
          failTips: 'Copy failed!',
        },
        mermaid: {
          flow: 'Flowchart',
          sequence: 'Sequence Diagram',
          gantt: 'Gantt Chart',
          class: 'Class Diagram',
          state: 'State Diagram',
          pie: 'Pie Chart',
          relationship: 'Relationship Diagram',
          journey: 'Journey Diagram',
        },
        katex: {
          inline: 'Inline Formula',
          block: 'Block Formula',
        },
        footer: {
          markdownTotal: 'Words',
          scrollAuto: 'Sync Scroll',
        },
      },
    },
  },
})

// Toolbar configuration
const toolbars: ToolbarNames[] = [
  'bold',
  'underline',
  'italic',
  'strikeThrough',
  '-',
  'title',
  'sub',
  'sup',
  'quote',
  'unorderedList',
  'orderedList',
  '-',
  'codeRow',
  'code',
  'link',
  'image',
  'table',
  '-',
  'revoke',
  'next',
  'save',
  '=',
  'pageFullscreen',
  'fullscreen',
  'preview',
  'htmlPreview',
  'catalog',
]

const scoreForm = reactive<ScoreCreate>({
  pull_request_id: '',
  pull_request_commit_id: '',
  project_key: '',
  repository_slug: '',
  reviewer: '',
  score: 0,
  reviewer_comments: undefined,  // Use undefined instead of null for MdEditor compatibility
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

const getReviewerDisplayName = (reviewData: Review | null) => {
  if (!reviewData) return 'Unassigned'

  return (
    reviewData.reviewer_info?.display_name ||
    reviewData.reviewer ||
    reviewData.pull_request_user_info?.display_name ||
    reviewData.pull_request_user ||
    'Unassigned'
  )
}

const normalizeNavigationValue = (value: string | null | undefined) => value || ''

const currentReviewIndex = computed(() => {
  const projectKey = normalizeRouteQueryValue(route.query.projectKey)
  const repositorySlug = normalizeRouteQueryValue(route.query.repositorySlug)
  const pullRequestId = normalizeRouteQueryValue(route.query.pullRequestId)
  const reviewer = normalizeRouteQueryValue(route.query.reviewer)
  const sourceFilename = normalizeRouteQueryValue(route.query.sourceFilename)

  return reviewNavigationStore.items.findIndex(item => {
    return (
      item.id === Number(route.params.id) &&
      item.projectKey === normalizeNavigationValue(projectKey) &&
      item.repositorySlug === normalizeNavigationValue(repositorySlug) &&
      item.pullRequestId === normalizeNavigationValue(pullRequestId) &&
      item.reviewer === normalizeNavigationValue(reviewer) &&
      item.sourceFilename === normalizeNavigationValue(sourceFilename)
    )
  })
})

const nextReview = computed<ReviewNavigationItem | null>(() => {
  if (currentReviewIndex.value < 0) {
    return null
  }

  return reviewNavigationStore.items[currentReviewIndex.value + 1] || null
})

const previousReview = computed<ReviewNavigationItem | null>(() => {
  if (currentReviewIndex.value <= 0) {
    return null
  }

  return reviewNavigationStore.items[currentReviewIndex.value - 1] || null
})

const normalizeRouteQueryValue = (value: unknown): string | null => {
  if (typeof value !== 'string') return null
  return value.length > 0 ? value : null
}

const findMatchingReview = (items: Review[], id: number): Review | null => {
  const routeReviewer = normalizeRouteQueryValue(route.query.reviewer)
  const routeSourceFilename = normalizeRouteQueryValue(route.query.sourceFilename)

  const matchedByComposite = items.find(item => {
    const reviewerMatches = (item.reviewer || null) === routeReviewer
    const sourceFilenameMatches = (item.source_filename || null) === routeSourceFilename
    return reviewerMatches && sourceFilenameMatches
  })

  if (matchedByComposite) {
    return matchedByComposite
  }

  return items.find(item => item.id === id) || items[0] || null
}

const loadReview = async () => {
  const id = Number(route.params.id)
  if (!id) return

  const projectKey = normalizeRouteQueryValue(route.query.projectKey)
  const repositorySlug = normalizeRouteQueryValue(route.query.repositorySlug)
  const pullRequestId = normalizeRouteQueryValue(route.query.pullRequestId)

  loading.value = true
  try {
    if (projectKey && repositorySlug && pullRequestId) {
      const response = await reviewsApi.getReviewByCompositeKey(
        projectKey,
        repositorySlug,
        pullRequestId,
        {
          reviewer: normalizeRouteQueryValue(route.query.reviewer) || undefined,
          source_filename: normalizeRouteQueryValue(route.query.sourceFilename) || undefined,
        }
      )
      review.value = findMatchingReview(response.items, id)
    } else {
      review.value = await reviewsApi.getReviewById(id)
    }
    
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
    // Set score form defaults
    scoreForm.pull_request_id = review.value.pull_request_id
    scoreForm.pull_request_commit_id = review.value.pull_request_commit_id || ''
    scoreForm.project_key = review.value.project_key
    scoreForm.repository_slug = review.value.repository_slug
    scoreForm.reviewer = effectiveReviewerUsername.value || ''
    scoreForm.source_filename = review.value.source_filename || null
  } catch (error) {
    console.error('Failed to load review:', error)
    ElMessage.error('Failed to load review')
    router.push('/reviews')
  } finally {
    loading.value = false
  }
}

const goToNextReview = () => {
  if (!nextReview.value) {
    return
  }

  router.replace({
    name: 'ReviewDetail',
    params: { id: nextReview.value.id },
    query: {
      projectKey: nextReview.value.projectKey,
      repositorySlug: nextReview.value.repositorySlug,
      pullRequestId: nextReview.value.pullRequestId,
      reviewer: nextReview.value.reviewer,
      sourceFilename: nextReview.value.sourceFilename,
    },
  })
}

const goToPreviousReview = () => {
  if (!previousReview.value) {
    return
  }

  router.replace({
    name: 'ReviewDetail',
    params: { id: previousReview.value.id },
    query: {
      projectKey: previousReview.value.projectKey,
      repositorySlug: previousReview.value.repositorySlug,
      pullRequestId: previousReview.value.pullRequestId,
      reviewer: previousReview.value.reviewer,
      sourceFilename: previousReview.value.sourceFilename,
    },
  })
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
        scoreForm.reviewer_comments = undefined
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
  scoreForm.reviewer_comments = score.reviewer_comments ?? undefined  // Convert null to undefined
  showScoreDialog.value = true
}

const canEditScore = (score: Score): boolean => {
  return effectiveReviewerUsername.value === score.reviewer
}

const canDeleteScore = (score: Score): boolean => {
  return effectiveReviewerUsername.value === score.reviewer
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

const toggleInfoCollapse = () => {
  isInfoExpanded.value = !isInfoExpanded.value
}

const handleCloseDialog = () => {
  showScoreDialog.value = false
  editingScore.value = null
  // Reset form
  scoreForm.score = 0
  scoreForm.reviewer_comments = undefined
}

// Watch for dialog open to set reviewer
watch(showScoreDialog, (isOpen) => {
  if (isOpen && review.value) {
    if (!canCreateScore.value) {
      ElMessage.warning(scoreActionDisabledReason.value)
      showScoreDialog.value = false
      return
    }

    // Always set reviewer to current user
    const currentUsername = effectiveReviewerUsername.value || ''
    scoreForm.reviewer = currentUsername
    
    // Check if current user already has a score for this review
    const existingScore = scores.value.find(s => s.reviewer === currentUsername)
    
    if (existingScore) {
      // User already has a score, enter edit mode
      editingScore.value = existingScore
      scoreForm.score = existingScore.score
      scoreForm.reviewer_comments = existingScore.reviewer_comments || ''
    } else {
      // No existing score, reset form for new score
      editingScore.value = null
      scoreForm.score = 0
      scoreForm.reviewer_comments = ''
    }
  }
})

// Watch for theme changes and force re-render of MdEditor
watch(isDarkTheme, () => {
  // Force re-computation by accessing the computed property
  void isDarkTheme.value
})

onMounted(() => {
  loadReview()
})

watch(
  () => route.fullPath,
  () => {
    loadReview()
  }
)
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

.detail-navigation-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.detail-navigation-button {
  width: 104px;
}

.detail-navigation-position {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--el-text-color-secondary);
  font-size: 13px;
  width: 104px;
  height: 32px;
  text-align: center;
  box-sizing: border-box;
  border-radius: 999px;
  background: var(--el-fill-color-light);
  border: 1px solid var(--el-border-color-lighter);
  font-weight: 500;
}

.content-row {
  margin-top: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-title-wrapper {
  display: flex;
  align-items: center;
  user-select: none;
}

.collapse-icon {
  font-size: 16px;
  color: var(--el-text-color-secondary);
}

.collapse-icon.is-collapsed {
  transform: rotate(-90deg);
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.reviewer-avatar {
  vertical-align: middle;
  margin-right: 8px;
  background: linear-gradient(135deg, #2563eb 0%, #0f766e 100%);
  color: #ffffff;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.02em;
  box-shadow: 0 1px 3px rgba(37, 99, 235, 0.22);
}

[data-theme='dark'] .reviewer-avatar {
  background: linear-gradient(135deg, #3b82f6 0%, #14b8a6 100%);
  box-shadow: 0 1px 4px rgba(20, 184, 166, 0.18);
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
  /* Responsive height based on viewport */
  height: calc(100vh - 380px);
  min-height: 500px;
  max-height: 800px;
  display: flex;
  flex-direction: column;
}

[data-theme='dark'] .analysis-column {
  background: #1e293b;
  border-color: #334155;
}

.analysis-column-header {
  background: var(--el-fill-color-light);
  color: var(--el-text-color-primary);
  border-bottom: 1px solid var(--el-border-color-light);
  padding: 12px 16px;
  font-weight: 600;
  font-size: 0.95rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-shrink: 0; /* Prevent header from shrinking */
  overflow: hidden; /* Ensure no scrollbar in header */
}

[data-theme='dark'] .analysis-column-header {
  background: #0f172a;
  color: var(--el-text-color-primary);
  border-bottom-color: #334155;
}

:deep(.diff-format-toggle) {
  display: inline-flex;
  align-items: center;
  padding: 2px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-fill-color-extra-light);
  box-shadow: none;
}

:deep(.diff-format-toggle .el-radio-button__inner) {
  min-width: 104px;
  height: 30px;
  padding: 0 12px;
  border: 0 !important;
  border-radius: 6px !important;
  background: transparent;
  color: var(--el-text-color-regular);
  font-size: 12px;
  font-weight: 500;
  line-height: 30px;
  box-shadow: none !important;
  transition: background-color 0.2s ease, color 0.2s ease;
}

:deep(.diff-format-toggle .el-radio-button:first-child .el-radio-button__inner),
:deep(.diff-format-toggle .el-radio-button:last-child .el-radio-button__inner) {
  border-radius: 6px !important;
}

:deep(.diff-format-toggle .el-radio-button__original-radio:checked + .el-radio-button__inner) {
  background: var(--el-fill-color-dark);
  color: var(--el-text-color-primary);
  font-weight: 600;
}

:deep(.diff-format-toggle .el-radio-button:not(.is-active) .el-radio-button__inner:hover) {
  background: var(--el-fill-color);
  color: var(--el-text-color-primary);
}

[data-theme='dark'] :deep(.diff-format-toggle) {
  background: #0f172a;
  border-color: #1e293b;
  box-shadow: none;
}

[data-theme='dark'] :deep(.diff-format-toggle .el-radio-button__inner) {
  color: #cbd5e1;
}

[data-theme='dark'] :deep(.diff-format-toggle .el-radio-button__original-radio:checked + .el-radio-button__inner) {
  background: #334155;
  color: #f8fafc;
}

[data-theme='dark'] :deep(.diff-format-toggle .el-radio-button:not(.is-active) .el-radio-button__inner:hover) {
  background: #172033;
  color: #f8fafc;
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

/* Responsive adjustments for smaller screens */
@media (max-width: 768px) {
  .analysis-column {
    height: calc(100vh - 320px);
    min-height: 400px;
  }
}

@media (min-width: 1920px) {
  .analysis-column {
    height: calc(100vh - 350px);
    max-height: 900px;
  }
}

@media (min-width: 2560px) {
  .analysis-column {
    height: calc(100vh - 320px);
    max-height: 1000px;
  }
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

/* MdEditor custom styles */
:deep(.md-editor) {
  border-radius: 6px;
  overflow: hidden;
  border: 1px solid var(--el-border-color);
  transition: all 0.3s ease;
}

/* Light theme customization */
:deep(.md-editor) {
  --md-bk-color: #ffffff;
  --md-color: var(--el-text-color-primary);
  --md-bk-color-outstand: #f8fafc;
  --md-border-color: var(--el-border-color);
  --md-scrollbar-bg-color: #f1f5f9;
  --md-scrollbar-thumb-color: #cbd5e1;
}

/* Dark theme customization */
[data-theme='dark'] :deep(.md-editor) {
  --md-bk-color: #1e293b !important;
  --md-color: #cbd5e1 !important;
  --md-bk-color-outstand: #0f172a !important;
  --md-border-color: #334155 !important;
  --md-scrollbar-bg-color: #0f172a !important;
  --md-scrollbar-thumb-color: #475569 !important;
}

/* Toolbar styling */
:deep(.md-editor-toolbar) {
  background: var(--el-fill-color-light);
  border-bottom: 1px solid var(--el-border-color);
  transition: all 0.3s ease;
}

[data-theme='dark'] :deep(.md-editor-toolbar) {
  background: #1e293b;
  border-bottom-color: #334155;
}

/* Toolbar button hover */
:deep(.md-editor-toolbar-item:hover) {
  background: var(--el-fill-color);
  color: var(--el-text-color-primary);
}

[data-theme='dark'] :deep(.md-editor-toolbar-item:hover) {
  background: #334155;
  color: #cbd5e1;
}

/* Active toolbar button */
:deep(.md-editor-toolbar-item.active) {
  color: #3b82f6;
}

[data-theme='dark'] :deep(.md-editor-toolbar-item.active) {
  color: #60a5fa;
}

/* Editor content area - textarea */
:deep(.md-editor-content) {
  background: white;
  transition: background 0.3s ease;
}

[data-theme='dark'] :deep(.md-editor-content) {
  background: #1e293b;
}

/* Textarea itself */
:deep(.md-editor-textarea) {
  background: white;
  color: var(--el-text-color-primary);
}

[data-theme='dark'] :deep(.md-editor-textarea) {
  background: #1e293b !important;
  color: #cbd5e1 !important;
}

/* Preview area */
:deep(.md-editor-preview) {
  background: white;
  color: var(--el-text-color-primary);
  transition: all 0.3s ease;
}

[data-theme='dark'] :deep(.md-editor-preview) {
  background: #1e293b !important;
  color: #cbd5e1 !important;
}

/* Code block styling */
:deep(.md-editor-preview pre) {
  background: #f1f5f9;
  border: 1px solid var(--el-border-color);
  transition: all 0.3s ease;
}

[data-theme='dark'] :deep(.md-editor-preview pre) {
  background: #0f172a;
  border-color: #334155;
}

/* Inline code */
:deep(.md-editor-preview code) {
  background: var(--el-fill-color-light);
  color: var(--el-text-color-primary);
  transition: all 0.3s ease;
}

[data-theme='dark'] :deep(.md-editor-preview code) {
  background: #334155;
  color: #cbd5e1;
}

/* Links */
:deep(.md-editor-preview a) {
  color: #3b82f6;
  transition: color 0.2s ease;
}

:deep(.md-editor-preview a:hover) {
  color: #2563eb;
}

[data-theme='dark'] :deep(.md-editor-preview a) {
  color: #60a5fa;
}

[data-theme='dark'] :deep(.md-editor-preview a:hover) {
  color: #93c5fd;
}

/* Blockquote */
:deep(.md-editor-preview blockquote) {
  border-left-color: #3b82f6;
  background: var(--el-fill-color-lighter);
  color: var(--el-text-color-regular);
  transition: all 0.3s ease;
}

[data-theme='dark'] :deep(.md-editor-preview blockquote) {
  background: #0f172a;
  border-left-color: #60a5fa;
  color: #94a3b8;
}

/* Table styling */
:deep(.md-editor-preview table) {
  border-color: var(--el-border-color);
}

:deep(.md-editor-preview table th),
:deep(.md-editor-preview table td) {
  border-color: var(--el-border-color);
  transition: all 0.3s ease;
}

[data-theme='dark'] :deep(.md-editor-preview table th),
[data-theme='dark'] :deep(.md-editor-preview table td) {
  border-color: #334155;
  background: #0f172a;
}

[data-theme='dark'] :deep(.md-editor-preview table th) {
  background: #1e293b;
}

/* Input area placeholder */
:deep(.md-editor-textarea::placeholder) {
  color: var(--el-text-color-placeholder);
}

[data-theme='dark'] :deep(.md-editor-textarea::placeholder) {
  color: #64748b;
}

/* Ensure all editor child elements inherit correct colors */
[data-theme='dark'] :deep(.md-editor-input) {
  background: #1e293b;
  color: #cbd5e1;
}

/* CodeMirror or other editor internals */
[data-theme='dark'] :deep(.cm-editor) {
  background: #1e293b;
  color: #cbd5e1;
}

[data-theme='dark'] :deep(.cm-content) {
  background: #1e293b;
  color: #cbd5e1;
}

[data-theme='dark'] :deep(.cm-gutters) {
  background: #0f172a;
  border-right-color: #334155;
  color: #64748b;
}

[data-theme='dark'] :deep(.cm-activeLineGutter) {
  background: #334155;
  color: #cbd5e1;
}

.editor-hint {
  padding: 6px 12px;
  background: var(--el-fill-color-lighter);
  font-size: 0.75rem;
  color: var(--el-text-color-secondary);
  border-radius: 4px;
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

/* MdEditor global dark mode overrides */
[data-theme='dark'] .md-editor {
  --md-bk-color: #1e293b !important;
  --md-color: #cbd5e1 !important;
}

[data-theme='dark'] .md-editor textarea,
[data-theme='dark'] .md-editor .md-editor-content,
[data-theme='dark'] .md-editor .md-editor-preview {
  background-color: #1e293b !important;
  color: #cbd5e1 !important;
}
</style>
