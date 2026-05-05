<template>
  <div class="notification-preferences-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <h2>{{ t('notifications.preferences_title') }}</h2>
          <el-button type="primary" @click="saveAllPreferences" :loading="saving">
            {{ t('common.save') }}
          </el-button>
        </div>
      </template>

      <el-alert
        :title="t('notifications.preferences_description')"
        type="info"
        :closable="false"
        style="margin-bottom: 20px"
      />

      <div v-loading="loading" class="preferences-list">
        <div
          v-for="pref in preferences"
          :key="pref.notification_type"
          class="preference-item"
        >
          <div class="preference-header">
            <h3>{{ getNotificationTypeLabel(pref.notification_type) }}</h3>
            <p class="preference-description">
              {{ getNotificationTypeDescription(pref.notification_type) }}
            </p>
          </div>

          <div class="preference-channels">
            <el-form label-position="left" label-width="120px">
              <el-form-item :label="t('notifications.channel_in_app')">
                <el-switch
                  v-model="pref.in_app_enabled"
                  :active-text="t('common.enabled')"
                  :inactive-text="t('common.disabled')"
                />
              </el-form-item>

              <el-form-item :label="t('notifications.channel_email')">
                <el-switch
                  v-model="pref.email_enabled"
                  :active-text="t('common.enabled')"
                  :inactive-text="t('common.disabled')"
                  :disabled="!smtpConfigured"
                />
                <el-tooltip
                  v-if="!smtpConfigured"
                  :content="t('notifications.smtp_not_configured')"
                  placement="top"
                >
                  <el-icon class="info-icon"><InfoFilled /></el-icon>
                </el-tooltip>
              </el-form-item>

              <el-form-item :label="t('notifications.channel_slack')">
                <el-switch
                  v-model="pref.slack_enabled"
                  :active-text="t('common.enabled')"
                  :inactive-text="t('common.disabled')"
                  :disabled="!slackConfigured"
                />
                <el-tooltip
                  v-if="!slackConfigured"
                  :content="t('notifications.slack_not_configured')"
                  placement="top"
                >
                  <el-icon class="info-icon"><InfoFilled /></el-icon>
                </el-tooltip>
              </el-form-item>

              <el-divider />

              <el-form-item :label="t('notifications.all_channels')">
                <el-switch
                  :model-value="areAllChannelsEnabled(pref)"
                  @change="(val: boolean) => toggleAllChannels(pref, val)"
                  :active-text="t('common.enable_all')"
                  :inactive-text="t('common.disable_all')"
                />
              </el-form-item>
            </el-form>
          </div>
        </div>

        <el-empty v-if="!loading && preferences.length === 0" :description="t('notifications.no_preferences')" />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { InfoFilled } from '@element-plus/icons-vue'
import {
  notificationsApi,
  type NotificationPreference,
} from '@/api/notifications'

const { t } = useI18n()

const loading = ref(false)
const saving = ref(false)
const preferences = ref<NotificationPreference[]>([])
const smtpConfigured = ref(false)
const slackConfigured = ref(false)

onMounted(() => {
  loadPreferences()
  checkIntegrations()
})

async function loadPreferences() {
  loading.value = true
  try {
    preferences.value = await notificationsApi.getPreferences()
  } catch (error) {
    ElMessage.error(t('notifications.load_preferences_error'))
    console.error('Failed to load preferences:', error)
  } finally {
    loading.value = false
  }
}

async function checkIntegrations() {
  // Check if SMTP is configured (would come from backend config endpoint)
  // For now, we'll assume it's not configured
  smtpConfigured.value = false
  
  // Check if Slack is configured
  slackConfigured.value = false
}

async function saveAllPreferences() {
  saving.value = true
  try {
    const promises = preferences.value.map((pref) =>
      notificationsApi.updatePreference(pref.notification_type, {
        in_app_enabled: pref.in_app_enabled,
        email_enabled: pref.email_enabled,
        slack_enabled: pref.slack_enabled,
      })
    )

    await Promise.all(promises)
    ElMessage.success(t('notifications.preferences_saved'))
  } catch (error) {
    ElMessage.error(t('notifications.save_preferences_error'))
    console.error('Failed to save preferences:', error)
  } finally {
    saving.value = false
  }
}

function areAllChannelsEnabled(pref: NotificationPreference): boolean {
  return pref.in_app_enabled && pref.email_enabled && pref.slack_enabled
}

function toggleAllChannels(pref: NotificationPreference, enabled: boolean) {
  pref.in_app_enabled = enabled
  pref.email_enabled = enabled && smtpConfigured.value
  pref.slack_enabled = enabled && slackConfigured.value
}

function getNotificationTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    review_assigned: t('notifications.type_review_assigned'),
    review_completed: t('notifications.type_review_completed'),
    delegation_expiry: t('notifications.type_delegation_expiry'),
    system_alert: t('notifications.type_system_alert'),
  }
  return labels[type] || type
}

function getNotificationTypeDescription(type: string): string {
  const descriptions: Record<string, string> = {
    review_assigned: t('notifications.desc_review_assigned'),
    review_completed: t('notifications.desc_review_completed'),
    delegation_expiry: t('notifications.desc_delegation_expiry'),
    system_alert: t('notifications.desc_system_alert'),
  }
  return descriptions[type] || ''
}
</script>

<style scoped>
.notification-preferences-container {
  padding: 20px;
  max-width: 900px;
  margin: 0 auto;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header h2 {
  margin: 0;
  font-size: 20px;
}

.preferences-list {
  min-height: 300px;
}

.preference-item {
  padding: 24px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  margin-bottom: 16px;
  background: var(--el-bg-color);
}

.preference-item:last-child {
  margin-bottom: 0;
}

.preference-header {
  margin-bottom: 20px;
  padding-bottom: 12px;
  border-bottom: 2px solid var(--el-border-color-lighter);
}

.preference-header h3 {
  margin: 0 0 8px 0;
  font-size: 18px;
  color: var(--el-text-color-primary);
}

.preference-description {
  margin: 0;
  font-size: 14px;
  color: var(--el-text-color-secondary);
  line-height: 1.5;
}

.preference-channels {
  padding-left: 20px;
}

.info-icon {
  margin-left: 8px;
  color: var(--el-color-info);
  cursor: help;
}

.el-form-item {
  margin-bottom: 16px;
}

@media (max-width: 768px) {
  .preference-channels {
    padding-left: 0;
  }
}
</style>
