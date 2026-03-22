from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.pull_request import PullRequestReview
from src.models.project import Project
from src.models.repository import Repository
from src.models.user import User
from src.schemas.pull_request import (
    ReviewCreate,
    ReviewUpdate,
    ReviewResponse,
    ReviewFilter,
    ReviewStats,
)
from src.core.exceptions import (
    ReviewNotFoundException,
    ReviewAlreadyExistsException,
    InvalidReviewDataException,
    ProjectNotFoundException,
    UserNotFoundException,
    ReviewStatusException,
)
from src.core.config import settings
from src.utils.redis import get_redis_client
from src.utils.metrics import MetricsCollector
import json
import logging

logger = logging.getLogger(__name__)


class ReviewService:
    """Service for managing pull request reviews"""

    def __init__(self, metrics_collector: Optional[MetricsCollector] = None):
        """Initialize the review service"""
        self.redis_client = get_redis_client()
        self.metrics = metrics_collector or MetricsCollector()

    def _get_cache_key(self, review_id: str) -> str:
        """Generate cache key for a review"""
        return f"review:{review_id}"

    def _get_list_cache_key(self, filters: Dict[str, Any], page: int, page_size: int) -> str:
        """Generate cache key for review list"""
        filter_str = ":".join(f"{k}={v}" for k, v in sorted(filters.items()) if v is not None)
        return f"reviews:list:{filter_str}:{page}:{page_size}"

    async def _get_review_from_cache(self, review_id: str) -> Optional[Dict[str, Any]]:
        """Try to get review from cache"""
        try:
            cached = await self.redis_client.get(self._get_cache_key(review_id))
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Failed to get review from cache: {str(e)}")
        return None

    async def _set_review_in_cache(self, review_id: str, review_data: Dict[str, Any]) -> None:
        """Store review in cache"""
        try:
            await self.redis_client.setex(
                self._get_cache_key(review_id), settings.CACHE_TTL_REVIEWS, json.dumps(review_data)
            )
        except Exception as e:
            logger.warning(f"Failed to set review in cache: {str(e)}")

    async def _invalidate_review_cache(self, review_id: str) -> None:
        """Invalidate review cache"""
        try:
            await self.redis_client.delete(self._get_cache_key(review_id))
        except Exception as e:
            logger.warning(f"Failed to invalidate review cache: {str(e)}")

    async def _invalidate_list_cache(self) -> None:
        """Invalidate all review list cache entries"""
        try:
            # Get all keys matching the review list pattern
            keys = await self.redis_client.keys("reviews:list:*")
            if keys:
                await self.redis_client.delete(*keys)
        except Exception as e:
            logger.warning(f"Failed to invalidate list cache: {str(e)}")

    async def create_review(
        self, review_data: ReviewCreate, db: AsyncSession, include_details: bool = False
    ) -> ReviewResponse:
        """
        Create a new pull request review

        Args:
            review_data: The review data to create
            db: Database session
            include_details: Whether to include detailed information

        Returns:
            ReviewResponse: The created review

        Raises:
            ProjectNotFoundException: If the project doesn't exist
            UserNotFoundException: If either user doesn't exist
            ReviewAlreadyExistsException: If a review with the same PR ID already exists
        """
        # Upsert project using business project_id (integer)
        project_result = await db.execute(
            select(Project).where(Project.project_id == review_data.project_id)
        )
        project = project_result.scalar_one_or_none()
        if not project:
            logger.warning(f"Project {review_data.project_id} not found. Please create it first.")
            raise ProjectNotFoundException(project_id=review_data.project_id)

        # Upsert repository if not exists
        repo_result = await db.execute(
            select(Repository).where(Repository.repository_id == review_data.repository_id)
        )
        repository = repo_result.scalar_one_or_none()
        if not repository:
            logger.warning(
                f"Repository {review_data.repository_id} not found. Please create it first."
            )
            from src.core.exceptions import RepositoryNotFoundException

            raise RepositoryNotFoundException(repository_id=review_data.repository_id)

        # Upsert pull request user if not exists (using business user_id)
        user_result = await db.execute(
            select(User).where(User.user_id == review_data.pull_request_user_id)
        )
        user = user_result.scalar_one_or_none()
        if not user:
            # Auto-create user with minimal info
            user = User(
                user_id=review_data.pull_request_user_id,
                username=f"user_{review_data.pull_request_user_id}",
                display_name=f"User {review_data.pull_request_user_id}",
                email_address=f"user_{review_data.pull_request_user_id}@example.com",
                active=True,
                is_reviewer=False,
            )
            db.add(user)
            await db.flush()
            logger.info(f"Auto-created user: {review_data.pull_request_user_id}")

        # Upsert reviewer if not exists (using business user_id)
        reviewer_result = await db.execute(
            select(User).where(User.user_id == review_data.reviewer_id)
        )
        reviewer = reviewer_result.scalar_one_or_none()
        if not reviewer:
            # Auto-create reviewer with minimal info
            reviewer = User(
                user_id=review_data.reviewer_id,
                username=f"reviewer_{review_data.reviewer_id}",
                display_name=f"Reviewer {review_data.reviewer_id}",
                email_address=f"reviewer_{review_data.reviewer_id}@example.com",
                active=True,
                is_reviewer=True,
            )
            db.add(reviewer)
            await db.flush()
            logger.info(f"Auto-created reviewer: {review_data.reviewer_id}")
        elif not reviewer.is_reviewer:
            # Update existing user to be a reviewer
            reviewer.is_reviewer = True
            logger.info(f"Updated user {review_data.reviewer_id} to reviewer status")

        # Check if review with same pull_request_id already exists
        existing_review_result = await db.execute(
            select(PullRequestReview).where(
                PullRequestReview.pull_request_id == review_data.pull_request_id
            )
        )
        existing_review = existing_review_result.scalar_one_or_none()
        if existing_review:
            raise ReviewAlreadyExistsException(review_id=review_data.pull_request_id)

        # Create new review using business IDs
        new_review = PullRequestReview(
            pull_request_id=review_data.pull_request_id,
            pull_request_commit_id=review_data.pull_request_commit_id,
            project_id=project.project_id,  # Use business ID
            repository_id=repository.repository_id,  # Use business ID
            pull_request_user_id=user.user_id,  # Use business ID
            reviewer_id=reviewer.user_id,  # Use business ID
            source_branch=review_data.source_branch,
            target_branch=review_data.target_branch,
            git_code_diff=review_data.git_code_diff,
            source_filename=review_data.source_filename,
            ai_suggestions=review_data.ai_suggestions,
            reviewer_comments=review_data.reviewer_comments,
            score=review_data.score,
            pull_request_status=review_data.pull_request_status,
            metadata=review_data.metadata,
        )
        db.add(new_review)
        await db.flush()
        await db.refresh(new_review)

        # Cache the new review
        review_dict = new_review.to_dict()
        if include_details:
            # Add project and user details
            review_dict["project_name"] = project.project_name
            review_dict["pull_request_user"] = {
                "id": user.user_id,
                "username": user.username,
                "display_name": user.display_name,
            }
            review_dict["reviewer"] = {
                "id": reviewer.user_id,
                "username": reviewer.username,
                "display_name": reviewer.display_name,
            }
        await self._set_review_in_cache(new_review.pull_request_id, review_dict)

        # Update metrics
        self.metrics.increment_review(project_id=project.project_id, reviewer_id=reviewer.user_id)

        # Invalidate list cache
        await self._invalidate_list_cache()

        logger.info(f"Created new review: {new_review.pull_request_id}")
        return ReviewResponse(**new_review.to_dict())

    async def upsert_review(
        self, review_data: ReviewCreate, db: AsyncSession, include_details: bool = False
    ) -> tuple[PullRequestReview, bool]:
        """
        Upsert a pull request review - create if not exists, update if exists

        Args:
            review_data: The review data to upsert
            db: Database session
            include_details: Whether to include detailed information

        Returns:
            tuple[PullRequestReview, bool]: The review and whether it was created

        Raises:
            ProjectNotFoundException: If the project doesn't exist
            UserNotFoundException: If either user doesn't exist
        """
        # Check if review already exists
        existing_review_result = await db.execute(
            select(PullRequestReview).where(
                PullRequestReview.pull_request_id == review_data.pull_request_id
            )
        )
        existing_review = existing_review_result.scalar_one_or_none()

        if existing_review:
            # Update existing review
            for field, value in review_data.model_dump().items():
                if hasattr(existing_review, field):
                    setattr(existing_review, field, value)

            existing_review.updated_date = datetime.utcnow()
            await db.flush()
            await db.refresh(existing_review)

            # Invalidate cache
            await self._invalidate_review_cache(existing_review.pull_request_id)
            await self._invalidate_list_cache()

            logger.info(f"Updated existing review: {existing_review.pull_request_id}")
            return existing_review, False
        else:
            # Create new review
            new_review_response = await self.create_review(review_data, db, include_details)
            await db.commit()
            # Convert response back to model for consistency
            new_review = PullRequestReview.from_dict(new_review_response.model_dump())
            return new_review, True

    async def get_review(
        self, review_id: str, db: AsyncSession, use_cache: bool = True
    ) -> Optional[PullRequestReview]:
        """
        Get a pull request review by ID

        Args:
            review_id: The pull request ID
            db: Database session
            use_cache: Whether to use cache

        Returns:
            PullRequestReview: The review, or None if not found
        """
        # Try cache first
        if use_cache:
            cached = await self._get_review_from_cache(review_id)
            if cached:
                logger.debug(f"Retrieved review from cache: {review_id}")
                return PullRequestReview.from_dict(cached)

        # Query database
        result = await db.execute(
            select(PullRequestReview)
            .options(
                selectinload(PullRequestReview.project),
                selectinload(PullRequestReview.pull_request_user),
                selectinload(PullRequestReview.reviewer),
            )
            .where(PullRequestReview.pull_request_id == review_id)
        )
        review = result.scalar_one_or_none()

        if review:
            # Cache the result
            await self._set_review_in_cache(review_id, review.to_dict())

        return review

    async def list_reviews(
        self,
        filters: ReviewFilter,
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        use_cache: bool = True,
    ) -> tuple[List[PullRequestReview], int]:
        """
        List pull request reviews with filtering and pagination

        Args:
            filters: Filter criteria
            page: Page number (1-indexed)
            page_size: Number of items per page
            db: Database session
            use_cache: Whether to use cache

        Returns:
            Tuple[List[PullRequestReview], int]: List of reviews and total count
        """
        # Build query conditions
        conditions = []
        if filters.pull_request_id:
            conditions.append(PullRequestReview.pull_request_id == filters.pull_request_id)
        if filters.project_id:
            conditions.append(PullRequestReview.project_id == filters.project_id)
        if filters.pull_request_user_id:
            conditions.append(
                PullRequestReview.pull_request_user_id == filters.pull_request_user_id
            )
        if filters.reviewer_id:
            conditions.append(PullRequestReview.reviewer_id == filters.reviewer_id)
        if filters.source_branch:
            conditions.append(PullRequestReview.source_branch == filters.source_branch)
        if filters.target_branch:
            conditions.append(PullRequestReview.target_branch == filters.target_branch)
        if filters.pull_request_status:
            conditions.append(PullRequestReview.pull_request_status == filters.pull_request_status)
        if filters.score_min is not None:
            conditions.append(PullRequestReview.score >= filters.score_min)
        if filters.score_max is not None:
            conditions.append(PullRequestReview.score <= filters.score_max)
        if filters.date_from:
            conditions.append(PullRequestReview.created_date >= filters.date_from)
        if filters.date_to:
            conditions.append(PullRequestReview.created_date <= filters.date_to)

        # Try cache first for list results
        filter_dict = filters.model_dump(exclude_unset=True)
        if use_cache:
            try:
                cache_key = self._get_list_cache_key(filter_dict, page, page_size)
                cached = await self.redis_client.get(cache_key)
                if cached:
                    data = json.loads(cached)
                    # Deserialize cached reviews
                    reviews = [PullRequestReview.from_dict(r) for r in data["reviews"]]
                    logger.debug(f"Retrieved review list from cache")
                    return reviews, data["total"]
            except Exception as e:
                logger.warning(f"Failed to get review list from cache: {str(e)}")

        # Get total count
        count_query = select(func.count()).select_from(PullRequestReview)
        if conditions:
            count_query = count_query.where(and_(*conditions))

        count_result = await db.execute(count_query)
        total = count_result.scalar()

        # Get reviews
        query = (
            select(PullRequestReview)
            .options(
                selectinload(PullRequestReview.project),
                selectinload(PullRequestReview.pull_request_user),
                selectinload(PullRequestReview.reviewer),
            )
            .order_by(desc(PullRequestReview.created_date))
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        if conditions:
            query = query.where(and_(*conditions))

        result = await db.execute(query)
        reviews = result.scalars().all()

        # Cache the result
        if use_cache and reviews:
            try:
                cache_key = self._get_list_cache_key(filter_dict, page, page_size)
                cache_data = {"reviews": [r.to_dict() for r in reviews], "total": total}
                await self.redis_client.setex(
                    cache_key, settings.CACHE_TTL_REVIEWS, json.dumps(cache_data)
                )
            except Exception as e:
                logger.warning(f"Failed to cache review list: {str(e)}")

        return list(reviews), total

    async def update_review(
        self, review_id: str, update_data: ReviewUpdate, db: AsyncSession
    ) -> PullRequestReview:
        """
        Update a pull request review

        Args:
            review_id: The pull request ID
            update_data: The update data
            db: Database session

        Returns:
            PullRequestReview: The updated review

        Raises:
            ReviewNotFoundException: If the review doesn't exist
            ReviewStatusException: If the status transition is invalid
        """
        review = await self.get_review(review_id, db, use_cache=False)
        if not review:
            raise ReviewNotFoundException(review_id=review_id)

        # Check status transition if status is being updated
        if (
            update_data.pull_request_status
            and update_data.pull_request_status != review.pull_request_status
        ):
            if not review.can_transition_to(update_data.pull_request_status):
                raise ReviewStatusException(
                    current_status=review.pull_request_status,
                    target_status=update_data.pull_request_status,
                )

        # Update review
        review.update(update_data.model_dump(exclude_unset=True))

        # Invalidate cache
        await self._invalidate_review_cache(review_id)
        await self._invalidate_list_cache()

        logger.info(f"Updated review: {review_id}")
        return review

    async def delete_review(self, review_id: str, db: AsyncSession) -> bool:
        """
        Delete a pull request review

        Args:
            review_id: The pull request ID
            db: Database session

        Returns:
            bool: True if deleted, False if not found
        """
        review = await self.get_review(review_id, db, use_cache=False)
        if not review:
            return False

        await db.delete(review)

        # Invalidate cache
        await self._invalidate_review_cache(review_id)
        await self._invalidate_list_cache()

        logger.info(f"Deleted review: {review_id}")
        return True

    async def get_review_statistics(
        self, db: AsyncSession, project_id: Optional[int] = None, use_cache: bool = True
    ) -> ReviewStats:
        """
        Get pull request review statistics

        Args:
            project_id: Optional project ID to filter statistics
            db: Database session
            use_cache: Whether to use cache

        Returns:
            ReviewStats: Review statistics
        """
        # Try cache first
        cache_key = f"stats:reviews:{project_id or 'all'}"
        if use_cache:
            try:
                cached = await self.redis_client.get(cache_key)
                if cached:
                    return ReviewStats(**json.loads(cached))
            except Exception as e:
                logger.warning(f"Failed to get review stats from cache: {str(e)}")

        # Build base query
        base_query = select(PullRequestReview)
        if project_id:
            base_query = base_query.where(PullRequestReview.project_id == project_id)

        # Get total reviews
        total_query = select(func.count()).select_from(base_query.subquery())
        total_result = await db.execute(total_query)
        total_reviews = total_result.scalar()

        # Get reviews by status
        status_query = select(
            PullRequestReview.pull_request_status, func.count(PullRequestReview.id)
        ).select_from(base_query.subquery())
        status_query = status_query.group_by(PullRequestReview.pull_request_status)
        status_result = await db.execute(status_query)
        status_counts = {row[0]: row[1] for row in status_result}

        open_reviews = status_counts.get("open", 0)
        merged_reviews = status_counts.get("merged", 0)
        closed_reviews = status_counts.get("closed", 0)

        # Get average score
        avg_score_query = select(func.avg(PullRequestReview.score)).select_from(
            base_query.subquery()
        )
        avg_score_result = await db.execute(avg_score_query)
        avg_score = avg_score_result.scalar() or 0.0

        # Get reviews by date
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        week_ago = today.replace(day=today.day - 7) if today.day > 7 else today.replace(day=1)
        month_ago = (
            today.replace(month=today.month - 1)
            if today.month > 1
            else today.replace(year=today.year - 1, month=12)
        )

        today_query = select(func.count()).select_from(
            base_query.where(PullRequestReview.created_date >= today).subquery()
        )
        today_result = await db.execute(today_query)
        reviews_today = today_result.scalar()

        week_query = select(func.count()).select_from(
            base_query.where(PullRequestReview.created_date >= week_ago).subquery()
        )
        week_result = await db.execute(week_query)
        reviews_this_week = week_result.scalar()

        month_query = select(func.count()).select_from(
            base_query.where(PullRequestReview.created_date >= month_ago).subquery()
        )
        month_result = await db.execute(month_query)
        reviews_this_month = month_result.scalar()

        # Create statistics object
        stats = ReviewStats(
            total_reviews=total_reviews,
            open_reviews=open_reviews,
            merged_reviews=merged_reviews,
            closed_reviews=closed_reviews,
            average_score=round(float(avg_score), 2),
            reviews_today=reviews_today,
            reviews_this_week=reviews_this_week,
            reviews_this_month=reviews_this_month,
        )

        # Cache the result
        if use_cache:
            try:
                await self.redis_client.setex(
                    cache_key, settings.CACHE_TTL_STATS, json.dumps(stats.model_dump())
                )
            except Exception as e:
                logger.warning(f"Failed to cache review stats: {str(e)}")

        return stats

    async def get_reviews_by_reviewer(
        self, reviewer_id: int, db: AsyncSession, page: int = 1, page_size: int = 20
    ) -> tuple[List[PullRequestReview], int]:
        """
        Get reviews by reviewer

        Args:
            reviewer_id: The reviewer ID
            page: Page number (1-indexed)
            page_size: Number of items per page
            db: Database session

        Returns:
            tuple[List[PullRequestReview], int]: List of reviews and total count
        """
        filters = ReviewFilter(reviewer_id=reviewer_id)
        return await self.list_reviews(filters, db, page, page_size)

    async def get_reviews_by_project(
        self, project_id: int, db: AsyncSession, page: int = 1, page_size: int = 20
    ) -> tuple[List[PullRequestReview], int]:
        """
        Get reviews by project

        Args:
            project_id: The project ID
            page: Page number (1-indexed)
            page_size: Number of items per page
            db: Database session

        Returns:
            tuple[List[PullRequestReview], int]: List of reviews and total count
        """
        filters = ReviewFilter(project_id=project_id)
        return await self.list_reviews(filters, db, page, page_size)

    async def get_reviews_by_status(
        self,
        status: str,
        db: AsyncSession,
        project_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[PullRequestReview], int]:
        """
        Get reviews by status

        Args:
            status: The status to filter by (open, merged, closed, draft)
            project_id: Optional project ID to further filter
            page: Page number (1-indexed)
            page_size: Number of items per page
            db: Database session

        Returns:
            tuple[List[PullRequestReview], int]: List of reviews and total count
        """
        filters = ReviewFilter(status=status, project_id=project_id)
        return await self.list_reviews(filters, db, page, page_size)

    async def update_review_status(
        self, review_id: str, new_status: str, db: AsyncSession
    ) -> PullRequestReview:
        """
        Update the status of a pull request review

        Args:
            review_id: The pull request ID
            new_status: The new status (open, merged, closed, draft)
            db: Database session

        Returns:
            PullRequestReview: The updated review

        Raises:
            ReviewNotFoundException: If the review doesn't exist
            ReviewStatusException: If the status transition is invalid
        """
        update_data = ReviewUpdate(pull_request_status=new_status)
        return await self.update_review(review_id, update_data, db)
