<template>
  <div class="review-detail" v-loading="loading">
    <el-page-header @back="$router.back()" :title="t('reviews.detail.back')">
      <template #content>
        <span class="header-content-title">{{ t('reviews.detail.title') }}</span>
      </template>
      <template #extra>
        <div class="detail-navigation-actions">
          <!-- Display format: "Page X - Y/Z" matching Code Reviews style -->
          <span v-if="currentReviewIndex >= 0" class="detail-navigation-position">
            {{ t('common.page') }} {{ reviewNavigationStore.currentPage }} · {{ currentReviewIndex + 1 }}/{{ reviewNavigationStore.items.length }}
          </span>
          <el-button 
            class="detail-navigation-button" 
            :disabled="!canGoToPreviousPage || navigatingPage"
            @click="goToPreviousReview"
          >
            <el-icon><ArrowLeft /></el-icon>
            {{ t('reviews.detail.previous') }}
          </el-button>
          
          <el-button 
            class="detail-navigation-button" 
            :disabled="!canGoToNextPage || navigatingPage"
            @click="goToNextReview"
          >
            {{ t('reviews.detail.next') }}
            <el-icon><ArrowRight /></el-icon>
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
            <div class="card-header" @click="toggleInfoCollapse">
              <div class="card-title-wrapper">
                <el-icon 
                  :class="['collapse-icon', { 'is-collapsed': !isInfoExpanded }]" 
                >
                  <ArrowDown />
                </el-icon>
                <span class="card-title">{{ t('reviews.detail.review_information') }} (#{{ review.pull_request_id }})</span>
              </div>
              <div class="card-meta-info">
                <div class="meta-item">
                  <el-icon><UserFilled /></el-icon>
                  <span>{{ review.pull_request_user_info?.display_name || review.pull_request_user }}</span>
                </div>
                <el-divider direction="vertical" />
                <div class="meta-item">
                  <el-icon><FolderOpened /></el-icon>
                  <span><strong>{{ review.project_key }}</strong> / {{ review.repository_slug }}</span>
                </div>
              </div>
              <div class="card-actions" @click.stop>
                <el-space>
                <!-- Pin/Flag Toggle Button -->
                <el-tooltip
                  :content="review.is_pinned_by_me ? t('reviews.unpin_tip', 'Unpin this review') : t('reviews.pin_tip', 'Pin this review')"
                  placement="top"
                >
                  <span
                    class="pin-cell-btn"
                    :class="{ 'pinned-active': review.is_pinned_by_me }"
                    @click="handleTogglePin"
                  >
                    <el-icon :size="15">
                      <StarFilled v-if="review.is_pinned_by_me" />
                      <Star v-else />
                    </el-icon>
                  </span>
                </el-tooltip>
                <!-- Add Score Button - Only show if user has permission -->
                <template v-if="hasScorePermissionRole">
                  <el-tooltip
                    v-if="currentUserHasScore"
                    :content="t('reviews.detail.already_has_score')"
                    placement="top"
                  >
                    <span>
                      <el-button type="success" size="small" disabled>
                        <el-icon><Plus /></el-icon>
                        {{ t('reviews.detail.add_score') }}
                      </el-button>
                    </span>
                  </el-tooltip>
                  <el-tooltip v-else-if="!canCreateScore" :content="scoreActionDisabledReason" placement="top">
                    <span>
                      <el-button type="success" size="small" disabled>
                        <el-icon><Plus /></el-icon>
                        {{ t('reviews.detail.add_score') }}
                      </el-button>
                    </span>
                  </el-tooltip>
                  <el-button v-else type="success" size="small" @click="showScoreDialog = true">
                    <el-icon><Plus /></el-icon>
                    {{ t('reviews.detail.add_score') }}
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
                  {{ t('reviews.detail.delete') }}
                </el-button>
              </el-space>
              </div>
            </div>
          </template>

          <el-collapse-transition>
            <el-descriptions v-if="isInfoExpanded" :column="3" border size="default">
              <el-descriptions-item :label="t('reviews.detail.pr_id')" label-align="right">
                <a 
                  v-if="review && getPrUrl(review)" 
                  :href="getPrUrl(review) || undefined" 
                  target="_blank" 
                  rel="noopener noreferrer"
                  class="pr-link"
                >
                  <el-tag type="info" size="small">
                    {{ review.pull_request_id }}
                    <el-icon style="margin-left: 4px;"><Link /></el-icon>
                  </el-tag>
                </a>
                <el-tag v-else type="info" size="small">{{ review?.pull_request_id }}</el-tag>
              </el-descriptions-item>
              <el-descriptions-item :label="t('reviews.detail.commit_id')" v-if="review.pull_request_commit_id" label-align="right">
                <el-tag type="success" size="small">{{ review.pull_request_commit_id.substring(0, 8) }}</el-tag>
              </el-descriptions-item>
              <el-descriptions-item :label="t('reviews.detail.project')" label-align="right">
                <strong>{{ review.project_key }}</strong> / {{ review.repository_slug }}
              </el-descriptions-item>
              <el-descriptions-item :label="t('reviews.detail.pr_user')" label-align="right">
                <el-avatar :size="24" class="reviewer-avatar">{{ getInitials(getReviewerDisplayName(review)) }}</el-avatar>
                {{ getReviewerDisplayName(review) }}
              </el-descriptions-item>
              <el-descriptions-item :label="t('reviews.detail.status')" label-align="right">
                <el-tag :type="getStatusType(review.pull_request_status)" effect="dark">
                  {{ review.pull_request_status }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item :label="t('reviews.detail.level')" label-align="right">
                <el-tag :type="review.source_filename ? 'warning' : 'success'" size="small">
                  {{ review.source_filename ? t('reviews.detail.file_level') : t('reviews.detail.pr_level') }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item :label="t('reviews.detail.summary')" :span="3" label-align="right">
                <div class="summary-text" :class="{ 'na-text': !review.reviewer_comments }">{{ review.reviewer_comments || t('reviews.detail.no_summary') }}</div>
              </el-descriptions-item>
              <el-descriptions-item :label="t('reviews.detail.pr_title')" :span="3" label-align="right">
                <span :class="{ 'na-text': !review?.metadata?.pull_request_title }">{{ review?.metadata?.pull_request_title || 'N/A' }}</span>
              </el-descriptions-item>
              <el-descriptions-item :label="t('reviews.detail.pr_description')" :span="3" label-align="right">
                <div class="pr-description-text" :class="{ 'na-text': !review?.metadata?.pull_request_description }">{{ review?.metadata?.pull_request_description || 'N/A' }}</div>
              </el-descriptions-item>
              <el-descriptions-item :label="t('reviews.detail.created')" label-align="right">
                <el-icon><Clock /></el-icon> {{ formatDate(review.created_date || '') }}
              </el-descriptions-item>
              <el-descriptions-item :label="t('reviews.detail.updated')" label-align="right">
                <el-icon><Clock /></el-icon> {{ formatDate(review.updated_date || '') }}
              </el-descriptions-item>
            </el-descriptions>
          </el-collapse-transition>
        </el-card>

        <!-- Dual Column Layout: Code Diff + AI Review -->
        <el-row :gutter="16" style="margin-top: 16px" v-if="review.git_code_diff">
          <!-- Code Diff Column -->
          <el-col :xs="24" :sm="24" :md="14" :lg="14" :xl="15">
            <div class="analysis-column">
              <div class="analysis-column-header">
                <span>{{ t('reviews.detail.code_changes') }}</span>
                <el-radio-group v-model="diffFormat" size="small" class="diff-format-toggle">
                  <el-radio-button value="line-by-line">{{ t('reviews.detail.line_by_line') }}</el-radio-button>
                  <el-radio-button value="side-by-side">{{ t('reviews.detail.side_by_side') }}</el-radio-button>
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

          <!-- AI Review Column - Always shown with placeholder if no data -->
          <el-col :xs="24" :sm="24" :md="10" :lg="10" :xl="9">
            <div class="analysis-column">
              <div class="analysis-column-header ai-review-header">
                <span class="ai-review-title">
                  {{ t('reviews.detail.ai_review_result') }}
                  <el-tag v-if="review.ai_review_id" size="small" type="info" style="margin-left: 8px">
                    {{ review.ai_review_id }}
                    <el-button
                      v-if="review.ai_review_id"
                      size="small"
                      text
                      @click.stop="copyToClipboard(review.ai_review_id!)"
                      style="margin-left: 4px; padding: 0 2px; min-height: auto;"
                    >
                      <el-icon :size="14"><CopyDocument /></el-icon>
                    </el-button>
                  </el-tag>
                </span>
                <div class="ai-review-header-actions">
                  <el-button
                    v-if="review.ai_suggestions"
                    size="small"
                    text
                    @click="aiReviewRef?.downloadScreenshot?.()"
                  >
                    <el-icon><Download /></el-icon>
                    {{ t('reviews.detail.screenshot_download') }}
                  </el-button>
                  <el-button
                    v-if="review.ai_suggestions"
                    size="small"
                    text
                    @click="aiReviewRef?.copyScreenshot?.()"
                  >
                    <el-icon><CopyDocument /></el-icon>
                    {{ t('reviews.detail.screenshot_copy') }}
                  </el-button>
                </div>
              </div>
              <div class="analysis-column-body">
                <!-- Show AI results if available -->
                <AIReviewResults
                  ref="aiReviewRef"
                  v-if="review.ai_suggestions"
                  :suggestions="review.ai_suggestions"
                  :ai-review-id="review.ai_review_id || ''"
                  :pr-user="(review.pull_request_user_info?.display_name || review.pull_request_user) || ''"
                  :pr-id="review.pull_request_id || ''"
                  :commit-id="review.pull_request_commit_id || ''"
                  :project-info="review.project_key + ' / ' + review.repository_slug"
                />
                
                <!-- Placeholder when no AI suggestions -->
                <div v-else class="no-ai-results-placeholder">
                  <el-empty
                    :image-size="120"
                    :description="t('reviews.detail.no_ai_results', 'No AI review results available')"
                  >
                    <template #image>
                      <el-icon :size="80" color="var(--el-text-color-secondary)">
                        <InfoFilled />
                      </el-icon>
                    </template>
                    <p class="placeholder-hint">
                      {{ t('reviews.detail.no_ai_hint', 'This PR was submitted without AI analysis. AI suggestions will appear here when available.') }}
                    </p>
                  </el-empty>
                </div>
              </div>
            </div>
          </el-col>
        </el-row>

        <!-- Scores Section -->
        <el-card class="scores-card" style="margin-top: 20px; margin-bottom: 40px">
          <template #header>
            <div class="card-header" @click="toggleScoresCollapse">
              <span class="card-title">
                <el-icon 
                  :class="['collapse-icon', { 'is-collapsed': !isScoresExpanded }]" 
                >
                  <ArrowDown />
                </el-icon>
                {{ t('reviews.detail.scores') }} ({{ scores.length }})
              </span>
              <div class="card-actions" @click.stop>
                <!-- Add Score Button - Only show if user has permission -->
                <template v-if="hasScorePermissionRole">
                  <el-tooltip
                    v-if="currentUserHasScore"
                    :content="t('reviews.detail.already_has_score_short')"
                    placement="top"
                  >
                    <span>
                      <el-button type="primary" size="small" disabled>
                        <el-icon><Plus /></el-icon>
                        {{ t('reviews.detail.add_score') }}
                      </el-button>
                    </span>
                  </el-tooltip>
                  <el-tooltip v-else-if="!canCreateScore" :content="scoreActionDisabledReason" placement="top">
                    <span>
                      <el-button type="primary" size="small" disabled>
                        <el-icon><Plus /></el-icon>
                        {{ t('reviews.detail.add_score') }}
                      </el-button>
                    </span>
                  </el-tooltip>
                  <el-button v-else type="primary" size="small" @click="showScoreDialog = true">
                    <el-icon><Plus /></el-icon>
                    {{ t('reviews.detail.add_score') }}
                  </el-button>
                </template>
              </div>
            </div>
          </template>

          <el-collapse-transition>
            <div v-if="isScoresExpanded">
              <el-table :data="scores" stripe>
                <el-table-column prop="reviewer" :label="t('reviews.detail.reviewer')" width="200">
                  <template #default="{ row }">
                    <div class="reviewer-cell">
                      <span>{{ row.reviewer_info?.display_name || row.reviewer }}</span>
                      <el-tag 
                        v-if="row.reviewer === review?.reviewer" 
                        size="small" 
                        type="primary" 
                        effect="plain"
                        class="primary-reviewer-badge"
                      >
                        {{ t('reviews.detail.primary_reviewer') }}
                      </el-tag>
                    </div>
                  </template>
                </el-table-column>
                <el-table-column :label="t('reviews.detail.ai_review_id')" min-width="200" align="center">
                  <template #default>
                    <div v-if="review?.ai_review_id" class="ai-review-id-cell">
                      <el-tag size="small" type="info">
                        {{ review.ai_review_id }}
                      </el-tag>
                      <el-button
                        size="small"
                        text
                        @click="copyToClipboard(review.ai_review_id!)"
                      >
                        <el-icon><CopyDocument /></el-icon>
                      </el-button>
                    </div>
                    <span v-else class="empty-value">{{ t('reviews.detail.na') }}</span>
                  </template>
                </el-table-column>
                <el-table-column prop="score" :label="t('reviews.detail.score')" width="120">
                  <template #default="{ row }">
                    <span :class="['score-value', getScoreColorClass(row.score)]">{{ row.score }}</span>
                    <span v-if="row.max_score" class="score-max"> / {{ row.max_score }}</span>
                  </template>
                </el-table-column>
                <el-table-column prop="reviewer_comments" :label="t('reviews.detail.comments')" min-width="200" show-overflow-tooltip />
                <el-table-column prop="created_date" :label="t('reviews.detail.created')" width="160">
                  <template #default="{ row }">
                    {{ formatDate(row.created_date || '') }}
                  </template>
                </el-table-column>
                <el-table-column prop="updated_date" :label="t('reviews.detail.updated')" width="160">
                  <template #default="{ row }">
                    {{ row.updated_date ? formatDate(row.updated_date) : '-' }}
                  </template>
                </el-table-column>
                <el-table-column :label="t('reviews.detail.actions')" width="180">
                  <template #default="{ row }">
                    <!-- Update button: 
                         - reviewer: can only update their own score
                         - review_admin: CANNOT update others' scores (only delete)
                    -->
                    <el-button 
                      v-if="hasScorePermissionRole && canEditScore(row)"
                      size="small" 
                      type="primary" 
                      @click="editScore(row)"
                    >
                      {{ t('reviews.detail.update') }}
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
                      {{ t('reviews.detail.delete') }}
                    </el-button>
                  </template>
                </el-table-column>
              </el-table>

              <el-empty v-if="scores.length === 0" :description="t('reviews.detail.no_scores')" />
            </div>
          </el-collapse-transition>
        </el-card>
      </el-col>
    </el-row>

    <!-- Add Score Dialog -->
    <el-dialog 
      v-model="showScoreDialog" 
      :title="editingScore ? t('reviews.detail.update_score') : t('reviews.detail.add_score')" 
      width="1100px"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
      show-close
      top="5vh"
      class="score-dialog"
    >
      <!-- Score Range Guide -->
      <ScoreRangeGuide />
      
      <el-form :model="scoreForm" :rules="scoreRules" ref="scoreFormRef" label-width="120px">
        <el-form-item :label="t('reviews.detail.reviewer')">
          <el-input 
            v-model="scoreForm.reviewer" 
            disabled
            :placeholder="t('reviews.detail.current_user')"
          >
            <template #prefix>
              <el-icon><User /></el-icon>
            </template>
          </el-input>
          <div class="form-item-hint">
            {{ t('reviews.detail.score_attributed') }}
          </div>
        </el-form-item>
        
        <el-form-item :label="t('reviews.detail.score')" prop="score">
          <div class="score-input-container">
            <!-- Visual Score Bar -->
            <div class="score-visual-bar">
              <div class="score-track"></div>
              <div class="score-indicator-range">
                <div 
                  class="score-indicator" 
                  :style="{ left: `${(scoreForm.score / 10) * 100}%` }"
                  :class="getScoreColorClass(scoreForm.score)"
                >
                  {{ scoreForm.score.toFixed(1) }}
                </div>
              </div>
              <div class="score-labels">
                <span>0</span>
                <span>5</span>
                <span>10</span>
              </div>
            </div>
            
            <!-- Quick Buttons -->
            <QuickScoreButtons @select="handleQuickScoreSelect" />
            
            <!-- Manual Input -->
            <div class="score-input-wrapper">
              <el-input-number 
                v-model="scoreForm.score" 
                :min="0" 
                :max="10" 
                :step="0.5"
                :precision="1"
                controls-position="right"
                style="width: 100%"
              />
            </div>
          </div>
          <div class="form-item-hint">
            {{ t('reviews.detail.quick_buttons_hint') }}
          </div>
        </el-form-item>
        
        <el-form-item :label="t('reviews.detail.comment_template')">
          <div class="template-picker-row">
            <el-select
              v-model="selectedTemplate"
              :placeholder="t('reviews.detail.comment_template_placeholder')"
              clearable
              class="template-select"
              @change="handleTemplateSelect"
            >
              <el-option-group
                v-if="availableTemplates.length"
                :label="t('reviews.detail.tpl_group_recommended')"
              >
                <el-option
                  v-for="tpl in availableTemplates"
                  :key="tpl.id"
                  :label="t(`reviews.detail.tpl_${tpl.id}`)"
                  :value="tpl.id"
                />
              </el-option-group>
              <el-option-group
                v-if="canManagePersonalTemplates && personalTemplates.length"
                :label="t('reviews.detail.tpl_group_personal')"
              >
                <el-option
                  v-for="tpl in personalTemplates"
                  :key="`personal-${tpl.id}`"
                  :label="tpl.name"
                  :value="`personal:${tpl.id}`"
                />
              </el-option-group>
            </el-select>
            <el-tooltip
              v-if="canManagePersonalTemplates"
              :content="t('reviews.detail.save_template_tooltip')"
              placement="top"
            >
              <el-button
                :icon="Plus"
                circle
                :disabled="!scoreForm.reviewer_comments"
                @click="handleSaveAsPersonalTemplate"
              />
            </el-tooltip>
          </div>
          <div class="form-item-hint">
            {{ t('reviews.detail.comment_template_hint') }}
          </div>
        </el-form-item>

        <el-form-item :label="t('reviews.detail.comments')">
          <MdEditor
            v-model="scoreForm.reviewer_comments"
            :toolbars="toolbars"
            :theme="isDarkTheme ? 'dark' : 'light'"
            language="en-US"
            preview-theme="vuepress"
            code-theme="atom"
            class="score-md-editor"
            :placeholder="t('reviews.detail.comments_placeholder')"
          />
          <div class="editor-hint">
            {{ t('reviews.detail.markdown_hint') }}
          </div>
        </el-form-item>
      </el-form>
      
      <template #footer>
        <el-button @click="handleCloseDialog">{{ t('reviews.detail.cancel') }}</el-button>
        <el-button type="primary" :loading="addingScore" @click="handleAddScore">
          {{ editingScore ? t('reviews.detail.update_score') : t('reviews.detail.add_score') }}
        </el-button>
      </template>
    </el-dialog>

    <!-- Floating Navigation Buttons -->
    <div 
      v-if="reviewNavigationStore.items.length > 1"
      class="floating-navigation"
    >
      <!-- Previous Button (Left Side) -->
      <transition name="fade-slide">
        <div 
          v-if="canGoToPreviousPage && !navigatingPage"
          class="floating-nav-btn floating-nav-prev"
          @click="goToPreviousReview"
        >
          <el-icon :size="20"><ArrowLeft /></el-icon>
        </div>
      </transition>

      <!-- Next Button (Right Side) -->
      <transition name="fade-slide">
        <div 
          v-if="canGoToNextPage && !navigatingPage"
          class="floating-nav-btn floating-nav-next"
          @click="goToNextReview"
        >
          <el-icon :size="20"><ArrowRight /></el-icon>
        </div>
      </transition>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted, watch, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Clock, Plus, Delete, User, UserFilled, FolderOpened, ArrowDown, ArrowLeft, ArrowRight, CopyDocument, Link, InfoFilled, Download, Star, StarFilled } from '@element-plus/icons-vue'
import { MdEditor, type ToolbarNames, config } from 'md-editor-v3'
import 'md-editor-v3/lib/style.css'
import { reviewsApi } from '@/api/reviews'
import { scoresApi } from '@/api/scores'
import { taskAssignmentApi } from '@/api/taskAssignment'
import {
  userCommentTemplatesApi,
  type UserCommentTemplate,
} from '@/api/userCommentTemplates'
import type { Review } from '@/api/reviews'
import type { Score, ScoreCreate } from '@/api/scores'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import dayjs from 'dayjs'
import { useI18n } from 'vue-i18n'
import CodeDiffViewer from '@/components/review/CodeDiffViewer.vue'
import QuickScoreButtons from '@/components/review/QuickScoreButtons.vue'
import ScoreRangeGuide from '@/components/review/ScoreRangeGuide.vue'
import AIReviewResults from '@/components/review/AIReviewResults.vue'
import { useAuthStore } from '@/stores/auth'
import { useReviewNavigationStore, type ReviewNavigationItem } from '@/stores/reviewNavigation'
import { usePrUrl } from '@/composables/usePrUrl'
import { useTheme } from '@/composables/useTheme'

const { t } = useI18n()

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const reviewNavigationStore = useReviewNavigationStore()
const { getPrUrl } = usePrUrl()
const loading = ref(false)
const addingScore = ref(false)
const review = ref<Review | null>(null)
const scores = ref<Score[]>([])
const showScoreDialog = ref(false)
const editingScore = ref<Score | null>(null)
const scoreFormRef = ref<FormInstance>()
const diffFormat = ref<'line-by-line' | 'side-by-side'>('line-by-line')
const isInfoExpanded = ref(false)
const isScoresExpanded = ref(true)
const navigatingPage = ref(false)
const showFloatingNav = ref(false)
const aiReviewRef = ref<InstanceType<typeof AIReviewResults> | null>(null)

// Track theme changes reactively
const themeTrigger = ref(0)

// Detect current theme - will recompute when themeTrigger changes
const isDarkTheme = computed(() => {
  // Access themeTrigger to make this computed reactive to theme changes
  void themeTrigger.value
  return document.documentElement.getAttribute('data-theme') === 'dark'
})

// Watch for theme changes and update the theme trigger
onMounted(() => {
  const observer = new MutationObserver(() => {
    // Trigger re-computation of isDarkTheme
    themeTrigger.value++
  })
  
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['data-theme']
  })
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

// Can create/update score if:
// 1. User has reviewer+ role AND
// 2. User has a linked Git username AND
// 3. Either:
//    a. User is the assigned reviewer for this review, OR
//    b. User already has a score for this review (can update their own)
const canCreateScore = computed(() => {
  if (!hasScorePermissionRole.value || !effectiveReviewerUsername.value) {
    return false
  }

  // If user already has a score, they can always update it
  if (currentUserHasScore.value) {
    return true
  }

  // Otherwise, check if user is the assigned reviewer
  return isCurrentReviewAssignedToUser.value
})

// Check if current user is assigned as a reviewer for this review
const isCurrentReviewAssignedToUser = computed(() => {
  if (!review.value || !effectiveReviewerUsername.value) {
    return false
  }

  // For multi-reviewer reviews, check if user is in the all_reviewers array
  if (review.value.all_reviewers && review.value.all_reviewers.length > 0) {
    return review.value.all_reviewers.some(
      (r: { username: string; display_name: string }) => r.username === effectiveReviewerUsername.value
    )
  }

  // Fallback: check single reviewer field (legacy)
  return review.value.reviewer === effectiveReviewerUsername.value
})

const scoreActionDisabledReason = computed(() => {
  if (!hasScorePermissionRole.value) {
    return t('reviews.detail.no_score_permission')
  }

  if (!effectiveReviewerUsername.value) {
    return t('reviews.detail.link_account_required')
  }

  // Check if review has any reviewers assigned (single or multi-reviewer)
  const hasAnyReviewer = review.value?.reviewer || (review.value?.all_reviewers && review.value.all_reviewers.length > 0)
  if (!hasAnyReviewer) {
    return t('reviews.detail.no_reviewer_assigned')
  }

  if (!isCurrentReviewAssignedToUser.value && !currentUserHasScore.value) {
    return t('reviews.detail.not_assigned_reviewer')
  }

  return ''
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

const lastAutoProgressAssignmentId = ref<number | null>(null)

const formatDate = (dateStr: string) => {
  return dayjs(dateStr).format('YYYY-MM-DD HH:mm:ss')
}

const formatPublicId = (publicId: string): string => {
  const parts = publicId.split('_')
  const hash = parts.length > 1 ? parts.slice(1).join('_') : publicId
  return `REV-${hash}`
}

// Get score color class based on score value
const getScoreColorClass = (score: number): string => {
  if (score >= 9) return 'score-excellent'
  if (score >= 7) return 'score-good'
  if (score >= 5) return 'score-acceptable'
  if (score >= 3) return 'score-needs-improvement'
  return 'score-poor'
}

const copyToClipboard = (text: string) => {
  navigator.clipboard.writeText(text).then(() => {
    ElMessage.success('Copied to clipboard')
  }).catch(() => {
    ElMessage.error('Failed to copy to clipboard')
  })
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

  const routeId = route.params.id as string
  return reviewNavigationStore.items.findIndex(item => {
    return (
      item.publicId === routeId &&
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

// Pagination state
const isOnLastPage = computed(() => {
  return currentReviewIndex.value === reviewNavigationStore.items.length - 1 && !reviewNavigationStore.hasMorePages
})

const isOnFirstPage = computed(() => {
  return currentReviewIndex.value === 0 && reviewNavigationStore.currentPage === 1
})

const canGoToNextPage = computed(() => {
  return reviewNavigationStore.hasMorePages || (currentReviewIndex.value < reviewNavigationStore.items.length - 1)
})

const canGoToPreviousPage = computed(() => {
  return reviewNavigationStore.currentPage > 1 || currentReviewIndex.value > 0
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
  const rawId = route.params.id as string
  if (!rawId) return

  const isNumeric = /^\d+$/.test(rawId)
  const id = isNumeric ? Number(rawId) : 0

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
    } else if (isNumeric) {
      review.value = await reviewsApi.getReviewById(id)
    } else {
      review.value = await reviewsApi.getReviewByPublicId(rawId)
    }
    
    if (!review.value) {
      throw new Error('Review not found')
    }

    await markReviewInProgressOnOpen(review.value)
    
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

const markReviewInProgressOnOpen = async (reviewData: Review) => {
  const currentUsername = effectiveReviewerUsername.value

  if (!currentUsername || reviewData.reviewer !== currentUsername) {
    return
  }

  if (reviewData.assignment_status !== 'assigned') {
    return
  }

  if (lastAutoProgressAssignmentId.value === reviewData.id) {
    return
  }

  try {
    lastAutoProgressAssignmentId.value = reviewData.id
    await taskAssignmentApi.updateAssignmentStatus(reviewData.id, {
      assignment_status: 'in_progress',
    })
    reviewData.assignment_status = 'in_progress'
  } catch (error) {
    lastAutoProgressAssignmentId.value = null
    console.warn('Failed to mark review as in progress on open:', error)
  }
}

const goToNextReview = async () => {
  // If there's a next review on current page, navigate to it
  if (nextReview.value) {
    router.replace({
      name: 'ReviewDetail',
      params: { id: nextReview.value.publicId },
      query: {
        projectKey: nextReview.value.projectKey,
        repositorySlug: nextReview.value.repositorySlug,
        pullRequestId: nextReview.value.pullRequestId,
        reviewer: nextReview.value.reviewer,
        sourceFilename: nextReview.value.sourceFilename,
      },
    })
    return
  }

  // If we're at the end of current page and there are more pages, load next page
  if (reviewNavigationStore.hasMorePages && currentReviewIndex.value === reviewNavigationStore.items.length - 1) {
    await loadNextPage()
  }
}

const goToPreviousReview = async () => {
  // If there's a previous review on current page, navigate to it
  if (previousReview.value) {
    router.replace({
      params: { id: previousReview.value.publicId },
      query: {
        projectKey: previousReview.value.projectKey,
        repositorySlug: previousReview.value.repositorySlug,
        pullRequestId: previousReview.value.pullRequestId,
        reviewer: previousReview.value.reviewer,
        sourceFilename: previousReview.value.sourceFilename,
      },
    })
    return
  }

  // If we're at the beginning of current page and not on first page, load previous page
  if (reviewNavigationStore.currentPage > 1 && currentReviewIndex.value === 0) {
    await loadPreviousPage()
  }
}

// Load next page of reviews
const loadNextPage = async () => {
  if (!review.value || navigatingPage.value) return

  navigatingPage.value = true
  try {
    const nextPage = reviewNavigationStore.currentPage + 1
    
    // Fetch next page from API WITH FILTERS to maintain consistency
    const params: any = {
      page: nextPage,
      page_size: reviewNavigationStore.pageSize,
    }
    
    // Apply stored filters
    const storedFilters = reviewNavigationStore.filters || {}
    if (storedFilters.app_names) params.app_names = storedFilters.app_names
    if (storedFilters.pull_request_user) params.pull_request_user = storedFilters.pull_request_user
    if (storedFilters.reviewer) params.reviewer = storedFilters.reviewer
    if (storedFilters.pull_request_status) params.pull_request_status = storedFilters.pull_request_status
    if (storedFilters.search_query) params.search_query = storedFilters.search_query
    if (storedFilters.has_scores !== undefined) params.has_scores = storedFilters.has_scores
    if (storedFilters.severity) params.severity = storedFilters.severity
    
    const response = await reviewsApi.getReviews(params)

    if (response.items.length === 0) {
      ElMessage.warning('No more reviews available')
      return
    }

    // Update navigation context with new page
    const totalPages = Math.ceil(response.total / reviewNavigationStore.pageSize)
    reviewNavigationStore.setContext({
      items: response.items.map(item => ({
        id: item.id,
        publicId: item.public_id || item.id.toString(),
        projectKey: item.project_key,
        repositorySlug: item.repository_slug,
        pullRequestId: item.pull_request_id,
        reviewer: item.reviewer || '',
        sourceFilename: item.source_filename || '',
      })),
      currentPage: nextPage,
      pageSize: reviewNavigationStore.pageSize,
      totalItems: response.total,
      hasMorePages: nextPage < totalPages,
      filters: storedFilters, // Preserve filters for subsequent navigation
    })

    // Navigate to first review on the new page
    const firstReview = response.items[0]
    if (firstReview) {
      router.replace({
        name: 'ReviewDetail',
        params: { id: firstReview.public_id || firstReview.id.toString() },
        query: {
          projectKey: firstReview.project_key,
          repositorySlug: firstReview.repository_slug,
          pullRequestId: firstReview.pull_request_id,
          reviewer: firstReview.reviewer || '',
          sourceFilename: firstReview.source_filename || '',
        },
      })
    }
  } catch (error) {
    console.error('Failed to load next page:', error)
    ElMessage.error('Failed to load next page')
  } finally {
    navigatingPage.value = false
  }
}

// Load previous page of reviews
const loadPreviousPage = async () => {
  if (!review.value || navigatingPage.value) return

  navigatingPage.value = true
  try {
    const prevPage = reviewNavigationStore.currentPage - 1
    
    // Fetch previous page from API WITH FILTERS to maintain consistency
    const params: any = {
      page: prevPage,
      page_size: reviewNavigationStore.pageSize,
    }
    
    // Apply stored filters
    const storedFilters = reviewNavigationStore.filters || {}
    if (storedFilters.app_names) params.app_names = storedFilters.app_names
    if (storedFilters.pull_request_user) params.pull_request_user = storedFilters.pull_request_user
    if (storedFilters.reviewer) params.reviewer = storedFilters.reviewer
    if (storedFilters.pull_request_status) params.pull_request_status = storedFilters.pull_request_status
    if (storedFilters.search_query) params.search_query = storedFilters.search_query
    if (storedFilters.has_scores !== undefined) params.has_scores = storedFilters.has_scores
    if (storedFilters.severity) params.severity = storedFilters.severity
    
    const response = await reviewsApi.getReviews(params)

    if (response.items.length === 0) {
      ElMessage.warning('No more reviews available')
      return
    }

    // Update navigation context with new page
    const totalPages = Math.ceil(response.total / reviewNavigationStore.pageSize)
    reviewNavigationStore.setContext({
      items: response.items.map(item => ({
        id: item.id,
        publicId: item.public_id || item.id.toString(),
        projectKey: item.project_key,
        repositorySlug: item.repository_slug,
        pullRequestId: item.pull_request_id,
        reviewer: item.reviewer || '',
        sourceFilename: item.source_filename || '',
      })),
      currentPage: prevPage,
      pageSize: reviewNavigationStore.pageSize,
      totalItems: response.total,
      hasMorePages: prevPage < totalPages,
      filters: storedFilters, // Preserve filters for subsequent navigation
    })

    // Navigate to last review on the new page
    const lastReview = response.items[response.items.length - 1]
    if (lastReview) {
      router.replace({
        name: 'ReviewDetail',
        params: { id: lastReview.public_id || lastReview.id.toString() },
        query: {
          projectKey: lastReview.project_key,
          repositorySlug: lastReview.repository_slug,
          pullRequestId: lastReview.pull_request_id,
          reviewer: lastReview.reviewer || '',
          sourceFilename: lastReview.source_filename || '',
        },
      })
    }
  } catch (error) {
    console.error('Failed to load previous page:', error)
    ElMessage.error('Failed to load previous page')
  } finally {
    navigatingPage.value = false
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
      `Are you sure you want to delete ${review.value.public_id ? formatPublicId(review.value.public_id) : `review #${review.value.id}`}?`,
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

// Toggle pin status for the current review
const handleTogglePin = async () => {
  if (!review.value) return
  try {
    if (review.value.is_pinned_by_me) {
      await reviewsApi.unpinReview(review.value.id)
      review.value.is_pinned_by_me = false
      ElMessage.success(t('reviews.pin_removed', 'Pin removed'))
    } else {
      await reviewsApi.pinReview(review.value.id)
      review.value.is_pinned_by_me = true
      ElMessage.success(t('reviews.pin_added', 'Review pinned'))
    }
  } catch (error: any) {
    console.error('Failed to toggle pin:', error)
    ElMessage.error(error.response?.data?.detail?.message || error.message || 'Failed to toggle pin')
  }
}

const handleQuickScoreSelect = (value: number) => {
  scoreForm.score = value
}

interface CommentTemplate {
  id: string
  min: number
  max: number
}

const commentTemplates: CommentTemplate[] = [
  { id: 'excellent', min: 9.0, max: 10 },
  { id: 'good', min: 7.5, max: 8.5 },
  { id: 'average', min: 6.0, max: 7.0 },
  { id: 'needs_changes', min: 4.5, max: 5.5 },
  { id: 'major_changes', min: 0, max: 4.0 },
]

const selectedTemplate = ref('')

// Personal comment templates saved by the current auth user
const personalTemplates = ref<UserCommentTemplate[]>([])
const savingPersonalTemplate = ref(false)

const canManagePersonalTemplates = computed(() => authStore.isAuthenticated)

const loadPersonalTemplates = async () => {
  if (!authStore.isAuthenticated) {
    personalTemplates.value = []
    return
  }
  try {
    const response = await userCommentTemplatesApi.listTemplates()
    personalTemplates.value = response.items
  } catch (error) {
    console.warn('Failed to load personal comment templates', error)
    personalTemplates.value = []
  }
}

const availableTemplates = computed(() => {
  const score = scoreForm.score
  if (score <= 0) return commentTemplates
  return commentTemplates.filter((tpl) => score >= tpl.min && score <= tpl.max)
})

const handleTemplateSelect = (value: string | undefined) => {
  if (!value) return
  if (value.startsWith('personal:')) {
    const templateId = Number(value.slice('personal:'.length))
    const template = personalTemplates.value.find((item) => item.id === templateId)
    if (template) {
      scoreForm.reviewer_comments = template.content
    }
    return
  }
  const content = t(`reviews.detail.tpl_${value}_content`)
  if (content) {
    scoreForm.reviewer_comments = content
  }
}

// Save the current comment as a reusable personal template
const handleSaveAsPersonalTemplate = async () => {
  const content = (scoreForm.reviewer_comments || '').trim()
  if (!content) {
    ElMessage.warning(t('reviews.detail.save_template_empty'))
    return
  }

  try {
    const { value } = await ElMessageBox.prompt(
      t('reviews.detail.save_template_message'),
      t('reviews.detail.save_template_title'),
      {
        confirmButtonText: t('common.save'),
        cancelButtonText: t('common.cancel'),
        inputPlaceholder: t('reviews.detail.save_template_name_placeholder'),
        inputValidator: (input: string) => {
          const name = (input || '').trim()
          if (!name) return t('reviews.detail.save_template_name_required')
          if (name.length > 100) return t('reviews.detail.save_template_name_too_long')
          return true
        },
      }
    )

    const name = String(value || '').trim()
    if (!name) return

    savingPersonalTemplate.value = true
    await userCommentTemplatesApi.createTemplate({ name, content })
    ElMessage.success(t('reviews.detail.save_template_success'))
    await loadPersonalTemplates()
  } catch (error: any) {
    if (error === 'cancel' || error?.action === 'cancel') return
    ElMessage.error(t('reviews.detail.save_template_failed'))
  } finally {
    savingPersonalTemplate.value = false
  }
}

// Keep the template selection in sync with the current score
// (personal templates are never filtered out, only built-in ones are)
watch(
  () => scoreForm.score,
  (score) => {
    if (
      score > 0 &&
      selectedTemplate.value &&
      !selectedTemplate.value.startsWith('personal:') &&
      !availableTemplates.value.some((tpl) => tpl.id === selectedTemplate.value)
    ) {
      selectedTemplate.value = ''
    }
  }
)

const toggleInfoCollapse = () => {
  isInfoExpanded.value = !isInfoExpanded.value
}

const toggleScoresCollapse = () => {
  isScoresExpanded.value = !isScoresExpanded.value
}

const handleCloseDialog = () => {
  showScoreDialog.value = false
  editingScore.value = null
  // Reset form
  scoreForm.score = 0
  scoreForm.reviewer_comments = undefined
  selectedTemplate.value = ''
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
    selectedTemplate.value = ''
  } else {
    selectedTemplate.value = ''
  }
})

watch(
  () => [review.value?.id, review.value?.reviewer, review.value?.assignment_status, effectiveReviewerUsername.value],
  async () => {
    if (!review.value) {
      return
    }

    await markReviewInProgressOnOpen(review.value)
  },
  { immediate: true }
)

// Watch for theme changes and force re-render of MdEditor
watch(isDarkTheme, () => {
  // Force re-computation by accessing the computed property
  void isDarkTheme.value
})

onMounted(() => {
  loadReview()
  loadPersonalTemplates()
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
}

.header-content-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.card-title-wrapper {
  display: flex;
  align-items: center;
}

.collapse-icon {
  margin-right: 8px;
  transition: transform 0.3s;
}

.form-item-hint {
  font-size: 0.8rem;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
}

/* Template picker row (select + quick save button) */
.template-picker-row {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.template-picker-row .template-select {
  flex: 1;
  min-width: 0;
}

.score-md-editor {
  height: 400px;
  border-radius: 6px;
  overflow: hidden;
}

.editor-hint {
  margin-top: 8px;
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
  min-width: 104px;
  height: 32px;
  padding: 0 16px;
  text-align: center;
  box-sizing: border-box;
  border-radius: 999px;
  background: var(--el-fill-color-light);
  border: 1px solid var(--el-border-color-lighter);
  font-weight: 500;
  white-space: nowrap;
}

.page-indicator {
  display: inline-flex;
  align-items: center;
}

.content-row {
  margin-top: 20px;
}

.card-header {
  display: flex;
  align-items: center;
  cursor: pointer;
  position: relative;
}

.card-title-wrapper {
  flex: 1;
  display: flex;
  align-items: center;
  min-width: 0;
}

.card-clickable-area {
  display: none;
}

.card-actions {
  margin-left: auto;
  cursor: default;
}

.card-meta-info {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
  white-space: nowrap;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
  white-space: nowrap;
}

.meta-item .el-icon {
  font-size: 14px;
}

/* PR Link Styles */
.pr-link {
  text-decoration: none;
  color: inherit;
  transition: all 0.2s ease;
  display: inline-flex;
  align-items: center;
}

.pr-link:hover {
  opacity: 0.8;
}

.pr-link :deep(.el-tag) {
  cursor: pointer;
  transition: all 0.2s ease;
}

.pr-link:hover :deep(.el-tag) {
  border-color: var(--el-color-primary);
  background-color: var(--el-color-primary-light-9);
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

.pr-description-text {
  line-height: 1.6;
  color: var(--el-text-color-regular);
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 200px;
  overflow-y: auto;
}

.na-text {
  font-style: italic;
  color: var(--el-text-color-placeholder);
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
}

.score-excellent {
  color: #10b981;
}

.score-good {
  color: #3b82f6;
}

.score-acceptable {
  color: #f59e0b;
}

.score-needs-improvement {
  color: #f97316;
}

.score-poor {
  color: #ef4444;
}

.score-max {
  font-size: 0.9rem;
  color: var(--el-text-color-secondary);
}

.score-input-container {
  width: 100%;
}

/* AI Review ID Styles */
.ai-review-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.ai-review-title {
  display: flex;
  align-items: center;
  flex: 1;
}

.copy-ai-id-btn {
  margin-left: 8px;
  flex-shrink: 0;
}

.ai-review-header-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.ai-review-id-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  justify-content: center;
}

.empty-value {
  color: var(--el-text-color-secondary);
  font-size: 12px;
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

.editor-hint {
  padding: 6px 12px;
  background: var(--el-fill-color-lighter);
  font-size: 0.75rem;
  color: var(--el-text-color-secondary);
  border-radius: 4px;
  margin-top: 8px;
}

/* Score Dialog Styles */
.score-dialog :deep(.el-dialog__body) {
  max-height: calc(90vh - 120px);
  overflow-y: auto;
  padding: 20px;
}

/* Visual Score Bar */
.score-visual-bar {
  position: relative;
  height: 60px;
  margin-bottom: 16px;
  background: rgba(0, 0, 0, 0.02);
  border-radius: 8px;
  overflow: visible;
  user-select: none;
}

.score-track {
  position: absolute;
  top: 50%;
  left: 30px;
  right: 30px;
  height: 8px;
  background: linear-gradient(to right, 
    #ef4444 0%, 
    #ef4444 25%,
    #f97316 30%, 
    #f59e0b 45%,
    #3b82f6 65%, 
    #10b981 85%,
    #10b981 100%
  );
  border-radius: 4px;
  transform: translateY(-50%);
  opacity: 0.6;
}

/* Positioning range for the sliding indicator - matches the track span */
.score-indicator-range {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 30px;
  right: 30px;
  z-index: 10;
}

.score-indicator {
  position: absolute;
  top: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 48px;
  height: 32px;
  font-weight: 700;
  font-size: 0.9rem;
  border-radius: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  transition: left 0.3s ease;
  padding: 0 8px;
  white-space: nowrap;
}

/* Color classes for indicator - matches existing getScoreColorClass and ScoreRangeGuide */
.score-indicator.score-excellent {
  background: #10b981;
  color: white;
}

.score-indicator.score-good {
  background: #3b82f6;
  color: white;
}

.score-indicator.score-acceptable {
  background: #f59e0b;
  color: white;
}

.score-indicator.score-needs-improvement {
  background: #f97316;
  color: white;
}

.score-indicator.score-poor {
  background: #ef4444;
  color: white;
}

.score-labels {
  position: absolute;
  bottom: 0;
  left: 30px;
  right: 30px;
  display: flex;
  justify-content: space-between;
  font-size: 0.75rem;
  color: var(--el-text-color-secondary);
}

/* Score input wrapper */
.score-input-wrapper {
  width: 100%;
  margin-top: 12px;
}

/* Style the input number for better UX */
.score-dialog :deep(.el-input-number) {
  width: 100%;
}

.score-dialog :deep(.el-input-number .el-input__inner) {
  text-align: left;
  font-size: 1.1rem;
  font-weight: 600;
}

.score-md-editor {
  height: 450px;
  border-radius: 6px;
  overflow: hidden;
}

/* Ensure editor content area scrolls properly */
.score-md-editor :deep(.md-editor-content) {
  max-height: 380px;
  overflow-y: auto;
}

/* Reviewer cell with badge */
.reviewer-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.primary-reviewer-badge {
  font-size: 0.7rem;
  padding: 2px 6px;
  white-space: nowrap;
}

/* Scores card spacing */
.scores-card {
  margin-bottom: 40px;
}

@media (max-width: 768px) {
  .scores-card {
    margin-bottom: 30px;
  }
}

/* Floating Navigation Styles */
.floating-navigation {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
  z-index: 100;
}

.floating-nav-btn {
  position: fixed;
  top: 50%;
  transform: translateY(-50%);
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  background: var(--el-color-primary);
  color: white;
  border-radius: 50%;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  transition: all 0.3s ease;
  pointer-events: auto;
  opacity: 0;
  visibility: hidden;
}

.floating-nav-btn:hover {
  background: var(--el-color-primary-light-3);
  transform: translateY(-50%) scale(1.15);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
}

.floating-nav-prev {
  left: 5px;
}

.floating-nav-next {
  right: 5px;
}

/* Show buttons when hovering near the edges (within 50px from edge) */
.review-detail:hover .floating-nav-prev,
.floating-navigation:hover .floating-nav-prev {
  opacity: 1;
  visibility: visible;
}

.review-detail:hover .floating-nav-next,
.floating-navigation:hover .floating-nav-next {
  opacity: 1;
  visibility: visible;
}

/* Transitions */
.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: all 0.3s ease;
}

.fade-slide-enter-from {
  opacity: 0;
  transform: translateY(-50%) translateX(-10px);
}

.fade-slide-leave-to {
  opacity: 0;
  transform: translateY(-50%) translateX(-10px);
}

.floating-nav-next.fade-slide-enter-from,
.floating-nav-next.fade-slide-leave-to {
  transform: translateY(-50%) translateX(10px);
}

/* Dark theme adjustments */
[data-theme='dark'] .floating-nav-btn {
  background: var(--el-color-primary-dark-2);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}

[data-theme='dark'] .floating-nav-btn:hover {
  background: var(--el-color-primary-light-5);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
}

/* Responsive adjustments */
@media (max-width: 768px) {
  .floating-nav-btn {
    width: 32px;
    height: 32px;
  }

  .floating-nav-prev {
    left: 8px;
  }

  .floating-nav-next {
    right: 8px;
  }
}

/* No AI Results Placeholder Styling */
.no-ai-results-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 400px;
  padding: 20px;
}

.placeholder-hint {
  margin-top: 16px;
  color: var(--el-text-color-secondary);
  font-size: 0.9rem;
  line-height: 1.6;
  text-align: center;
  max-width: 280px;
}

[data-theme='dark'] .placeholder-hint {
  color: var(--el-text-color-secondary);
}

/* Pin cell clickable area */
.pin-cell-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  cursor: pointer;
  transition: background-color 0.2s ease;
}

.pin-cell-btn:hover {
  background-color: var(--el-fill-color-light);
}

.pinned-active {
  color: #e6a23c !important;
}

.pinned-active:hover {
  color: #d48806 !important;
}
</style>