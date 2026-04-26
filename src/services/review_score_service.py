from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.config import settings
from src.models.pull_request import (
    PullRequestReviewAssignment,
    PullRequestReviewBase,
    PullRequestScore,
)
from src.schemas.pull_request import (
    ReviewScoreCreate,
    ReviewScoreResponse,
    ReviewScoreSummary,
)
from src.services.entity_sync_service import EntitySyncService
from src.utils.redis import get_redis_client
from src.utils.score_utils import normalize_source_filename
from src.utils.timezone import get_current_time


if TYPE_CHECKING:
    from src.models.user import User


logger = logging.getLogger(__name__)


class ReviewScoreService:
    """Service for managing pull request scores"""

    def __init__(self, metrics_collector: Any | None = None):
        self.redis_client = get_redis_client()
        from src.utils.metrics import MetricsCollector

        self.metrics = metrics_collector or MetricsCollector()

    async def upsert_score(
        self,
        score_data: ReviewScoreCreate,
        db: AsyncSession,
        review_base_id: int,
        include_details: bool = False,
    ) -> ReviewScoreResponse:
        """
        Upsert a review score

        Business logic:
        - If score exists for this reviewer + review target, UPDATE it
        - If not exists, CREATE new score
        - Auto-fill score_description if not provided
        - Support both file-level and PR-level scoring
        """

        # Normalize source filename
        source_filename = normalize_source_filename(score_data.source_filename)

        # Sync entities
        entity_sync_service = EntitySyncService(db)
        project = await entity_sync_service.sync_project(score_data.project_key)

        repository = await entity_sync_service.sync_repository(
            repository_slug=score_data.repository_slug,
            project=project,
        )

        reviewer = await entity_sync_service.sync_user(
            username=score_data.reviewer,
            is_reviewer=True,
        )

        # Check if score exists using composite key
        existing_score = await self._get_score_by_reviewer(
            db=db,
            pull_request_id=score_data.pull_request_id,
            project_key=project.project_key,
            repository_slug=repository.repository_slug,
            source_filename=source_filename,
            reviewer=score_data.reviewer,
        )

        if existing_score:
            # UPDATE existing score
            update_data = score_data.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(existing_score, field, value)

            existing_score.updated_date = get_current_time()
            await db.flush()
            score_obj = existing_score

            target = f"file '{source_filename}'" if source_filename else "PR"
            logger.info(
                f"Updated score for reviewer '{reviewer.username}' on {target}: {score_data.score}"
            )
        else:
            # CREATE new score
            from src.utils.score_utils import get_score_description

            # Auto-fill description if not provided
            final_description = get_score_description(
                score_data.score, score_data.score_description
            )

            new_score = PullRequestScore(
                pull_request_id=score_data.pull_request_id,
                pull_request_commit_id=score_data.pull_request_commit_id,
                project_key=project.project_key,
                repository_slug=repository.repository_slug,
                source_filename=source_filename,
                reviewer=reviewer.username,
                score=score_data.score,
                score_description=final_description,
                reviewer_comments=score_data.reviewer_comments,
            )
            db.add(new_score)
            await db.flush()
            score_obj = new_score

            target = f"file '{source_filename}'" if source_filename else "PR"
            logger.info(
                f"Created new score for reviewer '{reviewer.username}' on {target}: {score_data.score}"
            )

        await self._mark_assignment_completed(
            db=db,
            review_base_id=review_base_id,
            reviewer=reviewer.username,
        )
        await db.commit()
        await db.refresh(score_obj)

        # Cache invalidation
        # Invalidate both specific file cache and PR-level (all_files) cache
        await self._invalidate_score_cache(
            pull_request_id=score_data.pull_request_id,
            project_key=project.project_key,
            repository_slug=repository.repository_slug,
            source_filename=source_filename,
        )

        # Also invalidate the PR-level summary cache (all_files) to ensure UI gets fresh data
        if source_filename is not None:
            # If this was a file-level score, also invalidate the all_files cache
            await self._invalidate_score_cache(
                pull_request_id=score_data.pull_request_id,
                project_key=project.project_key,
                repository_slug=repository.repository_slug,
                source_filename=None,
            )

        # Update metrics
        self.metrics.observe_review_score(project=project.project_key, score=score_data.score)

        # Return enriched response - pass reviewer_obj to avoid lazy loading after commit
        return await self._enrich_score_response(
            score_obj, db, include_details, reviewer_obj=reviewer
        )

    async def _mark_assignment_completed(
        self,
        db: AsyncSession,
        review_base_id: int,
        reviewer: str,
    ) -> None:
        stmt = select(PullRequestReviewAssignment).where(
            PullRequestReviewAssignment.review_base_id == review_base_id,
            PullRequestReviewAssignment.reviewer == reviewer,
        )
        result = await db.execute(stmt)
        assignment = result.scalar_one_or_none()

        if not assignment or assignment.assignment_status == "completed":
            return

        assignment.assignment_status = "completed"
        assignment.updated_date = get_current_time()

        logger.info(
            "Marked assignment as completed after score submission: "
            f"review_base_id={review_base_id}, reviewer={reviewer}"
        )

    async def get_scores_by_review_target(
        self,
        pull_request_id: str,
        project_key: str,
        repository_slug: str,
        source_filename: str | None,
        db: AsyncSession,
        use_cache: bool = True,
    ) -> list[ReviewScoreResponse]:
        """
        Get all scores for a specific review target

        Args:
            pull_request_id: Pull request ID
            project_key: Project key
            repository_slug: Repository slug
            source_filename: If None, get all scores; if provided, get file-level scores for that file
            db: Database session
            use_cache: Whether to use cache
        """
        from src.utils.score_utils import normalize_source_filename

        # Normalize source filename
        source_filename = normalize_source_filename(source_filename)

        # Try cache first
        cache_key = self._get_scores_cache_key(
            pull_request_id=pull_request_id,
            project_key=project_key,
            repository_slug=repository_slug,
            source_filename=source_filename,
        )

        if use_cache:
            cached = await self.redis_client.get(cache_key)
            if cached:
                data = json.loads(cached)
                logger.info(f"Retrieved {len(data)} score(s) from cache")
                return [ReviewScoreResponse(**item) for item in data]
            else:
                logger.debug("Cache miss for scores")

        # Query database with composite key conditions
        query = (
            select(PullRequestScore)
            .where(
                PullRequestScore.pull_request_id == pull_request_id,
                PullRequestScore.project_key == project_key,
                PullRequestScore.repository_slug == repository_slug,
                PullRequestScore.active == True,  # Only return active scores
            )
            .options(
                selectinload(PullRequestScore.project),
                selectinload(PullRequestScore.repository),
                selectinload(PullRequestScore.reviewer_rel),
                selectinload(PullRequestScore.pull_request).selectinload(
                    PullRequestReviewBase.pull_request_user_rel
                ),
            )
        )

        # Handle source_filename filtering
        if source_filename is None:
            # When source_filename is not specified, don't filter by it
            # This returns both PR-level and file-level scores for the reviewer
            logger.debug("source_filename not specified - returning all scores for reviewer")
        else:
            # File-level scores only for specific filename
            query = query.where(PullRequestScore.source_filename == source_filename)

        result = await db.execute(query)
        scores = result.scalars().all()

        logger.info(
            f"Found {len(scores)} score(s) for PR={pull_request_id}, "
            f"project={project_key}, repo={repository_slug}, file={'ALL' if source_filename is None else source_filename}"
        )

        # Enrich responses
        enriched_scores = []
        for score in scores:
            enriched = await self._enrich_score_response(score, db, include_details=True)
            enriched_scores.append(enriched)

        # Cache results - use mode='json' for proper datetime serialization
        if use_cache and enriched_scores:
            try:
                cache_data = [s.model_dump(mode="json") for s in enriched_scores]
                await self.redis_client.setex(
                    cache_key,
                    settings.CACHE_TTL_REVIEWS,
                    json.dumps(cache_data),
                )
            except Exception as cache_error:
                logger.warning(f"Failed to cache scores: {cache_error}")
                # Continue without caching

        return enriched_scores

    async def get_score_by_reviewer(
        self,
        pull_request_id: str,
        project_key: str,
        repository_slug: str,
        source_filename: str | None,
        reviewer: str,
        db: AsyncSession,
    ) -> ReviewScoreResponse | None:
        """Get a specific reviewer's score for a review target"""
        source_filename = normalize_source_filename(source_filename)

        score = await self._get_score_by_reviewer(
            db=db,
            pull_request_id=pull_request_id,
            project_key=project_key,
            repository_slug=repository_slug,
            source_filename=source_filename,
            reviewer=reviewer,
        )

        if not score:
            return None

        return await self._enrich_score_response(score, db, include_details=True)

    async def get_score_summary(
        self,
        pull_request_id: str,
        project_key: str,
        repository_slug: str,
        source_filename: str | None,
        db: AsyncSession,
    ) -> ReviewScoreSummary:
        """Get summary statistics for all scores on a review target"""
        scores = await self.get_scores_by_review_target(
            pull_request_id=pull_request_id,
            project_key=project_key,
            repository_slug=repository_slug,
            source_filename=source_filename,
            db=db,
        )

        if not scores:
            return ReviewScoreSummary(
                pull_request_id=pull_request_id,
                project_key=project_key,
                repository_slug=repository_slug,
                source_filename=source_filename,
                total_scores=0,
                average_score=0.0,
                max_score=None,
                scores=[],
            )

        avg_score = sum(s.score for s in scores) / len(scores)
        max_score = max(s.score for s in scores) if len(scores) > 1 else None

        return ReviewScoreSummary(
            pull_request_id=pull_request_id,
            project_key=project_key,
            repository_slug=repository_slug,
            source_filename=source_filename,
            total_scores=len(scores),
            average_score=round(avg_score, 2),
            max_score=round(max_score, 2) if max_score is not None else None,
            scores=scores,
        )

    async def delete_score(
        self,
        pull_request_id: str,
        project_key: str,
        repository_slug: str,
        source_filename: str | None,
        reviewer: str,
        db: AsyncSession,
        current_user: str | None = None,
    ) -> bool:
        """
        Soft delete a reviewer's score (mark as inactive)

        Args:
            pull_request_id: Pull request ID
            project_key: Project key
            repository_slug: Repository slug
            source_filename: Source filename or None for PR-level
            reviewer: Reviewer username who owns the score
            db: Database session
            current_user: Current user performing deletion (defaults to reviewer)

        Returns:
            bool: True if deleted, False if not found
        """
        from src.utils.score_utils import normalize_source_filename

        source_filename = normalize_source_filename(source_filename)
        current_user = current_user or reviewer  # Default to reviewer if not provided

        score = await self._get_score_by_reviewer(
            db=db,
            pull_request_id=pull_request_id,
            project_key=project_key,
            repository_slug=repository_slug,
            source_filename=source_filename,
            reviewer=reviewer,
        )

        if not score:
            return False

        # Check if already inactive
        if not score.active:
            logger.warning(f"Score already inactive: {score.id}")
            return False

        # Soft delete: mark as inactive and record deletion info
        score.active = False
        score.deleted_by = current_user
        score.deleted_at = get_current_time()
        score.updated_date = get_current_time()

        await db.flush()
        await db.commit()
        await db.refresh(score)

        # Invalidate cache
        await self._invalidate_score_cache(
            pull_request_id=pull_request_id,
            project_key=project_key,
            repository_slug=repository_slug,
            source_filename=source_filename,
        )

        # Also invalidate PR-level cache
        await self._invalidate_score_cache(
            pull_request_id=pull_request_id,
            project_key=project_key,
            repository_slug=repository_slug,
            source_filename=None,
        )

        target = f"file '{source_filename}'" if source_filename else "PR"
        logger.info(
            f"Soft deleted score {score.id} for reviewer '{reviewer}' on {target} by '{current_user}'"
        )
        return True

    async def delete_scores_batch(
        self,
        scores_to_delete: list[dict[str, Any]],
        db: AsyncSession,
        current_user: str,
    ) -> dict[str, Any]:
        """
        Batch soft delete multiple scores

        Args:
            scores_to_delete: List of dicts with keys:
                - pull_request_id
                - project_key
                - repository_slug
                - source_filename (optional)
                - reviewer
            db: Database session
            current_user: Current user performing deletion

        Returns:
            dict: {
                "deleted": int,  # Number of successfully deleted scores
                "not_found": int,  # Number of scores not found
                "already_inactive": int,  # Number already inactive
                "errors": list[str]  # List of error messages
            }
        """
        result = {
            "deleted": 0,
            "not_found": 0,
            "already_inactive": 0,
            "errors": [],
        }

        for score_info in scores_to_delete:
            try:
                deleted = await self.delete_score(
                    pull_request_id=score_info["pull_request_id"],
                    project_key=score_info["project_key"],
                    repository_slug=score_info["repository_slug"],
                    source_filename=score_info.get("source_filename"),
                    reviewer=score_info["reviewer"],
                    db=db,
                    current_user=current_user,
                )

                if deleted:
                    result["deleted"] += 1
                else:
                    # Check why it wasn't deleted
                    score = await self._get_score_by_reviewer(
                        db=db,
                        pull_request_id=score_info["pull_request_id"],
                        project_key=score_info["project_key"],
                        repository_slug=score_info["repository_slug"],
                        source_filename=normalize_source_filename(
                            score_info.get("source_filename")
                        ),
                        reviewer=score_info["reviewer"],
                    )

                    if not score:
                        result["not_found"] += 1
                    elif not score.active:
                        result["already_inactive"] += 1

            except Exception as e:
                error_msg = (
                    f"Failed to delete score for "
                    f"{score_info.get('reviewer')} on {score_info.get('pull_request_id')}: "
                    f"{str(e)}"
                )
                logger.error(error_msg)
                result["errors"].append(error_msg)

        logger.info(
            f"Batch deletion completed: {result['deleted']} deleted, "
            f"{result['not_found']} not found, {result['already_inactive']} already inactive, "
            f"{len(result['errors'])} errors"
        )

        return result

    async def list_all_scores(
        self,
        db: AsyncSession,
        reviewer: str | None = None,
        project_key: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        """
        List all scores with pagination and optional filtering

        Args:
            db: Database session
            reviewer: Filter by reviewer username (optional)
            project_key: Filter by project key (optional)
            page: Page number (1-indexed)
            page_size: Number of items per page (max 100)

        Returns:
            dict: {
                "total": int,
                "items": list[ReviewScoreResponse],
                "page": int,
                "page_size": int
            }
        """
        from sqlalchemy import func

        # Enforce page_size limits
        page_size = min(max(page_size, 1), 100)

        # Build base query for counting (without eager loading options)
        base_query = select(PullRequestScore).where(PullRequestScore.active == True)

        # Apply filters to base query
        if reviewer:
            base_query = base_query.where(PullRequestScore.reviewer == reviewer)

        if project_key:
            base_query = base_query.where(PullRequestScore.project_key == project_key)

        # Get total count using the base query
        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # Build full query with eager loading for data retrieval
        query = (
            select(PullRequestScore)
            .where(PullRequestScore.active == True)
            .options(
                selectinload(PullRequestScore.project),
                selectinload(PullRequestScore.repository),
                selectinload(PullRequestScore.reviewer_rel),
                selectinload(PullRequestScore.pull_request).selectinload(
                    PullRequestReviewBase.pull_request_user_rel
                ),  # Load PR and its user relationship
            )
        )

        # Apply filters to full query
        if reviewer:
            query = query.where(PullRequestScore.reviewer == reviewer)

        if project_key:
            query = query.where(PullRequestScore.project_key == project_key)

        # Apply pagination
        offset = (page - 1) * page_size
        query = query.order_by(PullRequestScore.created_date.desc()).offset(offset).limit(page_size)

        # Execute query
        result = await db.execute(query)
        scores = result.scalars().all()

        logger.info(
            f"Listed {len(scores)} scores (page={page}, page_size={page_size}, total={total})"
            + (f", reviewer={reviewer}" if reviewer else "")
            + (f", project={project_key}" if project_key else "")
        )

        # Collect unique PR IDs for batch loading PR user info
        pr_keys = set()
        for score in scores:
            if score.pull_request_id and score.project_key and score.repository_slug:
                pr_keys.add((score.pull_request_id, score.project_key, score.repository_slug))

        # Batch load PRs with user relationships
        pr_map = {}
        if pr_keys:
            from sqlalchemy import and_, or_

            conditions = [
                and_(
                    PullRequestReviewBase.pull_request_id == pr_id,
                    PullRequestReviewBase.project_key == proj_key,
                    PullRequestReviewBase.repository_slug == repo_slug,
                )
                for pr_id, proj_key, repo_slug in pr_keys
            ]

            pr_query = (
                select(PullRequestReviewBase)
                .where(or_(*conditions))
                .options(selectinload(PullRequestReviewBase.pull_request_user_rel))
            )
            pr_result = await db.execute(pr_query)
            prs = pr_result.scalars().all()

            for pr in prs:
                key = (pr.pull_request_id, pr.project_key, pr.repository_slug)
                pr_map[key] = pr

        # Enrich scores with entity information
        enriched_scores = []
        for score in scores:
            try:
                # Get pre-loaded PR if available
                pr_key = (score.pull_request_id, score.project_key, score.repository_slug)
                pr_obj = pr_map.get(pr_key)

                # Temporarily attach PR to score for enrichment
                if pr_obj and not hasattr(score, "_temp_pr"):
                    score._temp_pr = pr_obj

                enriched = await self._enrich_score_response(score, db, include_details=True)
                enriched_scores.append(enriched)

                # Clean up temp attribute
                if hasattr(score, "_temp_pr"):
                    delattr(score, "_temp_pr")
            except Exception as e:
                logger.warning(f"Failed to enrich score {score.id}: {str(e)}")
                # Still include basic score data even if enrichment fails
                enriched_scores.append(ReviewScoreResponse(**score.to_dict()))

        return {
            "total": total,
            "items": enriched_scores,
            "page": page,
            "page_size": page_size,
        }

    # === Helper Methods ===

    async def _get_score_by_reviewer(
        self,
        db: AsyncSession,
        pull_request_id: str,
        project_key: str,
        repository_slug: str,
        source_filename: str | None,
        reviewer: str,
    ) -> PullRequestScore | None:
        """Get score by composite key and reviewer"""
        from sqlalchemy.orm import selectinload

        logger.debug(
            f"Querying score for reviewer='{reviewer}', PR={pull_request_id}, "
            f"project={project_key}, repo={repository_slug}, file={source_filename}"
        )

        # Build query with eager loading
        query = (
            select(PullRequestScore)
            .options(
                selectinload(PullRequestScore.project),
                selectinload(PullRequestScore.repository),
                selectinload(PullRequestScore.reviewer_rel),
                selectinload(PullRequestScore.pull_request).selectinload(
                    PullRequestReviewBase.pull_request_user_rel
                ),
            )
            .where(
                PullRequestScore.pull_request_id == pull_request_id,
                PullRequestScore.project_key == project_key,
                PullRequestScore.repository_slug == repository_slug,
                PullRequestScore.reviewer == reviewer,
                PullRequestScore.active == True,  # Only return active scores
            )
        )

        # Handle NULL source_filename correctly
        if source_filename is None:
            query = query.where(PullRequestScore.source_filename.is_(None))
        else:
            query = query.where(PullRequestScore.source_filename == source_filename)

        result = await db.execute(query)
        score = result.scalar_one_or_none()

        if score:
            logger.debug(f"Found score: id={score.id}")
        else:
            # Provide more helpful diagnostic information
            if source_filename is None:
                logger.warning(
                    f"No PR-level score found for reviewer='{reviewer}' on PR={pull_request_id}. "
                    f"Reviewer may only have file-level scores. "
                    f"Try providing 'source_filename' parameter or use GET /api/v1/reviews/scores to see all scores."
                )
            else:
                logger.warning(
                    f"No score found for reviewer='{reviewer}' on PR={pull_request_id}, file={source_filename}. "
                    f"Note: Check case sensitivity - database may have different PR ID case."
                )

        return score

    async def _enrich_score_response(
        self,
        score: PullRequestScore,
        db: AsyncSession,
        include_details: bool = False,
        reviewer_obj: User | None = None,
    ) -> ReviewScoreResponse:
        """Enrich score with entity information

        Args:
            score: The score object
            db: Database session
            include_details: Whether to include reviewer details
            reviewer_obj: Optional pre-loaded reviewer object (to avoid lazy loading after commit)
        """
        # Handle both ORM objects and dicts (from cache)
        if isinstance(score, dict):
            # Already a dict, create response directly
            return ReviewScoreResponse(**score)

        # It's an ORM object
        score_dict = {
            **score.to_dict(),
            "reviewer_info": None,
            # PR context fields
            "pull_request_id": score.pull_request_id,
            "project_key": score.project_key,
            "repository_slug": score.repository_slug,
            "pull_request_commit_id": None,
            "pull_request_user": None,
            "pull_request_user_info": None,
            "source_branch": None,
            "target_branch": None,
            "project_name": None,
            "project_url": None,
        }

        if include_details:
            # Use provided reviewer_obj if available, otherwise try to load from relationship
            reviewer = reviewer_obj
            if not reviewer and score.reviewer_rel:
                reviewer = score.reviewer_rel

            if reviewer:
                score_dict["reviewer_info"] = {
                    "username": reviewer.username,
                    "display_name": reviewer.display_name,
                    "email_address": reviewer.email_address,
                }

            # Enrich with PR context if pull_request relationship is loaded
            pr = score.pull_request
            # Also check for temporarily attached PR (from batch loading)
            if not pr and hasattr(score, "_temp_pr"):
                pr = score._temp_pr

            if pr:
                score_dict["pull_request_commit_id"] = pr.pull_request_commit_id
                score_dict["pull_request_user"] = pr.pull_request_user
                score_dict["source_branch"] = pr.source_branch
                score_dict["target_branch"] = pr.target_branch

                # Get PR author info
                if pr.pull_request_user_rel:
                    pr_user = pr.pull_request_user_rel
                    score_dict["pull_request_user_info"] = {
                        "username": pr_user.username,
                        "display_name": pr_user.display_name,
                        "email_address": pr_user.email_address,
                    }

            # Get project information
            if score.project:
                score_dict["project_name"] = score.project.project_name or score.project_key
                score_dict["project_url"] = score.project.project_url
        return ReviewScoreResponse(**score_dict)

    def _get_scores_cache_key(
        self,
        pull_request_id: str,
        project_key: str,
        repository_slug: str,
        source_filename: str | None,
    ) -> str:
        """Generate cache key for scores"""
        from src.utils.score_utils import normalize_source_filename

        source_filename = normalize_source_filename(source_filename)
        file_part = source_filename or "all_files"
        return f"scores:{project_key}:{repository_slug}:{pull_request_id}:{file_part}"

    async def _invalidate_score_cache(
        self,
        pull_request_id: str,
        project_key: str,
        repository_slug: str,
        source_filename: str | None,
    ) -> None:
        """Invalidate score cache"""
        try:
            cache_key = self._get_scores_cache_key(
                pull_request_id=pull_request_id,
                project_key=project_key,
                repository_slug=repository_slug,
                source_filename=source_filename,
            )
            logger.info(f"Invalidating score cache: {cache_key}")
            await self.redis_client.delete(cache_key)
        except Exception as e:
            logger.warning(f"Failed to invalidate score cache: {str(e)}")
