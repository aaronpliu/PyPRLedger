"""API endpoints for Personal Access Token management"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.core.permissions import get_current_user_with_token
from src.models.auth_user import AuthUser
from src.models.personal_access_token import PersonalAccessToken
from src.schemas.personal_access_token import (
    PATCreateRequest,
    PATCreationResponse,
    PATListResponse,
    PATResponse,
)
from src.services.pat_service import PATService


router = APIRouter(prefix="/personal-access-tokens")


def get_pat_service(db: Annotated[AsyncSession, Depends(get_db_session)]) -> PATService:
    """Dependency to get PAT service"""
    return PATService(db)


@router.get(
    "/",
    response_model=PATListResponse,
    summary="List personal access tokens",
    description="List all personal access tokens for the current user",
)
async def list_tokens(
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    pat_service: Annotated[PATService, Depends(get_pat_service)],
    include_expired: bool = False,
) -> PATListResponse:
    """List all personal access tokens for current user"""
    tokens = await pat_service.list_tokens(
        auth_user_id=current_user.id,
        include_expired=include_expired,
    )

    return PATListResponse(
        total=len(tokens),
        items=[PATResponse.model_validate(t) for t in tokens],
    )


@router.post(
    "/",
    response_model=PATCreationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create personal access token",
    description="Generate a new personal access token (token shown only once)",
)
async def create_token(
    request_data: PATCreateRequest,
    request: Request,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    pat_service: Annotated[PATService, Depends(get_pat_service)],
) -> PATCreationResponse:
    """Generate a new personal access token"""
    # Get request context
    forwarded_for = request.headers.get("X-Forwarded-For")
    ip_address = forwarded_for.split(",")[0].strip() if forwarded_for else None
    if not ip_address and request.client:
        ip_address = request.client.host
    user_agent = request.headers.get("User-Agent")

    # Create token
    full_token, token_record = await pat_service.create_token(
        auth_user_id=current_user.id,
        name=request_data.name,
        expires_in_days=request_data.expires_in_days,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return PATCreationResponse(
        id=token_record.id,
        name=token_record.name,
        prefix=token_record.prefix,
        created_at=token_record.created_at,
        expires_at=token_record.expires_at,
        last_used_at=token_record.last_used_at,
        is_active=token_record.is_active,
        token=full_token,
    )


@router.get(
    "/{token_id}",
    response_model=PATResponse,
    summary="Get token details",
    description="Get details of a specific personal access token",
)
async def get_token(
    token_id: int,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> PATResponse:
    """Get details of a specific token"""
    result = await db.execute(
        select(PersonalAccessToken)
        .where(PersonalAccessToken.id == token_id)
        .where(PersonalAccessToken.auth_user_id == current_user.id)
    )
    token_record = result.scalar_one_or_none()

    if not token_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Token not found",
        )

    return PATResponse.model_validate(token_record)


@router.delete(
    "/{token_id}",
    summary="Revoke personal access token",
    description="Revoke a personal access token immediately",
)
async def revoke_token(
    token_id: int,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    pat_service: Annotated[PATService, Depends(get_pat_service)],
) -> dict[str, str]:
    """Revoke a personal access token"""
    success = await pat_service.revoke_token(
        auth_user_id=current_user.id,
        token_id=token_id,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Token not found or already revoked",
        )

    return {"message": "Token revoked successfully"}
