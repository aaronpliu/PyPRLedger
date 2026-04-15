import json
import logging
import traceback
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.config import settings
from src.core.exceptions import (
    DatabaseException,
    ReviewAlreadyExistsException,
    ReviewNotFoundException,
    ReviewStatusException,
)
from src.models.project import Project
from src.models.project_registry import ProjectRegistry
from src.models.pull_request import (
    PullRequestReviewAssignment,
    PullRequestReviewBase,
    PullRequestScore,
)
from src.schemas.pull_request import (
    ReviewCreate,
    ReviewFilter,
    ReviewResponse,
    ReviewStats,
    ReviewUpdate,
)
from src.services.entity_sync_service import EntitySyncService
from src.services.project_registry_service import ProjectRegistryService
from src.services.review_score_service import ReviewScoreService
from src.utils.metrics import MetricsCollector
from src.utils.redis import get_redis_client


logger = logging.getLogger(__name__)


class ReviewService:
    """Service for managing pull request reviews"""

    def __init__(self, metrics_collector: MetricsCollector | None = None):
        """Initialize the review service"""
        self.redis_client = get_redis_client()
        self.metrics = metrics_collector or MetricsCollector()

    @staticmethod
    def _get_cache_key(project_key: str, repository_slug: str, pull_request_id: str) -> str:
        """
        Generate unique cache key for review using composite business key.

        Using composite key prevents collisions when different projects/repositories
        have PRs with the same ID.

        Args:
            project_key: The project key (e.g., 'ECOM')
            repository_slug: The repository slug (e.g., 'frontend-store')
            pull_request_id: The pull request ID

        Returns:
            Unique cache key string
        """
        return f"review:{project_key}:{repository_slug}:{pull_request_id}"

    @staticmethod
    def _get_list_cache_key(filters: dict[str, Any], page: int, page_size: int) -> str:
        """Generate cache key for review list"""
        filter_str = ":".join(f"{k}={v}" for k, v in sorted(filters.items()) if v is not None)
        return f"reviews:list:{filter_str}:{page}:{page_size}"

    async def _get_review_from_cache(
        self, project_key: str, repository_slug: str, pull_request_id: str
    ) -> dict[str, Any] | None:
        """
        Try to get review from cache using composite key.

        Args:
            project_key: The project key
            repository_slug: The repository slug
            pull_request_id: The pull request ID

        Returns:
            Cached review data or None
        """
        try:
            cached = await self.redis_client.get(
                self._get_cache_key(project_key, repository_slug, pull_request_id)
            )
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Failed to get review from cache: {str(e)}")
        return None

    async def _set_review_in_cache(
        self,
        project_key: str,
        repository_slug: str,
        pull_request_id: str,
        review_data: dict[str, Any],
    ) -> None:
        """
        Store review in cache using composite key.

        Args:
            project_key: The project key
            repository_slug: The repository slug
            pull_request_id: The pull request ID
            review_data: The review data to cache
        """
        try:
            await self.redis_client.setex(
                self._get_cache_key(project_key, repository_slug, pull_request_id),
                settings.CACHE_TTL_REVIEWS,
                json.dumps(review_data),
            )
        except Exception as e:
            logger.warning(f"Failed to set review in cache: {str(e)}")

    async def _invalidate_review_cache(
        self, project_key: str, repository_slug: str, pull_request_id: str
    ) -> None:
        """
        Invalidate review cache using composite key.

        Args:
            project_key: The project key
            repository_slug: The repository slug
            pull_request_id: The pull request ID
        """
        try:
            await self.redis_client.delete(
                self._get_cache_key(project_key, repository_slug, pull_request_id)
            )
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

    @staticmethod
    def _serialize_review(
        base: PullRequestReviewBase,
        assignment: PullRequestReviewAssignment | None = None,
    ) -> dict[str, Any]:
        review_dict = base.to_dict()
        review_dict.update(
            {
                "id": assignment.id if assignment else base.id,
                "reviewer": assignment.reviewer if assignment else None,
                "reviewer_comments": assignment.reviewer_comments if assignment else None,
                "assigned_by": assignment.assigned_by if assignment else None,
                "assigned_date": (
                    assignment.assigned_date.isoformat()
                    if assignment and isinstance(assignment.assigned_date, datetime)
                    else assignment.assigned_date
                    if assignment
                    else None
                ),
                "assignment_status": (
                    assignment.assignment_status if assignment else "auto_created"
                ),
            }
        )
        return review_dict

    @staticmethod
    def _flatten_reviews(
        bases: list[PullRequestReviewBase],
        reviewer: str | None = None,
    ) -> list[dict[str, Any]]:
        reviews: list[dict[str, Any]] = []

        for base in bases:
            assignments = list(base.assignments)
            if reviewer:
                assignments = [
                    assignment for assignment in assignments if assignment.reviewer == reviewer
                ]

            if assignments:
                reviews.extend(
                    ReviewService._serialize_review(base, assignment) for assignment in assignments
                )
            elif reviewer is None:
                reviews.append(ReviewService._serialize_review(base))

        return reviews

    @staticmethod
    def _build_base_conditions(
        review_data: ReviewCreate,
        project_key: str,
        repository_slug: str,
    ) -> list[Any]:
        conditions = [
            PullRequestReviewBase.pull_request_commit_id == review_data.pull_request_commit_id,
            PullRequestReviewBase.project_key == project_key,
            PullRequestReviewBase.repository_slug == repository_slug,
        ]
        if review_data.source_filename is None:
            conditions.append(PullRequestReviewBase.source_filename.is_(None))
        else:
            conditions.append(PullRequestReviewBase.source_filename == review_data.source_filename)
        return conditions

    async def _get_existing_base(
        self,
        review_data: ReviewCreate,
        db: AsyncSession,
        project_key: str,
        repository_slug: str,
    ) -> PullRequestReviewBase | None:
        stmt = (
            select(PullRequestReviewBase)
            .options(
                selectinload(PullRequestReviewBase.assignments).selectinload(
                    PullRequestReviewAssignment.reviewer_rel
                ),
                selectinload(PullRequestReviewBase.project),
                selectinload(PullRequestReviewBase.repository),
                selectinload(PullRequestReviewBase.pull_request_user_rel),
            )
            .where(*self._build_base_conditions(review_data, project_key, repository_slug))
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    def _get_existing_assignment(
        base: PullRequestReviewBase,
        reviewer: str,
    ) -> PullRequestReviewAssignment | None:
        return next(
            (assignment for assignment in base.assignments if assignment.reviewer == reviewer), None
        )

    @staticmethod
    def _populate_base(
        base: PullRequestReviewBase,
        review_data: ReviewCreate,
        pull_request_user: str,
    ) -> None:
        base.pull_request_id = review_data.pull_request_id
        base.pull_request_commit_id = review_data.pull_request_commit_id
        base.project_key = review_data.project_key
        base.repository_slug = review_data.repository_slug
        base.pull_request_user = pull_request_user
        base.source_branch = review_data.source_branch
        base.target_branch = review_data.target_branch
        base.git_code_diff = review_data.git_code_diff
        base.source_filename = review_data.source_filename
        base.ai_suggestions = review_data.ai_suggestions
        base.pull_request_status = review_data.pull_request_status
        base.review_metadata = review_data.metadata

    @staticmethod
    def _populate_assignment(
        assignment: PullRequestReviewAssignment,
        reviewer: str,
        review_data: ReviewCreate,
    ) -> None:
        assignment.reviewer = reviewer
        assignment.reviewer_comments = review_data.reviewer_comments
        if not assignment.assignment_status:
            assignment.assignment_status = "assigned"

    @staticmethod
    def _build_review_response(
        base: PullRequestReviewBase,
        assignment: PullRequestReviewAssignment | None = None,
    ) -> ReviewResponse:
        return ReviewResponse(**ReviewService._serialize_review(base, assignment))

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
        """
        # Initialize entity sync service
        entity_sync_service = EntitySyncService(db)

        # Sync all related entities using business keys only
        # This will query DB first, then fetch from Bitbucket API if not exists
        project: Project = await entity_sync_service.sync_project(review_data.project_key)

        repository = await entity_sync_service.sync_repository(
            repository_slug=review_data.repository_slug, project=project
        )

        pr_user = await entity_sync_service.sync_user(
            username=review_data.pull_request_user, is_reviewer=False
        )

        # Sync reviewer if provided, otherwise set to None
        reviewer = None
        if review_data.reviewer:
            reviewer = await entity_sync_service.sync_user(
                username=review_data.reviewer, is_reviewer=True
            )

        existing_base = await self._get_existing_base(
            review_data,
            db,
            project.project_key,
            repository.repository_slug,
        )

        if reviewer and existing_base:
            existing_assignment = self._get_existing_assignment(existing_base, reviewer.username)
            if existing_assignment:
                raise ReviewAlreadyExistsException(pull_request_id=review_data.pull_request_id)
        elif existing_base:
            raise ReviewAlreadyExistsException(pull_request_id=review_data.pull_request_id)

        new_base = PullRequestReviewBase()
        self._populate_base(new_base, review_data, pr_user.username)
        db.add(new_base)
        await db.flush()

        new_assignment = None
        if reviewer:
            new_assignment = PullRequestReviewAssignment(
                review_base_id=new_base.id,
                reviewer=reviewer.username,
                assignment_status="assigned",
            )
            self._populate_assignment(new_assignment, reviewer.username, review_data)
            db.add(new_assignment)
            await db.flush()

        await db.commit()  # Commit the transaction to make data visible to other connections

        # Cache the new review using composite key
        review_dict = self._serialize_review(new_base, new_assignment)
        if include_details:
            # Add project and user details
            review_dict["project_name"] = project.project_name
            review_dict["pull_request_user_info"] = {
                "username": pr_user.username,
                "display_name": pr_user.display_name,
            }
            if reviewer:
                if reviewer:
                    review_dict["reviewer_info"] = {
                        "username": reviewer.username,
                        "display_name": reviewer.display_name,
                    }
        await self._set_review_in_cache(
            project_key=str(project.project_key),
            repository_slug=str(repository.repository_slug),
            pull_request_id=str(new_base.pull_request_id),
            review_data=review_dict,
        )

        # Update metrics (only if reviewer is set)
        if reviewer:
            self.metrics.increment_review(
                project=str(project.project_key), reviewer=str(reviewer.username)
            )

        logger.info(f"Created new review: {new_base.pull_request_id}")
        return ReviewResponse(**review_dict)

    async def upsert_review(
        self, review_data: ReviewCreate, db: AsyncSession, include_details: bool = False
    ) -> tuple[ReviewResponse, bool]:
        """
        Upsert a pull request review - create if not exists, update if exists

        Args:
            review_data: The review data to upsert
            db: Database session
            include_details: Whether to include detailed information

        Returns:
            tuple[ReviewResponse, bool]: The created/updated review response and True (created) or False (updated)
        """
        # Initialize entity sync service
        entity_sync_service = EntitySyncService(db)

        # Sync all related entities using business keys only
        project: Project = await entity_sync_service.sync_project(review_data.project_key)

        repository = await entity_sync_service.sync_repository(
            repository_slug=review_data.repository_slug, project=project
        )

        pr_user = await entity_sync_service.sync_user(
            username=review_data.pull_request_user, is_reviewer=False
        )

        # Sync reviewer if provided, otherwise set to None
        reviewer = None
        if review_data.reviewer:
            reviewer = await entity_sync_service.sync_user(
                username=review_data.reviewer, is_reviewer=True
            )

        existing_base = await self._get_existing_base(
            review_data,
            db,
            project.project_key,
            repository.repository_slug,
        )
        existing_assignment = None
        if reviewer and existing_base:
            existing_assignment = self._get_existing_assignment(existing_base, reviewer.username)

        created = False
        if existing_base:
            self._populate_base(existing_base, review_data, pr_user.username)
            existing_base.updated_date = datetime.now(UTC)

            if reviewer:
                if existing_assignment:
                    self._populate_assignment(existing_assignment, reviewer.username, review_data)
                    existing_assignment.updated_date = datetime.now(UTC)
                else:
                    existing_assignment = PullRequestReviewAssignment(
                        review_base_id=existing_base.id,
                        reviewer=reviewer.username,
                        assignment_status="assigned",
                    )
                    self._populate_assignment(existing_assignment, reviewer.username, review_data)
                    db.add(existing_assignment)
                    created = True
            await db.flush()
            await db.commit()

            review_dict = self._serialize_review(existing_base, existing_assignment)
            if include_details:
                review_dict["project_name"] = project.project_name
                review_dict["pull_request_user_info"] = {
                    "username": pr_user.username,
                    "display_name": pr_user.display_name,
                }
                if reviewer:
                    review_dict["reviewer_info"] = {
                        "username": reviewer.username,
                        "display_name": reviewer.display_name,
                    }
            await self._set_review_in_cache(
                project_key=str(project.project_key),
                repository_slug=str(repository.repository_slug),
                pull_request_id=str(existing_base.pull_request_id),
                review_data=review_dict,
            )

            # Update metrics (only if reviewer is set)
            if reviewer:
                self.metrics.increment_review(
                    project=str(project.project_key), reviewer=str(reviewer.username)
                )

            logger.info(f"Updated review: {existing_base.pull_request_id}")
            return ReviewResponse(**review_dict), created
        else:
            new_review_response = await self.create_review(review_data, db, include_details)
            logger.info(f"Created new review: {new_review_response.pull_request_id}")
            return new_review_response, True

    async def get_review(
        self,
        project_key: str | None,
        repository_slug: str | None,
        pull_request_id: str,
        reviewer: str | None,
        source_filename: str | None,
        db: AsyncSession,
    ) -> list[dict[str, Any]]:
        """
        Get all pull request reviews by composite business key

        Args:
            project_key: The project key
            repository_slug: The repository slug
            pull_request_id: The pull request ID
            db: Database session

        Returns:
            list[dict[str, Any]]: List of all matching reviews for this PR

        Raises:
            DatabaseException: If database query fails
        """
        try:
            logger.info(f"Querying database for reviews: {pull_request_id}")

            query = (
                select(PullRequestReviewBase)
                .options(
                    selectinload(PullRequestReviewBase.project),
                    selectinload(PullRequestReviewBase.repository),
                    selectinload(PullRequestReviewBase.pull_request_user_rel),
                    selectinload(PullRequestReviewBase.assignments).selectinload(
                        PullRequestReviewAssignment.reviewer_rel
                    ),
                )
                .where(PullRequestReviewBase.pull_request_id == pull_request_id)
                .order_by(desc(PullRequestReviewBase.created_date))
            )

            if project_key:
                query = query.where(PullRequestReviewBase.project_key == project_key)
            if repository_slug:
                query = query.where(PullRequestReviewBase.repository_slug == repository_slug)
            if source_filename:
                query = query.where(PullRequestReviewBase.source_filename == source_filename)

            result = await db.execute(query)
            bases = result.scalars().unique().all()
            reviews = self._flatten_reviews(list(bases), reviewer)

            if reviews:
                logger.info(f"Found {len(reviews)} review(s) for PR: {pull_request_id}")
                for review in reviews:
                    await self._set_review_in_cache(
                        str(review["project_key"]),
                        str(review["repository_slug"]),
                        pull_request_id,
                        review,
                    )
                return reviews

            # No reviews found
            logger.info(f"No reviews found for PR: {pull_request_id}")
            return []

        except Exception as e:
            error_traceback = traceback.format_exc()
            logger.error(
                f"Database query failed for {pull_request_id}: {str(e)}\n{error_traceback}"
            )
            raise DatabaseException(
                message=f"Failed to query reviews for PR {pull_request_id}",
                detail={"error": str(e)},
            )

    async def list_reviews(
        self,
        filters: ReviewFilter,
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        use_cache: bool = True,
        app_names: list[str] | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """
        List pull request reviews with filtering and pagination

        Args:
            filters: Filter criteria using business keys
            page: Page number (1-indexed)
            page_size: Number of items per page
            db: Database session
            use_cache: Whether to use cache
            app_names: Optional list of app names to filter by (supports multiple apps)

        Returns:
            Tuple[List[dict[str, Any]], int]: List of reviews and total count
        """
        query = select(PullRequestReviewBase).options(
            selectinload(PullRequestReviewBase.project),
            selectinload(PullRequestReviewBase.repository),
            selectinload(PullRequestReviewBase.pull_request_user_rel),
            selectinload(PullRequestReviewBase.assignments).selectinload(
                PullRequestReviewAssignment.reviewer_rel
            ),
        )

        if app_names:
            registry_query = select(
                ProjectRegistry.project_key,
                ProjectRegistry.repository_slug,
            ).where(ProjectRegistry.app_name.in_(app_names))
            registry_result = await db.execute(registry_query)
            project_repo_pairs = registry_result.all()

            if project_repo_pairs:
                app_conditions = [
                    and_(
                        PullRequestReviewBase.project_key == pk,
                        PullRequestReviewBase.repository_slug == rs,
                    )
                    for pk, rs in project_repo_pairs
                ]
                query = query.where(or_(*app_conditions))
            else:
                return [], 0

        if filters.pull_request_id:
            query = query.where(PullRequestReviewBase.pull_request_id == filters.pull_request_id)
        if filters.project_key:
            query = query.where(PullRequestReviewBase.project_key == filters.project_key)
        if filters.repository_slug:
            query = query.where(PullRequestReviewBase.repository_slug == filters.repository_slug)
        if filters.pull_request_user:
            query = query.where(
                PullRequestReviewBase.pull_request_user == filters.pull_request_user
            )
        if filters.reviewer:
            query = query.join(PullRequestReviewBase.assignments).where(
                PullRequestReviewAssignment.reviewer == filters.reviewer
            )
        if filters.visible_to_username:
            query = query.outerjoin(PullRequestReviewBase.assignments).where(
                or_(
                    PullRequestReviewBase.pull_request_user == filters.visible_to_username,
                    PullRequestReviewAssignment.reviewer == filters.visible_to_username,
                )
            )
        if filters.source_branch:
            query = query.where(PullRequestReviewBase.source_branch == filters.source_branch)
        if filters.target_branch:
            query = query.where(PullRequestReviewBase.target_branch == filters.target_branch)
        if filters.pull_request_status:
            query = query.where(
                PullRequestReviewBase.pull_request_status == filters.pull_request_status
            )
        if filters.pull_request_commit_id:
            query = query.where(
                PullRequestReviewBase.pull_request_commit_id.like(
                    f"{filters.pull_request_commit_id}%"
                )
            )
        if filters.date_from:
            query = query.where(PullRequestReviewBase.created_date >= filters.date_from)
        if filters.date_to:
            query = query.where(PullRequestReviewBase.created_date <= filters.date_to)
        score_join = and_(
            PullRequestScore.pull_request_id == PullRequestReviewBase.pull_request_id,
            PullRequestScore.project_key == PullRequestReviewBase.project_key,
            PullRequestScore.repository_slug == PullRequestReviewBase.repository_slug,
            or_(
                and_(
                    PullRequestScore.source_filename.is_(None),
                    PullRequestReviewBase.source_filename.is_(None),
                ),
                PullRequestScore.source_filename == PullRequestReviewBase.source_filename,
            ),
        )
        if filters.score_min is not None or filters.score_max is not None:
            query = query.join(
                PullRequestScore,
                score_join,
            )
        if filters.score_min is not None:
            query = query.where(PullRequestScore.score >= filters.score_min)
        if filters.score_max is not None:
            query = query.where(PullRequestScore.score <= filters.score_max)

        # Try cache first for list results (only if no app_name filter)
        if not app_names and use_cache:
            try:
                filter_dict = filters.model_dump(exclude_unset=True)
                cache_key = self._get_list_cache_key(filter_dict, page, page_size)
                cached = await self.redis_client.get(cache_key)
                if cached:
                    data = json.loads(cached)
                    # Return reviews as dicts from cache (not ORM objects)
                    logger.debug("Retrieved review list from cache")
                    return data["reviews"], data["total"]
            except Exception as e:
                logger.warning(f"Failed to get review list from cache: {str(e)}")

        query = query.order_by(desc(PullRequestReviewBase.created_date)).distinct()
        result = await db.execute(query)
        bases = result.scalars().unique().all()
        flattened_reviews = self._flatten_reviews(list(bases), filters.reviewer)
        total = len(flattened_reviews)
        start = (page - 1) * page_size
        end = start + page_size
        reviews = flattened_reviews[start:end]

        # Cache the result (only if no app_name filter)
        if not app_names and use_cache and reviews:
            try:
                filter_dict = filters.model_dump(exclude_unset=True)
                cache_key = self._get_list_cache_key(filter_dict, page, page_size)
                cache_data = {"reviews": reviews, "total": total}
                await self.redis_client.setex(
                    cache_key, settings.CACHE_TTL_REVIEWS, json.dumps(cache_data)
                )
            except Exception as e:
                logger.warning(f"Failed to cache review list: {str(e)}")

        return reviews, total

    async def is_user_assigned_to_review(
        self,
        db: AsyncSession,
        *,
        pull_request_id: str,
        pull_request_commit_id: str | None,
        project_key: str,
        repository_slug: str,
        source_filename: str | None,
        reviewer: str,
    ) -> bool:
        query = (
            select(PullRequestReviewAssignment.id)
            .join(PullRequestReviewAssignment.review_base)
            .where(
                PullRequestReviewBase.pull_request_id == pull_request_id,
                PullRequestReviewBase.project_key == project_key,
                PullRequestReviewBase.repository_slug == repository_slug,
                PullRequestReviewAssignment.reviewer == reviewer,
            )
        )

        if pull_request_commit_id is not None:
            query = query.where(
                PullRequestReviewBase.pull_request_commit_id == pull_request_commit_id
            )

        if source_filename is None:
            query = query.where(PullRequestReviewBase.source_filename.is_(None))
        else:
            query = query.where(PullRequestReviewBase.source_filename == source_filename)

        result = await db.execute(query.limit(1))
        return result.scalar_one_or_none() is not None

    async def get_review_base_by_target(
        self,
        db: AsyncSession,
        *,
        pull_request_id: str,
        pull_request_commit_id: str | None,
        project_key: str,
        repository_slug: str,
        source_filename: str | None,
    ) -> PullRequestReviewBase | None:
        query = select(PullRequestReviewBase).where(
            PullRequestReviewBase.pull_request_id == pull_request_id,
            PullRequestReviewBase.project_key == project_key,
            PullRequestReviewBase.repository_slug == repository_slug,
        )

        if pull_request_commit_id is not None:
            query = query.where(
                PullRequestReviewBase.pull_request_commit_id == pull_request_commit_id
            )

        if source_filename is None:
            query = query.where(PullRequestReviewBase.source_filename.is_(None))
        else:
            query = query.where(PullRequestReviewBase.source_filename == source_filename)

        result = await db.execute(query.limit(1))
        return result.scalar_one_or_none()

    async def update_review(
        self,
        pull_request_id: str,
        update_data: ReviewUpdate,
        db: AsyncSession,
        project_key: str | None = None,
        repository_slug: str | None = None,
    ) -> dict:
        """
        Update a pull request review

        Args:
            pull_request_id: The pull request ID
            update_data: The update data
            db: Database session
            project_key: Optional project key (will be auto-detected if not provided)
            repository_slug: Optional repository slug (will be auto-detected if not provided)

        Returns:
            PullRequestReview: The updated review

        Raises:
            ReviewNotFoundException: If the review doesn't exist
            ReviewStatusException: If the status transition is invalid
        """
        # Get review - will auto-detect project_key and repository_slug if not provided
        reviews = await self.get_review(
            project_key=project_key,
            repository_slug=repository_slug,
            pull_request_id=pull_request_id,
            db=db,
        )
        if not reviews:
            raise ReviewNotFoundException(pull_request_id=pull_request_id)

        review = reviews[0]

        base_stmt = (
            select(PullRequestReviewBase)
            .options(selectinload(PullRequestReviewBase.assignments))
            .where(PullRequestReviewBase.id == review["id"])
        )
        if review.get("reviewer"):
            base_stmt = (
                select(PullRequestReviewBase)
                .options(selectinload(PullRequestReviewBase.assignments))
                .join(PullRequestReviewBase.assignments)
                .where(PullRequestReviewAssignment.id == review["id"])
            )
        base_result = await db.execute(base_stmt)
        base = base_result.scalar_one_or_none()
        if not base:
            raise ReviewNotFoundException(pull_request_id=pull_request_id)

        assignment = None
        if review.get("reviewer"):
            assignment = self._get_existing_assignment(base, review["reviewer"])

        if (
            update_data.pull_request_status
            and update_data.pull_request_status != base.pull_request_status
        ):
            if not base.can_transition_to(update_data.pull_request_status):
                raise ReviewStatusException(
                    current_status=str(base.pull_request_status),
                    target_status=update_data.pull_request_status,
                )

        update_payload = update_data.model_dump(exclude_unset=True)
        base_updates = {
            "git_code_diff": update_payload.get("git_code_diff"),
            "source_filename": update_payload.get("source_filename"),
            "ai_suggestions": update_payload.get("ai_suggestions"),
            "pull_request_status": update_payload.get("pull_request_status"),
            "review_metadata": update_payload.get("metadata"),
        }
        base.update({key: value for key, value in base_updates.items() if value is not None})
        base.updated_date = datetime.now(UTC)

        if assignment and "reviewer_comments" in update_payload:
            assignment.reviewer_comments = update_payload["reviewer_comments"]
            assignment.updated_date = datetime.now(UTC)

        if (
            assignment
            and update_payload.get("reviewer")
            and update_payload["reviewer"] != assignment.reviewer
        ):
            assignment.reviewer = update_payload["reviewer"]

        await db.flush()
        await db.commit()

        await self._invalidate_review_cache(
            str(base.project_key), str(base.repository_slug), pull_request_id
        )
        await self._invalidate_list_cache()

        logger.info(f"Updated review: {pull_request_id}")
        return self._serialize_review(base, assignment)

    async def delete_review(
        self,
        pull_request_id: str,
        db: AsyncSession,
        project_key: str | None = None,
        repository_slug: str | None = None,
    ) -> bool:
        """
        Delete a pull request review

        Args:
            pull_request_id: The pull request ID
            db: Database session
            project_key: Optional project key (will be auto-detected if not provided)
            repository_slug: Optional repository slug (will be auto-detected if not provided)

        Returns:
            bool: True if deleted, False if not found
        """
        # Get review - will auto-detect project_key and repository_slug if not provided
        reviews = await self.get_review(
            project_key=project_key,
            repository_slug=repository_slug,
            pull_request_id=pull_request_id,
            db=db,
        )
        if not reviews:
            return False

        review = reviews[0]

        if review.get("reviewer"):
            stmt = select(PullRequestReviewAssignment).where(
                PullRequestReviewAssignment.id == review["id"]
            )
            result = await db.execute(stmt)
            assignment = result.scalar_one_or_none()
            if not assignment:
                return False
            await db.delete(assignment)
        else:
            stmt = select(PullRequestReviewBase).where(PullRequestReviewBase.id == review["id"])
            result = await db.execute(stmt)
            base = result.scalar_one_or_none()
            if not base:
                return False
            await db.delete(base)

        await db.commit()

        await self._invalidate_review_cache(
            str(review["project_key"]), str(review["repository_slug"]), pull_request_id
        )
        await self._invalidate_list_cache()

        logger.info(f"Deleted review: {pull_request_id}")
        return True

    async def get_review_statistics(
        self,
        project_key: str | None = None,
        db: AsyncSession = None,
        use_cache: bool = True,
    ) -> ReviewStats:
        """
        Get pull request review statistics

        Args:
            project_key: Optional project key to filter statistics
            db: Database session
            use_cache: Whether to use cache

        Returns:
            ReviewStats: Review statistics
        """
        # Try cache first
        cache_key = f"stats:reviews:{project_key or 'all'}"
        if use_cache:
            try:
                cached = await self.redis_client.get(cache_key)
                if cached:
                    return ReviewStats(**json.loads(cached))
            except Exception as e:
                logger.warning(f"Failed to get review stats from cache: {str(e)}")

        base_query = select(PullRequestReviewBase)
        if project_key:
            base_query = base_query.where(PullRequestReviewBase.project_key == project_key)

        # Get total reviews
        total_query = select(func.count()).select_from(base_query.subquery())
        total_result = await db.execute(total_query)
        total_reviews = total_result.scalar()

        # Get reviews by status
        status_query = select(
            PullRequestReviewBase.pull_request_status,
            func.count(PullRequestReviewBase.id),
        ).select_from(base_query.subquery())
        status_query = status_query.group_by(PullRequestReviewBase.pull_request_status)
        status_result = await db.execute(status_query)
        status_counts = {row[0]: row[1] for row in status_result}

        open_reviews = status_counts.get("open", 0)
        merged_reviews = status_counts.get("merged", 0)
        closed_reviews = status_counts.get("closed", 0)

        # Get average score from PullRequestScore table
        avg_score_query = select(func.avg(PullRequestScore.score))

        # Apply same project_key filter if provided
        if project_key:
            avg_score_query = avg_score_query.where(PullRequestScore.project_key == project_key)

        avg_score_result = await db.execute(avg_score_query)
        avg_score = avg_score_result.scalar() or 0.0

        # Get reviews by date
        today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        week_ago = today.replace(day=today.day - 7) if today.day > 7 else today.replace(day=1)
        month_ago = (
            today.replace(month=today.month - 1)
            if today.month > 1
            else today.replace(year=today.year - 1, month=12)
        )

        today_query = select(func.count()).select_from(
            base_query.where(PullRequestReviewBase.created_date >= today).subquery()
        )
        today_result = await db.execute(today_query)
        reviews_today = today_result.scalar()

        week_query = select(func.count()).select_from(
            base_query.where(PullRequestReviewBase.created_date >= week_ago).subquery()
        )
        week_result = await db.execute(week_query)
        reviews_this_week = week_result.scalar()

        month_query = select(func.count()).select_from(
            base_query.where(PullRequestReviewBase.created_date >= month_ago).subquery()
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
                    cache_key, settings.CACHE_TTL_STATS, json.dumps(stats.model_dump(mode="json"))
                )
            except Exception as e:
                logger.warning(f"Failed to cache review stats: {str(e)}")

        return stats

    async def get_reviews_by_reviewer(
        self, reviewer_username: str, db: AsyncSession, page: int = 1, page_size: int = 20
    ) -> tuple[list[dict[str, Any]], int]:
        """
        Get reviews by reviewer

        Args:
            reviewer_username: The reviewer username
            page: Page number (1-indexed)
            page_size: Number of items per page
            db: Database session

        Returns:
            tuple[List[dict[str, Any]], int]: List of reviews and total count
        """
        filters = ReviewFilter(reviewer=reviewer_username)
        return await self.list_reviews(filters, db, page, page_size)

    async def get_reviews_by_project(
        self, project_key: str, db: AsyncSession, page: int = 1, page_size: int = 20
    ) -> tuple[list[dict[str, Any]], int]:
        """
        Get reviews by project

        Args:
            project_key: The project key
            page: Page number (1-indexed)
            page_size: Number of items per page
            db: Database session

        Returns:
            tuple[List[dict[str, Any]], int]: List of reviews and total count
        """
        filters = ReviewFilter(project_key=project_key)
        return await self.list_reviews(filters, db, page, page_size)

    async def get_reviews_by_status(
        self,
        review_status: str,
        db: AsyncSession,
        project_key: str | None = None,
        repository_slug: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        """
        Get reviews by status

        Args:
            review_status: The status to filter by (open, merged, closed, draft)
            project_key: Optional project key to further filter
            repository_slug: Optional repository slug to further filter
            page: Page number (1-indexed)
            page_size: Number of items per page
            db: Database session

        Returns:
            tuple[List[dict[str, Any]], int]: List of reviews and total count
        """
        filters = ReviewFilter(
            pull_request_status=review_status,
            project_key=project_key,
            repository_slug=repository_slug,
        )
        return await self.list_reviews(filters, db, page, page_size)

    async def update_review_status(
        self,
        pull_request_id: str,
        new_status: str,
        db: AsyncSession,
        project_key: str | None = None,
        repository_slug: str | None = None,
    ) -> dict:
        """
        Update the status of a pull request review

        Args:
            pull_request_id: The pull request ID
            new_status: The new status (open, merged, closed, draft)
            db: Database session
            project_key: Optional project key (will be auto-detected if not provided)
            repository_slug: Optional repository slug (will be auto-detected if not provided)

        Returns:
            PullRequestReview: The updated review

        Raises:
            ReviewNotFoundException: If the review doesn't exist
            ReviewStatusException: If the status transition is invalid
        """
        # Get review - will auto-detect project_key and repository_slug if not provided
        reviews = await self.get_review(
            project_key=project_key,
            repository_slug=repository_slug,
            pull_request_id=pull_request_id,
            db=db,
        )
        if not reviews:
            raise ReviewNotFoundException(pull_request_id=pull_request_id)

        review = reviews[0]

        stmt = (
            select(PullRequestReviewBase)
            .options(selectinload(PullRequestReviewBase.assignments))
            .where(PullRequestReviewBase.pull_request_id == pull_request_id)
        )
        if project_key:
            stmt = stmt.where(PullRequestReviewBase.project_key == project_key)
        if repository_slug:
            stmt = stmt.where(PullRequestReviewBase.repository_slug == repository_slug)
        result = await db.execute(stmt.order_by(desc(PullRequestReviewBase.created_date)))
        base = result.scalars().first()
        if not base:
            raise ReviewNotFoundException(pull_request_id=pull_request_id)

        if not base.can_transition_to(new_status):
            raise ReviewStatusException(
                current_status=str(base.pull_request_status),
                target_status=new_status,
            )

        base.pull_request_status = new_status
        base.updated_date = datetime.now(UTC)
        await db.flush()
        await db.commit()

        await self._invalidate_review_cache(
            str(base.project_key), str(base.repository_slug), pull_request_id
        )
        await self._invalidate_list_cache()

        assignment = None
        if review.get("reviewer"):
            assignment = next(
                (item for item in base.assignments if item.reviewer == review["reviewer"]),
                None,
            )

        return self._serialize_review(base, assignment)

    async def enrich_review_with_entities(
        self, review: PullRequestReviewBase | dict[str, Any], db: AsyncSession
    ) -> dict[str, Any]:
        """
        Enrich a review with full entity information using relationships or direct queries

        Args:
            review: The review to enrich (ORM object or dict from cache)
            db: Database session

        Returns:
            Dict containing review data with embedded entity information, app_name, and scores
        """

        # Convert review to dict if it's an ORM object
        if hasattr(review, "to_dict"):
            review_dict = review.to_dict()
            # Try to use loaded relationships first (if ORM object)
            enriched = await self._enrich_from_relationships(review, review_dict)
        else:
            # It's already a dict (from cache), query entities directly
            review_dict = review
            enriched = await self._enrich_from_queries(review_dict, db)

        # Resolve app_name from project registry
        try:
            registry_service = ProjectRegistryService()
            project_repo_pair = (review_dict.get("project_key"), review_dict.get("repository_slug"))
            app_name_mapping = await registry_service.get_app_names_batch([project_repo_pair], db)
            enriched["app_name"] = app_name_mapping.get(project_repo_pair, "Unknown")
        except Exception as e:
            logger.warning(
                f"Failed to resolve app_name for project {review_dict.get('project_key')}: {str(e)}"
            )
            enriched["app_name"] = "Unknown"

        # Load scores for this review target
        try:
            score_service = ReviewScoreService()

            # Get scores matching the review's level (PR-level or file-level)
            # If review is PR-level (source_filename is None), get only PR-level scores
            # If review is file-level, get only scores for that specific file
            review_source_filename = review_dict.get("source_filename")

            scores = await score_service.get_scores_by_review_target(
                pull_request_id=review_dict.get("pull_request_id"),
                project_key=review_dict.get("project_key"),
                repository_slug=review_dict.get("repository_slug"),
                source_filename=review_source_filename,  # Match review's level
                db=db,
                use_cache=True,
            )

            logger.info(
                f"Loaded {len(scores)} score(s) for review {review_dict.get('pull_request_id')} "
                f"(level: {'file' if review_source_filename else 'PR'})"
            )

            # Calculate and add score summary with simplified score list
            if scores:
                avg_score = sum(s.score for s in scores) / len(scores)
                max_score = max(s.score for s in scores) if len(scores) > 1 else None

                # Build simplified score list - handle both ORM objects and dicts
                simplified_scores = []
                for score in scores:
                    # Check if it's a dict (from cache) or ORM/Pydantic model
                    if isinstance(score, dict):
                        simplified_scores.append(
                            {
                                "id": score.get("id"),
                                "reviewer": score.get("reviewer"),
                                "reviewer_info": score.get("reviewer_info"),  # Already a dict
                                "score": score.get("score"),
                                "score_description": score.get("score_description"),
                                "source_filename": score.get(
                                    "source_filename"
                                ),  # null means PR-level, string means file-level
                                "created_date": score.get("created_date"),
                                "updated_date": score.get("updated_date"),
                                "reviewer_comments": score.get("reviewer_comments"),
                            }
                        )
                    else:
                        # It's an ORM object or Pydantic model

                        # Handle reviewer_info - could be dict or model
                        reviewer_info_data = None
                        if hasattr(score, "reviewer_info") and score.reviewer_info:
                            if isinstance(score.reviewer_info, dict):
                                reviewer_info_data = score.reviewer_info  # Already a dict
                            else:
                                reviewer_info_data = score.reviewer_info.model_dump(mode="json")

                        simplified_scores.append(
                            {
                                "id": score.id,
                                "reviewer": score.reviewer,
                                "reviewer_info": reviewer_info_data,
                                "score": score.score,
                                "score_description": score.score_description,
                                "source_filename": score.source_filename,  # null means PR-level, string means file-level
                                "created_date": score.created_date,
                                "updated_date": score.updated_date,
                                "reviewer_comments": score.reviewer_comments,
                            }
                        )

                enriched["score_summary"] = {
                    "pull_request_id": review_dict.get("pull_request_id"),
                    "project_key": review_dict.get("project_key"),
                    "repository_slug": review_dict.get("repository_slug"),
                    "total_scores": len(scores),
                    "average_score": round(avg_score, 2),
                    "max_score": round(max_score, 2) if max_score is not None else None,
                    "scores": simplified_scores,
                }
            else:
                enriched["score_summary"] = None

        except Exception as e:
            logger.error(
                f"Failed to load scores for review {review_dict.get('pull_request_id')}: {str(e)}",
                exc_info=True,
            )
            # Set default empty values if score loading fails
            enriched["score_summary"] = None

        return enriched

    async def _enrich_from_relationships(
        self, review: PullRequestReviewBase, review_dict: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Enrich review using pre-loaded SQLAlchemy relationships

        Args:
            review: ORM review object with relationships loaded
            review_dict: Dictionary representation of review

        Returns:
            Enriched review dict
        """
        project = None
        repository = None
        pr_user = None
        reviewer_user = None

        try:
            # Extract project from relationship
            if hasattr(review, "project") and review.project:
                project = {
                    "id": review.project.id,
                    "project_id": review.project.project_id,
                    "project_name": review.project.project_name,
                    "project_key": review.project.project_key,
                    "project_url": review.project.project_url,
                    "created_date": review.project.created_date.isoformat()
                    if review.project.created_date
                    else None,
                    "updated_date": review.project.updated_date.isoformat()
                    if review.project.updated_date
                    else None,
                }

            # Extract repository from relationship
            if hasattr(review, "repository") and review.repository:
                repository = {
                    "id": review.repository.id,
                    "repository_id": review.repository.repository_id,
                    "repository_name": review.repository.repository_name,
                    "repository_slug": review.repository.repository_slug,
                    "repository_url": review.repository.repository_url,
                    "created_date": review.repository.created_date.isoformat()
                    if review.repository.created_date
                    else None,
                    "updated_date": review.repository.updated_date.isoformat()
                    if review.repository.updated_date
                    else None,
                }

            # Extract PR author from relationship
            if hasattr(review, "pull_request_user_rel") and review.pull_request_user_rel:
                pr_user = {
                    "id": review.pull_request_user_rel.id,
                    "user_id": review.pull_request_user_rel.user_id,
                    "username": review.pull_request_user_rel.username,
                    "display_name": review.pull_request_user_rel.display_name,
                    "email_address": review.pull_request_user_rel.email_address,
                    "active": review.pull_request_user_rel.active,
                    "is_reviewer": review.pull_request_user_rel.is_reviewer,
                    "created_date": review.pull_request_user_rel.created_date.isoformat()
                    if review.pull_request_user_rel.created_date
                    else None,
                    "updated_date": review.pull_request_user_rel.updated_date.isoformat()
                    if review.pull_request_user_rel.updated_date
                    else None,
                }

            # Extract reviewer from relationship
            if hasattr(review, "reviewer_rel") and review.reviewer_rel:
                reviewer_user = {
                    "id": review.reviewer_rel.id,
                    "user_id": review.reviewer_rel.user_id,
                    "username": review.reviewer_rel.username,
                    "display_name": review.reviewer_rel.display_name,
                    "email_address": review.reviewer_rel.email_address,
                    "active": review.reviewer_rel.active,
                    "is_reviewer": review.reviewer_rel.is_reviewer,
                    "created_date": review.reviewer_rel.created_date.isoformat()
                    if review.reviewer_rel.created_date
                    else None,
                    "updated_date": review.reviewer_rel.updated_date.isoformat()
                    if review.reviewer_rel.updated_date
                    else None,
                }

        except Exception as e:
            logger.warning(f"Failed to extract entity information from relationships: {str(e)}")

        return self._build_enriched_response(
            review_dict, project, repository, pr_user, reviewer_user
        )

    async def _enrich_from_queries(
        self, review_dict: dict[str, Any], db: AsyncSession
    ) -> dict[str, Any]:
        """
        Enrich review by directly querying entities using business keys
        Used when review is from cache (dict) without loaded relationships

        Args:
            review_dict: Review data from cache
            db: Database session

        Returns:
            Enriched review dict
        """
        from sqlalchemy import text

        project = None
        repository = None
        pr_user = None
        reviewer_user = None

        try:
            # Get project info
            project_result = await db.execute(
                text("""
                    SELECT id, project_id, project_name, project_key, project_url, created_date, updated_date 
                    FROM project 
                    WHERE project_key = :project_key
                """),
                {"project_key": review_dict.get("project_key")},
            )
            project_row = project_result.fetchone()

            if project_row:
                project = {
                    "id": project_row[0],
                    "project_id": project_row[1],
                    "project_name": project_row[2],
                    "project_key": project_row[3],
                    "project_url": project_row[4],
                    "created_date": project_row[5].isoformat() if project_row[5] else None,
                    "updated_date": project_row[6].isoformat() if project_row[6] else None,
                }

                # Get repository info
                repo_result = await db.execute(
                    text("""
                        SELECT id, repository_id, repository_name, repository_slug, repository_url, created_date, updated_date 
                        FROM repository 
                        WHERE repository_slug = :repository_slug 
                        AND project_id = :project_id
                    """),
                    {
                        "repository_slug": review_dict.get("repository_slug"),
                        "project_id": project["project_id"],
                    },
                )
                repo_row = repo_result.fetchone()

                if repo_row:
                    repository = {
                        "id": repo_row[0],
                        "repository_id": repo_row[1],
                        "repository_name": repo_row[2],
                        "repository_slug": repo_row[3],
                        "repository_url": repo_row[4],
                        "created_date": repo_row[5].isoformat() if repo_row[5] else None,
                        "updated_date": repo_row[6].isoformat() if repo_row[6] else None,
                    }

            # Get PR author info
            pr_user_result = await db.execute(
                text("""
                    SELECT id, user_id, username, display_name, email_address, active, is_reviewer, created_date, updated_date 
                    FROM user 
                    WHERE username = :username
                """),
                {"username": review_dict.get("pull_request_user")},
            )
            pr_user_row = pr_user_result.fetchone()

            if pr_user_row:
                pr_user = {
                    "id": pr_user_row[0],
                    "user_id": pr_user_row[1],
                    "username": pr_user_row[2],
                    "display_name": pr_user_row[3],
                    "email_address": pr_user_row[4],
                    "active": pr_user_row[5],
                    "is_reviewer": pr_user_row[6],
                    "created_date": pr_user_row[7].isoformat() if pr_user_row[7] else None,
                    "updated_date": pr_user_row[8].isoformat() if pr_user_row[8] else None,
                }

            # Get reviewer info
            reviewer_result = await db.execute(
                text("""
                    SELECT id, user_id, username, display_name, email_address, active, is_reviewer, created_date, updated_date 
                    FROM user 
                    WHERE username = :username
                """),
                {"username": review_dict.get("reviewer")},
            )
            reviewer_row = reviewer_result.fetchone()

            if reviewer_row:
                reviewer_user = {
                    "id": reviewer_row[0],
                    "user_id": reviewer_row[1],
                    "username": reviewer_row[2],
                    "display_name": reviewer_row[3],
                    "email_address": reviewer_row[4],
                    "active": reviewer_row[5],
                    "is_reviewer": reviewer_row[6],
                    "created_date": reviewer_row[7].isoformat() if reviewer_row[7] else None,
                    "updated_date": reviewer_row[8].isoformat() if reviewer_row[8] else None,
                }

        except Exception as e:
            logger.warning(f"Failed to load entity information from queries: {str(e)}")

        return self._build_enriched_response(
            review_dict, project, repository, pr_user, reviewer_user
        )

    @staticmethod
    def _build_enriched_response(
        review_dict: dict[str, Any],
        project: dict | None,
        repository: dict | None,
        pr_user: dict | None,
        reviewer_user: dict | None,
    ) -> dict[str, Any]:
        """
        Build the final enriched response dictionary

        Args:
            review_dict: Base review data
            project: Project entity data
            repository: Repository entity data
            pr_user: PR author user data
            reviewer_user: Reviewer user data

        Returns:
            Enriched review dict with nested entity objects
        """
        return {
            "id": review_dict["id"],
            "pull_request_id": review_dict["pull_request_id"],
            "pull_request_commit_id": review_dict["pull_request_commit_id"],
            "project_key": review_dict["project_key"],
            "repository_slug": review_dict["repository_slug"],
            "reviewer": review_dict["reviewer"],
            "pull_request_user": review_dict["pull_request_user"],
            "source_branch": review_dict["source_branch"],
            "target_branch": review_dict["target_branch"],
            "git_code_diff": review_dict.get("git_code_diff"),
            "source_filename": review_dict.get("source_filename"),
            "ai_suggestions": review_dict.get("ai_suggestions"),
            "reviewer_comments": review_dict.get("reviewer_comments"),
            "pull_request_status": review_dict["pull_request_status"],
            "metadata": review_dict.get("metadata"),
            "created_date": review_dict["created_date"],
            "updated_date": review_dict["updated_date"],
            "project": project,
            "repository": repository,
            "pull_request_user_info": pr_user,
            "reviewer_info": reviewer_user,
            "score_summary": None,
        }

    async def list_reviews_with_entities(
        self,
        filters: ReviewFilter,
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        use_cache: bool = False,
        app_names: list[str] | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """
        List pull request reviews with full entity information

        Args:
            filters: Filter criteria using business keys
            page: Page number (1-indexed)
            page_size: Number of items per page
            db: Database session
            use_cache: Whether to use cache (disabled for enriched queries)
            app_names: Optional list of app names to filter by

        Returns:
            Tuple[List[Dict], int]: List of enriched reviews and total count
        """
        # Get basic reviews from database with app_name filtering
        reviews, total = await self.list_reviews(
            filters, db, page, page_size, use_cache=False, app_names=app_names
        )

        # Collect unique project-repo pairs for batch app_name resolution
        project_repo_pairs = [
            (
                str(review["project_key"] if isinstance(review, dict) else review.project_key),
                str(
                    review["repository_slug"]
                    if isinstance(review, dict)
                    else review.repository_slug
                ),
            )
            for review in reviews
        ]

        # Batch resolve app_names
        registry_service = ProjectRegistryService()
        app_name_mapping = await registry_service.get_app_names_batch(project_repo_pairs, db)

        # Enrich each review with entity information AND app_name
        enriched_reviews = []
        for review in reviews:
            enriched = await self.enrich_review_with_entities(review, db)
            pair_key = (
                str(review["project_key"] if isinstance(review, dict) else review.project_key),
                str(
                    review["repository_slug"]
                    if isinstance(review, dict)
                    else review.repository_slug
                ),
            )
            enriched["app_name"] = app_name_mapping.get(pair_key, "Unknown")
            enriched_reviews.append(enriched)

        return enriched_reviews, total
