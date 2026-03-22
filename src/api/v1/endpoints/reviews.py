from datetime import datetime
from typing import Annotated, Optional
import logging
from fastapi import APIRouter, Depends, Query, status, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.schemas.pull_request import (
    ReviewCreate,
    ReviewResponse,
    ReviewUpdate,
    ReviewListResponse,
    ReviewFilter,
    ReviewStats,
)
from src.services.review_service import ReviewService
from src.core.exceptions import (
    ProjectNotFoundException,
    ReviewNotFoundException,
    ReviewStatusException,
    UserNotFoundException,
)
from src.utils.metrics import OperationTimer, metrics

logger = logging.getLogger(__name__)

router = APIRouter()


# Get a review service instance with metrics
def get_review_service() -> ReviewService:
    """Get a review service instance"""
    return ReviewService(metrics_collector=metrics)


@router.post("", response_model=ReviewResponse)
async def upsert_review(
    review_data: ReviewCreate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    review_service: Annotated[ReviewService, Depends(get_review_service)],
) -> ReviewResponse:
    """
    Create or update a pull request review (upsert operation)

    If a review with the same pull_request_id exists, it will be updated.
    Otherwise, a new review will be created.

    Args:
        review_data: The review data to upsert
        db: Database session
        review_service: Review service instance

    Returns:
        ReviewResponse: The created or updated review

    Raises:
        ProjectNotFoundException: If the project doesn't exist
        UserNotFoundException: If either user doesn't exist
        HTTPException: 201 Created if new review, 200 OK if updated
    """
    with OperationTimer(
        metrics, operation_type="review", labels={"project": review_data.project_id}
    ):
        try:
            review, is_created = await review_service.upsert_review(review_data, db)
            metrics.increment_pull_request(
                project=review.project_id, status=review.pull_request_status
            )
            status_code = status.HTTP_201_CREATED if is_created else status.HTTP_200_OK
            return JSONResponse(
                status_code=status_code, content=ReviewResponse(**review.model_dump()).model_dump()
            )
        except (ProjectNotFoundException, UserNotFoundException) as e:
            metrics.increment_error(error_type=e.code, endpoint="POST /api/v1/reviews")
            raise HTTPException(
                status_code=e.status_code,
                detail={"error": e.code, "message": e.message, "detail": e.detail},
            )
        except Exception as e:
            metrics.increment_error(
                error_type="INTERNAL_SERVER_ERROR", endpoint="POST /api/v1/reviews"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to upsert review"},
            )


@router.get("", response_model=ReviewListResponse)
async def list_reviews(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    review_service: Annotated[ReviewService, Depends(get_review_service)],
    pull_request_id: Optional[str] = Query(None, description="Filter by pull request ID"),
    project_key: Optional[str] = Query(None, min_length=1, max_length=32, description="Filter by project key"),
    repository_slug: Optional[str] = Query(None, min_length=1, max_length=128, description="Filter by repository slug"),
    pull_request_user: Optional[str] = Query(None, min_length=1, max_length=64, description="Filter by pull request user username"),
    reviewer: Optional[str] = Query(None, min_length=1, max_length=64, description="Filter by reviewer username"),
    source_branch: Optional[str] = Query(None, description="Filter by source branch"),
    target_branch: Optional[str] = Query(None, description="Filter by target branch"),
    pull_request_status: Optional[str] = Query(
        None, description="Filter by pull request status (open, merged, closed, draft)"
    ),
    score_min: Optional[int] = Query(None, ge=0, le=10, description="Filter by minimum score"),
    score_max: Optional[int] = Query(None, ge=0, le=10, description="Filter by maximum score"),
    date_from: Optional[datetime] = Query(
        None, description="Filter reviews created after this date"
    ),
    date_to: Optional[datetime] = Query(
        None, description="Filter reviews created before this date"
    ),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Number of items per page"),
) -> ReviewListResponse:
    """
    List pull request reviews with filtering and pagination

    Args:
        pull_request_id: Filter by pull request ID
        project_key: Filter by project key
        repository_slug: Filter by repository slug
        pull_request_user: Filter by pull request user username
        reviewer: Filter by reviewer username
        source_branch: Filter by source branch
        target_branch: Filter by target branch
        pull_request_status: Filter by pull request status
        score_min: Filter by minimum score
        score_max: Filter by maximum score
        date_from: Filter reviews created after this date
        date_to: Filter reviews created before this date
        page: Page number (1-indexed)
        page_size: Number of items per page
        db: Database session
        review_service: Review service instance

    Returns:
        ReviewListResponse: List of reviews with pagination info
    """
    try:
        filters = ReviewFilter(
            pull_request_id=pull_request_id,
            project_key=project_key,
            repository_slug=repository_slug,
            pull_request_user=pull_request_user,
            reviewer=reviewer,
            source_branch=source_branch,
            target_branch=target_branch,
            pull_request_status=pull_request_status,
            score_min=score_min,
            score_max=score_max,
            date_from=date_from,
            date_to=date_to,
        )

        reviews, total = await review_service.list_reviews(filters, db, page, page_size)

        return ReviewListResponse(
            items=[ReviewResponse(**r.to_dict()) for r in reviews],
            total=total,
            page=page,
            page_size=page_size,
        )
    except Exception as e:
        logger.error(f"Failed to list reviews: {str(e)}", exc_info=True)
        metrics.increment_error(error_type="INTERNAL_SERVER_ERROR", endpoint="GET /api/v1/reviews")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to list reviews"},
        )


