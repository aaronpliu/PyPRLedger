import { computed, readonly, ref } from 'vue'

/**
 * A global account of the requests in flight.
 *
 * A page waiting on the git provider has nothing to show but the wait: the tags
 * and branches of a repository arrive one page at a time, and how many pages
 * there are is only known from the last one. What the app *can* say is that work
 * is running, what it is, and for how long - and it says it for every request,
 * rather than only for the calls a page remembered to announce.
 *
 * The delay keeps a call answered in a few milliseconds from flickering the bar on
 * and off, and the floor keeps one that did appear on screen long enough to read.
 */

/** How long a request may run before it is worth announcing. */
export const PROGRESS_SHOW_DELAY_MS = 180

/** How long the bar stays once shown, however quickly the rest is answered. */
export const PROGRESS_MIN_VISIBLE_MS = 400

/**
 * The calls that leave our own backend - to the git provider or to a model - and
 * can take long enough to be worth naming. A call with no entry here is tracked
 * all the same; it just shows the generic label, since the bar cannot explain
 * what it does not know.
 */
const SLOW_CALLS: ReadonlyArray<readonly [RegExp, string]> = [
  [/\/release\/diff\/refs/, 'common.loading_refs'],
  [/\/release\/diff\/(compare|check)/, 'common.loading_compare'],
  [/\/release\/notes\/preview/, 'common.loading_preview'],
]

/** The translation key naming what ``url`` is doing, or ``null`` when silent. */
export function progressLabelFor(url: string | undefined): string | null {
  if (!url) {
    return null
  }
  for (const [pattern, key] of SLOW_CALLS) {
    if (pattern.test(url)) {
      return key
    }
  }
  return null
}

const pendingIds = new Set<string>()
const pending = ref(0)
const label = ref<string | null>(null)
const visible = ref(false)
const elapsedSeconds = ref(0)

let sequence = 0
let shownAt = 0
let showTimer: ReturnType<typeof setTimeout> | undefined
let hideTimer: ReturnType<typeof setTimeout> | undefined
let tickTimer: ReturnType<typeof setInterval> | undefined

function stopTicking(): void {
  if (tickTimer !== undefined) {
    clearInterval(tickTimer)
    tickTimer = undefined
  }
}

function show(): void {
  visible.value = true
  shownAt = Date.now()
  elapsedSeconds.value = 0
  stopTicking()
  // a call that runs for seconds is the case this exists for: count for the
  // reader rather than leave them a spinner that could mean anything
  tickTimer = setInterval(() => {
    elapsedSeconds.value = Math.floor((Date.now() - shownAt) / 1000)
  }, 1000)
}

function hide(): void {
  visible.value = false
  label.value = null
  elapsedSeconds.value = 0
  stopTicking()
}

/**
 * Record that a request has started and return the id that ends it.
 *
 * ``requestLabel`` is a translation key: what the call is doing, for the calls
 * that take long enough for the reader to wonder.
 */
export function beginProgress(requestLabel?: string | null): string {
  const id = `request-${++sequence}`
  pendingIds.add(id)
  pending.value = pendingIds.size
  if (requestLabel) {
    label.value = requestLabel
  }

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
    // never became visible: it does not need to, but the name it carried must
    // not outlive the work it named
    if (showTimer !== undefined) {
      clearTimeout(showTimer)
      showTimer = undefined
    }
    label.value = null
    elapsedSeconds.value = 0
    stopTicking()
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

/** Name what is running, for a call the caller knows more about than the bar. */
export function setProgressLabel(requestLabel: string | null): void {
  label.value = requestLabel
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
    label: readonly(label),
    elapsedSeconds: readonly(elapsedSeconds),
    pending: readonly(pending),
    active: computed(() => pending.value > 0),
  }
}
