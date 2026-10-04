import { describe, expect, it } from 'vitest'
import {
  GIT_PROVIDER_OPTIONS,
  GitProvider,
  getGitProviderLabel,
  getGitProviderTagType,
} from '@/constants/gitProvider'

/**
 * Every provider the system knows has to be presentable and selectable: a
 * provider missing from the options reads as its raw value and cannot be picked
 * in any dropdown built from them.
 */
describe('git provider presentation', () => {
  it('offers every provider the system knows', () => {
    expect(GIT_PROVIDER_OPTIONS.map((option) => option.value)).toEqual(
      Object.values(GitProvider),
    )
  })

  it('labels every provider with something other than its raw value', () => {
    for (const provider of Object.values(GitProvider)) {
      expect(getGitProviderLabel(provider)).not.toBe(provider)
    }
  })

  it('distinguishes the providers it knows', () => {
    expect(getGitProviderTagType(GitProvider.BITBUCKET_SERVER)).toBe('')
    expect(getGitProviderTagType(GitProvider.BITBUCKET_CLOUD)).toBe('warning')
    expect(getGitProviderTagType(GitProvider.GITHUB_ENTERPRISE)).toBe('success')
  })

  it('falls back to the raw name for something it does not know', () => {
    expect(getGitProviderLabel('bitbucket_team')).toBe('bitbucket_team')
    expect(getGitProviderTagType('bitbucket_team')).toBe('info')
  })
})
