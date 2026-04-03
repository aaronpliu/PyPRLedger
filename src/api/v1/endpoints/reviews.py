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
    ReviewScoreCreate,
    ReviewScoreResponse,
    ReviewScoreSummary,
    ReviewStats,
    ReviewUpdate,
)
from src.services.review_score_service import ReviewScoreService
from src.services.review_service import ReviewService
from src.utils.metrics import OperationTimer, metrics


logger = logging.getLogger(__name__)

router = APIRouter()


# Get a review service instance with metrics
def get_review_service() -> ReviewService:
    """Get a review service instance"""
    return ReviewService(metrics_collector=metrics)


# Get a score service instance with metrics
def get_score_service() -> ReviewScoreService:
    """Get a review score service instance"""
    return ReviewScoreService(metrics_collector=metrics)


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


@router.get("/{project_key}/{repository_slug}/{pull_request_id}", response_model=ReviewListResponse)
async def get_review(
    project_key: Annotated[str, Path(min_length=1, max_length=32, description="Project key")],
    repository_slug: Annotated[
        str,
        Path(min_length=1, max_length=128, description="Repository slug"),
    ],
    pull_request_id: Annotated[str, Path(description="Pull request ID")],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    review_service: Annotated[ReviewService, Depends(get_review_service)],
) -> ReviewListResponse:
    """
    Get all pull request reviews by composite business key.
    Returns all reviews for a PR (multiple reviewers may have reviewed the same PR).

    Args:
        project_key: The project key
        repository_slug: The repository slug
        pull_request_id: The pull request ID
        db: Database session
        review_service: Review service instance

    Returns:
        ReviewListResponse: List of all matching reviews with entity information

    Raises:
        NotFoundException: If no reviews are found
    """
    try:
        # Get all reviews for this PR (may have multiple reviews from different reviewers)
        reviews = await review_service.get_review(
            project_key=project_key,
            repository_slug=repository_slug,
            pull_request_id=pull_request_id,
            db=db,
        )

        if not reviews:
            metrics.increment_error(
                error_type="NOT_FOUND",
                endpoint=f"GET /api/v1/reviews/{project_key}/{repository_slug}/{pull_request_id}",
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "NOT_FOUND",
                    "message": f"No reviews found for PR {pull_request_id} in project {project_key}/{repository_slug}",
                },
            )

        logger.info(f"Retrieved {len(reviews)} review(s) for PR {pull_request_id}")

        # Enrich all reviews with full entity information
        enriched_reviews = []
        for review in reviews:
            if hasattr(review, "to_dict"):
                # ORM object - enrich with full entity information using relationships
                review_data = await review_service._enrich_review_with_entities(review, db)
            elif isinstance(review, dict):
                # Already a dict from cache - enrich by querying entities
                review_data = await review_service._enrich_review_with_entities(review, db)
            else:
                # Fallback to dict() method
                review_data = dict(review)

            enriched_reviews.append(ReviewResponse(**review_data))

        return ReviewListResponse(
            items=enriched_reviews,
            total=len(reviews),
            page=1,
            page_size=len(reviews),
        )
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
    project_key: Annotated[str, Path(min_length=1, max_length=32, description="Project key")],
    repository_slug: Annotated[
        str,
        Path(min_length=1, max_length=128, description="Repository slug"),
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
    project_key: Annotated[str, Path(min_length=1, max_length=32, description="Project key")],
    repository_slug: Annotated[
        str,
        Path(min_length=1, max_length=128, description="Repository slug"),
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
    project_key: Annotated[str, Path(min_length=1, max_length=32, description="Project key")],
    repository_slug: Annotated[
        str,
        Path(min_length=1, max_length=128, description="Repository slug"),
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
                # ORM object - use to_dict() which includes all fields
                review_data = r.to_dict()
            elif isinstance(r, dict):
                # Already a dict from cache - ensure all required fields are present
                review_data = r.copy()
                # Add missing required fields with defaults if needed
                if "id" not in review_data or review_data["id"] is None:
                    logger.warning(
                        f"Review from cache missing 'id' field: {review_data.get('pull_request_id')}"
                    )
                    continue  # Skip invalid cache entries
                if "created_date" not in review_data or review_data["created_date"] is None:
                    logger.warning(
                        f"Review from cache missing 'created_date': {review_data.get('pull_request_id')}"
                    )
                    continue  # Skip invalid cache entries
                if "updated_date" not in review_data or review_data["updated_date"] is None:
                    logger.warning(
                        f"Review from cache missing 'updated_date': {review_data.get('pull_request_id')}"
                    )
                    continue  # Skip invalid cache entries
            else:
                # Fallback - convert to dict
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


@router.get("/status/{review_status}", response_model=ReviewListResponse)
async def get_reviews_by_status(
    review_status: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    review_service: Annotated[ReviewService, Depends(get_review_service)],
    project_key: str | None = Query(None, max_length=32, description="Filter by project key"),
    repository_slug: str | None = Query(
        None, max_length=128, description="Filter by repository slug"
    ),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Number of items per page"),
) -> ReviewListResponse:
    """
    Get pull request reviews by status

    Args:
        review_status: The status to filter by (open, merged, closed, draft)
        project_key: Optional project key to further filter
        repository_slug: Optional repository slug to further filter
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
        if review_status not in ["open", "merged", "closed", "draft"]:
            metrics.increment_error(
                error_type="VALIDATION_ERROR",
                endpoint=f"GET /api/v1/reviews/status/{review_status}",
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "VALIDATION_ERROR",
                    "message": "Invalid status. Must be one of: open, merged, closed, draft",
                },
            )

        reviews, total = await review_service.get_reviews_by_status(
            review_status=review_status,
            project_key=project_key,
            repository_slug=repository_slug,
            page=page,
            page_size=page_size,
            db=db,
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
            error_type="INTERNAL_SERVER_ERROR",
            endpoint=f"GET /api/v1/reviews/status/{review_status}",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to get reviews by status"},
        )


# ============================================================================
# Score Management Endpoints
# ============================================================================


@router.put("/score", response_model=ReviewScoreResponse)
async def upsert_score(
    score_data: ReviewScoreCreate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    score_service: Annotated[ReviewScoreService, Depends(get_score_service)],
) -> ReviewScoreResponse:
    """
    Create or update a pull request review score

    This endpoint implements an UPSERT operation:
    - **If the reviewer already has a score for this target**: Updates their score
    - **If the reviewer doesn't have a score**: Creates a new score record

    ## Multi-Reviewer Support

    Each reviewer can independently submit and update their own score for the same
    PR/file combination. Scores are tracked separately per reviewer, so:

    - Reviewer A can score file "src/main.py" with 8.5
    - Reviewer B can score the same file "src/main.py" with 9.0
    - Both scores coexist independently in the system
    - Updating one reviewer's score does not affect other reviewers' scores

    ## Scoring Modes

    - **File-level scoring**: Provide `source_filename` to score a specific file
    - **PR-level scoring**: Omit `source_filename` or set to null to score entire PR

    ## Score Description

    If `score_description` is not provided, it will be auto-filled based on the score value:
    - 0.0: "Meaningless suggestion"
    - 1.0-2.0: "Bad suggestion"
    - 3.0-5.0: "No need to handle"
    - 6.0-8.0: "Can apply but not required"
    - 9.0: "Good suggestion"
    - 10.0: "Must apply change"

    Args:
        score_data: The score upsert payload containing:
            - pull_request_id: PR identifier
            - pull_request_commit_id: Commit identifier
            - project_key: Project identifier
            - repository_slug: Repository identifier
            - source_filename: Optional filename (null for PR-level score)
            - reviewer: Username of the reviewer submitting score
            - score: Score value (0.0-10.0)
            - score_description: Optional description (auto-filled if not provided)
            - reviewer_comments: Optional detailed feedback
        db: Database session
        score_service: Review score service instance

    Returns:
        ReviewScoreResponse: The created/updated score with enriched information including:
            - id: Score database ID
            - reviewer_info: Reviewer information
            - created_date: When the score was first created
            - updated_date: When the score was last updated

    Raises:
        HTTPException: 201 Created if new score, 200 OK if updated
    """
    try:
        score = await score_service.upsert_score(score_data, db, include_details=True)

        # Determine if this was a create or update by checking updated_date vs created_date
        is_created = score.created_date == score.updated_date
        status_code = status.HTTP_201_CREATED if is_created else status.HTTP_200_OK

        return JSONResponse(
            status_code=status_code,
            content=score.model_dump(mode="json"),
        )
    except Exception as e:
        error_traceback = traceback.format_exc()
        logger.error(f"Failed to upsert score: {str(e)}\n{error_traceback}")
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR",
            endpoint="PUT /api/v1/reviews/score",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to upsert score"},
        )


@router.get("/scores", response_model=list[ReviewScoreResponse])
async def get_scores(
    pull_request_id: str = Query(..., description="Pull request ID"),
    project_key: str = Query(..., min_length=1, max_length=32, description="Project key"),
    repository_slug: str = Query(..., min_length=1, max_length=128, description="Repository slug"),
    source_filename: str | None = Query(
        None,
        description="Optional filename to filter (when omitted, returns all scores)",
    ),
    db: Annotated[AsyncSession, Depends(get_db_session)] = None,
    score_service: Annotated[ReviewScoreService, Depends(get_score_service)] = None,
) -> list[ReviewScoreResponse]:
    """
    Get all scores for a specific review target

    ## Usage

    - **All scores (PR-level + all file-level)**: Omit `source_filename` parameter (default behavior)
    - **Specific file-level scores**: Provide `source_filename` parameter to filter by filename

    Args:
        pull_request_id: Pull request ID
        project_key: Project key
        repository_slug: Repository slug
        source_filename: Optional filename to filter (when omitted, returns all scores)
        db: Database session
        score_service: Review score service instance

    Returns:
        list[ReviewScoreResponse]: List of reviewer scores for the specified target

    Raises:
        HTTPException: If an error occurs while fetching scores
    """
    try:
        scores = await score_service.get_scores_by_review_target(
            pull_request_id=pull_request_id,
            project_key=project_key,
            repository_slug=repository_slug,
            source_filename=source_filename,
            db=db,
        )
        return scores
    except Exception as e:
        error_traceback = traceback.format_exc()
        logger.error(f"Failed to get scores: {str(e)}\n{error_traceback}")
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR",
            endpoint="GET /api/v1/reviews/scores",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to get scores"},
        )


@router.get("/scores/summary", response_model=ReviewScoreSummary)
async def get_score_summary(
    pull_request_id: str = Query(..., description="Pull request ID"),
    project_key: str = Query(..., min_length=1, max_length=32, description="Project key"),
    repository_slug: str = Query(..., min_length=1, max_length=128, description="Repository slug"),
    source_filename: str | None = Query(
        None,
        description="Optional filename (omit or null for PR-level summary)",
    ),
    db: Annotated[AsyncSession, Depends(get_db_session)] = None,
    score_service: Annotated[ReviewScoreService, Depends(get_score_service)] = None,
) -> ReviewScoreSummary:
    """
    Get summary statistics for all scores on a review target

    ## Usage

    Returns aggregated statistics including:
    - total_scores: Number of reviewer scores
    - average_score: Average of all scores
    - scores: List of individual scores

    Args:
        pull_request_id: Pull request ID
        project_key: Project key
        repository_slug: Repository slug
        source_filename: Optional filename (omit or null for PR-level)
        db: Database session
        score_service: Review score service instance

    Returns:
        ReviewScoreSummary: Aggregated score statistics

    Raises:
        HTTPException: If an error occurs while fetching summary
    """
    try:
        summary = await score_service.get_score_summary(
            pull_request_id=pull_request_id,
            project_key=project_key,
            repository_slug=repository_slug,
            source_filename=source_filename,
            db=db,
        )
        return summary
    except Exception as e:
        error_traceback = traceback.format_exc()
        logger.error(f"Failed to get score summary: {str(e)}\n{error_traceback}")
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR",
            endpoint="GET /api/v1/reviews/scores/summary",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to get score summary"},
        )


@router.get("/score/{reviewer}", response_model=ReviewScoreResponse)
async def get_score_by_reviewer(
    reviewer: Annotated[str, Path(min_length=1, max_length=64, description="Reviewer username")],
    pull_request_id: str = Query(..., description="Pull request ID"),
    project_key: str = Query(..., min_length=1, max_length=32, description="Project key"),
    repository_slug: str = Query(..., min_length=1, max_length=128, description="Repository slug"),
    source_filename: str | None = Query(
        None,
        description="Optional filename (omit or null for PR-level score)",
    ),
    db: Annotated[AsyncSession, Depends(get_db_session)] = None,
    score_service: Annotated[ReviewScoreService, Depends(get_score_service)] = None,
) -> ReviewScoreResponse:
    """
    Get a specific reviewer's score for a review target

    Args:
        reviewer: Reviewer username
        pull_request_id: Pull request ID
        project_key: Project key
        repository_slug: Repository slug
        source_filename: Optional filename (omit or null for PR-level)
        db: Database session
        score_service: Review score service instance

    Returns:
        ReviewScoreResponse: The reviewer's score

    Raises:
        HTTPException: 404 if score not found
    """
    try:
        score = await score_service.get_score_by_reviewer(
            pull_request_id=pull_request_id,
            project_key=project_key,
            repository_slug=repository_slug,
            source_filename=source_filename,
            reviewer=reviewer,
            db=db,
        )

        if not score:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "NOT_FOUND",
                    "message": f"Score not found for reviewer '{reviewer}'",
                },
            )

        return score
    except HTTPException:
        raise
    except Exception as e:
        error_traceback = traceback.format_exc()
        logger.error(f"Failed to get score by reviewer: {str(e)}\n{error_traceback}")
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR",
            endpoint=f"GET /api/v1/reviews/score/{reviewer}",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to get score by reviewer"},
        )


@router.delete("/score/{reviewer}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_score(
    reviewer: Annotated[str, Path(min_length=1, max_length=64, description="Reviewer username")],
    pull_request_id: str = Query(..., description="Pull request ID"),
    project_key: str = Query(..., min_length=1, max_length=32, description="Project key"),
    repository_slug: str = Query(..., min_length=1, max_length=128, description="Repository slug"),
    source_filename: str | None = Query(
        None,
        description="Optional filename (omit or null for PR-level score)",
    ),
    db: Annotated[AsyncSession, Depends(get_db_session)] = None,
    score_service: Annotated[ReviewScoreService, Depends(get_score_service)] = None,
) -> None:
    """
    Delete a reviewer's score for a review target

    Args:
        reviewer: Reviewer username
        pull_request_id: Pull request ID
        project_key: Project key
        repository_slug: Repository slug
        source_filename: Optional filename (omit or null for PR-level)
        db: Database session
        score_service: Review score service instance

    Returns:
        None: Successful deletion returns 204 No Content

    Raises:
        HTTPException: 404 if score not found
    """
    try:
        deleted = await score_service.delete_score(
            pull_request_id=pull_request_id,
            project_key=project_key,
            repository_slug=repository_slug,
            source_filename=source_filename,
            reviewer=reviewer,
            db=db,
        )

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "NOT_FOUND",
                    "message": f"Score not found for reviewer '{reviewer}'",
                },
            )
    except HTTPException:
        raise
    except Exception as e:
        error_traceback = traceback.format_exc()
        logger.error(f"Failed to delete score: {str(e)}\n{error_traceback}")
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR",
            endpoint=f"DELETE /api/v1/reviews/score/{reviewer}",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to delete score"},
        )
