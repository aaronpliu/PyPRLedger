<template>
  <div
    class="contributor-overflow-panel"
    data-test="contributor-overflow-panel"
    @mouseleave="activeIndex = null"
  >
    <!-- The people a crowded release only counts: a list short enough to scan, with
         the card of whoever the pointer rests on underneath, so a name is never all
         that is known about a person -->
    <p class="contributor-overflow-title">
      {{ t('releaseNotes.contributor_more', { count: contributors.length }) }}
    </p>

    <ul class="contributor-overflow-list">
      <li
        v-for="(person, index) in contributors"
        :key="person.username || person.display_name || index"
        class="contributor-overflow-row"
        :class="{ 'is-active': activeIndex === index }"
        data-test="contributor-overflow-row"
        tabindex="0"
        @mouseenter="activeIndex = index"
        @focusin="activeIndex = index"
      >
        <UserAvatar
          :username="person.username || person.display_name || '?'"
          :avatar-url="person.avatar_url"
          :size="24"
        />
        <span class="contributor-overflow-name">{{ label(person) }}</span>
        <span class="contributor-overflow-commits">
          {{ t('releaseNotes.contributor_commits', { count: person.commit_count }) }}
        </span>
      </li>
    </ul>

    <div v-if="active" class="contributor-overflow-detail">
      <ContributorProfileCard
        :username="active.username"
        :display-name="active.display_name"
        :avatar-url="active.avatar_url"
        :profile-url="active.profile_url"
        :commit-count="active.commit_count"
        :last-committed="active.last_committed"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import type { ReleaseNoteContributor } from '@/api/releaseNotes'
import ContributorProfileCard from '@/components/release/ContributorProfileCard.vue'
import UserAvatar from '@/components/user/UserAvatar.vue'

interface Props {
  /** The people the faces did not draw, in the order they are credited */
  contributors: ReleaseNoteContributor[]
}

const props = defineProps<Props>()

const { t } = useI18n()

// Whichever row the pointer (or the keyboard) is on: its card is what the panel
// shows below the list, so the list stays one line per person
const activeIndex = ref<number | null>(null)

const active = computed<ReleaseNoteContributor | null>(() =>
  activeIndex.value === null ? null : (props.contributors[activeIndex.value] ?? null),
)

/** The login a person is credited under, or the name when the commits carry none. */
function label(person: ReleaseNoteContributor): string {
  return person.username ? `@${person.username}` : person.display_name || ''
}
</script>

<style scoped>
.contributor-overflow-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.contributor-overflow-title {
  margin: 0;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  font-weight: 600;
}

.contributor-overflow-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  max-height: 200px;
  margin: 0;
  padding: 0;
  overflow-y: auto;
  list-style: none;
}

.contributor-overflow-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 6px;
  border-radius: 6px;
  outline: none;
  cursor: default;
}

.contributor-overflow-row.is-active,
.contributor-overflow-row:focus-visible {
  background: var(--el-fill-color-light);
}

.contributor-overflow-name {
  flex: 1;
  overflow: hidden;
  color: var(--el-text-color-regular);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.contributor-overflow-row.is-active .contributor-overflow-name {
  color: var(--el-color-primary);
}

.contributor-overflow-commits {
  flex: none;
  color: var(--el-text-color-secondary);
  font-size: 11px;
}

.contributor-overflow-detail {
  padding-top: 8px;
  border-top: 1px solid var(--el-border-color-lighter);
}
</style>
