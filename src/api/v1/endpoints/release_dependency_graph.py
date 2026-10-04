from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.core.permissions import get_current_user_with_token
from src.models.auth_user import AuthUser
from src.schemas.dependency_graph import DependencyGraphRequest, DependencyGraphResponse
from src.services.dependency_graph_service import DependencyGraphService
from src.services.project_registry_service import ProjectRegistryService
from src.utils.log import get_logger


logger = get_logger(__name__)

router = APIRouter(prefix="/release/dependency-graph")


def get_dependency_graph_service() -> DependencyGraphService:
    return DependencyGraphService()


def get_registry_service() -> ProjectRegistryService:
    return ProjectRegistryService()


@router.post(
    "/read",
    response_model=DependencyGraphResponse,
    summary="Read the dependency graph of one ref",
    description=(
        "Consolidate the dependency database into the graph of one repository ref. The "
        "repository is resolved to an application through the project registry - the "
        "database holds what an application shipped, and the application is what the "
        "registry maps a repository to."
    ),
)
async def read_dependency_graph(
    payload: DependencyGraphRequest,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[DependencyGraphService, Depends(get_dependency_graph_service)],
    registry: Annotated[ProjectRegistryService, Depends(get_registry_service)],
) -> DependencyGraphResponse:
    app_name = await registry.get_app_name(payload.project_key, payload.repository_slug, db)
    logger.info(
        "Reading dependency graph",
        extra={
            "project_key": payload.project_key,
            "repository_slug": payload.repository_slug,
            "ref": payload.ref,
            "app_name": app_name,
            "user_id": current_user.id,
        },
    )

    graph = await service.build(
        app_name=app_name,
        project_key=payload.project_key,
        repository_slug=payload.repository_slug,
        ref=payload.ref,
        git_provider=payload.git_provider,
    )
    return DependencyGraphResponse(**graph)
