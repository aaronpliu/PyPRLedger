<template>
  <div class="task-detail-container">
    <el-card v-loading="loading">
      <template #header>
        <div class="card-header">
          <el-button @click="goBack">
            <el-icon><Back /></el-icon>
            Back
          </el-button>
          <span>Task Assignment Details</span>
          <el-tag type="info">Review Admin</el-tag>
        </div>
      </template>

      <div v-if="review" class="detail-content">
        <!-- PR Information -->
        <el-descriptions title="PR Information" :column="2" border>
          <el-descriptions-item label="PR ID">{{ review.pull_request_id }}</el-descriptions-item>
          <el-descriptions-item label="Commit ID">{{ review.pull_request_commit_id || 'N/A' }}</el-descriptions-item>
          <el-descriptions-item label="Project">{{ review.project_key }}</el-descriptions-item>
          <el-descriptions-item label="Repository">{{ review.repository_slug }}</el-descriptions-item>
          <el-descriptions-item label="Source Branch">
            <el-tag>{{ review.source_branch }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="Target Branch">
            <el-tag type="success">{{ review.target_branch }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="Status">
            <el-tag :type="getStatusType(review.pull_request_status)">
              {{ review.pull_request_status }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="Created">
            {{ formatDate(review.created_date) }}
          </el-descriptions-item>
        </el-descriptions>

        <!-- Reviewers Management -->
        <el-divider />
        <div class="section-header">
          <h3>Reviewers ({{ review.total_reviewers }})</h3>
          <el-button type="primary" size="small" @click="handleAssignReviewer">
            + Assign Reviewer
          </el-button>
        </div>

        <el-table :data="review.reviewers" stripe border>
          <el-table-column prop="id" label="ID" width="80" />
          
          <el-table-column label="Reviewer" min-width="150">
            <template #default="{ row }">
              <div class="reviewer-info">
                <strong>{{ row.reviewer }}</strong>
                <div v-if="row.reviewer_info" class="display-name">
                  {{ row.reviewer_info.display_name }}
                </div>
              </div>
            </template>
          </el-table-column>

          <el-table-column label="Assigned By" width="150">
            <template #default="{ row }">
              {{ row.assigned_by || 'N/A' }}
            </template>
          </el-table-column>

          <el-table-column label="Assigned Date" width="180">
            <template #default="{ row }">
              {{ row.assigned_date ? formatDate(row.assigned_date) : 'N/A' }}
            </template>
          </el-table-column>

          <el-table-column label="Status" width="120">
            <template #default="{ row }">
              <el-dropdown @command="(cmd: string) => handleUpdateStatus(row.id, cmd)">
                <el-tag :type="getAssignmentStatusType(row.assignment_status)" class="clickable">
                  {{ row.assignment_status }}
                  <el-icon class="el-icon--right"><ArrowDown /></el-icon>
                </el-tag>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="pending">Pending</el-dropdown-item>
                    <el-dropdown-item command="assigned">Assigned</el-dropdown-item>
                    <el-dropdown-item command="in_progress">In Progress</el-dropdown-item>
                    <el-dropdown-item command="completed">Completed</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </template>
          </el-table-column>

          <el-table-column label="Comments" min-width="200">
            <template #default="{ row }">
              {{ row.reviewer_comments || '-' }}
            </template>
          </el-table-column>

          <el-table-column label="Actions" width="100" fixed="right">
            <template #default="{ row }">
              <el-button
                size="small"
                type="danger"
                link
                @click="handleRemoveReviewer(row.reviewer)"
              >
                Remove
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <!-- AI Suggestions -->
        <el-divider />
        <div v-if="review.ai_suggestions" class="ai-section">
          <h3>AI Suggestions</h3>
          <el-alert
            v-if="review.ai_suggestions.overall_assessment"
            :title="review.ai_suggestions.overall_assessment"
            type="info"
            :closable="false"
            style="margin-bottom: 16px"
          />
          
          <div v-if="review.ai_suggestions.issues && review.ai_suggestions.issues.length > 0">
            <h4>Issues Found ({{ review.ai_suggestions.issues.length }})</h4>
            <el-collapse>
              <el-collapse-item
                v-for="(issue, index) in review.ai_suggestions.issues"
                :key="index"
                :title="`${issue.category} - ${issue.severity} (${issue.file}:${issue.line})`"
              >
                <p><strong>Description:</strong> {{ issue.description }}</p>
                <p v-if="issue.suggestion"><strong>Suggestion:</strong> {{ issue.suggestion }}</p>
                <pre v-if="issue.code_snippet" class="code-snippet">{{ issue.code_snippet }}</pre>
              </el-collapse-item>
            </el-collapse>
          </div>
        </div>

        <!-- Code Diff -->
        <el-divider />
        <div v-if="review.git_code_diff" class="diff-section">
          <h3>Code Diff</h3>
          <pre class="code-diff">{{ review.git_code_diff }}</pre>
        </div>
      </div>
    </el-card>

    <!-- Assign Reviewer Dialog -->
    <el-dialog v-model="assignDialogVisible" title="Assign Reviewer" width="500px">
      <el-form :model="assignForm" label-width="100px">
        <el-form-item label="Reviewer" required>
          <el-select v-model="assignForm.reviewer" placeholder="Select reviewer" style="width: 100%">
            <el-option
              v-for="user in availableReviewers"
              :key="user.username"
              :label="`${user.display_name} (${user.username})`"
              :value="user.username"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="assignDialogVisible = false">Cancel</el-button>
        <el-button type="primary" @click="submitAssignment" :loading="assigning">
          Assign
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Back, ArrowDown } from '@element-plus/icons-vue'
import { taskAssignmentApi, type ReviewV2 } from '@/api/taskAssignment'

const route = useRoute()
const router = useRouter()

// State
const loading = ref(false)
const review = ref<ReviewV2 | null>(null)

// Assign dialog
const assignDialogVisible = ref(false)
const assigning = ref(false)
const assignForm = ref({
  reviewer: '',
})
const availableReviewers = ref<any[]>([])

// Load review details
const loadReview = async () => {
  const id = Number(route.params.id)
  if (!id) return

  loading.value = true
  try {
    review.value = await taskAssignmentApi.getReviewById(id)
  } catch (error) {
    console.error('Failed to load review:', error)
    ElMessage.error('Failed to load review details')
  } finally {
    loading.value = false
  }
}

// Format date
const formatDate = (dateStr: string) => {
  return new Date(dateStr).toLocaleString()
}

// Get status type
const getStatusType = (status: string) => {
  switch (status) {
    case 'open':
      return 'success'
    case 'merged':
      return 'info'
    case 'closed':
      return 'danger'
    default:
      return ''
  }
}

// Get assignment status type
const getAssignmentStatusType = (status: string) => {
  switch (status) {
    case 'completed':
      return 'success'
    case 'in_progress':
      return 'warning'
    case 'assigned':
      return 'primary'
    default:
      return 'info'
  }
}

// Go back
const goBack = () => {
  router.push('/task-assignment')
}

// Handle assign reviewer
const handleAssignReviewer = () => {
  assignForm.value.reviewer = ''
  assignDialogVisible.value = true
  // TODO: Load available reviewers
}

// Submit assignment
const submitAssignment = async () => {
  if (!assignForm.value.reviewer || !review.value) return

  assigning.value = true
  try {
    await taskAssignmentApi.assignReviewer(review.value.id, {
      reviewer: assignForm.value.reviewer,
    })
    ElMessage.success('Reviewer assigned successfully')
    assignDialogVisible.value = false
    loadReview()
  } catch (error) {
    console.error('Failed to assign reviewer:', error)
    ElMessage.error('Failed to assign reviewer')
  } finally {
    assigning.value = false
  }
}

// Update assignment status
const handleUpdateStatus = async (assignmentId: number, status: string) => {
  try {
    await taskAssignmentApi.updateAssignmentStatus(assignmentId, {
      assignment_status: status as any,
    })
    ElMessage.success('Status updated successfully')
    loadReview()
  } catch (error) {
    console.error('Failed to update status:', error)
    ElMessage.error('Failed to update status')
  }
}

// Remove reviewer
const handleRemoveReviewer = async (reviewer: string) => {
  try {
    await ElMessageBox.confirm(
      `Are you sure you want to remove reviewer "${reviewer}"?`,
      'Confirm Removal',
      {
        confirmButtonText: 'Remove',
        cancelButtonText: 'Cancel',
        type: 'warning',
      }
    )

    if (!review.value) return

    await taskAssignmentApi.removeReviewer(review.value.id, reviewer)
    ElMessage.success('Reviewer removed successfully')
    loadReview()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('Failed to remove reviewer:', error)
      ElMessage.error('Failed to remove reviewer')
    }
  }
}

onMounted(() => {
  loadReview()
})
</script>

<style scoped>
.task-detail-container {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

.detail-content {
  max-width: 1200px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.reviewer-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.display-name {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.clickable {
  cursor: pointer;
}

.ai-section {
  margin-top: 20px;
}

.code-snippet {
  background: var(--el-fill-color-light);
  padding: 12px;
  border-radius: 4px;
  overflow-x: auto;
  font-size: 12px;
}

.diff-section {
  margin-top: 20px;
}

.code-diff {
  background: var(--el-fill-color-light);
  padding: 16px;
  border-radius: 4px;
  overflow-x: auto;
  font-size: 12px;
  line-height: 1.5;
}
</style>
