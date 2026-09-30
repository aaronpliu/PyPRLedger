import { computed, readonly, ref } from 'vue'

/**
 * A global account of the requests in flight.
 *
 * A page waiting on the git provider has nothing to show but the wait: the tags
 * and branches of a repository arrive one page at a time, and how many pages
 * there are is only known from the last one. What the app can say is that work
 * is running - and it says it for every request, rather than only for the calls
 * a page remembered to announce.
 *
 * The delay keeps a call answered in a few milliseconds from flickering the bar on
 * and off, and the floor keeps one that did appear on screen long enough to read.
 */

/** How long a request may run before it is worth announcing. */
export const PROGRESS_SHOW_DELAY_MS = 180

/** How long the bar stays once shown, however quickly the rest is answered. */
export const PROGRESS_MIN_VISIBLE_MS = 400

const pendingIds = new Set<string>()
const pending = ref(0)
const visible = ref(false)

let sequence = 0
let shownAt = 0
let showTimer: ReturnType<typeof setTimeout> | undefined
let hideTimer: ReturnType<typeof setTimeout> | undefined

function show(): void {
  visible.value = true
  shownAt = Date.now()
}

function hide(): void {
  visible.value = false
}

/**
 * Record that a request has started and return the id that ends it.
 */
export function beginProgress(): string {
  const id = `request-${++sequence}`
  pendingIds.add(id)
  pending.value = pendingIds.size

  if (hideTimer !== undefined) {
    // work resumed while the bar was on its way out: let it stay where it is
    clearTimeout(hideTimer)
    hideTimer = undefined
  }
  if (!visible.value && showTimer === undefined) {
    showTimer = setTimeout(() => {
      showTimer = undefined
      if (pendingIds.size > 0) {
        show()
      }
    }, PROGRESS_SHOW_DELAY_MS)
  }
  return id
}

/**
 * End the request ``id``, or every open one when no id is given.
 *
 * Ending an id nobody opened does nothing: a request that was retried, or an
 * answer that arrived twice, must not end the work of another call.
 */
export function endProgress(id?: string | null): void {
  if (id) {
    if (!pendingIds.delete(id)) {
      return
    }
  } else {
    pendingIds.clear()
  }
  pending.value = pendingIds.size
  if (pending.value > 0) {
    return
  }

  if (!visible.value) {
    // never became visible: it does not need to, so leave no timer behind
    if (showTimer !== undefined) {
      clearTimeout(showTimer)
      showTimer = undefined
    }
    return
  }

  const remaining = Math.max(0, PROGRESS_MIN_VISIBLE_MS - (Date.now() - shownAt))
  if (hideTimer !== undefined) {
    clearTimeout(hideTimer)
  }
  hideTimer = setTimeout(() => {
    hideTimer = undefined
    if (pendingIds.size === 0) {
      hide()
    }
  }, remaining)
}

/** Drop every open request. For a session that ended, and for tests. */
export function resetProgress(): void {
  pendingIds.clear()
  pending.value = 0
  if (showTimer !== undefined) {
    clearTimeout(showTimer)
    showTimer = undefined
  }
  if (hideTimer !== undefined) {
    clearTimeout(hideTimer)
    hideTimer = undefined
  }
  hide()
}

/** The progress state, for the component that draws it. */
export function useProgress() {
  return {
    visible: readonly(visible),
    pending: readonly(pending),
    active: computed(() => pending.value > 0),
  }
}
