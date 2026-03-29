import logging
import traceback
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.core.exceptions import (
    ProjectNotFoundException,
    ReviewNotFoundException,
    ReviewStatusException,
    UserNotFoundException,
)
from src.schemas.pull_request import (
    ReviewCreate,
    ReviewFilter,
    ReviewListResponse,
    ReviewResponse,
    ReviewStats,
    ReviewUpdate,
)
from src.services.review_service import ReviewService
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
        metrics, operation_type="review", labels={"project": review_data.project_key}
    ):
        try:
            review, is_created = await review_service.upsert_review(review_data, db)
            metrics.increment_pull_request(
                project=review.project_key, status=review.pull_request_status
            )
            status_code = status.HTTP_201_CREATED if is_created else status.HTTP_200_OK
            # Handle both ORM object and Pydantic model
            if hasattr(review, "to_dict"):
                # ORM object (PullRequestReview) - to_dict already converts datetime to ISO format
                review_data_dict = review.to_dict()
            elif hasattr(review, "model_dump"):
                # Pydantic model (ReviewResponse) - use mode='json' for proper datetime serialization
                review_data_dict = review.model_dump(mode="json")
            else:
                # Fallback to dict() method
                review_data_dict = dict(review)

            return JSONResponse(status_code=status_code, content=review_data_dict)
        except (ProjectNotFoundException, UserNotFoundException) as e:
            metrics.increment_error(error_type=e.code, endpoint="POST /api/v1/reviews")
            raise HTTPException(
                status_code=e.status_code,
                detail={"error": e.code, "message": e.message, "detail": e.detail},
            )
        except Exception as e:
            import traceback

            error_traceback = traceback.format_exc()
            logger.error(f"Failed to upsert review: {str(e)}\n{error_traceback}")
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
    pull_request_id: str | None = Query(None, description="Filter by pull request ID"),
    project_key: str | None = Query(
        None, min_length=1, max_length=32, description="Filter by project key"
    ),
    repository_slug: str | None = Query(
        None, min_length=1, max_length=128, description="Filter by repository slug"
    ),
    pull_request_user: str | None = Query(
        None, min_length=1, max_length=64, description="Filter by pull request user username"
    ),
    reviewer: str | None = Query(
        None, min_length=1, max_length=64, description="Filter by reviewer username"
    ),
    source_branch: str | None = Query(None, description="Filter by source branch"),
    target_branch: str | None = Query(None, description="Filter by target branch"),
    pull_request_status: str | None = Query(
        None, description="Filter by pull request status (open, merged, closed, draft)"
    ),
    score_min: int | None = Query(None, ge=0, le=10, description="Filter by minimum score"),
    score_max: int | None = Query(None, ge=0, le=10, description="Filter by maximum score"),
    date_from: datetime | None = Query(None, description="Filter reviews created after this date"),
    date_to: datetime | None = Query(None, description="Filter reviews created before this date"),
    app_names: str | None = Query(
        None,
        description="Filter by application names (comma-separated for multiple apps, e.g., 'member,tv,football')",
    ),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Number of items per page"),
) -> ReviewListResponse:
    """
    List pull request reviews with filtering and pagination

    Response includes full entity information for project, repository, and users,
    plus the virtual app_name field resolved from project registry.

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
        app_names: Filter by application names (comma-separated for multiple apps)
        page: Page number (1-indexed)
        page_size: Number of items per page
        db: Database session
        review_service: Review service instance

    Returns:
        ReviewListResponse: List of reviews with full entity information, app_name, and pagination info
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

        # Parse app_names from comma-separated string
        app_names_list = None
        if app_names:
            app_names_list = [name.strip() for name in app_names.split(",") if name.strip()]

        # Get enriched reviews with full entity information and app_name resolution
        enriched_reviews, total = await review_service.list_reviews_with_entities(
            filters, db, page, page_size, app_names=app_names_list
        )

        return ReviewListResponse(
            items=enriched_reviews,
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
    project_key: str | None = Query(
        None, min_length=1, max_length=32, description="Filter statistics by project key"
    ),
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
    except Exception:
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR", endpoint="GET /api/v1/reviews/statistics"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to get review statistics"},
        )


@router.put(
    "/score",
    response_model=ReviewResponse,
    dependencies=[Depends(get_db_session), Depends(get_review_service)],
)
async def update_review_score(
    project_key: Annotated[str, Query(description="Project key (e.g., 'ECOM')")],
    repository_slug: Annotated[str, Query(description="Repository slug (e.g., 'frontend-store')")],
    pull_request_id: Annotated[str, Query(description="Pull request ID")],
    reviewer: Annotated[str, Query(description="Reviewer username")],
    source_filename: Annotated[
        str, Query(description="Source filename being reviewed (e.g., 'src/services/cart.py')")
    ],
    score: Annotated[int, Query(ge=0, le=10, description="Score (0-10)")],
    db: AsyncSession = Depends(get_db_session),
    review_service: ReviewService = Depends(get_review_service),
) -> ReviewResponse:
    """
    Update the score of a specific review record

    This endpoint updates the score for a specific review identified by the composite key:
    (project_key, repository_slug, pull_request_id, source_filename, reviewer)

    Args:
        project_key: The project key
        repository_slug: The repository slug
        pull_request_id: The pull request ID
        source_filename: The source filename being reviewed
        reviewer: The reviewer username
        score: The new score (0-10)
        db: Database session
        review_service: Review service instance

    Returns:
        ReviewResponse: The updated review

    Raises:
        ReviewNotFoundException: If the review doesn't exist
    """
    import traceback

    try:
        updated_review = await review_service.update_review_score(
            project_key=project_key,
            repository_slug=repository_slug,
            pull_request_id=pull_request_id,
            source_filename=source_filename,
            reviewer=reviewer,
            score=score,
            db=db,
        )
        return ReviewResponse(**updated_review.to_dict())
    except ReviewNotFoundException as e:
        metrics.increment_error(error_type=e.code, endpoint="PUT /api/v1/reviews/score")
        raise HTTPException(
            status_code=e.status_code,
            detail={"error": e.code, "message": e.message, "detail": e.detail},
        )
    except Exception as ex:
        error_traceback = traceback.format_exc()
        logger.error(f"Failed to update review score: {str(ex)}\n{error_traceback}")
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR",
            endpoint="PUT /api/v1/reviews/score",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to update review score"},
        )


@router.get("/{project_key}/{repository_slug}/{pull_request_id}", response_model=ReviewResponse)
async def get_review(
    project_key: Annotated[
        str, Path(min_length=1, max_length=32, description="Project key (e.g., 'ECOM')")
    ],
    repository_slug: Annotated[
        str,
        Path(min_length=1, max_length=128, description="Repository slug (e.g., 'frontend-store')"),
    ],
    pull_request_id: Annotated[str, Path(description="Pull request ID")],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    review_service: Annotated[ReviewService, Depends(get_review_service)],
) -> ReviewResponse:
    """
    Get a pull request review by composite business key

    Args:
        project_key: The project key
        repository_slug: The repository slug
        pull_request_id: The pull request ID
        db: Database session
        review_service: Review service instance

    Returns:
        ReviewResponse: The requested review

    Raises:
        ReviewNotFoundException: If the review doesn't exist
    """
    try:
        # Use composite key for precise cache operations
        review = await review_service.get_review(
            project_key=project_key,
            repository_slug=repository_slug,
            pull_request_id=pull_request_id,
            db=db,
        )
        if not review:
            metrics.increment_error(
                error_type="NOT_FOUND",
                endpoint=f"GET /api/v1/reviews/{project_key}/{repository_slug}/{pull_request_id}",
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "NOT_FOUND",
                    "message": f"Review with ID {pull_request_id} not found in project {project_key}/{repository_slug}",
                },
            )

        # Enrich review with full entity information
        if hasattr(review, "to_dict"):
            # ORM object - enrich with full entity information using relationships
            logger.info(f"Enriching ORM review {pull_request_id} with entity information")
            review_data = await review_service._enrich_review_with_entities(review, db)
        elif isinstance(review, dict):
            # Already a dict from cache - enrich by querying entities
            logger.info(f"Review {pull_request_id} from cache, querying entity information")
            review_data = await review_service._enrich_review_with_entities(review, db)
        else:
            # Fallback to dict() method
            review_data = dict(review)

        return ReviewResponse(**review_data)

    except HTTPException:
        raise
    except Exception as e:
        import traceback

        error_traceback = traceback.format_exc()
        logger.error(f"Failed to get review {pull_request_id}: {str(e)}\n{error_traceback}")
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR",
            endpoint=f"GET /api/v1/reviews/{project_key}/{repository_slug}/{pull_request_id}",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to get review"},
        )


@router.put("/{project_key}/{repository_slug}/{pull_request_id}", response_model=ReviewResponse)
async def update_review(
    project_key: Annotated[
        str, Path(min_length=1, max_length=32, description="Project key (e.g., 'ECOM')")
    ],
    repository_slug: Annotated[
        str,
        Path(min_length=1, max_length=128, description="Repository slug (e.g., 'frontend-store')"),
    ],
    pull_request_id: Annotated[str, Path(description="Pull request ID")],
    review_update: ReviewUpdate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    review_service: Annotated[ReviewService, Depends(get_review_service)],
) -> ReviewResponse:
    """
    Update a pull request review using composite business key

    Args:
        project_key: The project key
        repository_slug: The repository slug
        pull_request_id: The pull request ID
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
        # Use composite key for precise cache operations
        review = await review_service.update_review(
            pull_request_id=pull_request_id,
            update_data=review_update,
            db=db,
            project_key=project_key,
            repository_slug=repository_slug,
        )
        return ReviewResponse(**review.to_dict())
    except (ReviewNotFoundException, ReviewStatusException) as e:
        metrics.increment_error(
            error_type=e.code,
            endpoint=f"PUT /api/v1/reviews/{project_key}/{repository_slug}/{pull_request_id}",
        )
        raise HTTPException(
            status_code=e.status_code,
            detail={"error": e.code, "message": e.message, "detail": e.detail},
        )
    except Exception:
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR",
            endpoint=f"PUT /api/v1/reviews/{project_key}/{repository_slug}/{pull_request_id}",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to update review"},
        )


