# Vue Project Core Function Verification & Optimization Plan

## Executive Summary

基于原始`web/index.html`和系统定位,**PR Ledger是一个AI评审数据存储系统**,而非用户创建评审的系统。

### 核心业务逻辑
1. **数据来源**: AI通过`POST /reviews`提交PR评审数据
2. **用户权限**: 登录后只能**查看**评审、**添加/更新/删除评分**(基于权限)
3. **禁止操作**: 用户**不能从UI创建**任何PR评审记录

---

## Current Issues Found ❌

### Issue 1: Vue Project Allows Creating Reviews (CRITICAL)

**Location**: `frontend/src/views/reviews/ReviewListView.vue:400`

```typescript
// CURRENT CODE - WRONG!
await reviewsApi.createReview(createForm)
```

**Problem**: 
- Vue项目允许用户从UI创建新的PR评审
- 这违反了核心业务逻辑
- Review应该只由AI系统通过API提交

**Impact**: HIGH - 数据一致性问题

---

### Issue 2: Missing Score Management Focus

**Current State**:
- Vue项目有复杂的Review管理界面
- 但缺少清晰的Score管理重点
- 用户可能不清楚系统的核心价值是"评分管理"

**Expected**:
- Review列表应该是**只读**的(展示AI提交的评审)
- Score操作应该是**主要功能**(用户的核心交互)

---

### Issue 3: Permission System Not Enforced for Scores

**Current State**:
- RBAC系统已实现
- 但Score的增删改操作未严格检查权限
- 任何登录用户都可能修改评分

**Expected**:
- 只有有权限的用户才能添加/更新/删除评分
- 需要明确的权限检查

---

## Optimization Plan

### Phase A: Remove Review Creation (Priority: CRITICAL)

#### Task A1: Remove Create Review UI
**Files to modify**:
- `frontend/src/views/reviews/ReviewListView.vue`
  - Remove "Create Review" button
  - Remove create review dialog/form
  - Remove `createReview` API call

**Changes**:
```vue
<!-- REMOVE THIS -->
<el-button type="primary" @click="showCreateDialog">
  Create Review
</el-button>

<!-- KEEP ONLY -->
<el-button @click="refreshList">Refresh</el-button>
```

#### Task A2: Update Review API Service
**File**: `frontend/src/api/reviews.ts`

```typescript
// REMOVE or DEPRECATE
export const createReview = (data: ReviewCreate) => {
  // This should NOT be used by frontend
  // Only AI system should call POST /reviews
  throw new Error('Reviews can only be created by AI system')
}

// KEEP (read-only operations)
export const getReviews = () => {...}
export const getReviewById = (id: number) => {...}
export const updateReviewStatus = (id: number, status: string) => {...}
```

#### Task A3: Add Disclaimer to Review List
**File**: `frontend/src/views/reviews/ReviewListView.vue`

```vue
<template>
  <div class="review-list-container">
    <!-- Add info banner -->
    <el-alert
      title="PR Reviews are submitted by AI system"
      type="info"
      :closable="false"
      show-icon
    >
      <template #default>
        Pull request reviews are automatically collected from AI analysis. 
        You can view reviews and add/update scores based on your permissions.
      </template>
    </el-alert>
    
    <!-- Rest of the review list -->
  </div>
</template>
```

---

### Phase B: Enhance Score Management (Priority: HIGH)

#### Task B1: Make Score Operations More Prominent

**Current Layout**:
```
Review List → Click Review → See Details → Find Score Section
```

**Proposed Layout**:
```
Dashboard
├── My Pending Scores (需要我评分的PR)
├── Recent Reviews I Scored (我已评分的PR)
└── All Reviews (只读浏览)
```

**Implementation**:
- Create new "My Scores" page as default dashboard
- Show PRs that need scoring prominently
- Quick score action buttons

#### Task B2: Add Score Permission Checks

**File**: `frontend/src/composables/usePermission.ts`

```typescript
export function useScorePermission() {
  const authStore = useAuthStore()
  
  /**
   * Check if user can add/update scores for a PR
   */
  const canManageScores = (prId: string): boolean => {
    // Check if user is reviewer
    if (!authStore.user?.is_reviewer) {
      return false
    }
    
    // Check if user has already scored this PR
    // (prevent duplicate scores unless updating own)
    return true
  }
  
  /**
   * Check if user can delete their own score
   */
  const canDeleteOwnScore = (scoreReviewer: string): boolean => {
    return authStore.user?.username === scoreReviewer
  }
  
  return {
    canManageScores,
    canDeleteOwnScore,
  }
}
```

**Apply to Score Components**:
```vue
<template>
  <!-- Show score form only if user has permission -->
  <div v-if="scorePermission.canManageScores(review.id)">
    <ScoreForm :review-id="review.id" />
  </div>
  
  <!-- Show read-only scores for others -->
  <div v-else>
    <ReadOnlyScores :review-id="review.id" />
  </div>
</template>
```

#### Task B3: Improve Score UX

**Features to add**:
1. **Quick Score Buttons** (like original HTML)
   - Predefined score values (5, 6, 7, 8, 9, 10)
   - One-click scoring
   
2. **Score Range Guide**
   - Visual guide showing what each score means
   - 5-6: Poor, 7-8: Good, 9-10: Excellent

3. **Score History**
   - Show previous scores for same PR
   - Track score changes over time

4. **Score Comments**
   - Allow adding comments with scores
   - Explain reasoning

---

### Phase C: Clarify System Purpose (Priority: MEDIUM)

#### Task C1: Update Landing Page/Dashboard

**Current**: Generic dashboard with stats

**Proposed**: Clear value proposition

