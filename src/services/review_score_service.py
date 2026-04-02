import json
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.config import settings
from src.models.pull_request import PullRequestScore
from src.schemas.pull_request import (
    ReviewScoreCreate,
    ReviewScoreResponse,
    ReviewScoreSummary,
)
from src.services.entity_sync_service import EntitySyncService
from src.utils.redis import get_redis_client
from src.utils.score_utils import normalize_source_filename


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

            existing_score.updated_date = datetime.now(UTC)
            await db.flush()
            await db.refresh(existing_score)
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
            await db.refresh(new_score)
            score_obj = new_score

            target = f"file '{source_filename}'" if source_filename else "PR"
            logger.info(
                f"Created new score for reviewer '{reviewer.username}' on {target}: {score_data.score}"
            )

        # Commit transaction
        await db.commit()

        # Cache invalidation
        await self._invalidate_score_cache(
            pull_request_id=score_data.pull_request_id,
            project_key=project.project_key,
            repository_slug=repository.repository_slug,
            source_filename=source_filename,
        )

        # Update metrics
        self.metrics.increment_score(project=project.project_key, reviewer=reviewer.username)

        # Return enriched response
        return await self._enrich_score_response(score_obj, db, include_details)

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
            source_filename: If None, get PR-level scores; if provided, get file-level scores
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
                return [ReviewScoreResponse(**item) for item in data]

        # Query database with composite key conditions
        query = (
            select(PullRequestScore)
            .where(
                PullRequestScore.pull_request_id == pull_request_id,
                PullRequestScore.project_key == project_key,
                PullRequestScore.repository_slug == repository_slug,
            )
            .options(
                selectinload(PullRequestScore.project),
                selectinload(PullRequestScore.repository),
                selectinload(PullRequestScore.reviewer_rel),
            )
        )

        # Handle NULL source_filename correctly
        if source_filename is None:
            query = query.where(PullRequestScore.source_filename.is_(None))
        else:
            query = query.where(PullRequestScore.source_filename == source_filename)

        result = await db.execute(query)
        scores = result.scalars().all()

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
                scores=[],
            )

        avg_score = sum(s.score for s in scores) / len(scores)

        return ReviewScoreSummary(
            pull_request_id=pull_request_id,
            project_key=project_key,
            repository_slug=repository_slug,
            source_filename=source_filename,
            total_scores=len(scores),
            average_score=round(avg_score, 2),
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
    ) -> bool:
        """Delete a reviewer's score"""
        from src.utils.score_utils import normalize_source_filename

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
            return False

        await db.delete(score)
        await self._invalidate_score_cache(
            pull_request_id=pull_request_id,
            project_key=project_key,
            repository_slug=repository_slug,
            source_filename=source_filename,
        )

        target = f"file '{source_filename}'" if source_filename else "PR"
        logger.info(f"Deleted score for reviewer '{reviewer}' on {target}")
        return True

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
        query = select(PullRequestScore).where(
            PullRequestScore.pull_request_id == pull_request_id,
            PullRequestScore.project_key == project_key,
            PullRequestScore.repository_slug == repository_slug,
            PullRequestScore.reviewer == reviewer,
        )

        # Handle NULL source_filename correctly
        if source_filename is None:
            query = query.where(PullRequestScore.source_filename.is_(None))
        else:
            query = query.where(PullRequestScore.source_filename == source_filename)

        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def _enrich_score_response(
        self,
        score: PullRequestScore,
        db: AsyncSession,
        include_details: bool = False,
    ) -> ReviewScoreResponse:
        """Enrich score with entity information"""
        # Handle both ORM objects and dicts (from cache)
        if isinstance(score, dict):
            # Already a dict, create response directly
            return ReviewScoreResponse(**score)

        # It's an ORM object
        score_dict = {
            **score.to_dict(),
            "reviewer_info": None,
        }

        if include_details and score.reviewer_rel:
            score_dict["reviewer_info"] = {
                "username": score.reviewer_rel.username,
                "display_name": score.reviewer_rel.display_name,
                "email_address": score.reviewer_rel.email_address,
            }

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
        file_part = source_filename or "pr_level"
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
            await self.redis_client.delete(cache_key)
        except Exception as e:
            logger.warning(f"Failed to invalidate score cache: {str(e)}")
