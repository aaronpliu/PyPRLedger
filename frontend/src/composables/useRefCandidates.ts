import { computed, ref } from 'vue'
import type { ComputedRef, Ref } from 'vue'

/**
 * How many candidates a picker offers without typing.
 *
 * The list a picker holds is the provider's whole answer - hundreds of tags, most
 * recently modified first - and it is meant to be searched rather than scrolled: a
 * dropdown holding every one of them is slow to open and impossible to read. What
 * is not offered is still reached by typing, and the search runs over the whole
 * listing rather than over this page of it.
 */
export const REF_CANDIDATE_LIMIT = 100

/**
 * The refs a picker offers for a query: the matches, capped, best first.
 *
 * What the query *is* comes first, then what it begins, then what merely contains
 * it - the matches are capped, so their order is what keeps a common substring
 * ("v1.0.5" inside "v1.0.599") from burying the ref being spelled out. The order
 * the caller passes in decides within each group, so a listing that arrives most
 * recently modified first stays that way.
 */
export function searchCandidates(
  refs: string[],
  query: string,
  limit: number = REF_CANDIDATE_LIMIT,
): string[] {
  const keyword = (query ?? '').trim().toLowerCase()
  if (!keyword) {
    return refs.slice(0, limit)
  }

  const rank = (ref: string) => {
    const name = ref.toLowerCase()
    if (name === keyword) return 0
    return name.startsWith(keyword) ? 1 : 2
  }

  return refs
    .filter((ref) => ref.toLowerCase().includes(keyword))
    .sort((a, b) => rank(a) - rank(b))
    .slice(0, limit)
}

/** A provider's ref listing, as `POST /release/diff/refs` answers it. */
export interface RefListing {
  tags: string[]
  branches: string[]
  /** What the repository holds, when the provider reports a count of its own. */
  tags_total?: number | null
  branches_total?: number | null
}

export interface RefCandidates {
  /** What the listing holds, most recently modified first. */
  tags: Ref<string[]>
  branches: Ref<string[]>
  /** What the repository holds, when the provider reports it. */
  tagsTotal: Ref<number | null>
  branchesTotal: Ref<number | null>
  /** What the reader has typed. */
  search: Ref<string>
  /** What the picker renders: matching refs out of the whole listing, capped. */
  visibleTags: ComputedRef<string[]>
  visibleBranches: ComputedRef<string[]>
  /** How many refs are held, how many offered, and whether more exist. */
  loadedCount: ComputedRef<number>
  totalCount: ComputedRef<number>
  /** True when the repository holds more refs than this listing received. */
  capped: ComputedRef<boolean>
  /** True when the picker offers fewer refs than the listing holds. */
  searchable: ComputedRef<boolean>
  /** Whether the repository reports this ref at all. */
  knows: (ref: string) => boolean
  /** Take a provider answer, and forget what was typed for the last one. */
  setCandidates: (listing: RefListing) => void
  /** Drop the candidates: another repository is being looked at. */
  clearCandidates: () => void
}

/** A ref picker's candidates: the whole listing, searched, capped for display. */
export function useRefCandidates(): RefCandidates {
  const tags = ref<string[]>([])
  const branches = ref<string[]>([])
  const tagsTotal = ref<number | null>(null)
  const branchesTotal = ref<number | null>(null)
  const search = ref('')

  const visibleTags = computed(() => searchCandidates(tags.value, search.value))
  const visibleBranches = computed(() => searchCandidates(branches.value, search.value))

  const loadedCount = computed(() => tags.value.length + branches.value.length)
  // A kind the provider did not count counts as its listing: an uncounted kind must
  // not inflate the total into a cap that is not there.
  const totalCount = computed(
    () => (tagsTotal.value ?? tags.value.length) + (branchesTotal.value ?? branches.value.length),
  )
  const capped = computed(() => totalCount.value > loadedCount.value)
  const searchable = computed(
    () => loadedCount.value > REF_CANDIDATE_LIMIT || capped.value,
  )

  function knows(ref: string): boolean {
    const name = (ref ?? '').trim()
    return tags.value.includes(name) || branches.value.includes(name)
  }

  function setCandidates(listing: RefListing): void {
    tags.value = listing.tags ?? []
    branches.value = listing.branches ?? []
    tagsTotal.value = listing.tags_total ?? null
    branchesTotal.value = listing.branches_total ?? null
    search.value = ''
  }

  function clearCandidates(): void {
    setCandidates({ tags: [], branches: [] })
  }

  return {
    tags,
    branches,
    tagsTotal,
    branchesTotal,
    search,
    visibleTags,
    visibleBranches,
    loadedCount,
    totalCount,
    capped,
    searchable,
    knows,
    setCandidates,
    clearCandidates,
  }
}
