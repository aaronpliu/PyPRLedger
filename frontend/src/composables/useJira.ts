import { ref } from 'vue'
import { rbacApi } from '@/api/rbac'
import type { JiraSettings } from '@/utils/jira'

/**
 * JIRA link settings of the backend.
 *
 * They do not depend on the selected repository, so they are fetched once per
 * session and shared by every commit table / the release report. A failure is
 * not an error: JIRA is optional, the ticket keys then stay plain text.
 */

const jiraSettings = ref<JiraSettings | null>(null)
let pending: Promise<void> | null = null

/** Drop the cached settings (tests / a user switching to another backend). */
export function resetJiraSettings(): void {
  jiraSettings.value = null
  pending = null
}

export function useJira() {
  async function loadJiraSettings(force = false): Promise<void> {
    if (pending && !force) {
      return pending
    }

    pending = rbacApi
      .getJiraSettings()
      .then((loaded) => {
        jiraSettings.value = loaded?.base_url ? loaded : null
      })
      .catch(() => {
        jiraSettings.value = null
      })
      .finally(() => {
        pending = null
      })

    return pending
  }

  return { jiraSettings, loadJiraSettings }
}