@router.get("/statistics", response_model=ReviewStats)
async def get_review_statistics(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    review_service: Annotated[ReviewService, Depends(get_review_service)],
    project_key: Optional[str] = Query(None, min_length=1, max_length=32, description="Filter statistics by project key"),
) -> ReviewStats:
    """
    Get pull request review statistics

    Args:
        project_key: Optional project key to filter statistics
        db: Database session
        review_service: Review service instance

    Returns:
        ReviewStats: Review statistics
    """
    try:
        stats = await review_service.get_review_statistics(project_key, db)
        return stats
    except Exception as e:
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR", endpoint="GET /api/v1/reviews/statistics"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to get review statistics"},
        )


@router.get("/{review_id}", response_model=ReviewResponse)
async def get_review(
    review_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    review_service: Annotated[ReviewService, Depends(get_review_service)],
) -> ReviewResponse:
    """
    Get a pull request review by ID

    Args:
        review_id: The pull request ID
        db: Database session
        review_service: Review service instance

    Returns:
        ReviewResponse: The requested review

    Raises:
        ReviewNotFoundException: If the review doesn't exist
    """
    try:
        review = await review_service.get_review(review_id, db)
        if not review:
            metrics.increment_error(
                error_type="NOT_FOUND", endpoint=f"GET /api/v1/reviews/{review_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "NOT_FOUND", "message": f"Review with ID {review_id} not found"},
            )
        return ReviewResponse(**review.to_dict())
    except HTTPException:
        raise
    except Exception as e:
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR", endpoint=f"GET /api/v1/reviews/{review_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to get review"},
        )


@router.put("/{review_id}", response_model=ReviewResponse)
async def update_review(
    review_id: str,
    review_update: ReviewUpdate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    review_service: Annotated[ReviewService, Depends(get_review_service)],
) -> ReviewResponse:
    """
    Update a pull request review

    Args:
        review_id: The pull request ID
        review_update: The update data
        db: Database session
        review_service: Review service instance

    Returns:
        ReviewResponse: The updated review

    Raises:
        ReviewNotFoundException: If the review doesn't exist
        ReviewStatusException: If the status transition is invalid
    """
    try:
        review = await review_service.update_review(review_id, review_update, db)
        return ReviewResponse(**review.to_dict())
    except (ReviewNotFoundException, ReviewStatusException) as e:
        metrics.increment_error(error_type=e.code, endpoint=f"PUT /api/v1/reviews/{review_id}")
        raise HTTPException(
            status_code=e.status_code,
            detail={"error": e.code, "message": e.message, "detail": e.detail},
        )
    except Exception as e:
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR", endpoint=f"PUT /api/v1/reviews/{review_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to update review"},
        )


@router.patch("/{review_id}/status", response_model=ReviewResponse)
async def update_review_status(
    review_id: str,
    new_status: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    review_service: Annotated[ReviewService, Depends(get_review_service)],
) -> ReviewResponse:
    """
    Update the status of a pull request review

    Args:
        review_id: The pull request ID
        new_status: The new status (open, merged, closed, draft)
        db: Database session
        review_service: Review service instance

    Returns:
        ReviewResponse: The updated review

    Raises:
        ReviewNotFoundException: If the review doesn't exist
        ReviewStatusException: If the status transition is invalid
    """
    try:
        review = await review_service.update_review_status(review_id, new_status, db)
        metrics.increment_pull_request(project=review.project_id, status=new_status)
        return ReviewResponse(**review.to_dict())
    except (ReviewNotFoundException, ReviewStatusException) as e:
        metrics.increment_error(
            error_type=e.code, endpoint=f"PATCH /api/v1/reviews/{review_id}/status"
        )
        raise HTTPException(
            status_code=e.status_code,
            detail={"error": e.code, "message": e.message, "detail": e.detail},
        )
    except Exception as e:
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR", endpoint=f"PATCH /api/v1/reviews/{review_id}/status"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to update review status"},
        )


