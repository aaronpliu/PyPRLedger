import { ElMessageBox } from 'element-plus'
import type { Router } from 'vue-router'

import i18n from '@/i18n'

/**
 * Recovery for a tab left open across a deployment.
 *
 * Route components are lazy imports, and a build names each chunk after its own
 * content. A tab that was open when the build was replaced still names the files
 * of the build before it, so the next navigation asks the server for a chunk that
 * no longer exists: the navigation rejects with "Failed to fetch dynamically
 * imported module" and, with nothing listening, the click appears to do nothing.
 *
 * The tab cannot repair itself - only a reload fetches the index the server serves
 * now - and reloading on its own would throw away whatever is being written on the
 * page. So the reader is told what happened and asked, once, whether to reload.
 */
const STALE_CHUNK_MESSAGES = [
  'failed to fetch dynamically imported module',
  'error loading dynamically imported module',
  'importing a module script failed',
  'unable to preload css',
  'loading chunk',
]

export function isStaleChunkError(error: unknown): boolean {
  const message =
    error instanceof Error ? error.message : typeof error === 'string' ? error : ''
  const lower = message.toLowerCase()
  return STALE_CHUNK_MESSAGES.some((known) => lower.includes(known))
}

/**
 * Watch for the two ways a stale chunk surfaces: a navigation whose lazy import
 * rejects, and Vite's own `vite:preloadError` for preloads started ahead of it.
 * Returns a function that stops watching.
 */
export function installStaleChunkRecovery(
  router: Router,
  reload: () => void = () => window.location.reload(),
): () => void {
  let asking = false
  let declined = false

  const askToReload = async () => {
    // One question at a time, and none after the reader said no: every click on a
    // stale tab fails the same way, so repeating it would be the same question
    // until they gave in.
    if (asking || declined) return
    asking = true

    try {
      await ElMessageBox.confirm(
        i18n.global.t('common.new_version.message'),
        i18n.global.t('common.new_version.title'),
        {
          confirmButtonText: i18n.global.t('common.new_version.refresh'),
          cancelButtonText: i18n.global.t('common.new_version.later'),
          type: 'warning',
          showClose: false,
          closeOnClickModal: false,
          closeOnPressEscape: false,
        },
      )
      reload()
    } catch {
      declined = true
    } finally {
      asking = false
    }
  }

  const stopRouterErrors = router.onError((error) => {
    if (isStaleChunkError(error)) void askToReload()
  })

  const onPreloadError = (event: Event) => {
    // Vite would rethrow once the event has been dispatched, turning a question we
    // are about to ask into an uncaught error in the console.
    event.preventDefault()
    void askToReload()
  }
  window.addEventListener('vite:preloadError', onPreloadError)

  return () => {
    stopRouterErrors()
    window.removeEventListener('vite:preloadError', onPreloadError)
  }
}
