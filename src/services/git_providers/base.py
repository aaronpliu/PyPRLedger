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
        """Provider identifier (e.g., 'bitbucket_server', 'github_enterprise')."""

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
