/**
 * Git provider constants following Open/Closed Principle.
 *
 * To add a new provider:
 * 1. Add a new constant here
 * 2. Update GIT_PROVIDER_OPTIONS if UI selection is needed
 * 3. Update usePrUrl composable for URL generation logic
 */

export const GitProvider = {
  BITBUCKET_SERVER: 'bitbucket_server',
  BITBUCKET_CLOUD: 'bitbucket_cloud',
  GITHUB_ENTERPRISE: 'github_enterprise',
} as const

export type GitProviderType = (typeof GitProvider)[keyof typeof GitProvider]

export const DEFAULT_GIT_PROVIDER = GitProvider.BITBUCKET_SERVER

/**
 * UI options for git provider selection dropdowns
 */
export const GIT_PROVIDER_OPTIONS = [
  { value: GitProvider.BITBUCKET_SERVER, label: 'Bitbucket Server' },
  { value: GitProvider.GITHUB_ENTERPRISE, label: 'GitHub Enterprise' },
] as const

/**
 * Get display label for a git provider
 */
export function getGitProviderLabel(provider: string): string {
  const option = GIT_PROVIDER_OPTIONS.find((o) => o.value === provider)
  return option?.label || provider
}

/**
 * Get Element Plus tag type for a git provider
 */
export function getGitProviderTagType(provider: string): '' | 'success' | 'warning' | 'info' | 'danger' {
  switch (provider) {
    case GitProvider.BITBUCKET_SERVER:
      return ''
    case GitProvider.GITHUB_ENTERPRISE:
      return 'success'
    default:
      return 'info'
  }
}
