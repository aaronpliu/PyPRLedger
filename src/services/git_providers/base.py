from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any


logger = logging.getLogger(__name__)


class BaseGitProvider(ABC):
    """Abstract base class for Git provider integrations.

    Each provider implements methods to fetch project, repository, and user
    metadata from the respective Git platform's REST API.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier (see GitProvider enum)."""

    @abstractmethod
    async def get_project_info(self, project_key: str) -> dict[str, Any] | None:
        """Fetch project/organization information.

        Args:
            project_key: Project key (Bitbucket) or org name (GitHub)

        Returns:
            Dict with keys: project_id, project_name, project_key, project_url
            None if not found.
        """

    @abstractmethod
    async def get_repository_info(self, workspace: str, repo_slug: str) -> dict[str, Any] | None:
        """Fetch repository information.

        Args:
            workspace: Project key (Bitbucket) or org/owner (GitHub)
            repo_slug: Repository slug/name

        Returns:
            Dict with keys: repository_id, repository_name, repository_slug,
            repository_url, project_id
            None if not found.
        """

    @abstractmethod
    async def get_user_info(self, username: str) -> dict[str, Any] | None:
        """Fetch user information.

        Args:
            username: User login/username

        Returns:
            Dict with keys: user_id, username, display_name, email_address
            None if not found.
        """

    async def compare_commits(
        self,
        project_key: str,
        repository_slug: str,
        from_ref: str,
        to_ref: str,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Return raw commits reachable from ``to_ref`` but not from ``from_ref``.

        Args:
            project_key: Project key (Bitbucket) or org/owner (GitHub)
            repository_slug: Repository slug/name
            from_ref: Base ref (exclusive)
            to_ref: Target ref (inclusive)
            limit: Maximum number of commits to return

        Returns:
            List of provider-specific raw commit dicts.

        Raises:
            NotImplementedError: When the provider does not expose a compare API.
        """
        raise NotImplementedError(f"Provider '{self.name}' does not implement compare_commits()")

    async def list_commits_until(
        self,
        project_key: str,
        repository_slug: str,
        until_ref: str,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Return raw commits reachable from ``until_ref`` (newest first).

        Args:
            project_key: Project key (Bitbucket) or org/owner (GitHub)
            repository_slug: Repository slug/name
            until_ref: Ref to walk from (inclusive)
            limit: Maximum number of commits to return

        Returns:
            List of provider-specific raw commit dicts.

        Raises:
            NotImplementedError: When the provider does not expose a commit listing API.
        """
        raise NotImplementedError(f"Provider '{self.name}' does not implement list_commits_until()")

    async def list_refs(
        self,
        project_key: str,
        repository_slug: str,
        limit: int = 100,
    ) -> dict[str, list[str]]:
        """Return the tags and branches of a repository.

        Args:
            project_key: Project key (Bitbucket) or org/owner (GitHub)
            repository_slug: Repository slug/name
            limit: Maximum number of names returned per ref type

        Returns:
            Dict with ``tags`` and ``branches`` keys, each holding ref names.

        Raises:
            NotImplementedError: When the provider does not expose ref listing.
        """
        raise NotImplementedError(f"Provider '{self.name}' does not implement list_refs()")
