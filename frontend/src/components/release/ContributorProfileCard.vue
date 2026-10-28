<template>
  <!-- What a hover over a contributor says about them: the picture and the name
       the instance holds, the login the commits carry, and the way to their page
       on the platform. Nothing is invented for an author the instance has no
       account for - the card then shows what the commits said. -->
  <div class="contributor-card" data-test="contributor-card">
    <div class="contributor-card-head">
      <UserAvatar
        class="contributor-card-avatar"
        :username="username || displayName || '?'"
        :avatar-url="avatarUrl"
        :size="44"
      />
      <div class="contributor-card-identity">
        <p class="contributor-card-name">{{ displayName || login }}</p>
        <p v-if="displayName && username" class="contributor-card-login">{{ login }}</p>
      </div>
    </div>

    <p class="contributor-card-commits">
      {{ t('releaseNotes.contributor_commits', { count: commitCount }) }}
    </p>

    <a
      v-if="profileUrl"
      class="contributor-card-link"
      :href="profileUrl"
      target="_blank"
      rel="noopener"
    >
      {{ t('releaseNotes.contributor_profile') }}
    </a>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import UserAvatar from '@/components/user/UserAvatar.vue'

interface Props {
  /** Provider login the commits carry, when they carry one */
  username?: string | null
  /** Name the commits report for the author */
  displayName?: string | null
  /** Picture of the instance account the author is bound to, when there is one */
  avatarUrl?: string | null
  /** Browsable profile page on the platform, when it has one */
  profileUrl?: string | null
  /** Commits this person wrote in the release scope */
  commitCount?: number
}

const props = withDefaults(defineProps<Props>(), {
  username: null,
  displayName: null,
  avatarUrl: null,
  profileUrl: null,
  commitCount: 0,
})

const { t } = useI18n()

const login = computed(() => (props.username ? `@${props.username}` : ''))
</script>

<style scoped>
.contributor-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 2px;
}

.contributor-card-head {
  display: flex;
  align-items: center;
  gap: 12px;
}

.contributor-card-avatar {
  box-sizing: border-box;
  flex: none;
  border: 1px solid var(--el-border-color-lighter);
}

.contributor-card-identity {
  min-width: 0;
}

.contributor-card-name {
  margin: 0;
  overflow: hidden;
  color: var(--el-text-color-primary);
  font-weight: 600;
  font-size: 14px;
  line-height: 1.3;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.contributor-card-login {
  margin: 2px 0 0;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.4;
}

.contributor-card-commits {
  margin: 0;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.4;
}

.contributor-card-link {
  align-self: flex-start;
  color: var(--el-color-primary);
  font-size: 12px;
  text-decoration: none;
}

.contributor-card-link:hover {
  text-decoration: underline;
}
</style>
