<template>
  <div class="comment-template-management">
    <div class="ctm-header">
      <h3>My Comment Templates</h3>
      <div class="header-actions">
        <el-button @click="loadTemplates" :loading="loading">
          <el-icon><Refresh /></el-icon>
          Refresh
        </el-button>
        <el-button type="primary" @click="openCreateDialog">
          <el-icon><Plus /></el-icon>
          New Template
        </el-button>
      </div>
    </div>

    <p class="ctm-description">
      Save frequently used review comments as reusable templates. They will be available in the
      "Add Score" dialog when writing a score review, making your comments personalized.
    </p>

    <!-- Template List -->
    <div v-loading="loading" class="template-list">
      <el-empty v-if="!loading && templates.length === 0" description="No comment templates yet">
        <el-button type="primary" @click="openCreateDialog">Create Template</el-button>
      </el-empty>

      <el-table v-else :data="templates" stripe style="width: 100%">
        <el-table-column prop="name" label="Name" min-width="180">
          <template #default="{ row }">
            <span class="template-name">{{ row.name }}</span>
          </template>
        </el-table-column>

        <el-table-column label="Content" min-width="280">
          <template #default="{ row }">
            <div class="template-content">{{ row.content }}</div>
          </template>
        </el-table-column>

        <el-table-column label="Updated" width="170">
          <template #default="{ row }">
            {{ formatDate(row.updated_at) }}
          </template>
        </el-table-column>

        <el-table-column label="Created" width="170">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>

        <el-table-column label="Actions" width="150" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" link @click="openEditDialog(row)">
              Edit
            </el-button>
            <el-button size="small" type="danger" link @click="handleDeleteTemplate(row)">
              Delete
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- Create / Edit Template Dialog -->
    <el-dialog
      v-model="showDialog"
      :title="editingTemplate ? 'Edit Comment Template' : 'New Comment Template'"
      width="650px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="formRules"
        label-width="100px"
      >
        <el-form-item label="Name" prop="name">
          <el-input
            v-model="form.name"
            placeholder="e.g., Excellent - approve, Minor typo fixes"
            maxlength="100"
            show-word-limit
          />
          <div class="form-help">A short name shown in the template dropdown</div>
        </el-form-item>

        <el-form-item label="Content" prop="content">
          <el-input
            v-model="form.content"
            type="textarea"
            :rows="8"
            placeholder="Write the review comment (Markdown supported)..."
            maxlength="5000"
            show-word-limit
          />
          <div class="form-help">The comment inserted into the editor when this template is selected</div>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="showDialog = false">Cancel</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">
          {{ editingTemplate ? 'Save Changes' : 'Create Template' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'
import dayjs from 'dayjs'
import {
  userCommentTemplatesApi,
  type UserCommentTemplate,
} from '@/api/userCommentTemplates'

const loading = ref(false)
const saving = ref(false)
const templates = ref<UserCommentTemplate[]>([])

// Create / Edit dialog
const showDialog = ref(false)
const editingTemplate = ref<UserCommentTemplate | null>(null)
const formRef = ref<FormInstance>()
const form = reactive<{ name: string; content: string }>({
  name: '',
  content: '',
})

const formRules: FormRules = {
  name: [
    { required: true, message: 'Please enter a template name', trigger: 'blur' },
    { min: 1, max: 100, message: 'Name must be between 1 and 100 characters', trigger: 'blur' },
  ],
  content: [
    { required: true, message: 'Please enter template content', trigger: 'blur' },
    {
      min: 1,
      max: 5000,
      message: 'Content must be between 1 and 5000 characters',
      trigger: 'blur',
    },
  ],
}

// Load templates
const loadTemplates = async () => {
  loading.value = true
  try {
    const response = await userCommentTemplatesApi.listTemplates()
    templates.value = response.items
  } catch (error) {
    ElMessage.error('Failed to load comment templates')
  } finally {
    loading.value = false
  }
}

const resetForm = () => {
  form.name = ''
  form.content = ''
  editingTemplate.value = null
}

const openCreateDialog = () => {
  resetForm()
  showDialog.value = true
}

const openEditDialog = (template: UserCommentTemplate) => {
  editingTemplate.value = template
  form.name = template.name
  form.content = template.content
  showDialog.value = true
}

const handleSave = async () => {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (!valid) return

    saving.value = true
    try {
      if (editingTemplate.value) {
        await userCommentTemplatesApi.updateTemplate(editingTemplate.value.id, {
          name: form.name,
          content: form.content,
        })
        ElMessage.success('Template updated successfully')
      } else {
        await userCommentTemplatesApi.createTemplate({
          name: form.name,
          content: form.content,
        })
        ElMessage.success('Template created successfully')
      }

      showDialog.value = false
      await loadTemplates()
    } catch (error: any) {
      ElMessage.error(error?.response?.data?.message || 'Failed to save template')
    } finally {
      saving.value = false
    }
  })
}

const handleDeleteTemplate = async (template: UserCommentTemplate) => {
  try {
    await ElMessageBox.confirm(
      `Are you sure you want to delete the template "${template.name}"? This action cannot be undone.`,
      'Delete Template',
      { type: 'warning' },
    )

    await userCommentTemplatesApi.deleteTemplate(template.id)
    ElMessage.success('Template deleted successfully')
    await loadTemplates()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('Failed to delete template')
    }
  }
}

// Format date - converts UTC to local timezone
const formatDate = (dateStr: string) => {
  return dayjs(dateStr).format('YYYY-MM-DD HH:mm:ss')
}

onMounted(() => {
  loadTemplates()
})
</script>

<style scoped>
.comment-template-management {
  padding: 20px;
}

.ctm-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.ctm-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.ctm-description {
  color: var(--el-text-color-secondary);
  font-size: 14px;
  line-height: 1.6;
  margin-bottom: 24px;
}

.template-list {
  min-height: 300px;
}

.template-name {
  font-weight: 500;
}

.template-content {
  color: var(--el-text-color-regular);
  font-size: 13px;
  white-space: pre-wrap;
  word-break: break-word;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.form-help {
  color: var(--el-text-color-secondary);
  font-size: 12px;
  margin-top: 4px;
  line-height: 1.4;
}
</style>
