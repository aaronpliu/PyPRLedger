"""Administration of explicit user-to-repository visibility grants."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.core.permissions import get_current_user_with_token
from src.models.auth_user import AuthUser
from src.schemas.repository_access import (
    RepositoryAccessReplaceRequest,
    RepositoryAccessResponse,
    RepositoryCatalogItem,
)
from src.services.rbac_service import RBACService
from src.services.repository_access_service import RepositoryAccessService


router = APIRouter(prefix="/repository-access", tags=["repository-access"])


def get_rbac_service(db: Annotated[AsyncSession, Depends(get_db_session)]) -> RBACService:
    return RBACService(db)


def get_access_service(
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> RepositoryAccessService:
    return RepositoryAccessService(db)


async def _require_admin(current_user: AuthUser, rbac_service: RBACService) -> None:
    await rbac_service.require_permission(current_user.id, "manage", "users")


@router.get("/catalog", response_model=list[RepositoryCatalogItem])
async def list_catalog(
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    rbac_service: Annotated[RBACService, Depends(get_rbac_service)],
    access_service: Annotated[RepositoryAccessService, Depends(get_access_service)],
) -> list[dict]:
    """Full repository catalogue, names only, for the assignment dialog."""
    await _require_admin(current_user, rbac_service)
    return await access_service.list_catalog()


@router.get("/{subject_type}/{subject_id}", response_model=RepositoryAccessResponse)
async def get_access(
    subject_type: str,
    subject_id: int,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    rbac_service: Annotated[RBACService, Depends(get_rbac_service)],
    access_service: Annotated[RepositoryAccessService, Depends(get_access_service)],
) -> RepositoryAccessResponse:
    await _require_admin(current_user, rbac_service)
    username = await access_service.resolve_subject(subject_type, subject_id)
    items = await access_service.list_access(subject_type, subject_id)
    return RepositoryAccessResponse(
        subject_type=subject_type,
        subject_id=subject_id,
        subject_username=username,
        items=items,
        total=len(items),
    )


@router.put("/{subject_type}/{subject_id}", response_model=RepositoryAccessResponse)
async def replace_access(
    subject_type: str,
    subject_id: int,
    payload: RepositoryAccessReplaceRequest,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    rbac_service: Annotated[RBACService, Depends(get_rbac_service)],
    access_service: Annotated[RepositoryAccessService, Depends(get_access_service)],
) -> RepositoryAccessResponse:
    """Replace the complete grant list of one subject."""
    await _require_admin(current_user, rbac_service)
    pairs = {(item.project_key, item.repository_slug) for item in payload.items}
    items = await access_service.replace_access(
        subject_type=subject_type,
        subject_id=subject_id,
        pairs=pairs,
        granted_by=current_user.id,
    )
    return RepositoryAccessResponse(
        subject_type=subject_type,
        subject_id=subject_id,
        subject_username=await access_service.resolve_subject(subject_type, subject_id),
        items=items,
        total=len(items),
    )
