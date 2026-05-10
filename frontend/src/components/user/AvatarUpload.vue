<template>
  <div class="avatar-upload">
    <div class="avatar-preview" @click="handlePreviewClick">
      <UserAvatar 
        :username="username" 
        :avatar-url="localAvatarUrl"
        :size="size"
      />
      <div class="avatar-overlay">
        <el-icon><Camera /></el-icon>
        <span>{{ localAvatarUrl ? t('avatar.edit_current') : t('common.change') }}</span>
      </div>
    </div>
    
    <input
      ref="fileInput"
      type="file"
      accept="image/jpeg,image/png,image/webp,image/gif"
      class="hidden-input"
      @change="handleFileSelect"
    />
    
    <!-- Crop Dialog -->
    <el-dialog
      v-model="showCropDialog"
      :title="t('avatar.crop_title')"
      width="600px"
      :close-on-click-modal="false"
    >
      <div class="crop-container">
        <Cropper
          ref="cropperRef"
          :src="imageSrc"
          :stencil-props="{
            aspectRatio: 1,
            movable: true,
            resizable: true
          }"
          :canvas-options="{
            fillColor: '#fff'
          }"
          class="cropper"
        />
      </div>
      
      <template #footer>
        <el-button @click="cancelCrop">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" @click="confirmCrop" :loading="uploading">
          {{ t('common.confirm') }}
        </el-button>
      </template>
    </el-dialog>
    
    <el-progress
      v-if="uploading && !showCropDialog"
      :percentage="uploadProgress"
      :stroke-width="4"
      class="upload-progress"
    />
    
    <div v-if="showActions" class="avatar-actions">
      <el-button 
        size="small" 
        type="danger" 
        :disabled="!localAvatarUrl || uploading"
        @click="handleDeleteAvatar"
      >
        {{ t('common.remove') }}
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Camera } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'
import { Cropper } from 'vue-advanced-cropper'
import 'vue-advanced-cropper/dist/style.css'
import UserAvatar from './UserAvatar.vue'
import { usersApi } from '@/api/users'

const { t } = useI18n()

const props = defineProps<{
  username: string
  avatarUrl?: string | null
  size?: number
  showActions?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:avatarUrl', url: string | null): void
  (e: 'change', url: string | null): void
}>()

const fileInput = ref<HTMLInputElement>()
const uploading = ref(false)
const uploadProgress = ref(0)
const localAvatarUrl = ref(props.avatarUrl)
const avatarSize = props.size || 80

// Cropper state
const showCropDialog = ref(false)
const imageSrc = ref('')
const selectedFile = ref<File | null>(null)
const cropperRef = ref()

// Watch for prop changes
watch(() => props.avatarUrl, (newUrl) => {
  localAvatarUrl.value = newUrl
})

const handlePreviewClick = () => {
  if (uploading.value) return
  
  // If avatar exists, show dialog to choose between edit or replace
  if (localAvatarUrl.value) {
    ElMessageBox.confirm(
      t('avatar.confirm_edit_or_replace'),
      t('avatar.edit_current'),
      {
        confirmButtonText: t('avatar.edit_current'),
        cancelButtonText: t('avatar.upload_new'),
        distinguishCancelAndClose: true,
        type: 'info',
      }
    ).then(async () => {
      // Edit current - load existing image into cropper
      await loadExistingForCrop()
    }).catch((action) => {
      if (action === 'cancel') {
        // Upload new - trigger file input
        triggerFileInput()
      }
      // If 'close', do nothing
    })
  } else {
    // No avatar yet, just trigger file input
    triggerFileInput()
  }
}

const loadExistingForCrop = async () => {
  if (!localAvatarUrl.value) return
  
  try {
    // Fetch the existing avatar image
    const response = await fetch(localAvatarUrl.value)
    const blob = await response.blob()
    
    // Create a file from the blob
    const file = new File([blob], 'avatar.jpg', { type: blob.type })
    
    // Load into cropper
    selectedFile.value = file
    imageSrc.value = URL.createObjectURL(file)
    showCropDialog.value = true
  } catch (error) {
    console.error('Failed to load existing avatar:', error)
    ElMessage.error(t('avatar.load_failed'))
    // Fallback to file upload
    triggerFileInput()
  }
}

const triggerFileInput = () => {
  if (!uploading.value) {
    fileInput.value?.click()
  }
}

