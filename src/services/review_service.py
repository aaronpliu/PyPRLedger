import json
import logging
import traceback
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, desc, exists, func, or_, select
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
    PullRequestReviewRaw,
    PullRequestScore,
    ReviewAssociation,
    UserPinnedReview,
)
from src.schemas.pull_request import (
    ReviewCreate,
    ReviewFilter,
    ReviewResponse,
    ReviewStats,
    ReviewUpdate,
)
from src.services.auto_assign_service import AutoTaskAssignmentService
from src.services.entity_sync_service import EntitySyncService
from src.services.project_registry_service import ProjectRegistryService
from src.services.review_score_service import ReviewScoreService
from src.utils.ai_review_utils import generate_ai_review_id
from src.utils.metrics import MetricsCollector, metrics
from src.utils.redis import get_redis_client
from src.utils.timezone import get_current_time, utc_to_local


logger = logging.getLogger(__name__)


class ReviewService:
    """Service for managing pull request reviews"""

    def __init__(self, metrics_collector: MetricsCollector | None = None):
        """Initialize the review service"""
        self.redis_client = get_redis_client()
        self.metrics = metrics_collector or metrics

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

    @staticmethod
    def _count_diff_lines(diff_text: str | None) -> tuple[int, int]:
        """
        Count added and deleted lines from a git diff.

        Counts lines starting with ``+`` (but not ``+++``) as additions,
        and lines starting with ``-`` (but not ``---``) as deletions.

        Args:
            diff_text: Raw git diff content, or None.

        Returns:
            Tuple of (added_lines, deleted_lines).
        """
        if not diff_text:
            return 0, 0

        added = 0
        deleted = 0
        for line in diff_text.splitlines():
            if line.startswith("+++") or line.startswith("---") or line.startswith("@@"):
                continue
            if line.startswith("+"):
                added += 1
            elif line.startswith("-"):
                deleted += 1
        return added, deleted

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

    async def _publish_sse_event(self, review_dict: dict[str, Any]) -> None:
        """
        Publish a review creation event to Redis pub/sub for SSE subscribers.

        Args:
            review_dict: Serialized review dictionary with all fields including
                         reviewer, assigned_by, pull_request_user, etc.
        """
        try:
            event_payload = {
                "event": "review_created",
                "review_id": review_dict["id"],
                "project_key": review_dict["project_key"],
                "repository_slug": review_dict["repository_slug"],
                "pull_request_id": review_dict["pull_request_id"],
                "created_date": review_dict["created_date"],
                "pull_request_user": review_dict.get("pull_request_user"),
                "pull_request_status": review_dict.get("pull_request_status"),
                "reviewer": review_dict.get("reviewer"),
                "assigned_by": review_dict.get("assigned_by"),
            }
            await self.redis_client.publish("reviews:created", json.dumps(event_payload))
            self.metrics.sse_events_published_total.labels(status="success").inc()
            logger.info(
                "SSE event published",
                extra={
                    "review_id": review_dict["id"],
                    "project_key": review_dict["project_key"],
                    "channel": "reviews:created",
                },
            )
        except Exception as e:
            self.metrics.sse_events_published_total.labels(status="failed").inc()
            logger.warning(
                "SSE event publish failed",
                extra={
                    "review_id": review_dict.get("id"),
                    "error": str(e),
                },
            )

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
                    utc_to_local(assignment.assigned_date).isoformat()
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
        visible_to_username: str | None = None,
    ) -> list[dict[str, Any]]:
        reviews: list[dict[str, Any]] = []

        for base in bases:
            assignments = list(base.assignments)

            # Determine which assignments to show based on user context
            if reviewer:
                # Admin filtering by specific reviewer
                assignments = [
                    assignment for assignment in assignments if assignment.reviewer == reviewer
                ]

            if visible_to_username:
                # Regular user view - filter to their own assignments
                visible_assignments = [
                    assignment
                    for assignment in assignments
                    if assignment.reviewer == visible_to_username
                ]

                if base.pull_request_user == visible_to_username:
                    # PR owner ALWAYS sees ONE row with all reviewer info
                    review_dict = ReviewService._serialize_review(base)
                    if assignments:
                        review_dict["all_reviewers"] = [
                            {
                                "username": a.reviewer,
                                "display_name": (
                                    a.reviewer_rel.display_name if a.reviewer_rel else a.reviewer
                                ),
                            }
                            for a in assignments
                        ]
                        review_dict["total_reviewers"] = len(assignments)
                    reviews.append(review_dict)
                elif visible_assignments:
                    # Regular reviewer sees ONE row with multi-reviewer info
                    review_dict = ReviewService._serialize_review(base, visible_assignments[0])
                    if assignments:
                        review_dict["all_reviewers"] = [
                            {
                                "username": a.reviewer,
                                "display_name": (
                                    a.reviewer_rel.display_name if a.reviewer_rel else a.reviewer
                                ),
                            }
                            for a in assignments
                        ]
                        review_dict["total_reviewers"] = len(assignments)
                    reviews.append(review_dict)
                continue

            # Admin view or general listing - ALWAYS show ONE row per PR with all reviewers
            review_dict = ReviewService._serialize_review(base)
            if assignments:
                review_dict["all_reviewers"] = [
                    {
                        "username": a.reviewer,
                        "display_name": (
                            a.reviewer_rel.display_name if a.reviewer_rel else a.reviewer
                        ),
                    }
                    for a in assignments
                ]
                review_dict["total_reviewers"] = len(assignments)
            reviews.append(review_dict)

        return reviews

    @staticmethod
    def _build_base_conditions(
        review_data: ReviewCreate,
        project_key: str,
        repository_slug: str,
    ) -> list[Any]:
        conditions = [
            PullRequestReviewBase.pull_request_id == review_data.pull_request_id,
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

        # Generate AI review ID if not already set (per PR, stable across re-reviews)
        if not base.ai_review_id:
            base.ai_review_id = generate_ai_review_id(
                project_key=review_data.project_key,
                repository_slug=review_data.repository_slug,
                pull_request_commit_id=review_data.pull_request_commit_id,
            )

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

    async def _count_open_prs(self, db: AsyncSession, project_key: str) -> int:
        """Count total distinct pull requests for a project (all PR event types)."""
        # Use subquery with DISTINCT (supports multiple columns)
        distinct_prs = (
            select(
                PullRequestReviewBase.project_key,
                PullRequestReviewBase.pull_request_id,
                PullRequestReviewBase.repository_slug,
            )
            .where(PullRequestReviewBase.project_key == project_key)
            .distinct()
            .subquery()
        )
        result = await db.execute(select(func.count()).select_from(distinct_prs))
        return result.scalar() or 0

    async def _count_pending_reviews(self, db: AsyncSession, project_key: str) -> int:
        """Count distinct PRs without any reviewer assigned (all PR event types)."""
        # Use subquery with DISTINCT for multi-column uniqueness
        distinct_prs = (
            select(
                PullRequestReviewBase.project_key,
                PullRequestReviewBase.pull_request_id,
                PullRequestReviewBase.repository_slug,
            )
            .outerjoin(
                PullRequestReviewAssignment,
                PullRequestReviewBase.id == PullRequestReviewAssignment.review_base_id,
            )
            .where(
                PullRequestReviewBase.project_key == project_key,
                PullRequestReviewAssignment.id.is_(None),
            )
            .distinct()
            .subquery()
        )
        result = await db.execute(select(func.count()).select_from(distinct_prs))
        return result.scalar() or 0

    async def _count_active_reviewers(self, db: AsyncSession, project_key: str) -> int:
        """Count distinct reviewers with active assignments for a project."""
        # Use subquery to get distinct reviewers from assignments
        distinct_reviewers = (
            select(PullRequestReviewAssignment.reviewer)
            .join(
                PullRequestReviewBase,
                PullRequestReviewAssignment.review_base_id == PullRequestReviewBase.id,
            )
            .where(PullRequestReviewBase.project_key == project_key)
            .distinct()
            .subquery()
        )
        result = await db.execute(select(func.count()).select_from(distinct_reviewers))
        return result.scalar() or 0

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
        else:
            # No explicit reviewer — run auto-assignment rules
            try:
                auto_service = AutoTaskAssignmentService(metrics_collector=self.metrics)
                await auto_service.auto_assign(
                    db=db,
                    review_base=new_base,
                    review_data=review_data,
                )
            except Exception as e:
                # Non-fatal: review is created successfully even if auto-assign fails
                logger.error(
                    f"Auto-assignment failed for PR {review_data.pull_request_id}: {e}",
                    exc_info=True,
                )

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

        # Update metrics
        self.metrics.increment_pull_request(
            project=str(project.project_key),
            status=review_data.pull_request_status or "open",
        )
        if reviewer:
            self.metrics.increment_review(
                project=str(project.project_key), reviewer=str(reviewer.username)
            )

        # Track review detail metrics
        project_key_str = str(project.project_key)
        if review_data.source_filename:
            self.metrics.increment_files_reviewed(project=project_key_str)
        added, deleted = self._count_diff_lines(review_data.git_code_diff)
        if added > 0:
            self.metrics.increment_lines_changed(project=project_key_str, change_type="added")
        if deleted > 0:
            self.metrics.increment_lines_changed(project=project_key_str, change_type="deleted")

        # Update open PR count and backlog
        try:
            project_key_str = str(project.project_key)
            open_count = await self._count_open_prs(db, project_key_str)
            self.metrics.set_pull_requests_open(open_count, project=project_key_str)
            backlog_count = await self._count_pending_reviews(db, project_key_str)
            self.metrics.set_review_backlog(backlog_count, project=project_key_str)
            active_reviewers_count = await self._count_active_reviewers(db, project_key_str)
            reviewers_load = backlog_count / max(active_reviewers_count, 1)
            self.metrics.set_reviewers_load(reviewers_load, project=project_key_str)
        except Exception as e:
            logger.warning(f"Failed to update PR metrics: {e}")

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
        # Step 1: Save raw request data immediately (always succeeds)
        raw_record = PullRequestReviewRaw(
            request_payload=review_data.model_dump(),
            status="pending",
        )
        db.add(raw_record)
        await db.flush()  # Get raw_record.id

        try:
            # Step 2: Process review (existing logic)
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
                existing_assignment = self._get_existing_assignment(
                    existing_base, reviewer.username
                )

            created = False
            if existing_base:
                self._populate_base(existing_base, review_data, pr_user.username)
                existing_base.updated_date = get_current_time()

                if reviewer:
                    if existing_assignment:
                        self._populate_assignment(
                            existing_assignment, reviewer.username, review_data
                        )
                        existing_assignment.updated_date = get_current_time()
                    else:
                        existing_assignment = PullRequestReviewAssignment(
                            review_base_id=existing_base.id,
                            reviewer=reviewer.username,
                            assignment_status="assigned",
                        )
                        self._populate_assignment(
                            existing_assignment, reviewer.username, review_data
                        )
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

                # Update metrics
                self.metrics.increment_pull_request(
                    project=str(project.project_key),
                    status=review_data.pull_request_status or "open",
                )
                if reviewer:
                    self.metrics.increment_review(
                        project=str(project.project_key), reviewer=str(reviewer.username)
                    )

                # Track review detail metrics
                up_project_key_str = str(project.project_key)
                if review_data.source_filename:
                    self.metrics.increment_files_reviewed(project=up_project_key_str)
                added, deleted = self._count_diff_lines(review_data.git_code_diff)
                if added > 0:
                    self.metrics.increment_lines_changed(
                        project=up_project_key_str, change_type="added"
                    )
                if deleted > 0:
                    self.metrics.increment_lines_changed(
                        project=up_project_key_str, change_type="deleted"
                    )

                logger.info(f"Updated review: {existing_base.pull_request_id}")

                # Publish SSE event if a new assignment was created
                if created:
                    await self._publish_sse_event(review_dict)
                    await self._invalidate_list_cache()

                # Step 3: Mark raw record as success and delete it to keep validation table clean
                # The successful review is now in pull_request_review_base
                await db.delete(raw_record)

                # Also clean up any other failed raw records for the same PR commit/file
                # This handles the case where user retries multiple times or re-posts the same PR
                # Use JSON_EXTRACT for MySQL compatibility
                cleanup_query = select(PullRequestReviewRaw).where(
                    and_(
                        PullRequestReviewRaw.status == "failed",
                        func.json_extract(PullRequestReviewRaw.request_payload, "$.pull_request_id")
                        == str(existing_base.pull_request_id),
                        func.json_extract(PullRequestReviewRaw.request_payload, "$.project_key")
                        == str(project.project_key),
                        func.json_extract(PullRequestReviewRaw.request_payload, "$.repository_slug")
                        == str(repository.repository_slug),
                    )
                )
                old_failed_records = (await db.execute(cleanup_query)).scalars().all()
                for old_record in old_failed_records:
                    await db.delete(old_record)
                    logger.info(
                        f"Cleaned up old failed raw record {old_record.id} for PR {existing_base.pull_request_id}"
                    )

                await db.commit()

                return ReviewResponse(**review_dict), created
            else:
                new_review_response = await self.create_review(review_data, db, include_details)
                logger.info(f"Created new review: {new_review_response.pull_request_id}")

                # Publish SSE event for newly created review
                new_review_dict = new_review_response.model_dump(mode="json")
                await self._publish_sse_event(new_review_dict)
                await self._invalidate_list_cache()

                # Step 3: Delete raw record and clean up old failed records for this PR
                # The successful review is now in pull_request_review_base
                await db.delete(raw_record)

                # Clean up any other failed raw records for the same PR commit/file
                # This handles re-commits and multiple retry attempts
                existing_base_after_create = await self._get_existing_base(
                    review_data,
                    db,
                    review_data.project_key,
                    review_data.repository_slug,
                )
                if existing_base_after_create:
                    cleanup_query = select(PullRequestReviewRaw).where(
                        and_(
                            PullRequestReviewRaw.status == "failed",
                            func.json_extract(
                                PullRequestReviewRaw.request_payload, "$.pull_request_id"
                            )
                            == str(existing_base_after_create.pull_request_id),
                            func.json_extract(PullRequestReviewRaw.request_payload, "$.project_key")
                            == str(review_data.project_key),
                            func.json_extract(
                                PullRequestReviewRaw.request_payload, "$.repository_slug"
                            )
                            == str(review_data.repository_slug),
                        )
                    )
                    old_failed_records = (await db.execute(cleanup_query)).scalars().all()
                    for old_record in old_failed_records:
                        await db.delete(old_record)
                        logger.info(
                            f"Cleaned up old failed raw record {old_record.id} for PR {existing_base_after_create.pull_request_id}"
                        )

                await db.commit()

                return new_review_response, True

        except Exception as e:
            # Step 4: Mark raw record as failed
            raw_record.status = "failed"
            raw_record.error_message = str(e)
            raw_record.error_details = {
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc(),
            }
            raw_record.processed_date = get_current_time()
            await db.commit()

            raise  # Re-raise to API endpoint

    async def get_review(
        self,
        project_key: str | None,
        repository_slug: str | None,
        pull_request_id: str,
        reviewer: str | None,
        source_filename: str | None,
        db: AsyncSession,
        visible_to_username: str | None = None,
        current_user_id: int | None = None,
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
            reviews = self._flatten_reviews(list(bases), reviewer, visible_to_username)

            # If current_user_id provided, fetch pinned review IDs for this user
            pinned_ids: set[int] = set()
            if current_user_id is not None:
                try:
                    pin_stmt = select(UserPinnedReview.review_id).where(
                        UserPinnedReview.user_id == current_user_id
                    )
                    pin_result = await db.execute(pin_stmt)
                    pinned_ids = {row[0] for row in pin_result.all()}
                except Exception as e:
                    logger.warning(f"Failed to fetch pinned reviews: {str(e)}")

            if reviews:
                logger.info(f"Found {len(reviews)} review(s) for PR: {pull_request_id}")

                # Batch fetch associated review IDs
                all_review_ids = [review["id"] for review in reviews]
                assoc_id_map = await self.batch_get_association_ids(all_review_ids, db)

                for review in reviews:
                    review["is_pinned_by_me"] = review["id"] in pinned_ids
                    review["associated_review_ids"] = assoc_id_map.get(review["id"], [])
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
        current_user_id: int | None = None,
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
            current_user_id: Current user ID for pinned_only filter

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
            # Check if filtering for unassigned (special value)
            if filters.reviewer == "__unassigned__":
                # Show reviews with NO assignments
                query = query.where(
                    ~exists(
                        select(1).where(
                            PullRequestReviewAssignment.review_base_id == PullRequestReviewBase.id
                        )
                    )
                )
            else:
                # Use EXISTS to avoid creating duplicate rows from JOIN
                query = query.where(
                    exists(
                        select(1).where(
                            and_(
                                PullRequestReviewAssignment.review_base_id
                                == PullRequestReviewBase.id,
                                PullRequestReviewAssignment.reviewer == filters.reviewer,
                            )
                        )
                    )
                )
        if filters.visible_to_username:
            # Don't join - just filter by base table fields
            # The _flatten_reviews method will handle assignment filtering
            query = query.where(
                or_(
                    PullRequestReviewBase.pull_request_user == filters.visible_to_username,
                    # Use EXISTS subquery to check if user is a reviewer without creating duplicates
                    exists(
                        select(1).where(
                            and_(
                                PullRequestReviewAssignment.review_base_id
                                == PullRequestReviewBase.id,
                                PullRequestReviewAssignment.reviewer == filters.visible_to_username,
                            )
                        )
                    ),
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

        # Apply search_query filter (search across multiple fields)
        if filters.search_query:
            search_term = f"%{filters.search_query.lower()}%"
            query = query.where(
                or_(
                    PullRequestReviewBase.pull_request_id.ilike(search_term),
                    # Search reviewer comments in assignments
                    exists(
                        select(1).where(
                            and_(
                                PullRequestReviewAssignment.review_base_id
                                == PullRequestReviewBase.id,
                                PullRequestReviewAssignment.reviewer_comments.ilike(search_term),
                            )
                        )
                    ),
                    # Note: reviewer, project_key, repository_slug are already in base table
                    # but we need to check assignments for reviewer search
                    exists(
                        select(1).where(
                            and_(
                                PullRequestReviewAssignment.review_base_id
                                == PullRequestReviewBase.id,
                                PullRequestReviewAssignment.reviewer.ilike(search_term),
                            )
                        )
                    ),
                )
            )

        # Apply has_scores filter (scored vs unscored)
        if filters.has_scores is not None:
            has_scores_subquery = (
                select(1)
                .where(
                    and_(
                        PullRequestScore.pull_request_id == PullRequestReviewBase.pull_request_id,
                        PullRequestScore.project_key == PullRequestReviewBase.project_key,
                        PullRequestScore.repository_slug == PullRequestReviewBase.repository_slug,
                        or_(
                            and_(
                                PullRequestScore.source_filename.is_(None),
                                PullRequestReviewBase.source_filename.is_(None),
                            ),
                            PullRequestScore.source_filename
                            == PullRequestReviewBase.source_filename,
                        ),
                    )
                )
                .correlate(PullRequestReviewBase)
                .exists()
            )

            if filters.has_scores:
                # Show only scored reviews
                query = query.where(has_scores_subquery)
            else:
                # Show only unscored reviews
                query = query.where(~has_scores_subquery)

        # Apply severity filter (check AI review issues in JSON field)
        if filters.severity:
            # Filter by AI suggestions issues with matching severity
            # ai_suggestions is a JSON column with structure: {"issues": [{"severity": "high", ...}]}
            # Use explicit func.JSON_CONTAINS for reliable MySQL JSON query
            query = query.where(
                func.JSON_CONTAINS(
                    PullRequestReviewBase.ai_suggestions,
                    json.dumps({"issues": [{"severity": filters.severity}]}),
                )
            )

        # Apply pinned_only filter — only show reviews pinned by current user
        if filters.pinned_only and current_user_id is not None:
            pinned_subquery = (
                select(UserPinnedReview.review_id)
                .where(UserPinnedReview.user_id == current_user_id)
                .scalar_subquery()
            )
            query = query.where(PullRequestReviewBase.id.in_(pinned_subquery))

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

        # Custom sorting: unscored reviews first, then scored reviews by updated_date desc
        # Use LEFT JOIN with score table to check if review has scores
        from sqlalchemy import case

        # Create a subquery to check if review has any scores
        has_scores_subquery = (
            select(1)
            .where(
                and_(
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
            )
            .correlate(PullRequestReviewBase)
            .exists()
        )

        # Order by: unscored first (0), then scored (1), within each group by updated_date desc
        query = query.order_by(
            case((has_scores_subquery, 1), else_=0),  # Unscored=0 (first), Scored=1 (second)
            desc(PullRequestReviewBase.updated_date),  # Within each group, newest first
        ).distinct()
        result = await db.execute(query)
        bases = result.scalars().unique().all()

        flattened_reviews = self._flatten_reviews(
            list(bases), filters.reviewer, filters.visible_to_username
        )
        total = len(flattened_reviews)
        if page_size == 0:
            # page_size=0 sentinel: return all matching records (no pagination slicing)
            reviews = flattened_reviews
        else:
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
        base.updated_date = get_current_time()

        if assignment and "reviewer_comments" in update_payload:
            assignment.reviewer_comments = update_payload["reviewer_comments"]
            assignment.updated_date = get_current_time()

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
        # Build query to find the base review by composite key
        query = select(PullRequestReviewBase).where(
            PullRequestReviewBase.pull_request_id == pull_request_id
        )
        if project_key:
            query = query.where(PullRequestReviewBase.project_key == project_key)
        if repository_slug:
            query = query.where(PullRequestReviewBase.repository_slug == repository_slug)

        result = await db.execute(query)
        base = result.scalar_one_or_none()

        if not base:
            return False

        resolved_project_key = str(project_key or base.project_key)
        resolved_repository_slug = str(repository_slug or base.repository_slug)

        # Soft-delete associated scores (no FK cascade to base - uses composite key)
        score_stmt = select(PullRequestScore).where(
            and_(
                PullRequestScore.pull_request_id == pull_request_id,
                PullRequestScore.project_key == resolved_project_key,
                PullRequestScore.repository_slug == resolved_repository_slug,
            )
        )
        scores = (await db.execute(score_stmt)).scalars().all()
        for score in scores:
            score.active = False
            score.deleted_by = "system"
            score.deleted_at = get_current_time()

        # Delete associated raw records (both pending and failed)
        cleanup_raw_query = select(PullRequestReviewRaw).where(
            and_(
                func.json_extract(PullRequestReviewRaw.request_payload, "$.pull_request_id")
                == pull_request_id,
                func.json_extract(PullRequestReviewRaw.request_payload, "$.project_key")
                == resolved_project_key,
                func.json_extract(PullRequestReviewRaw.request_payload, "$.repository_slug")
                == resolved_repository_slug,
            )
        )
        raw_records_to_delete = (await db.execute(cleanup_raw_query)).scalars().all()
        for raw_record in raw_records_to_delete:
            await db.delete(raw_record)
            logger.info(f"Deleted associated raw record {raw_record.id} for PR {pull_request_id}")

        # Delete the base review (cascades to assignments, pins, associations via FK)
        await db.delete(base)

        await db.commit()

        await self._invalidate_review_cache(
            resolved_project_key, resolved_repository_slug, pull_request_id
        )
        await self._invalidate_list_cache()

        logger.info(f"Deleted review: {pull_request_id}")
        return True

    async def get_review_statistics(
        self,
        project_key: str | None = None,
        db: AsyncSession = None,
        use_cache: bool = True,
        reviewer_username: str | None = None,
        app_names: list[str] | None = None,
    ) -> ReviewStats:
        """
        Get pull request review statistics

        Args:
            project_key: Optional project key to filter statistics
            db: Database session
            use_cache: Whether to use cache
            reviewer_username: Optional username to filter statistics by reviewer
            app_names: Optional list of app names to filter by (resolved via project_registry)

        Returns:
            ReviewStats: Review statistics
        """
        # Try cache first
        cache_key = f"stats:reviews:{project_key or 'all'}:{reviewer_username or 'all'}:{','.join(sorted(app_names)) if app_names else 'all'}"
        if use_cache:
            try:
                cached = await self.redis_client.get(cache_key)
                if cached:
                    logger.info(f"Retrieved review stats from cache: {cache_key}")
                    return ReviewStats(**json.loads(cached))
            except Exception as e:
                logger.warning(f"Failed to get review stats from cache: {str(e)}")

        logger.info(
            f"Calculating review statistics - project_key={project_key}, reviewer_username={reviewer_username}, app_names={app_names}"
        )

        # Resolve app_names to (project_key, repository_slug) pairs
        app_conditions = None
        score_app_conditions = None
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
                score_app_conditions = [
                    and_(
                        PullRequestScore.project_key == pk,
                        PullRequestScore.repository_slug == rs,
                    )
                    for pk, rs in project_repo_pairs
                ]
            else:
                return ReviewStats(
                    total_reviews=0,
                    open_reviews=0,
                    merged_reviews=0,
                    closed_reviews=0,
                    average_score=0.0,
                    reviews_today=0,
                    reviews_this_week=0,
                    reviews_this_month=0,
                )

        # Build base query for PullRequestReviewBase
        base_query = select(PullRequestReviewBase)
        if project_key:
            base_query = base_query.where(PullRequestReviewBase.project_key == project_key)
        if app_conditions:
            base_query = base_query.where(or_(*app_conditions))

        # Filter by reviewer if specified (assigned reviews)
        if reviewer_username:
            # Join with PullRequestReviewAssignment to filter by reviewer
            base_query = base_query.join(
                PullRequestReviewAssignment,
                PullRequestReviewBase.id == PullRequestReviewAssignment.review_base_id,
            ).where(PullRequestReviewAssignment.reviewer == reviewer_username)

        # Get total unique pull requests (distinct by pull_request_id and pull_request_commit_id)
        total_query = select(
            func.count(func.distinct(PullRequestReviewBase.pull_request_commit_id))
        )
        if project_key:
            total_query = total_query.where(PullRequestReviewBase.project_key == project_key)
        if app_conditions:
            total_query = total_query.where(or_(*app_conditions))

        # Apply reviewer filter
        if reviewer_username:
            total_query = total_query.join(
                PullRequestReviewAssignment,
                PullRequestReviewBase.id == PullRequestReviewAssignment.review_base_id,
            ).where(PullRequestReviewAssignment.reviewer == reviewer_username)

        total_result = await db.execute(total_query)
        total_reviews = total_result.scalar() or 0

        # Get reviews by status - count unique PRs per status
        status_subquery = select(
            PullRequestReviewBase.pull_request_commit_id,
            PullRequestReviewBase.pull_request_status,
        ).distinct()
        if project_key:
            status_subquery = status_subquery.where(
                PullRequestReviewBase.project_key == project_key
            )
        if app_conditions:
            status_subquery = status_subquery.where(or_(*app_conditions))

        # Apply reviewer filter
        if reviewer_username:
            status_subquery = status_subquery.join(
                PullRequestReviewAssignment,
                PullRequestReviewBase.id == PullRequestReviewAssignment.review_base_id,
            ).where(PullRequestReviewAssignment.reviewer == reviewer_username)

        status_query = select(
            status_subquery.c.pull_request_status,
            func.count(status_subquery.c.pull_request_commit_id),
        ).group_by(status_subquery.c.pull_request_status)

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
        if score_app_conditions:
            avg_score_query = avg_score_query.where(or_(*score_app_conditions))

        # Filter scores by reviewer if specified
        if reviewer_username:
            avg_score_query = avg_score_query.where(PullRequestScore.reviewer == reviewer_username)

        avg_score_result = await db.execute(avg_score_query)
        avg_score = avg_score_result.scalar() or 0.0

        # Get reviews by date - count unique PRs
        today = get_current_time().replace(hour=0, minute=0, second=0, microsecond=0)
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)

        # Reviews today (unique PRs)
        today_query = select(
            func.count(func.distinct(PullRequestReviewBase.pull_request_commit_id))
        ).where(PullRequestReviewBase.created_date >= today)
        if project_key:
            today_query = today_query.where(PullRequestReviewBase.project_key == project_key)
        if app_conditions:
            today_query = today_query.where(or_(*app_conditions))

        # Apply reviewer filter
        if reviewer_username:
            today_query = today_query.join(
                PullRequestReviewAssignment,
                PullRequestReviewBase.id == PullRequestReviewAssignment.review_base_id,
            ).where(PullRequestReviewAssignment.reviewer == reviewer_username)

        today_result = await db.execute(today_query)
        reviews_today = today_result.scalar() or 0

        # Reviews this week (unique PRs)
        week_query = select(
            func.count(func.distinct(PullRequestReviewBase.pull_request_commit_id))
        ).where(PullRequestReviewBase.created_date >= week_ago)
        if project_key:
            week_query = week_query.where(PullRequestReviewBase.project_key == project_key)
        if app_conditions:
            week_query = week_query.where(or_(*app_conditions))

        # Apply reviewer filter
        if reviewer_username:
            week_query = week_query.join(
                PullRequestReviewAssignment,
                PullRequestReviewBase.id == PullRequestReviewAssignment.review_base_id,
            ).where(PullRequestReviewAssignment.reviewer == reviewer_username)

        week_result = await db.execute(week_query)
        reviews_this_week = week_result.scalar() or 0

        # Reviews this month (unique PRs)
        month_query = select(
            func.count(func.distinct(PullRequestReviewBase.pull_request_commit_id))
        ).where(PullRequestReviewBase.created_date >= month_ago)
        if project_key:
            month_query = month_query.where(PullRequestReviewBase.project_key == project_key)
        if app_conditions:
            month_query = month_query.where(or_(*app_conditions))

        # Apply reviewer filter
        if reviewer_username:
            month_query = month_query.join(
                PullRequestReviewAssignment,
                PullRequestReviewBase.id == PullRequestReviewAssignment.review_base_id,
            ).where(PullRequestReviewAssignment.reviewer == reviewer_username)

        month_result = await db.execute(month_query)
        reviews_this_month = month_result.scalar() or 0

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

        old_status = base.pull_request_status
        base.pull_request_status = new_status
        base.updated_date = get_current_time()
        await db.flush()
        await db.commit()

        # Track merge metrics
        if new_status == "merged" and old_status != "merged":
            prj_key = str(base.project_key)
            self.metrics.set_pull_requests_merged(1, project=prj_key)
            # observe_pr_merge_time would go here if PR creation timestamp were available

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
        # Preserve multi-reviewer fields if they exist
        all_reviewers = review_dict.get("all_reviewers")
        total_reviewers = review_dict.get("total_reviewers")

        enriched = {
            "id": review_dict["id"],
            "pull_request_id": review_dict["pull_request_id"],
            "pull_request_commit_id": review_dict["pull_request_commit_id"],
            "project_key": review_dict["project_key"],
            "repository_slug": review_dict["repository_slug"],
            "reviewer": review_dict["reviewer"],
            "pull_request_user": review_dict["pull_request_user"],
            "assigned_by": review_dict.get("assigned_by"),
            "assigned_date": review_dict.get("assigned_date"),
            "assignment_status": review_dict.get("assignment_status"),
            "source_branch": review_dict["source_branch"],
            "target_branch": review_dict["target_branch"],
            "git_code_diff": review_dict.get("git_code_diff"),
            "source_filename": review_dict.get("source_filename"),
            "ai_suggestions": review_dict.get("ai_suggestions"),
            "reviewer_comments": review_dict.get("reviewer_comments"),
            "pull_request_status": review_dict["pull_request_status"],
            "metadata": review_dict.get("metadata"),
            "ai_review_id": review_dict.get("ai_review_id"),
            "created_date": review_dict["created_date"],
            "updated_date": review_dict.get("updated_date"),
            # Embedded entity information
            "project": project,
            "repository": repository,
            "pull_request_user_info": pr_user,
            "reviewer_info": reviewer_user,
        }

        # Add multi-reviewer fields if they exist
        if all_reviewers is not None:
            enriched["all_reviewers"] = all_reviewers
        if total_reviewers is not None:
            enriched["total_reviewers"] = total_reviewers

        # Preserve is_pinned_by_me if present
        if "is_pinned_by_me" in review_dict:
            enriched["is_pinned_by_me"] = review_dict["is_pinned_by_me"]

        return enriched

    async def get_review_by_id(
        self,
        review_id: int,
        db: AsyncSession,
        current_user_id: int | None = None,
    ) -> dict[str, Any] | None:
        """
        Get a single review by its primary key ID with full entity enrichment.

        Args:
            review_id: The review ID (primary key)
            db: Database session
            current_user_id: Current user ID for checking pin status

        Returns:
            Enriched review dict or None if not found
        """
        try:
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
                .where(PullRequestReviewBase.id == review_id)
            )
            result = await db.execute(query)
            base = result.scalars().first()
            if not base:
                return None

            reviews = self._flatten_reviews([base], reviewer=None, visible_to_username=None)
            if not reviews:
                return None

            review = reviews[0]

            # Check pinned status
            review["is_pinned_by_me"] = False
            if current_user_id is not None:
                try:
                    pin_stmt = select(UserPinnedReview.review_id).where(
                        UserPinnedReview.user_id == current_user_id,
                        UserPinnedReview.review_id == review_id,
                    )
                    pin_result = await db.execute(pin_stmt)
                    review["is_pinned_by_me"] = pin_result.first() is not None
                except Exception as e:
                    logger.warning(f"Failed to fetch pinned status: {str(e)}")

            # Enrich with entities
            enriched = await self.enrich_review_with_entities(review, db)

            # Get associated review IDs
            assoc_ids = await self.get_associated_review_ids(review_id, db)
            enriched["associated_review_ids"] = assoc_ids

            return enriched
        except Exception as e:
            logger.error(f"Failed to get review by id {review_id}: {str(e)}")
            return None

    async def list_reviews_with_entities(
        self,
        filters: ReviewFilter,
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        use_cache: bool = False,
        app_names: list[str] | None = None,
        current_user_id: int | None = None,
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
            current_user_id: Current user ID for checking pin status

        Returns:
            Tuple[List[Dict], int]: List of enriched reviews and total count
        """
        # Get basic reviews from database with app_name filtering
        reviews, total = await self.list_reviews(
            filters,
            db,
            page,
            page_size,
            use_cache=False,
            app_names=app_names,
            current_user_id=current_user_id,
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

        # If current_user_id provided, fetch pinned review IDs for this user
        pinned_ids: set[int] = set()
        if current_user_id is not None:
            try:
                pin_stmt = select(UserPinnedReview.review_id).where(
                    UserPinnedReview.user_id == current_user_id
                )
                pin_result = await db.execute(pin_stmt)
                pinned_ids = {row[0] for row in pin_result.all()}
            except Exception as e:
                logger.warning(f"Failed to fetch pinned reviews: {str(e)}")

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
            # Add is_pinned_by_me flag
            review_id = review["id"] if isinstance(review, dict) else review.id
            enriched["is_pinned_by_me"] = review_id in pinned_ids
            enriched_reviews.append(enriched)

        # Batch fetch associated review IDs
        all_review_ids = [
            review["id"] if isinstance(review, dict) else review.id for review in reviews
        ]
        assoc_id_map = await self.batch_get_association_ids(all_review_ids, db)
        for enriched in enriched_reviews:
            rid = enriched["id"]
            enriched["associated_review_ids"] = assoc_id_map.get(rid, [])

        return enriched_reviews, total

    async def get_associated_review_ids(self, review_id: int, db: AsyncSession) -> list[int]:
        """
        Get IDs of all reviews associated with the given review (bidirectional).

        Args:
            review_id: The review ID to find associations for
            db: Database session

        Returns:
            list[int]: List of associated review IDs
        """
        try:
            stmt = select(ReviewAssociation.associated_review_id).where(
                ReviewAssociation.review_id == review_id
            )
            result = await db.execute(stmt)
            forward_ids = {row[0] for row in result.all()}

            stmt_rev = select(ReviewAssociation.review_id).where(
                ReviewAssociation.associated_review_id == review_id
            )
            result_rev = await db.execute(stmt_rev)
            reverse_ids = {row[0] for row in result_rev.all()}

            return list(forward_ids | reverse_ids)
        except Exception as e:
            logger.warning(f"Failed to fetch associated reviews for {review_id}: {str(e)}")
            return []

    async def batch_get_association_ids(
        self, review_ids: list[int], db: AsyncSession
    ) -> dict[int, list[int]]:
        """
        Batch fetch associated review IDs for multiple reviews.

        Args:
            review_ids: List of review IDs to find associations for
            db: Database session

        Returns:
            dict[int, list[int]]: Mapping of review ID to its associated review IDs
        """
        if not review_ids:
            return {}

        result_map: dict[int, set[int]] = {rid: set() for rid in review_ids}
        try:
            # Forward direction: review_id -> associated_review_id
            stmt = select(
                ReviewAssociation.review_id, ReviewAssociation.associated_review_id
            ).where(ReviewAssociation.review_id.in_(review_ids))
            rows = await db.execute(stmt)
            for row in rows.all():
                if row[0] in result_map:
                    result_map[row[0]].add(row[1])

            # Reverse direction: associated_review_id -> review_id
            stmt_rev = select(
                ReviewAssociation.associated_review_id, ReviewAssociation.review_id
            ).where(ReviewAssociation.associated_review_id.in_(review_ids))
            rows_rev = await db.execute(stmt_rev)
            for row in rows_rev.all():
                if row[0] in result_map:
                    result_map[row[0]].add(row[1])

        except Exception as e:
            logger.warning(f"Failed to batch fetch associated review IDs: {str(e)}")

        return {rid: sorted(ids) for rid, ids in result_map.items()}

    async def associate_reviews(
        self,
        review_id: int,
        target_review_id: int,
        created_by: int,
        db: AsyncSession,
    ) -> bool:
        """
        Associate two reviews together (bidirectional).
        Skips if already associated (idempotent).

        Args:
            review_id: The source review ID
            target_review_id: The target review ID to associate with
            created_by: The user ID creating the association
            db: Database session

        Returns:
            bool: True if new association created, False if already existed
        """
        if review_id == target_review_id:
            return False

        # Ensure consistent ordering to avoid (A,B) vs (B,A) duplicates
        first_id = min(review_id, target_review_id)
        second_id = max(review_id, target_review_id)

        try:
            stmt = select(ReviewAssociation).where(
                ReviewAssociation.review_id == first_id,
                ReviewAssociation.associated_review_id == second_id,
            )
            result = await db.execute(stmt)
            if result.scalar_one_or_none():
                return False

            assoc = ReviewAssociation(
                review_id=first_id,
                associated_review_id=second_id,
                created_by=created_by,
            )
            db.add(assoc)
            await db.flush()
            return True
        except Exception as e:
            logger.warning(
                f"Failed to associate reviews {review_id} <-> {target_review_id}: {str(e)}"
            )
            return False

    async def disassociate_reviews(
        self,
        review_id: int,
        target_review_id: int,
        db: AsyncSession,
    ) -> bool:
        """
        Remove association between two reviews.

        Args:
            review_id: One review ID
            target_review_id: The other review ID
            db: Database session

        Returns:
            bool: True if association was removed, False if not found
        """
        first_id = min(review_id, target_review_id)
        second_id = max(review_id, target_review_id)

        try:
            stmt = select(ReviewAssociation).where(
                ReviewAssociation.review_id == first_id,
                ReviewAssociation.associated_review_id == second_id,
            )
            result = await db.execute(stmt)
            assoc = result.scalar_one_or_none()
            if not assoc:
                return False

            await db.delete(assoc)
            await db.flush()
            return True
        except Exception as e:
            logger.warning(
                f"Failed to disassociate reviews {review_id} <-> {target_review_id}: {str(e)}"
            )
            return False
