"""Bitbucket Cloud workspace suggestions.

Bitbucket Cloud addresses repositories by workspace, so the UI offers workspace
slugs next to the project key. Suggestions are merged from three sources:

1. ``BITBUCKET_CLOUD_WORKSPACES`` - explicit operator configuration
2. the provider API - works with app passwords / OAuth tokens, not with
   Atlassian API tokens (account level endpoints answer 404 there)
3. the local database - project keys and repository URLs already synced

Arbitrary workspace slugs can still be typed manually in the UI, the list is
only a suggestion.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.git_provider import GitProvider
from src.models.project import Project
from src.models.repository import Repository
from src.schemas.cloud_workspace import CloudWorkspaceOption
from src.services.git_providers import BaseGitProvider, get_git_provider


logger = logging.getLogger(__name__)

SOURCE_CONFIG = "config"
SOURCE_API = "api"
SOURCE_DATABASE = "database"

BITBUCKET_CLOUD_HOST = "bitbucket.org"


def workspace_from_repository_url(url: str | None) -> str | None:
    """Extract the workspace slug from a Bitbucket Cloud repository URL.

    ``https://bitbucket.org/aaronpliu/pylang.git`` -> ``aaronpliu``
    """
    if not url:
        return None
    parsed = urlsplit(url.strip())
    if (parsed.hostname or "").lower() != BITBUCKET_CLOUD_HOST:
        return None
    segments = [segment for segment in parsed.path.split("/") if segment]
    if len(segments) < 2:
        return None
    return segments[0]


class CloudWorkspaceService:
    """Collects the Bitbucket Cloud workspaces that can be offered to the UI."""

    def __init__(
        self,
        provider_factory: Callable[[str], BaseGitProvider] = get_git_provider,
        configured_workspaces: str | None = None,
    ) -> None:
        self._provider_factory = provider_factory
        self._configured_workspaces = (
            settings.BITBUCKET_CLOUD_WORKSPACES
            if configured_workspaces is None
            else configured_workspaces
        )

    async def list_workspaces(self, db: AsyncSession | None = None) -> list[CloudWorkspaceOption]:
        """Return the merged workspace suggestions (duplicates removed, order kept)."""
        options: list[CloudWorkspaceOption] = []
        seen: set[str] = set()

        def add(slug: str | None, name: str | None, source: str) -> None:
            if not slug:
                return
            key = slug.strip().lower()
            if not key or key in seen:
                return
            seen.add(key)
            options.append(
                CloudWorkspaceOption(
                    slug=slug.strip(),
                    name=(name or slug).strip() or slug.strip(),
                    source=source,
                )
            )

        for slug in self._configured_slugs():
            add(slug, slug, SOURCE_CONFIG)

        for workspace in await self._discover_from_api():
            add(workspace.get("slug"), workspace.get("name"), SOURCE_API)

        if db is not None:
            for slug in await self._discover_from_database(db):
                add(slug, slug, SOURCE_DATABASE)

        return options

    def _configured_slugs(self) -> list[str]:
        raw = self._configured_workspaces or ""
        return [part.strip() for part in raw.split(",") if part.strip()]

    async def _discover_from_api(self) -> list[dict[str, Any]]:
        """Ask the configured Cloud credentials for their workspaces (best effort)."""
        try:
            provider = self._provider_factory(GitProvider.BITBUCKET_CLOUD.value)
        except ValueError:
            logger.warning("Bitbucket Cloud provider is not available for workspace discovery")
            return []

        try:
            return await provider.list_workspaces()
        except Exception as e:  # noqa: BLE001 - suggestions must never break the endpoint
            logger.warning(f"Bitbucket Cloud workspace discovery failed: {e}")
            return []

    async def _discover_from_database(self, db: AsyncSession) -> list[str]:
        """Derive workspaces from Cloud projects and repositories already stored.

        The repository URL is authoritative because it carries the real
        ``bitbucket.org/<workspace>/<repo>`` path. A project without any Cloud
        repository only contributes its key, which equals the workspace whenever
        no explicit ``workspace_slug`` alias is in use.
        """
        cloud_projects = await db.execute(
            select(Project.project_id, Project.project_key).where(
                Project.git_provider == GitProvider.BITBUCKET_CLOUD.value
            )
        )
        projects = {row[0]: row[1] for row in cloud_projects.all()}

        cloud_repositories = await db.execute(
            select(Repository.project_id, Repository.repository_url)
            .join(Project, Project.project_id == Repository.project_id)
            .where(Project.git_provider == GitProvider.BITBUCKET_CLOUD.value)
        )

        slugs: list[str] = []
        projects_with_url: set[int] = set()
        for project_id, url in cloud_repositories.all():
            workspace = workspace_from_repository_url(url)
            if workspace:
                slugs.append(workspace)
                projects_with_url.add(project_id)

        for project_id, project_key in projects.items():
            if project_key and project_id not in projects_with_url:
                slugs.append(project_key)

        return slugs
