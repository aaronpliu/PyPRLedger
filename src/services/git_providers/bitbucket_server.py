from __future__ import annotations

import logging
from typing import Any

from src.core.git_provider import GitProvider
from src.services.bitbucket_service import BitbucketService
from src.services.git_providers.base import BaseGitProvider


logger = logging.getLogger(__name__)


class BitbucketServerProvider(BaseGitProvider):
    """Adapter that wraps the existing BitbucketService to conform to BaseGitProvider."""

    def __init__(self) -> None:
        self._service = BitbucketService()

    @property
    def name(self) -> str:
        return GitProvider.BITBUCKET_SERVER.value

    async def get_project_info(self, project_key: str) -> dict[str, Any] | None:
        return await self._service.get_project_info(project_key)

    async def get_repository_info(self, workspace: str, repo_slug: str) -> dict[str, Any] | None:
        return await self._service.get_repository_info(workspace, repo_slug)

    async def get_user_info(self, username: str) -> dict[str, Any] | None:
        return await self._service.get_user_info(username)
