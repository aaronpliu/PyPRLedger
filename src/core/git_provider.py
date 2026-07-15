from __future__ import annotations

from enum import StrEnum


class GitProvider(StrEnum):
    """Git provider enumeration following Open/Closed Principle.

    To add a new provider:
    1. Add a new enum member here
    2. Create provider implementation in src/services/git_providers/
    3. Register in get_git_provider() factory
    """

    BITBUCKET_SERVER = "bitbucket_server"
    BITBUCKET_CLOUD = "bitbucket_cloud"
    GITHUB_ENTERPRISE = "github_enterprise"

    @classmethod
    def default(cls) -> GitProvider:
        """Return the default git provider."""
        return cls.BITBUCKET_SERVER

    @classmethod
    def values(cls) -> set[str]:
        """Return all valid provider values."""
        return {member.value for member in cls}

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if a provider value is valid."""
        return value in cls.values()

    def __str__(self) -> str:
        return self.value
