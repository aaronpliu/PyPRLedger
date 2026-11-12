from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.core.permissions import CurrentRepositoryAccess, get_current_user_with_token
from src.core.repository_access import ensure_pair_granted
from src.models.auth_user import AuthUser
from src.schemas.app_version_diff import (
    AppVersionDiffCoordinates,
    AppVersionDiffPackagesRequest,
    AppVersionDiffPackagesResponse,
    AppVersionDiffRequest,
    AppVersionDiffResponse,
)
from src.services.app_diff_report import render_app_diff_report
from src.services.app_version_diff_service import (
    AppVersionDiffService,
    DependencyRepository,
    DependencyRepositoryResolver,
)
from src.services.git_provider_resolver import with_repository_provider
from src.services.project_registry_service import ProjectRegistryService
from src.utils.log import get_logger


logger = get_logger(__name__)

router = APIRouter(prefix="/release/apps")


def get_app_version_diff_service() -> AppVersionDiffService:
    return AppVersionDiffService()


def get_registry_service() -> ProjectRegistryService:
    return ProjectRegistryService()


def _dependency_repository_resolver(
    registry: ProjectRegistryService,
    request: AppVersionDiffCoordinates,
    db: AsyncSession,
) -> DependencyRepositoryResolver:
    """Where a package a release moved lives, read out of the project registry.

    A dependency record names its packages and their versions, never their
    repositories. The name it uses is the one the database knows an application
    by - the same name this side sends the other way - so the registry is asked
    for it from this side, and the answer carries both the repository and the
    provider it lives on.

    Both the first comparison and the batches that continue it resolve through
    here, so a package's repository is read the same way whichever asked.
    """

    async def resolve(name: str) -> DependencyRepository:
        entry, reason = await registry.find_dependency_repository(name, request.project_key, db)
        if entry is None:
            return DependencyRepository(reason=reason)
        return DependencyRepository(
            project_key=entry.project_key,
            repository_slug=entry.repository_slug,
            git_provider=entry.git_provider,
        )

    return resolve


@router.post(
    "/diff",
    response_model=AppVersionDiffResponse,
    summary="Compare two or more application releases",
    description=(
        "Compare two or more releases of one application at direct-dependency level. The "
        "repository is resolved to an application through the project registry, each release "
        "is read from the dependency source, and the releases are placed in the order their "
        "datetimes put them. Every adjacent pair is then compared package by package. A "
        "release the source holds no record for is reported as such and makes the "
        "comparisons that touch it incomplete - never 'no changes'. A pair that moved more "
        "packages than one response reads reports the rest as deferred, each with the "
        "repository it lives in, so they can be asked for in batches."
    ),
)
async def compare_app_releases(
    payload: AppVersionDiffRequest,
    access: CurrentRepositoryAccess,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[AppVersionDiffService, Depends(get_app_version_diff_service)],
    registry: Annotated[ProjectRegistryService, Depends(get_registry_service)],
) -> AppVersionDiffResponse:
    return await _run_compare(payload, access, current_user, db, service, registry)


async def _run_compare(
    payload: AppVersionDiffRequest,
    access: CurrentRepositoryAccess,
    current_user: AuthUser,
    db: AsyncSession,
    service: AppVersionDiffService,
    registry: ProjectRegistryService,
) -> AppVersionDiffResponse:
    """The comparison both the page and the report endpoint read through."""
    ensure_pair_granted(access, payload.project_key, payload.repository_slug)
    # The provider decides the shape of the rest of the read (only a Cloud request
    # carries a workspace), so it is filled in before the application is resolved.
    payload = await with_repository_provider(payload, db)
    # the dependency database is asked for the repository's alias when it has one
    app_name = await registry.get_dependency_app_name(
        payload.project_key, payload.repository_slug, db
    )
    logger.info(
        "Comparing application releases",
        extra={
            "project_key": payload.project_key,
            "repository_slug": payload.repository_slug,
            "app_name": app_name,
            "releases": payload.refs,
            "refresh": payload.refresh,
            "user_id": current_user.id,
        },
    )

    return await service.compare(
        payload,
        app_name=app_name,
        resolve_dependency_repository=_dependency_repository_resolver(registry, payload, db),
    )


