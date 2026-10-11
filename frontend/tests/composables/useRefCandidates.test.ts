import { describe, expect, it } from 'vitest'
import { REF_CANDIDATE_LIMIT, useRefCandidates } from '@/composables/useRefCandidates'

/** A listing of ``count`` tags, newest first, the way the API answers it. */
function listing(count: number) {
  return {
    tags: Array.from({ length: count }, (_, index) => `v1.0.${count - index}`),
    branches: ['main'],
  }
}

describe('useRefCandidates', () => {
  it('offers the recent refs and keeps the rest for the search', () => {
    const candidates = useRefCandidates()
    candidates.setCandidates(listing(842))

    expect(candidates.visibleTags.value).toHaveLength(REF_CANDIDATE_LIMIT)
    // the provider's order is kept: the first ref is the most recent one
    expect(candidates.visibleTags.value[0]).toBe('v1.0.842')
    expect(candidates.loadedCount.value).toBe(843)
  })

  it('searches the whole listing, not only the offered page', () => {
    const candidates = useRefCandidates()
    candidates.setCandidates(listing(842))

    // a tag far past the offered page is still reached by typing it
    candidates.search.value = 'v1.0.17'

    expect(candidates.visibleTags.value).toContain('v1.0.17')
    expect(candidates.visibleTags.value.length).toBeLessThanOrEqual(REF_CANDIDATE_LIMIT)
  })

  it('offers the ref being typed before the ones that merely contain it', () => {
    const candidates = useRefCandidates()
    candidates.setCandidates(listing(842))

    // "v1.0.5" is a substring of ninety-odd refs, of which the matches are capped:
    // the ref the reader is spelling out has to be the one they see
    candidates.search.value = 'v1.0.5'

    expect(candidates.visibleTags.value[0]).toBe('v1.0.5')
    expect(candidates.visibleTags.value).toContain('v1.0.5')
    expect(candidates.visibleTags.value.length).toBeLessThanOrEqual(REF_CANDIDATE_LIMIT)
  })

  it('offers nothing for a ref the repository does not report', () => {
    const candidates = useRefCandidates()
    candidates.setCandidates(listing(10))

    candidates.search.value = 'v9.9.9'

    expect(candidates.visibleTags.value).toEqual([])
    expect(candidates.visibleBranches.value).toEqual([])
    expect(candidates.knows('v9.9.9')).toBe(false)
    expect(candidates.knows('v1.0.10')).toBe(true)
    expect(candidates.knows('main')).toBe(true)
  })

  it('answers case-insensitively, the way a reader types', () => {
    const candidates = useRefCandidates()
    candidates.setCandidates({ tags: ['V1.0.0'], branches: ['Main'] })

    candidates.search.value = 'v1.0'

    expect(candidates.visibleTags.value).toEqual(['V1.0.0'])
    expect(candidates.knows('V1.0.0')).toBe(true)
  })

  it('says when the repository holds more refs than the listing received', () => {
    const candidates = useRefCandidates()
    candidates.setCandidates({ ...listing(2000), tags_total: 4210, branches_total: 12 })

    expect(candidates.capped.value).toBe(true)
    expect(candidates.loadedCount.value).toBe(2001)
    expect(candidates.totalCount.value).toBe(4222)
  })

  it('invents no cap for a provider that reports no count', () => {
    const candidates = useRefCandidates()
    candidates.setCandidates(listing(5))

    expect(candidates.capped.value).toBe(false)
    expect(candidates.totalCount.value).toBe(6)
    // six refs are all offered, so there is nothing to search for
    expect(candidates.searchable.value).toBe(false)
  })

  it('points a reader at the search once the picker offers less than it holds', () => {
    const candidates = useRefCandidates()
    candidates.setCandidates(listing(150))

    expect(candidates.searchable.value).toBe(true)
  })

  it('forgets what was typed when another repository is looked at', () => {
    const candidates = useRefCandidates()
    candidates.setCandidates(listing(10))
    candidates.search.value = 'v1.0.1'

    candidates.setCandidates(listing(3))

    expect(candidates.search.value).toBe('')
    expect(candidates.visibleTags.value).toEqual(['v1.0.3', 'v1.0.2', 'v1.0.1'])

    candidates.clearCandidates()

    expect(candidates.visibleTags.value).toEqual([])
    expect(candidates.loadedCount.value).toBe(0)
    expect(candidates.knows('v1.0.3')).toBe(false)
  })
})
