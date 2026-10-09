from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.core.permissions import get_current_user_with_token
from src.models.auth_user import AuthUser
from src.schemas.app_version_diff import AppVersionDiffRequest, AppVersionDiffResponse
from src.services.app_version_diff_service import AppVersionDiffService
from src.services.git_provider_resolver import with_repository_provider
from src.services.project_registry_service import ProjectRegistryService
from src.utils.log import get_logger


logger = get_logger(__name__)

router = APIRouter(prefix="/release/apps")


def get_app_version_diff_service() -> AppVersionDiffService:
    return AppVersionDiffService()


def get_registry_service() -> ProjectRegistryService:
    return ProjectRegistryService()


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
        "comparisons that touch it incomplete - never 'no changes'."
    ),
)
async def compare_app_releases(
    payload: AppVersionDiffRequest,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[AppVersionDiffService, Depends(get_app_version_diff_service)],
    registry: Annotated[ProjectRegistryService, Depends(get_registry_service)],
) -> AppVersionDiffResponse:
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

    return await service.compare(payload, app_name=app_name)