@router.post(
    "/diff/packages",
    response_model=AppVersionDiffPackagesResponse,
    summary="Compare the packages a release pair moved, a batch at a time",
    description=(
        "Compare named packages of one release pair. The comparison endpoint reports the "
        "packages past the pair's first-read ceiling as deferred, and this is how they are "
        "read: a release that moved thirty packages is drawn from the first few and filled "
        "in as the rest are read, instead of holding the page back. Each package is read the "
        "way the first response read the others, in the repository the registry resolves it "
        "to, and the comparison underneath is cached - so a batch asked for twice is cheap."
    ),
)
async def compare_app_release_packages(
    payload: AppVersionDiffPackagesRequest,
    access: CurrentRepositoryAccess,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[AppVersionDiffService, Depends(get_app_version_diff_service)],
    registry: Annotated[ProjectRegistryService, Depends(get_registry_service)],
) -> AppVersionDiffPackagesResponse:
    ensure_pair_granted(access, payload.project_key, payload.repository_slug)
    payload = await with_repository_provider(payload, db)
    logger.info(
        "Comparing the deferred packages of an application release pair",
        extra={
            "project_key": payload.project_key,
            "repository_slug": payload.repository_slug,
            "source_ref": payload.source_ref,
            "target_ref": payload.target_ref,
            "packages": [entry.name for entry in payload.packages],
            "user_id": current_user.id,
        },
    )

    return await service.compare_packages(
        payload,
        resolve_dependency_repository=_dependency_repository_resolver(registry, payload, db),
    )


@router.post(
    "/diff/report",
    summary="Render the comparison as a standalone HTML report (for CI pipelines)",
    response_class=Response,
    responses={200: {"content": {"text/html": {}, "application/json": {}}}},
)
async def compare_app_releases_report(
    payload: AppVersionDiffRequest,
    access: CurrentRepositoryAccess,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[AppVersionDiffService, Depends(get_app_version_diff_service)],
    registry: Annotated[ProjectRegistryService, Depends(get_registry_service)],
    format: Literal["html", "json"] = Query(default="html"),
    download: bool = Query(default=False),
) -> Response:
    """Run the comparison and return it as a self-contained HTML report.

    Same request body and authorization as ``POST /release/apps/diff``; the
    answer is the rendered document instead of the raw JSON. Built for CI: a
    pipeline authenticates with a Personal Access Token (``Authorization:
    Bearer pat_...``) whose user is granted the repository, runs the call after
    a build, and keeps the file as an artifact or mails it on.

    Query parameters:

    - ``format``: ``html`` (default) for the rendered report, ``json`` for the
      same structure ``/diff`` returns - useful when the pipeline wants to
      post-process the data itself.
    - ``download``: adds a ``Content-Disposition: attachment`` header with a
      timestamped filename, so a browser saves instead of displays.

    Example::

        curl -X POST "$PRL_URL/api/v1/release/apps/diff/report" \\
          -H "Authorization: Bearer $PRL_TOKEN" \\
          -H "Content-Type: application/json" \\
          -d '{"project_key":"CORE","repository_slug":"app","refs":["v1.0.0","v1.1.0"]}' \\
          -o app-diff.html
    """
    result = await _run_compare(payload, access, current_user, db, service, registry)

    if format == "json":
        return JSONResponse(content=result.model_dump(mode="json"))

    html = render_app_diff_report(result)
    headers = {}
    if download:
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        scope = re.sub(
            r"[^A-Za-z0-9._-]+", "_", f"{result.project_key}-{result.repository_slug}"
        )
        headers["Content-Disposition"] = f'attachment; filename="app-diff-{scope}-{stamp}.html"'
    return Response(content=html, media_type="text/html", headers=headers)