const handleFileSelect = async (event: Event) => {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  
  if (!file) return
  
  // Validate file size (5MB)
  if (file.size > 5 * 1024 * 1024) {
    ElMessage.error(t('avatar.file_size_exceeded', { maxSize: '5MB' }))
    return
  }
  
  // Validate file type
  if (!['image/jpeg', 'image/png', 'image/webp', 'image/gif'].includes(file.type)) {
    ElMessage.error(t('avatar.invalid_file_type'))
    return
  }
  
  // Show crop dialog instead of uploading directly
  selectedFile.value = file
  imageSrc.value = URL.createObjectURL(file)
  showCropDialog.value = true
  
  // Reset input to allow re-uploading same file
  target.value = ''
}

const cancelCrop = () => {
  showCropDialog.value = false
  imageSrc.value = ''
  selectedFile.value = null
}

const confirmCrop = async () => {
  if (!cropperRef.value || !selectedFile.value) return
  
  try {
    // Get cropped canvas
    const { canvas } = cropperRef.value.getResult()
    
    // Convert canvas to blob
    const blob = await new Promise<Blob>((resolve) => {
      canvas.toBlob((b: Blob | null) => resolve(b!), 'image/png', 1.0)
    })
    
    // Create file from blob
    const croppedFile = new File([blob], selectedFile.value.name, {
      type: 'image/png',
    })
    
    // Close dialog
    showCropDialog.value = false
    imageSrc.value = ''
    
    // Upload the cropped image
    await uploadAvatar(croppedFile)
  } catch (error) {
    console.error('Crop error:', error)
    ElMessage.error(t('avatar.crop_failed'))
  }
}

const uploadAvatar = async (file: File) => {
  // Validate username is available
  if (!props.username || props.username === 'undefined') {
    ElMessage.error('User information not loaded. Please refresh the page.')
    return
  }
  
  uploading.value = true
  uploadProgress.value = 0
  
  try {
    const formData = new FormData()
    formData.append('file', file)
    
    // Simulate progress
    const progressInterval = setInterval(() => {
      if (uploadProgress.value < 90) {
        uploadProgress.value += 10
      }
    }, 200)
    
    const response = await usersApi.uploadAvatar(props.username, formData)
    
    clearInterval(progressInterval)
    uploadProgress.value = 100
    
    localAvatarUrl.value = response.avatar_url
    emit('update:avatarUrl', response.avatar_url)
    emit('change', response.avatar_url)
    
    ElMessage.success(t('avatar.upload_success'))
  } catch (error: any) {
    ElMessage.error(error.response?.data?.message || t('avatar.upload_failed'))
    console.error('Avatar upload failed:', error)
  } finally {
    uploading.value = false
    setTimeout(() => {
      uploadProgress.value = 0
    }, 500)
  }
}

const handleDeleteAvatar = async () => {
  // Validate username is available
  if (!props.username || props.username === 'undefined') {
    ElMessage.error('User information not loaded. Please refresh the page.')
    return
  }
  
  try {
    await ElMessageBox.confirm(
      t('confirm.delete_avatar'),
      t('common.warning'),
      {
        confirmButtonText: t('common.confirm'),
        cancelButtonText: t('common.cancel'),
        type: 'warning',
      }
    )
    
    const response = await usersApi.deleteAvatar(props.username)
    
    localAvatarUrl.value = null
    emit('update:avatarUrl', null)
    emit('change', null)
    
    ElMessage.success(t('avatar.delete_success'))
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.message || t('avatar.delete_failed'))
      console.error('Avatar deletion failed:', error)
    }
  }
}
</script>

<style scoped>
.avatar-upload {
  position: relative;
  display: inline-block;
}

.avatar-preview {
  position: relative;
  cursor: pointer;
  transition: all 0.3s ease;
}

.avatar-preview:hover .avatar-overlay {
  opacity: 1;
}

.avatar-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.5);
  border-radius: 50%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.3s ease;
  color: white;
  gap: 4px;
}

.avatar-overlay .el-icon {
  font-size: 20px;
}

.avatar-overlay span {
  font-size: 12px;
}

.hidden-input {
  display: none;
}

.upload-progress {
  margin-top: 8px;
}

.avatar-actions {
  margin-top: 8px;
  text-align: center;
}

/* Cropper styles */
.crop-container {
  height: 400px;
  width: 100%;
}

.cropper {
  height: 100%;
  width: 100%;
  background: #f5f7fa;
}

:deep(.vue-advanced-cropper) {
  border-radius: 8px;
  overflow: hidden;
}
</style>
