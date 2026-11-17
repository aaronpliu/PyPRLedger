"""Repository-scoped insights.

The personal dashboard reads one user's activity through four trend endpoints,
each hard-coded to the caller. This service answers the other question - "how is
this repository (or project) doing?" - in a single reading, so a page can draw
its cards and charts from one query set and one cache entry instead of stitching
several round trips together.
"""

from __future__ import annotations

import json
import logging
from datetime import timedelta
from typing import Any

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.repository_access import (
    RepositoryPair,
    access_scope,
    repository_pair_condition,
)
from src.models.pull_request import (
    PullRequestReviewAssignment,
    PullRequestReviewBase,
    PullRequestScore,
)
from src.schemas.insights import (
    InsightsBreakdown,
    InsightsCount,
    InsightsKpis,
    InsightsRecentReview,
    InsightsReviewerStat,
    InsightsScope,
    InsightsTrendPoint,
    RepositoryInsights,
)
from src.utils.redis import get_redis_client
from src.utils.timezone import get_current_time


logger = logging.getLogger(__name__)

# The reading is meant to feel live: a page polls it, and a minute-old answer is
# close enough to the database to be worth saving the aggregation queries.
INSIGHTS_CACHE_TTL_SECONDS = 60


async def invalidate_insights_cache(
    redis_client,
    project_key: str | None,
    repository_slug: str | None = None,
) -> None:
    """Drop the cached readings a write to this repository made stale.

    The stream event tells watching pages to refetch; without this the refetch
    would be served the very entry the write had just made stale, and the page
    would faithfully re-display yesterday's numbers. A write can land in the
    single-repository reading or the project-wide one (whose cache key says
    ``*`` for the repository), so one pattern clears both. Best effort by
    design: a cache that refuses to clear costs at most one TTL of staleness,
    never the write itself.
    """
    if not project_key:
        return
    try:
        stale_keys = await redis_client.keys(f"insights:repo:{project_key}:*")
        if stale_keys:
            await redis_client.delete(*stale_keys)
    except Exception as exc:
        logger.warning("Failed to invalidate insights cache: %s", exc)

# How many rows each distribution keeps. A dashboard reads the shape of the
# numbers, not the long tail.
TOP_REVIEWERS = 10
RECENT_LIMIT = 10

_PERIOD_FORMATS = {
    "daily": {"sqlite": "%Y-%m-%d", "mysql": "%Y-%m-%d", "postgresql": "YYYY-MM-DD"},
    "weekly": {"sqlite": "%Y-W%W", "mysql": "%Y-W%u", "postgresql": "IYYY-IW"},
    "monthly": {"sqlite": "%Y-%m", "mysql": "%Y-%m", "postgresql": "YYYY-MM"},
}


def _period_expr(column, period: str, dialect: str):
    """Bucket a timestamp column the way the database can.

    The production database is MySQL, the tests run on SQLite and a deployment
    may run PostgreSQL, so the same bucket label is built per dialect rather than
    assuming one function name.
    """
    formats = _PERIOD_FORMATS[period]
    if dialect in ("mysql", "mariadb"):
        return func.date_format(column, formats["mysql"])
    if dialect == "sqlite":
        return func.strftime(formats["sqlite"], column)
    return func.to_char(column, formats["postgresql"])