```vue
<template>
  <div class="dashboard">
    <el-card class="welcome-card">
      <h1>Welcome to PR Ledger</h1>
      <p class="subtitle">AI-Powered Code Review Scoring System</p>
      
      <el-descriptions :column="3" border>
        <el-descriptions-item label="What we do">
          Store and manage AI-generated code review results
        </el-descriptions-item>
        <el-descriptions-item label="Your role">
          Review AI findings and add human scoring
        </el-descriptions-item>
        <el-descriptions-item label="Key feature">
          Multi-level scoring (PR-level + File-level)
        </el-descriptions-item>
      </el-descriptions>
    </el-card>
    
    <!-- Quick actions -->
    <div class="quick-actions">
      <el-button type="primary" size="large" @click="$router.push('/my-scores')">
        <el-icon><Edit /></el-icon>
        Score Pending Reviews
      </el-button>
      <el-button size="large" @click="$router.push('/reviews')">
        <el-icon><View /></el-icon>
        Browse All Reviews
      </el-button>
    </div>
  </div>
</template>
```

#### Task C2: Add Tooltips and Help Text

**Throughout the app**:
- Explain what PR-level vs File-level scores mean
- Show who can perform which actions
- Clarify data flow (AI → Storage → Human Scoring)

---

### Phase D: Align with Original HTML Features (Priority: MEDIUM)

#### Task D1: Implement Missing Features from Original HTML

**Original HTML has**:
1. ✅ Theme switcher (light/dark/warm/cool)
2. ✅ Code diff viewer (Diff2Html integration)
3. ✅ AI suggestions display
4. ✅ Collapsible PR groups
5. ✅ Score range guide visualization
6. ✅ Quick score buttons

**Vue project missing**:
- ❌ Theme switcher (only has language switcher)
- ❌ Code diff viewer integration
- ❌ AI suggestions display
- ⚠️ Score range guide (needs improvement)
- ⚠️ Quick score buttons (needs implementation)

**Implementation Priority**:
1. **Code Diff Viewer** (HIGH) - Critical for understanding PR changes
2. **Theme Switcher** (MEDIUM) - Nice to have
3. **AI Suggestions** (LOW) - Can be added later

#### Task D2: Integrate Code Diff Viewer

**Install dependency**:
```bash
npm install diff2html
```

**Create component**: `frontend/src/components/review/CodeDiffViewer.vue`

```vue
<template>
  <div class="code-diff-viewer">
    <div ref="diffContainer"></div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { Diff2HtmlUI } from 'diff2html/lib/ui/js/diff2html-ui-slim.js'
import 'diff2html/bundles/css/diff2html.min.css'

const props = defineProps<{
  diff: string
  outputFormat?: 'line-by-line' | 'side-by-side'
}>()

const diffContainer = ref<HTMLElement | null>(null)

onMounted(() => {
  renderDiff()
})

watch(() => props.diff, () => {
  renderDiff()
})

const renderDiff = () => {
  if (!diffContainer.value || !props.diff) return
  
  const configuration = {
    drawFileList: true,
    fileListToggle: true,
    fileListStartVisible: false,
    fileContentToggle: true,
    matching: 'lines',
    outputFormat: props.outputFormat || 'line-by-line',
    synchronisedScroll: true,
    highlight: true,
    renderNothingWhenEmpty: false,
  }
  
  const diff2htmlUi = new Diff2HtmlUI(diffContainer.value, props.diff, configuration)
  diff2htmlUi.draw()
  diff2htmlUi.highlightCode()
}
</script>
```

---

## Implementation Roadmap

### Week 1: Critical Fixes
- [ ] Remove Review creation UI
- [ ] Add disclaimer banners
- [ ] Update API services
- [ ] Test all changes

### Week 2: Score Management Enhancement
- [ ] Create "My Scores" dashboard
- [ ] Implement permission checks
- [ ] Add quick score buttons
- [ ] Improve score UX

### Week 3: Feature Parity with Original HTML
- [ ] Integrate code diff viewer
- [ ] Add theme switcher
- [ ] Implement AI suggestions display
- [ ] Polish UI/UX

### Week 4: Documentation & Testing
- [ ] Update user documentation
- [ ] Add inline help text
- [ ] Write integration tests
- [ ] User acceptance testing

---

## Success Metrics

### Functional Requirements
- ✅ Users cannot create Reviews from UI
- ✅ Score operations require proper permissions
- ✅ Clear distinction between AI data and human scoring
- ✅ Code diff viewer integrated

### UX Improvements
- ✅ Dashboard clearly explains system purpose
- ✅ Score management is prominent and easy
- ✅ Helpful tooltips and guidance throughout
- ✅ Consistent with original HTML features

### Technical Quality
- ✅ No unused code (removed create review logic)
- ✅ Proper error handling for permission denied
- ✅ Type-safe permission checks
- ✅ Comprehensive test coverage

---

## Risk Assessment

### High Risk
- **Breaking existing workflows**: Some users may rely on creating reviews manually
  - **Mitigation**: Communicate change clearly, provide migration path if needed

### Medium Risk
- **Permission system complexity**: May confuse users
  - **Mitigation**: Clear UI indicators, helpful error messages

### Low Risk
- **Feature additions**: New components shouldn't break existing functionality
  - **Mitigation**: Thorough testing, gradual rollout

---

## Next Steps

1. **Immediate**: Remove Review creation functionality
2. **Short-term**: Enhance Score management UX
3. **Medium-term**: Achieve feature parity with original HTML
4. **Long-term**: Continuous improvement based on user feedback

---

**Created**: 2026-04-06  
**Status**: Planning - Awaiting Approval  
**Priority**: CRITICAL (Issue 1 must be fixed immediately)
