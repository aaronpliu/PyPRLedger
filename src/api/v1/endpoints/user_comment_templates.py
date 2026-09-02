"""API endpoints for managing personalized user comment templates"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.core.permissions import get_current_user_with_token
from src.models.auth_user import AuthUser
from src.schemas.user_comment_template import (
    UserCommentTemplateCreateRequest,
    UserCommentTemplateListResponse,
    UserCommentTemplateResponse,
    UserCommentTemplateUpdateRequest,
)
from src.services.user_comment_template_service import UserCommentTemplateService


router = APIRouter(prefix="/user-comment-templates")


def get_user_comment_template_service(
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserCommentTemplateService:
    """Dependency to get user comment template service"""
    return UserCommentTemplateService(db)


@router.get(
    "/",
    response_model=UserCommentTemplateListResponse,
    summary="List personal comment templates",
    description="List all comment templates saved by the current user (most recently updated first)",
)
async def list_templates(
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[UserCommentTemplateService, Depends(get_user_comment_template_service)],
) -> UserCommentTemplateListResponse:
    """List all comment templates for current user"""
    templates = await service.list_templates(auth_user_id=current_user.id)

    return UserCommentTemplateListResponse(
        total=len(templates),
        items=[UserCommentTemplateResponse.model_validate(t) for t in templates],
    )


@router.post(
    "/",
    response_model=UserCommentTemplateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a personal comment template",
    description="Save a new comment template for the current user",
)
async def create_template(
    request_data: UserCommentTemplateCreateRequest,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[UserCommentTemplateService, Depends(get_user_comment_template_service)],
) -> UserCommentTemplateResponse:
    """Save a new comment template for current user"""
    template_record = await service.create_template(
        auth_user_id=current_user.id,
        name=request_data.name,
        content=request_data.content,
    )

    return UserCommentTemplateResponse.model_validate(template_record)


@router.put(
    "/{template_id}",
    response_model=UserCommentTemplateResponse,
    summary="Update a personal comment template",
    description="Update the name/content of one of the current user's comment templates",
)
async def update_template(
    template_id: int,
    request_data: UserCommentTemplateUpdateRequest,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[UserCommentTemplateService, Depends(get_user_comment_template_service)],
) -> UserCommentTemplateResponse:
    """Update one of the current user's comment templates"""
    template_record = await service.update_template(
        auth_user_id=current_user.id,
        template_id=template_id,
        name=request_data.name,
        content=request_data.content,
    )

    if not template_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment template not found",
        )

    return UserCommentTemplateResponse.model_validate(template_record)


@router.delete(
    "/{template_id}",
    summary="Delete a personal comment template",
    description="Delete one of the current user's comment templates",
)
async def delete_template(
    template_id: int,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[UserCommentTemplateService, Depends(get_user_comment_template_service)],
) -> dict[str, str]:
    """Delete one of the current user's comment templates"""
    success = await service.delete_template(
        auth_user_id=current_user.id,
        template_id=template_id,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment template not found",
        )

    return {"message": "Comment template deleted successfully"}
