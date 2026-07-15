from __future__ import annotations

import logging

from src.core.git_provider import GitProvider
from src.services.git_providers.base import BaseGitProvider


logger = logging.getLogger(__name__)

_provider_cache: dict[str, BaseGitProvider] = {}


def get_git_provider(provider_name: str | GitProvider) -> BaseGitProvider:
    """Factory to get the appropriate git provider instance.

    Args:
        provider_name: GitProvider enum or string value

    Returns:
        BaseGitProvider instance (cached singleton per provider name)

    Raises:
        ValueError: If provider_name is not a recognized GitProvider value
    """
    provider_str = provider_name.value if isinstance(provider_name, GitProvider) else provider_name

    if provider_str in _provider_cache:
        return _provider_cache[provider_str]

    if provider_str in (GitProvider.BITBUCKET_SERVER, GitProvider.BITBUCKET_CLOUD):
        from src.services.git_providers.bitbucket_server import BitbucketServerProvider

        provider = BitbucketServerProvider()
    elif provider_str == GitProvider.GITHUB_ENTERPRISE:
        from src.services.git_providers.github_enterprise import GitHubEnterpriseProvider

        provider = GitHubEnterpriseProvider()
    else:
        raise ValueError(
            f"Unknown git provider '{provider_str}'. "
            f"Valid providers: {', '.join(sorted(GitProvider.values()))}"
        )

    _provider_cache[provider_str] = provider
    return provider


__all__ = ["BaseGitProvider", "get_git_provider", "GitProvider"]
