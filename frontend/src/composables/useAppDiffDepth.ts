import { ref, watch } from 'vue'
import type { AppVersionDiffRequest } from '@/api/appVersionDiff'

const DEPTH_STORAGE_KEY = 'app_diff_depth'

/**
 * How deep a comparison reads: a choice, rather than two numbers in a form.
 *
 * The numbers behind each depth are asking prices, not facts - the server holds the
 * ceilings and answers with what it actually read, and the page shows that. So the
 * default depth asks for nothing and lets the server's defaults stand, rather than
 * repeating them here where they could drift.
 */
export type AppDiffDepth = 'default' | 'deep' | 'all'

/** What a depth asks the server for. */
type AppDiffDepthRequest = Pick<
  AppVersionDiffRequest,
  'max_package_comparisons' | 'max_total_package_comparisons'
>

const DEPTH_REQUESTS: Record<AppDiffDepth, AppDiffDepthRequest> = {
  // nothing is asked for: the server's own defaults decide what a request reads
  default: {},
  // more of each pair in the answer, and more of the rest read behind the page
  deep: { max_package_comparisons: 25, max_total_package_comparisons: 200 },
  // everything a request may read: a deeper ask than this only meets the ceiling
  all: { max_package_comparisons: 50, max_total_package_comparisons: 300 },
}

const DEPTHS: AppDiffDepth[] = ['default', 'deep', 'all']

function isDepth(value: string | null): value is AppDiffDepth {
  return DEPTHS.some((depth) => depth === value)
}

/**
 * The reading depth, and whether the choice is kept for the next visit.
 *
 * A reader who compares the same shape of releases over and over should not have to
 * deepen the reading every time, and one who wanted it once should not have to undo
 * it. So keeping it is their choice, and it is kept where a preference belongs -
 * against the browser, not against the comparison, which is shareable by link.
 */
export function useAppDiffDepth() {
  const stored = localStorage.getItem(DEPTH_STORAGE_KEY)
  const depth = ref<AppDiffDepth>(isDepth(stored) ? stored : 'default')
  const remembered = ref(isDepth(stored))

  // Keeping the choice means keeping it current: deepening it while it is remembered
  // changes what the next visit opens on; letting it go drops it.
  watch([depth, remembered], ([value, keep]) => {
    if (keep) {
      localStorage.setItem(DEPTH_STORAGE_KEY, value)
    } else {
      localStorage.removeItem(DEPTH_STORAGE_KEY)
    }
  })

  /** What the chosen depth asks the server for. */
  function depthRequest(): AppDiffDepthRequest {
    return DEPTH_REQUESTS[depth.value]
  }

  return { depth, remembered, depthRequest }
}
