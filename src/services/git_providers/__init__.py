from __future__ import annotations

import logging

from src.services.git_providers.base import BaseGitProvider


logger = logging.getLogger(__name__)

_provider_cache: dict[str, BaseGitProvider] = {}


def get_git_provider(provider_name: str) -> BaseGitProvider:
    """Factory to get the appropriate git provider instance.

    Args:
        provider_name: One of 'bitbucket_server', 'bitbucket_cloud', 'github_enterprise'

    Returns:
        BaseGitProvider instance (cached singleton per provider name)
    """
    if provider_name in _provider_cache:
        return _provider_cache[provider_name]

    if provider_name in ("bitbucket_server", "bitbucket_cloud"):
        from src.services.git_providers.bitbucket_server import BitbucketServerProvider

        provider = BitbucketServerProvider()
    elif provider_name == "github_enterprise":
        from src.services.git_providers.github_enterprise import GitHubEnterpriseProvider

        provider = GitHubEnterpriseProvider()
    else:
        logger.warning(f"Unknown git provider '{provider_name}', falling back to bitbucket_server")
        from src.services.git_providers.bitbucket_server import BitbucketServerProvider

        provider = BitbucketServerProvider()

    _provider_cache[provider_name] = provider
    return provider


__all__ = ["BaseGitProvider", "get_git_provider"]