@router.patch(
    "/{project_key}/{repository_slug}/{pull_request_id}/status", response_model=ReviewResponse
)
async def update_review_status(
    project_key: Annotated[
        str, Path(min_length=1, max_length=32, description="Project key (e.g., 'ECOM')")
    ],
    repository_slug: Annotated[
        str,
        Path(min_length=1, max_length=128, description="Repository slug (e.g., 'frontend-store')"),
    ],
    pull_request_id: Annotated[str, Path(description="Pull request ID")],
    new_status: Annotated[str, Query(description="The new status (open, merged, closed, draft)")],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    review_service: Annotated[ReviewService, Depends(get_review_service)],
) -> ReviewResponse:
    """
    Update the status of a pull request review using composite business key

    Args:
        project_key: The project key
        repository_slug: The repository slug
        pull_request_id: The pull request ID
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
        # Use composite key for precise cache operations
        review = await review_service.update_review_status(
            pull_request_id=pull_request_id,
            new_status=new_status,
            db=db,
            project_key=project_key,
            repository_slug=repository_slug,
        )
        metrics.increment_pull_request(project=review.project_key, status=new_status)
        return ReviewResponse(**review.to_dict())
    except (ReviewNotFoundException, ReviewStatusException) as e:
        metrics.increment_error(
            error_type=e.code,
            endpoint=f"PATCH /api/v1/reviews/{project_key}/{repository_slug}/{pull_request_id}/status",
        )
        raise HTTPException(
            status_code=e.status_code,
            detail={"error": e.code, "message": e.message, "detail": e.detail},
        )
    except Exception:
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR",
            endpoint=f"PATCH /api/v1/reviews/{project_key}/{repository_slug}/{pull_request_id}/status",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to update review status"},
        )


@router.delete(
    "/{project_key}/{repository_slug}/{pull_request_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_review(
    project_key: Annotated[
        str, Path(min_length=1, max_length=32, description="Project key (e.g., 'ECOM')")
    ],
    repository_slug: Annotated[
        str,
        Path(min_length=1, max_length=128, description="Repository slug (e.g., 'frontend-store')"),
    ],
    pull_request_id: Annotated[str, Path(description="Pull request ID")],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    review_service: Annotated[ReviewService, Depends(get_review_service)],
) -> None:
    """
    Delete a pull request review using composite business key

    Args:
        project_key: The project key
        repository_slug: The repository slug
        pull_request_id: The pull request ID
        db: Database session
        review_service: Review service instance

    Returns:
        None: Successful deletion returns 204 No Content

    Raises:
        ReviewNotFoundException: If the review doesn't exist
    """
    try:
        # Use composite key for precise cache operations
        deleted = await review_service.delete_review(
            pull_request_id=pull_request_id,
            db=db,
            project_key=project_key,
            repository_slug=repository_slug,
        )
        if not deleted:
            metrics.increment_error(
                error_type="NOT_FOUND",
                endpoint=f"DELETE /api/v1/reviews/{project_key}/{repository_slug}/{pull_request_id}",
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "NOT_FOUND",
                    "message": f"Review with ID {pull_request_id} not found in project {project_key}/{repository_slug}",
                },
            )
    except HTTPException:
        raise
    except Exception:
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR",
            endpoint=f"DELETE /api/v1/reviews/{project_key}/{repository_slug}/{pull_request_id}",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to delete review"},
        )


@router.get("/project/{project_key}", response_model=ReviewListResponse)
async def get_reviews_by_project(
    project_key: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    review_service: Annotated[ReviewService, Depends(get_review_service)],
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Number of items per page"),
) -> ReviewListResponse:
    """
    Get pull request reviews by project

    Args:
        project_key: The project key
        page: Page number (1-indexed)
        page_size: Number of items per page
        db: Database session
        review_service: Review service instance

    Returns:
        ReviewListResponse: List of reviews with pagination info
    """
    import traceback

    try:
        reviews, total = await review_service.get_reviews_by_project(
            project_key, db, page, page_size
        )

        # Handle both ORM objects and dicts
        items = []
        for r in reviews:
            if hasattr(r, "to_dict"):
                review_data = r.to_dict()
            elif isinstance(r, dict):
                review_data = r
            else:
                review_data = dict(r)
            items.append(ReviewResponse(**review_data))

        return ReviewListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )
    except Exception as e:
        error_traceback = traceback.format_exc()
        logger.error(f"Failed to get reviews by project {project_key}: {str(e)}\n{error_traceback}")
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR",
            endpoint=f"GET /api/v1/reviews/project/{project_key}",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": "Failed to get reviews by project",
            },
        )


@router.get("/reviewer/{reviewer_username}", response_model=ReviewListResponse)
async def get_reviews_by_reviewer(
    reviewer_username: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    review_service: Annotated[ReviewService, Depends(get_review_service)],
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Number of items per page"),
) -> ReviewListResponse:
    """
    Get pull request reviews by reviewer

    Args:
        reviewer_username: The reviewer username
        page: Page number (1-indexed)
        page_size: Number of items per page
        db: Database session
        review_service: Review service instance

    Returns:
        ReviewListResponse: List of reviews with pagination info
    """
    try:
        reviews, total = await review_service.get_reviews_by_reviewer(
            reviewer_username, db, page, page_size
        )

        # Handle both ORM objects and dicts
        items = []
        for r in reviews:
            if hasattr(r, "to_dict"):
                review_data = r.to_dict()
            elif isinstance(r, dict):
                review_data = r
            else:
                review_data = dict(r)
            items.append(ReviewResponse(**review_data))

        return ReviewListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )
    except Exception as e:
        error_traceback = traceback.format_exc()
        logger.error(
            f"Failed to get reviews by reviewer {reviewer_username}: {str(e)}\n{error_traceback}"
        )
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR",
            endpoint=f"GET /api/v1/reviews/reviewer/{reviewer_username}",
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
    project_id: int | None = Query(None, gt=0, description="Filter by project ID"),
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
    except Exception:
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR", endpoint=f"GET /api/v1/reviews/status/{status}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to get reviews by status"},
        )