class InsightsService:
    """Reads one repository or project into a single dashboard payload."""

    def __init__(self, allowed_pairs: set[RepositoryPair] | None = None):
        self.redis_client = get_redis_client()
        self._allowed_pairs = allowed_pairs

    @staticmethod
    def _empty(scope: InsightsScope) -> RepositoryInsights:
        return RepositoryInsights(
            scope=scope,
            kpis=InsightsKpis(),
            trends=[],
            breakdown=InsightsBreakdown(by_status=[], by_reviewer=[], by_project=[]),
            recent=[],
        )

    def _scoped_pairs(
        self, project_key: str | None, repository_slug: str | None
    ) -> set[RepositoryPair] | None:
        """Narrow the caller's grants to the requested scope.

        ``None`` keeps the unrestricted reading internal callers get; an empty set
        means the caller asked for something they hold nothing for.
        """
        if self._allowed_pairs is None:
            return None
        pairs = self._allowed_pairs
        if project_key:
            pairs = {(pk, rs) for pk, rs in pairs if pk == project_key}
        if repository_slug:
            pairs = {(pk, rs) for pk, rs in pairs if rs == repository_slug}
        return pairs

    @staticmethod
    def _scope_conditions(model, pairs: set[RepositoryPair] | None, project_key: str | None):
        """Conditions that limit a query to the requested scope."""
        conditions: list[Any] = []
        pair_condition = repository_pair_condition(
            model.project_key, model.repository_slug, pairs
        )
        if pair_condition is not None:
            conditions.append(pair_condition)
        if project_key:
            conditions.append(model.project_key == project_key)
        return conditions

    async def get_repository_insights(
        self,
        db: AsyncSession,
        project_key: str | None = None,
        repository_slug: str | None = None,
        days: int = 30,
        period: str = "weekly",
        use_cache: bool = True,
    ) -> RepositoryInsights:
        """Read the scope into KPIs, trends, distributions and recent activity."""
        now = get_current_time()
        scope = InsightsScope(
            project_key=project_key,
            repository_slug=repository_slug,
            days=days,
            period=period,
            generated_at=now,
        )

        pairs = self._scoped_pairs(project_key, repository_slug)
        if pairs is not None and not pairs:
            # Nothing granted in this scope: answer with an empty reading rather
            # than an unrestricted query.
            return self._empty(scope)

        cache_key = (
            f"insights:repo:{project_key or '*'}:{repository_slug or '*'}:"
            f"{days}:{period}:{access_scope(pairs)}"
        )
        if use_cache:
            try:
                cached = await self.redis_client.get(cache_key)
                if cached:
                    return RepositoryInsights(**json.loads(cached))
            except Exception as exc:  # a cache miss must never fail the reading
                logger.warning("Failed to read insights from cache: %s", exc)

        reading = await self._read(db, scope, pairs)
        try:
            await self.redis_client.set(
                cache_key,
                json.dumps(reading.model_dump(mode="json")),
                ex=INSIGHTS_CACHE_TTL_SECONDS,
            )
        except Exception as exc:
            logger.warning("Failed to cache insights: %s", exc)
        return reading

    async def _read(
        self, db: AsyncSession, scope: InsightsScope, pairs: set[RepositoryPair] | None
    ) -> RepositoryInsights:
        start_date = get_current_time() - timedelta(days=scope.days)
        end_date = get_current_time()

        base_conditions = self._scope_conditions(
            PullRequestReviewBase, pairs, scope.project_key
        )
        base_conditions.append(PullRequestReviewBase.created_date >= start_date)
        base_conditions.append(PullRequestReviewBase.created_date <= end_date)

        score_conditions = self._scope_conditions(PullRequestScore, pairs, scope.project_key)
        score_conditions.append(PullRequestScore.active.is_(True))
        score_conditions.append(PullRequestScore.created_date >= start_date)
        score_conditions.append(PullRequestScore.created_date <= end_date)

        dialect = db.get_bind().dialect.name
        today = get_current_time().replace(hour=0, minute=0, second=0, microsecond=0)

        status_counts = await self._status_counts(db, base_conditions)
        reviews_total = sum(status_counts.values())
        avg_score, high_scores, score_total = await self._score_totals(db, score_conditions)
        reviews_today = await self._count_reviews(db, [*base_conditions, PullRequestReviewBase.created_date >= today])
        assignment_kpis = await self._assignment_kpis(db, base_conditions)
        trends = await self._trends(db, base_conditions, score_conditions, scope.period, dialect)
        reviewer_stats = await self._reviewer_stats(db, base_conditions)
        project_counts = (
            []
            if scope.repository_slug
            else await self._project_counts(db, base_conditions)
        )
        recent = await self._recent(db, base_conditions, score_conditions)

        kpis = InsightsKpis(
            reviews_total=reviews_total,
            reviews_open=status_counts.get("open", 0),
            reviews_today=reviews_today,
            avg_score=round(avg_score, 2),
            good_suggestion_rate=(
                round(high_scores / score_total, 4) if score_total else 0.0
            ),
            assigned_pending=assignment_kpis["assigned"],
            assigned_in_progress=assignment_kpis["in_progress"],
            unassigned_count=assignment_kpis["unassigned"],
            active_reviewers=assignment_kpis["reviewers"],
        )

        return RepositoryInsights(
            scope=scope,
            kpis=kpis,
            trends=trends,
            breakdown=InsightsBreakdown(
                by_status=[
                    InsightsCount(key=status, count=count)
                    for status, count in sorted(status_counts.items())
                ],
                by_reviewer=reviewer_stats,
                by_project=[
                    InsightsCount(key=project_key, count=count)
                    for project_key, count in project_counts
                ],
            ),
            recent=recent,
        )

    async def _status_counts(self, db: AsyncSession, conditions: list[Any]) -> dict[str, int]:
        """Reviews per PR status, counted once per PR commit as the statistics do."""
        query = (
            select(
                PullRequestReviewBase.pull_request_status,
                func.count(func.distinct(PullRequestReviewBase.pull_request_commit_id)),
            )
            .where(*conditions)
            .group_by(PullRequestReviewBase.pull_request_status)
        )
        result = await db.execute(query)
        return {row[0]: int(row[1]) for row in result if row[0]}

    async def _count_reviews(self, db: AsyncSession, conditions: list[Any]) -> int:
        query = select(
            func.count(func.distinct(PullRequestReviewBase.pull_request_commit_id))
        ).where(*conditions)
        result = await db.execute(query)
        return int(result.scalar() or 0)

    async def _score_totals(
        self, db: AsyncSession, conditions: list[Any]
    ) -> tuple[float, int, int]:
        """Average score, the number of high scores, and how many scores there are."""
        high = func.sum(case((PullRequestScore.score >= 8.0, 1), else_=0))
        query = select(func.avg(PullRequestScore.score), high, func.count(PullRequestScore.id)).where(
            *conditions
        )
        result = await db.execute(query)
        row = result.one()
        return float(row[0] or 0.0), int(row[1] or 0), int(row[2] or 0)

    async def _assignment_kpis(
        self, db: AsyncSession, base_conditions: list[Any]
    ) -> dict[str, int]:
        """Where the review work stands, and how much of it nobody holds yet."""
        status_query = (
            select(
                PullRequestReviewAssignment.assignment_status,
                func.count(func.distinct(PullRequestReviewAssignment.review_base_id)),
                func.count(func.distinct(PullRequestReviewAssignment.reviewer)),
            )
            .join(
                PullRequestReviewBase,
                PullRequestReviewBase.id == PullRequestReviewAssignment.review_base_id,
            )
            .where(*base_conditions)
            .group_by(PullRequestReviewAssignment.assignment_status)
        )
        result = await db.execute(status_query)

        by_status: dict[str, int] = {}
        for status, count, _ in result:
            by_status[status] = int(count)

        reviewer_query = (
            select(func.count(func.distinct(PullRequestReviewAssignment.reviewer)))
            .join(
                PullRequestReviewBase,
                PullRequestReviewBase.id == PullRequestReviewAssignment.review_base_id,
            )
            .where(*base_conditions)
        )
        reviewer_result = await db.execute(reviewer_query)
        active_reviewers = int(reviewer_result.scalar() or 0)

        bases_total = await self._count_bases(db, base_conditions)
        assigned_bases_query = (
            select(func.count(func.distinct(PullRequestReviewAssignment.review_base_id)))
            .join(
                PullRequestReviewBase,
                PullRequestReviewBase.id == PullRequestReviewAssignment.review_base_id,
            )
            .where(*base_conditions)
        )
        assigned_bases = int((await db.execute(assigned_bases_query)).scalar() or 0)

        return {
            "assigned": by_status.get("assigned", 0),
            "in_progress": by_status.get("in_progress", 0),
            "completed": by_status.get("completed", 0),
            "reviewers": active_reviewers,
            "unassigned": max(bases_total - assigned_bases, 0),
        }

    async def _count_bases(self, db: AsyncSession, conditions: list[Any]) -> int:
        query = select(func.count(func.distinct(PullRequestReviewBase.id))).where(*conditions)
        result = await db.execute(query)
        return int(result.scalar() or 0)

    async def _reviewer_stats(
        self, db: AsyncSession, base_conditions: list[Any]
    ) -> list[InsightsReviewerStat]:
        """Who carries the review work, most loaded first."""
        completed = func.sum(
            case((PullRequestReviewAssignment.assignment_status == "completed", 1), else_=0)
        )
        query = (
            select(
                PullRequestReviewAssignment.reviewer,
                func.count(func.distinct(PullRequestReviewAssignment.review_base_id)),
                completed,
            )
            .join(
                PullRequestReviewBase,
                PullRequestReviewBase.id == PullRequestReviewAssignment.review_base_id,
            )
            .where(*base_conditions, PullRequestReviewAssignment.reviewer.is_not(None))
            .group_by(PullRequestReviewAssignment.reviewer)
            .order_by(func.count(func.distinct(PullRequestReviewAssignment.review_base_id)).desc())
            .limit(TOP_REVIEWERS)
        )
        result = await db.execute(query)
        return [
            InsightsReviewerStat(reviewer=row[0], assigned=int(row[1] or 0), completed=int(row[2] or 0))
            for row in result
            if row[0]
        ]

    async def _project_counts(
        self, db: AsyncSession, base_conditions: list[Any]
    ) -> list[tuple[str, int]]:
        """The projects the reading covers, when no single repository was picked."""
        query = (
            select(
                PullRequestReviewBase.project_key,
                func.count(func.distinct(PullRequestReviewBase.pull_request_commit_id)),
            )
            .where(*base_conditions)
            .group_by(PullRequestReviewBase.project_key)
            .order_by(func.count(func.distinct(PullRequestReviewBase.pull_request_commit_id)).desc())
            .limit(TOP_REVIEWERS)
        )
        result = await db.execute(query)
        return [(row[0], int(row[1])) for row in result if row[0]]

    async def _trends(
        self,
        db: AsyncSession,
        base_conditions: list[Any],
        score_conditions: list[Any],
        period: str,
        dialect: str,
    ) -> list[InsightsTrendPoint]:
        """Reviews, score and assignment per bucket, merged on the bucket label."""
        review_bucket = _period_expr(PullRequestReviewBase.created_date, period, dialect).label(
            "bucket"
        )
        review_query = (
            select(
                review_bucket,
                func.count(func.distinct(PullRequestReviewBase.pull_request_commit_id)),
            )
            .where(*base_conditions)
            .group_by("bucket")
            .order_by("bucket")
        )
        review_rows = {
            row[0]: int(row[1]) for row in await db.execute(review_query) if row[0] is not None
        }

        score_bucket = _period_expr(PullRequestScore.created_date, period, dialect).label("bucket")
        score_query = (
            select(
                score_bucket,
                func.avg(PullRequestScore.score),
                func.sum(case((PullRequestScore.score >= 8.0, 1), else_=0)),
            )
            .where(*score_conditions)
            .group_by("bucket")
            .order_by("bucket")
        )
        score_rows = {
            row[0]: (float(row[1] or 0.0), int(row[2] or 0))
            for row in await db.execute(score_query)
            if row[0] is not None
        }

        assignment_bucket = _period_expr(
            PullRequestReviewAssignment.created_date, period, dialect
        ).label("bucket")
        completed = func.sum(
            case((PullRequestReviewAssignment.assignment_status == "completed", 1), else_=0)
        )
        assignment_query = (
            select(
                assignment_bucket,
                func.count(func.distinct(PullRequestReviewAssignment.review_base_id)),
                completed,
            )
            .join(
                PullRequestReviewBase,
                PullRequestReviewBase.id == PullRequestReviewAssignment.review_base_id,
            )
            .where(*base_conditions)
            .group_by("bucket")
            .order_by("bucket")
        )
        assignment_rows = {
            row[0]: (int(row[1] or 0), int(row[2] or 0))
            for row in await db.execute(assignment_query)
            if row[0] is not None
        }

        buckets = sorted(set(review_rows) | set(score_rows) | set(assignment_rows))
        points: list[InsightsTrendPoint] = []
        for bucket in buckets:
            avg, high = score_rows.get(bucket, (0.0, 0))
            assigned, done = assignment_rows.get(bucket, (0, 0))
            points.append(
                InsightsTrendPoint(
                    period_start=str(bucket),
                    reviews=review_rows.get(bucket, 0),
                    avg_score=round(avg, 2),
                    high_scores=high,
                    assigned=assigned,
                    completed=done,
                )
            )
        return points

    async def _recent(
        self, db: AsyncSession, base_conditions: list[Any], score_conditions: list[Any]
    ) -> list[InsightsRecentReview]:
        """The last few reviews, with the score each one carries."""
        query = (
            select(
                PullRequestReviewBase.project_key,
                PullRequestReviewBase.repository_slug,
                PullRequestReviewBase.pull_request_id,
                PullRequestReviewBase.pull_request_commit_id,
                PullRequestReviewBase.pull_request_status,
                func.max(PullRequestReviewBase.created_date).label("latest"),
            )
            .where(*base_conditions)
            .group_by(
                PullRequestReviewBase.project_key,
                PullRequestReviewBase.repository_slug,
                PullRequestReviewBase.pull_request_id,
                PullRequestReviewBase.pull_request_commit_id,
                PullRequestReviewBase.pull_request_status,
            )
            .order_by(func.max(PullRequestReviewBase.created_date).desc())
            .limit(RECENT_LIMIT)
        )
        rows = list(await db.execute(query))
        if not rows:
            return []

        # The score each of those PRs carries, read in one grouped query rather
        # than one query per row.
        pair_conditions = [
            and_(
                PullRequestScore.project_key == row.project_key,
                PullRequestScore.repository_slug == row.repository_slug,
                PullRequestScore.pull_request_id == row.pull_request_id,
            )
            for row in rows
        ]
        score_query = (
            select(
                PullRequestScore.project_key,
                PullRequestScore.repository_slug,
                PullRequestScore.pull_request_id,
                func.avg(PullRequestScore.score),
            )
            .where(*score_conditions, or_(*pair_conditions))
            .group_by(
                PullRequestScore.project_key,
                PullRequestScore.repository_slug,
                PullRequestScore.pull_request_id,
            )
        )
        scores = {
            (row[0], row[1], row[2]): round(float(row[3] or 0.0), 2)
            for row in await db.execute(score_query)
        }

        return [
            InsightsRecentReview(
                project_key=row.project_key,
                repository_slug=row.repository_slug,
                pull_request_id=row.pull_request_id,
                pull_request_commit_id=row.pull_request_commit_id,
                status=row.pull_request_status,
                avg_score=scores.get(
                    (row.project_key, row.repository_slug, row.pull_request_id), 0.0
                ),
                created_date=row.latest,
            )
            for row in rows
        ]
