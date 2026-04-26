"""API endpoints for task assignment management (review_admin only)"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.core.permissions import get_current_user_with_token
from src.models.auth_user import AuthUser
from src.models.pull_request import PullRequestReviewAssignment
from src.models.user import User
from src.schemas.review import (
    AssignReviewerRequest,
    ReviewListResponse,
    ReviewWithAssignmentsResponse,
    UpdateAssignmentStatusRequest,
)
from src.services.multi_reviewer_service import MultiReviewerService
from src.services.rbac_service import RBACService


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
    app_names: str | None = Query(
        None,
        description="Filter by application names (comma-separated for multiple apps, e.g., 'member,tv,football')",
    ),
    pull_request_user: str | None = Query(
        None, min_length=1, max_length=64, description="Filter by pull request user username"
    ),
) -> ReviewListResponse:
    """
    Get list of reviews with their assignments (requires review_admin role)

    This endpoint is for review admins to manage and assign review tasks.

    Supports filtering by:
    - project_key: Filter by Bitbucket project key
    - reviewer: Filter by assigned reviewer username
    - status: Filter by PR status (open, merged, closed, draft)
    - app_names: Filter by registered app names (comma-separated)
    - pull_request_user: Filter by PR author username
    """
    # TODO: Add permission check - must be review_admin or system_admin

    try:
        # Parse app_names from comma-separated string
        app_names_list = None
        if app_names:
            app_names_list = [name.strip() for name in app_names.split(",") if name.strip()]

        reviews, total = await service.get_reviews(
            db=db,
            page=page,
            page_size=page_size,
            project_key=project_key,
            reviewer=reviewer,
            status=status,
            app_names=app_names_list,
            pull_request_user=pull_request_user,
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
    """Assign a reviewer to a review (requires review_admin or system_admin role)

    Note: All users (including system admins) must have an associated Git account
    to assign review tasks. This ensures proper audit trail and data integrity.
    """
    # TODO: Add permission check

    try:
        # Get the Git username from the associated User record
        git_username = await _get_git_username(current_user.id, db)

        if not git_username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "BAD_REQUEST",
                    "message": f"User '{current_user.username}' does not have an associated Git account. "
                    f"All users (including system admins) must have a Git account to assign review tasks. "
                    f"Please contact your administrator to create a Git user account linked to this system account.",
                    "hint": "To fix this, create a User record in the 'user' table with a username, "
                    f"then link it to AuthUser (id={current_user.id}) by setting auth_user.user_id",
                },
            )

        result = await service.assign_reviewer(
            db=db,
            review_base_id=review_id,
            assignment_data=request,
            assigned_by=git_username,
        )
        return result
    except HTTPException:
        raise
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
    try:
        stmt = select(PullRequestReviewAssignment).where(
            PullRequestReviewAssignment.id == assignment_id
        )
        result = await db.execute(stmt)
        assignment = result.scalar_one_or_none()

        if not assignment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "NOT_FOUND", "message": "Assignment not found"},
            )

        rbac_service = RBACService(db)
        is_review_admin = await rbac_service.check_permission(
            auth_user_id=current_user.id,
            action="assign",
            resource_type="reviews",
        )
        git_username = await _get_git_username(current_user.id, db)

        if not is_review_admin:
            if not git_username or assignment.reviewer != git_username:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "error": "FORBIDDEN",
                        "message": "You can only update assignment status for tasks assigned to you.",
                    },
                )

            if request.assignment_status != "in_progress":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "error": "FORBIDDEN",
                        "message": "Assigned reviewers can only mark their own tasks as in_progress.",
                    },
                )

            if assignment.assignment_status == "completed":
                return {"message": "Status unchanged", "assignment": assignment.to_dict()}

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
        git_username = await _get_git_username(current_user.id, db)
        if not git_username:
            return ReviewListResponse(items=[], total=0, page=page, page_size=page_size)

        reviews, total = await service.get_reviews(
            db=db,
            page=page,
            page_size=page_size,
            visible_to_username=git_username,
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


async def _get_git_username(auth_user_id: int, db: AsyncSession) -> str | None:
    stmt = select(AuthUser).where(AuthUser.id == auth_user_id)
    result = await db.execute(stmt)
    auth_user = result.scalar_one_or_none()

    if not auth_user or not auth_user.user_id:
        return None

    stmt = select(User).where(User.id == auth_user.user_id)
    result = await db.execute(stmt)
    git_user = result.scalar_one_or_none()
    return git_user.username if git_user else None
