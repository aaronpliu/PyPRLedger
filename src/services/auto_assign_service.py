"""Auto-assignment service for pull request reviews

Evaluates configured rules against incoming reviews and automatically
assigns reviewers when conditions match.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.auto_assign_rule import PullRequestReviewAutoAssignmentRule
from src.models.pull_request import (
    PullRequestReviewAssignment,
    PullRequestReviewBase,
)
from src.models.user import User
from src.schemas.notification import NotificationCreate
from src.schemas.pull_request import ReviewCreate
from src.services.notification_service import NotificationService
from src.utils.metrics import MetricsCollector
from src.utils.timezone import get_current_time


if TYPE_CHECKING:
    pass


logger = logging.getLogger(__name__)


class AutoTaskAssignmentService:
    """Service for evaluating auto-assignment rules and creating assignments"""

    def __init__(self, metrics_collector: MetricsCollector | None = None):
        self.metrics = metrics_collector or MetricsCollector()
        self._notification_service: NotificationService | None = None

    @property
    def notification_service(self) -> NotificationService:
        """Lazy initialization of notification service"""
        if self._notification_service is None:
            try:
                from src.utils.redis import get_redis_client, init_redis

                try:
                    get_redis_client()
                except RuntimeError:
                    logger.info("Initializing Redis for notifications")
                    init_redis()

                self._notification_service = NotificationService()
            except Exception as e:
                logger.warning(f"Redis not available, notifications will work without caching: {e}")
                self._notification_service = NotificationService.__new__(NotificationService)
                self._notification_service.metrics = self.metrics

                class MockRedis:
                    async def get(self, key):
                        return None

                    async def setex(self, key, ttl, value):
                        pass

                    async def delete(self, key):
                        pass

                    async def incr(self, key):
                        pass

                    async def expireat(self, key, timestamp):
                        pass

                self._notification_service.redis_client = MockRedis()
        return self._notification_service

    async def get_active_rules(self, db: AsyncSession) -> list[PullRequestReviewAutoAssignmentRule]:
        """Get all active, non-expired rules ordered by priority (ascending)

        Args:
            db: Database session

        Returns:
            List of active rules sorted by priority (lower = evaluated first)
        """
        now = get_current_time()
        stmt = (
            select(PullRequestReviewAutoAssignmentRule)
            .where(
                PullRequestReviewAutoAssignmentRule.is_active == True,
                or_(
                    PullRequestReviewAutoAssignmentRule.starts_at.is_(None),
                    PullRequestReviewAutoAssignmentRule.starts_at <= now,
                ),
                or_(
                    PullRequestReviewAutoAssignmentRule.expires_at.is_(None),
                    PullRequestReviewAutoAssignmentRule.expires_at > now,
                ),
            )
            .order_by(PullRequestReviewAutoAssignmentRule.priority)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    def rule_matches(
        self,
        rule: PullRequestReviewAutoAssignmentRule,
        review_data: ReviewCreate,
    ) -> bool:
        """Check if a rule's conditions match the review data

        Conditions are ANDed across keys. List values are ORed (any match).
        Missing condition keys act as wildcards (no filter on that dimension).

        Args:
            rule: The rule to evaluate
            review_data: The incoming review data

        Returns:
            True if the rule matches, False otherwise
        """
        conditions = rule.conditions
        if not conditions:
            return False  # Empty conditions match nothing

        # Build review data map for matching
        review = {
            "project_key": review_data.project_key,
            "repository_slug": review_data.repository_slug,
            "pull_request_user": review_data.pull_request_user,
            "source_branch": review_data.source_branch,
            "target_branch": review_data.target_branch,
            "pull_request_status": review_data.pull_request_status,
        }

        for key, value in conditions.items():
            if key.endswith("_prefix"):
                # Prefix match — value is a single string prefix
                field = key.replace("_prefix", "")
                actual = review.get(field, "")
                if not actual or not actual.startswith(value):
                    return False
            elif key == "pull_request_status":
                # Status exact match against list
                if review.get(key) not in value:
                    return False
            elif isinstance(value, list):
                # Exact match against list of acceptable values
                actual = review.get(key)
                if actual is None or actual not in value:
                    return False
            else:
                # Unexpected condition format — log and treat as no match
                logger.warning(f"Unexpected condition format: key={key}, value={type(value)}")
                return False

        return True

    async def _ensure_reviewer_exists(self, db: AsyncSession, username: str) -> bool:
        """Verify that a reviewer username exists in the User table

        Args:
            db: Database session
            username: Git username to verify

        Returns:
            True if user exists, False otherwise
        """
        result = await db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none() is not None

    async def auto_assign(
        self,
        db: AsyncSession,
        review_base: PullRequestReviewBase,
        review_data: ReviewCreate,
    ) -> list[PullRequestReviewAssignment]:
        """Evaluate rules and auto-assign reviewers to a review

        Runs on the create path only (when a new review base is created
        without an explicit reviewer). Finds the first matching rule
        by priority and creates assignments.

        Args:
            db: Database session
            review_base: The newly created review base
            review_data: The original review creation data

        Returns:
            List of created PullRequestReviewAssignment records
        """
        rules = await self.get_active_rules(db)

        for rule in rules:
            if not self.rule_matches(rule, review_data):
                continue

            # First matching rule wins
            logger.info(
                "Auto-assign rule matched",
                extra={
                    "rule_id": rule.id,
                    "rule_name": rule.name,
                    "pull_request_id": review_data.pull_request_id,
                    "project_key": review_data.project_key,
                    "repository_slug": review_data.repository_slug,
                },
            )
            assigned = []
            reviewers = list(rule.assign_to)

            # Apply max_assignments cap
            if rule.max_assignments > 0 and len(reviewers) > rule.max_assignments:
                reviewers = reviewers[: rule.max_assignments]

            for reviewer_username in reviewers:
                # Verify reviewer exists in User table
                if not await self._ensure_reviewer_exists(db, reviewer_username):
                    logger.warning(
                        "Auto-assign: reviewer not found, skipping",
                        extra={
                            "reviewer": reviewer_username,
                            "rule_id": rule.id,
                            "pull_request_id": review_data.pull_request_id,
                        },
                    )
                    continue

                # Check for existing assignment (unique constraint safety)
                existing_stmt = select(PullRequestReviewAssignment).where(
                    and_(
                        PullRequestReviewAssignment.review_base_id == review_base.id,
                        PullRequestReviewAssignment.reviewer == reviewer_username,
                    )
                )
                existing_result = await db.execute(existing_stmt)
                if existing_result.scalar_one_or_none():
                    logger.info(
                        "Auto-assign: reviewer already assigned, skipping",
                        extra={"reviewer": reviewer_username, "review_base_id": review_base.id},
                    )
                    continue

                # Create the assignment
                # assigned_by is NULL (not a sentinel string) because the FK
                # constraint references user(username). Auto-assignments are
                # distinguishable by assignment_status='pending' vs manual's 'assigned'.
                assignment = PullRequestReviewAssignment(
                    review_base_id=review_base.id,
                    reviewer=reviewer_username,
                    assigned_by=None,
                    assigned_date=get_current_time(),
                    assignment_status="pending",
                )
                db.add(assignment)
                assigned.append(assignment)

            if assigned:
                await db.flush()
                logger.info(
                    "Auto-assign: assignments created",
                    extra={
                        "count": len(assigned),
                        "pull_request_id": review_data.pull_request_id,
                        "rule_id": rule.id,
                    },
                )

                # Dispatch notifications for each assignment
                for assignment in assigned:
                    await self._dispatch_assignment_notification(
                        db=db,
                        reviewer_username=assignment.reviewer,
                        review_base=review_base,
                    )

            return assigned

        # No rule matched
        logger.info(
            "No auto-assign rule matched",
            extra={
                "pull_request_id": review_data.pull_request_id,
                "project_key": review_data.project_key,
            },
        )
        return []

    async def _dispatch_assignment_notification(
        self,
        db: AsyncSession,
        reviewer_username: str,
        review_base: PullRequestReviewBase,
    ) -> None:
        """Dispatch an in-app notification for an auto-assigned review

        Args:
            db: Database session
            reviewer_username: The reviewer to notify
            review_base: The review base record
        """
        try:
            notification_data = NotificationCreate(
                user_id=reviewer_username,
                type="review_assigned",
                title=f"New Review Assigned: PR #{review_base.pull_request_id}",
                message=(
                    f"You have been auto-assigned to review PR #{review_base.pull_request_id} "
                    f"in {review_base.project_key}/{review_base.repository_slug}"
                ),
                related_id=str(review_base.pull_request_id),
                related_type="pull_request",
                priority="high",
                channel="in_app",
            )
            await self.notification_service.create_notification(
                db=db, notification_data=notification_data
            )
            logger.info(
                "Auto-assign notification dispatched",
                extra={
                    "reviewer": reviewer_username,
                    "pull_request_id": review_base.pull_request_id,
                },
            )
        except Exception as e:
            logger.error(
                f"Failed to dispatch auto-assign notification: {e}",
                extra={
                    "reviewer": reviewer_username,
                    "pull_request_id": review_base.pull_request_id,
                },
            )
