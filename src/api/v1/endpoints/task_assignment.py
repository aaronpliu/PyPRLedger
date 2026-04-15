"""API endpoints for task assignment management (review_admin only)"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.core.permissions import get_current_user_with_token
from src.models.auth_user import AuthUser
from src.models.user import User
from src.schemas.review import (
    AssignReviewerRequest,
    ReviewListResponse,
    ReviewWithAssignmentsResponse,
    UpdateAssignmentStatusRequest,
)
from src.services.multi_reviewer_service import MultiReviewerService


router = APIRouter(prefix="/task-assignment", tags=["task-assignment"])


def get_multi_reviewer_service() -> MultiReviewerService:
    """Dependency to get multi-reviewer service instance"""
    return MultiReviewerService()


@router.get("/", response_model=ReviewListResponse)
async def list_reviews(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[MultiReviewerService, Depends(get_multi_reviewer_service)],
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    project_key: str | None = Query(None, description="Filter by project key"),
    reviewer: str | None = Query(None, description="Filter by reviewer"),
    status: str | None = Query(None, description="Filter by PR status"),
) -> ReviewListResponse:
    """
    Get list of reviews with their assignments (requires review_admin role)

    This endpoint is for review admins to manage and assign review tasks.
    """
    # TODO: Add permission check - must be review_admin or system_admin

    try:
        reviews, total = await service.get_reviews(
            db=db,
            page=page,
            page_size=page_size,
            project_key=project_key,
            reviewer=reviewer,
            status=status,
        )

        return ReviewListResponse(
            items=reviews,
            total=total,
            page=page,
            page_size=page_size,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": str(e)},
        )


@router.get("/{review_id}", response_model=ReviewWithAssignmentsResponse)
async def get_review(
    review_id: int,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[MultiReviewerService, Depends(get_multi_reviewer_service)],
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
) -> ReviewWithAssignmentsResponse:
    """Get a single review with all assignments (requires review_admin role)"""
    # TODO: Add permission check

    try:
        return await service.get_review_by_id(db=db, review_id=review_id)
    except Exception as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "NOT_FOUND", "message": str(e)},
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": str(e)},
        )


@router.post("/{review_id}/assign")
async def assign_reviewer(
    review_id: int,
    request: AssignReviewerRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[MultiReviewerService, Depends(get_multi_reviewer_service)],
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
) -> dict:
    """Assign a reviewer to a review (requires review_admin or system_admin role)"""
    # TODO: Add permission check

    try:
        result = await service.assign_reviewer(
            db=db,
            review_base_id=review_id,
            assignment_data=request,
            assigned_by=current_user.username,
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": str(e)},
        )


@router.delete("/{review_id}/assign/{reviewer}")
async def remove_reviewer(
    review_id: int,
    reviewer: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[MultiReviewerService, Depends(get_multi_reviewer_service)],
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
) -> dict:
    """Remove a reviewer assignment (requires review_admin or system_admin role)"""
    # TODO: Add permission check

    try:
        success = await service.remove_reviewer(
            db=db,
            review_base_id=review_id,
            reviewer=reviewer,
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "NOT_FOUND", "message": "Assignment not found"},
            )

        return {"message": "Reviewer removed successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": str(e)},
        )


@router.patch("/assignments/{assignment_id}/status")
async def update_assignment_status(
    assignment_id: int,
    request: UpdateAssignmentStatusRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[MultiReviewerService, Depends(get_multi_reviewer_service)],
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
) -> dict:
    """Update assignment status (reviewer can update their own status, admin can update any)"""
    # TODO: Add permission check

    try:
        result = await service.update_assignment_status(
            db=db,
            assignment_id=assignment_id,
            status=request.assignment_status,
            comments=request.reviewer_comments,
        )
        return result
    except Exception as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "NOT_FOUND", "message": str(e)},
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": str(e)},
        )


@router.delete("/{review_id}")
async def delete_review(
    review_id: int,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[MultiReviewerService, Depends(get_multi_reviewer_service)],
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
) -> dict:
    """Delete a review and all assignments (requires review_admin or system_admin)"""
    # TODO: Add permission check

    try:
        success = await service.delete_review(db=db, review_base_id=review_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "NOT_FOUND", "message": "Review not found"},
            )

        return {"message": "Review deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": str(e)},
        )


@router.get("/my-tasks", response_model=ReviewListResponse)
async def get_my_tasks(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[MultiReviewerService, Depends(get_multi_reviewer_service)],
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ReviewListResponse:
    """Get reviews assigned to current user"""
    try:
        bitbucket_username = await _get_bitbucket_username(current_user.id, db)
        if not bitbucket_username:
            return ReviewListResponse(items=[], total=0, page=page, page_size=page_size)

        reviews, total = await service.get_reviews(
            db=db,
            page=page,
            page_size=page_size,
            visible_to_username=bitbucket_username,
        )

        return ReviewListResponse(
            items=reviews,
            total=total,
            page=page,
            page_size=page_size,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": str(e)},
        )


async def _get_bitbucket_username(auth_user_id: int, db: AsyncSession) -> str | None:
    stmt = select(AuthUser).where(AuthUser.id == auth_user_id)
    result = await db.execute(stmt)
    auth_user = result.scalar_one_or_none()

    if not auth_user or not auth_user.user_id:
        return None

    stmt = select(User).where(User.id == auth_user.user_id)
    result = await db.execute(stmt)
    bitbucket_user = result.scalar_one_or_none()
    return bitbucket_user.username if bitbucket_user else None