@router.delete("/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_review(
    review_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    review_service: Annotated[ReviewService, Depends(get_review_service)],
) -> None:
    """
    Delete a pull request review

    Args:
        review_id: The pull request ID
        db: Database session
        review_service: Review service instance

    Returns:
        None: Successful deletion returns 204 No Content

    Raises:
        ReviewNotFoundException: If the review doesn't exist
    """
    try:
        deleted = await review_service.delete_review(review_id, db)
        if not deleted:
            metrics.increment_error(
                error_type="NOT_FOUND", endpoint=f"DELETE /api/v1/reviews/{review_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "NOT_FOUND", "message": f"Review with ID {review_id} not found"},
            )
    except HTTPException:
        raise
    except Exception as e:
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR", endpoint=f"DELETE /api/v1/reviews/{review_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to delete review"},
        )


@router.get("/project/{project_id}", response_model=ReviewListResponse)
async def get_reviews_by_project(
    project_id: int,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    review_service: Annotated[ReviewService, Depends(get_review_service)],
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Number of items per page"),
) -> ReviewListResponse:
    """
    Get pull request reviews by project

    Args:
        project_id: The project ID
        page: Page number (1-indexed)
        page_size: Number of items per page
        db: Database session
        review_service: Review service instance

    Returns:
        ReviewListResponse: List of reviews with pagination info
    """
    try:
        reviews, total = await review_service.get_reviews_by_project(
            project_id, page, page_size, db
        )

        return ReviewListResponse(
            items=[ReviewResponse(**r.to_dict()) for r in reviews],
            total=total,
            page=page,
            page_size=page_size,
        )
    except Exception as e:
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR", endpoint=f"GET /api/v1/reviews/project/{project_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": "Failed to get reviews by project",
            },
        )


@router.get("/reviewer/{reviewer_id}", response_model=ReviewListResponse)
async def get_reviews_by_reviewer(
    reviewer_id: int,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    review_service: Annotated[ReviewService, Depends(get_review_service)],
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Number of items per page"),
) -> ReviewListResponse:
    """
    Get pull request reviews by reviewer

    Args:
        reviewer_id: The reviewer ID
        page: Page number (1-indexed)
        page_size: Number of items per page
        db: Database session
        review_service: Review service instance

    Returns:
        ReviewListResponse: List of reviews with pagination info
    """
    try:
        reviews, total = await review_service.get_reviews_by_reviewer(
            reviewer_id, page, page_size, db
        )

        return ReviewListResponse(
            items=[ReviewResponse(**r.to_dict()) for r in reviews],
            total=total,
            page=page,
            page_size=page_size,
        )
    except Exception as e:
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR",
            endpoint=f"GET /api/v1/reviews/reviewer/{reviewer_id}",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": "Failed to get reviews by reviewer",
            },
        )


@router.get("/status/{status}", response_model=ReviewListResponse)
async def get_reviews_by_status(
    status: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    review_service: Annotated[ReviewService, Depends(get_review_service)],
    project_id: Optional[int] = Query(None, gt=0, description="Filter by project ID"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Number of items per page"),
) -> ReviewListResponse:
    """
    Get pull request reviews by status

    Args:
        status: The status to filter by (open, merged, closed, draft)
        project_id: Optional project ID to further filter
        page: Page number (1-indexed)
        page_size: Number of items per page
        db: Database session
        review_service: Review service instance

    Returns:
        ReviewListResponse: List of reviews with pagination info

    Raises:
        InvalidReviewDataException: If the status is invalid
    """
    try:
        if status not in ["open", "merged", "closed", "draft"]:
            metrics.increment_error(
                error_type="VALIDATION_ERROR", endpoint=f"GET /api/v1/reviews/status/{status}"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "VALIDATION_ERROR",
                    "message": "Invalid status. Must be one of: open, merged, closed, draft",
                },
            )

        reviews, total = await review_service.get_reviews_by_status(
            status, project_id, page, page_size, db
        )

        return ReviewListResponse(
            items=[ReviewResponse(**r.to_dict()) for r in reviews],
            total=total,
            page=page,
            page_size=page_size,
        )
    except HTTPException:
        raise
    except Exception as e:
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR", endpoint=f"GET /api/v1/reviews/status/{status}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to get reviews by status"},
        )
