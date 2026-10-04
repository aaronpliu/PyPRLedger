from __future__ import annotations

from typing import Any, cast

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.git_provider import GitProvider
from src.models.project import Project
from src.models.repository import Repository
from src.services.cloud_workspace_service import workspace_from_repository_url
from src.services.project_registry_service import ProjectRegistryService
from src.utils.log import get_logger


logger = get_logger(__name__)


async def registered_provider(
    project_key: str,
    repository_slug: str,
    db: AsyncSession,
    registry: ProjectRegistryService | None = None,
) -> str | None:
    """The provider a repository is registered under, when it is registered.

    A name the enumeration does not know is not worth propagating: it is logged
    and left for the caller to fall back from, rather than sent to the factory
    to raise on. A registry that cannot be read is the same kind of absence -
    the configured default stands, and the request is never failed over a lookup
    that only exists to improve on it.
    """
    service = registry or ProjectRegistryService()
    try:
        registered = await service.get_git_provider(project_key, repository_slug, db)
    except Exception as e:
        logger.warning(
            "Could not read the registered git provider, falling back to the default",
            extra={
                "project_key": project_key,
                "repository_slug": repository_slug,
                "error": str(e),
            },
        )
        return None

    if not registered:
        return None

    if not GitProvider.is_valid(registered):
        logger.warning(
            "Registry entry names an unknown git provider",
            extra={
                "project_key": project_key,
                "repository_slug": repository_slug,
                "git_provider": registered,
            },
        )
        return None
    return registered


async def registered_workspace_slug(
    project_key: str,
    repository_slug: str,
    db: AsyncSession,
) -> str | None:
    """The Bitbucket Cloud workspace a repository lives in, from its stored URL.

    The repository URL is the authoritative statement of the workspace because it
    carries the real ``bitbucket.org/<workspace>/<repo>`` path. A project key is
    not one: it may be an alias that names something else entirely (``AI`` for the
    workspace ``aaronpliu``), and asking Cloud for the wrong workspace finds
    nothing. A URL that is not a Cloud one yields nothing, so a Server or GitHub
    repository never invents a workspace.
    """
    try:
        url = (
            await db.execute(
                select(Repository.repository_url)
                .join(Project, Project.project_id == Repository.project_id)
                .where(
                    Project.project_key == project_key,
                    Repository.repository_slug == repository_slug,
                )
            )
        ).scalar_one_or_none()
    except Exception as e:
        logger.warning(
            "Could not read the repository URL, leaving the workspace unset",
            extra={
                "project_key": project_key,
                "repository_slug": repository_slug,
                "error": str(e),
            },
        )
        return None

    return workspace_from_repository_url(url)


async def with_repository_provider[PayloadT: BaseModel](
    payload: PayloadT,
    db: AsyncSession,
    registry: ProjectRegistryService | None = None,
) -> PayloadT:
    """The request with the coordinates of its repository filled in.

    A caller that names a provider is taken at its word; otherwise the registry
    answers, since a repository is registered under the provider it lives on and
    the browser has no business knowing. The provider comes first because it
    decides the shape of the rest: only a Cloud request carries a workspace, and
    it is filled from the repository's own URL - left to itself, the request
    would address Cloud with the project key as the workspace.
    """
    project_key = getattr(payload, "project_key", "")
    repository_slug = getattr(payload, "repository_slug", "")

    provider = getattr(payload, "git_provider", None)
    updates: dict[str, Any] = {}
    if not provider:
        provider = await registered_provider(project_key, repository_slug, db, registry)
        if provider:
            updates["git_provider"] = provider

    workspace = getattr(payload, "workspace_slug", None)
    if not workspace and provider == GitProvider.BITBUCKET_CLOUD.value:
        resolved = await registered_workspace_slug(project_key, repository_slug, db)
        if resolved:
            updates["workspace_slug"] = resolved

    if not updates:
        return payload
    return cast(PayloadT, payload.model_copy(update=updates))
