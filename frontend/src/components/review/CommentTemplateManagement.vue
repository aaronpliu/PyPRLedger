<template>
  <div class="comment-template-management">
    <div class="ctm-header">
      <h3>{{ t('profile.comment_templates.title') }}</h3>
      <div class="header-actions">
        <el-button type="primary" @click="loadTemplates" :loading="loading">
          <el-icon><Refresh /></el-icon>
          {{ t('profile.comment_templates.refresh') }}
        </el-button>
        <el-button type="primary" @click="openCreateDialog">
          <el-icon><Plus /></el-icon>
          {{ t('profile.comment_templates.new_template') }}
        </el-button>
      </div>
    </div>

    <p class="ctm-description">{{ t('profile.comment_templates.description') }}</p>

    <!-- Template List -->
    <div v-loading="loading" class="template-list">
      <el-empty v-if="!loading && templates.length === 0" :description="t('profile.comment_templates.empty')">
        <el-button type="primary" @click="openCreateDialog">{{ t('profile.comment_templates.create_template') }}</el-button>
      </el-empty>

      <el-table v-else :data="templates" stripe style="width: 100%">
        <el-table-column prop="name" :label="t('profile.comment_templates.name')" min-width="180">
          <template #default="{ row }">
            <span class="template-name">{{ row.name }}</span>
          </template>
        </el-table-column>

        <el-table-column :label="t('profile.comment_templates.content')" min-width="280">
          <template #default="{ row }">
            <div class="template-content">{{ row.content }}</div>
          </template>
        </el-table-column>

        <el-table-column :label="t('profile.comment_templates.updated')" width="170">
          <template #default="{ row }">
            {{ formatDate(row.updated_at) }}
          </template>
        </el-table-column>

        <el-table-column :label="t('profile.comment_templates.created')" width="170">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>

        <el-table-column :label="t('profile.comment_templates.actions')" width="150" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" link @click="openEditDialog(row)">
              {{ t('profile.comment_templates.edit') }}
            </el-button>
            <el-button size="small" type="danger" link @click="handleDeleteTemplate(row)">
              {{ t('profile.comment_templates.delete') }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- Create / Edit Template Dialog -->
    <el-dialog
      v-model="showDialog"
      :title="editingTemplate ? t('profile.comment_templates.dialog_edit') : t('profile.comment_templates.dialog_new')"
      width="650px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="formRules"
        label-width="100px"
      >
        <el-form-item :label="t('profile.comment_templates.name')" prop="name">
          <el-input
            v-model="form.name"
            :placeholder="t('profile.comment_templates.name_ph')"
            maxlength="100"
            show-word-limit
          />
          <div class="form-help">{{ t('profile.comment_templates.name_help') }}</div>
        </el-form-item>

        <el-form-item :label="t('profile.comment_templates.content')" prop="content">
          <el-input
            v-model="form.content"
            type="textarea"
            :rows="8"
            :placeholder="t('profile.comment_templates.content_ph')"
            maxlength="5000"
            show-word-limit
          />
          <div class="form-help">{{ t('profile.comment_templates.content_help') }}</div>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="showDialog = false">{{ t('common.cancel', 'Cancel') }}</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">
          {{ editingTemplate ? t('profile.comment_templates.save_changes') : t('profile.comment_templates.create_template') }}
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
import { useI18n } from 'vue-i18n'
import {
  userCommentTemplatesApi,
  type UserCommentTemplate,
} from '@/api/userCommentTemplates'

const { t } = useI18n()
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
    { required: true, message: t('profile.comment_templates.rule_name'), trigger: 'blur' },
    { min: 1, max: 100, message: t('profile.comment_templates.rule_name_len'), trigger: 'blur' },
  ],
  content: [
    { required: true, message: t('profile.comment_templates.rule_content'), trigger: 'blur' },
    {
      min: 1,
      max: 5000,
      message: t('profile.comment_templates.rule_content_len'),
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
    ElMessage.error(t('profile.comment_templates.load_failed'))
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
        ElMessage.success(t('profile.comment_templates.updated_success'))
      } else {
        await userCommentTemplatesApi.createTemplate({
          name: form.name,
          content: form.content,
        })
        ElMessage.success(t('profile.comment_templates.created_success'))
      }

      showDialog.value = false
      await loadTemplates()
    } catch (error: any) {
      ElMessage.error(error?.response?.data?.message || t('profile.comment_templates.save_failed'))
    } finally {
      saving.value = false
    }
  })
}

const handleDeleteTemplate = async (template: UserCommentTemplate) => {
  try {
    await ElMessageBox.confirm(
      t('profile.comment_templates.delete_body', { name: template.name }),
      t('profile.comment_templates.delete_title'),
      { type: 'warning' },
    )

    await userCommentTemplatesApi.deleteTemplate(template.id)
    ElMessage.success(t('profile.comment_templates.deleted_success'))
    await loadTemplates()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(t('profile.comment_templates.delete_failed'))
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
