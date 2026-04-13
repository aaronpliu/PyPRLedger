"""Service for managing multi-reviewer pull request reviews"""

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.exceptions import ReviewNotFoundException
from src.models.pull_request import PullRequestReviewAssignment, PullRequestReviewBase
from src.schemas.review import (
    AssignReviewerRequest,
    ReviewBaseResponse,
    ReviewWithAssignmentsResponse,
)
from src.utils.metrics import MetricsCollector


logger = logging.getLogger(__name__)


class MultiReviewerService:
    """Service for managing reviews with multiple reviewers"""

    def __init__(self, metrics_collector: MetricsCollector | None = None):
        self.metrics = metrics_collector or MetricsCollector()

    async def get_reviews(
        self,
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        project_key: str | None = None,
        reviewer: str | None = None,
        status: str | None = None,
    ) -> tuple[list[ReviewWithAssignmentsResponse], int]:
        """
        Get list of reviews with their assignments

        Returns:
            Tuple of (reviews, total_count)
        """
        # Build base query
        stmt = select(PullRequestReviewBase).options(
            selectinload(PullRequestReviewBase.assignments).selectinload(
                PullRequestReviewAssignment.reviewer_rel
            ),
            selectinload(PullRequestReviewBase.assignments).selectinload(
                PullRequestReviewAssignment.assigned_by_rel
            ),
        )

        # Apply filters
        if project_key:
            stmt = stmt.where(PullRequestReviewBase.project_key == project_key)
        if status:
            stmt = stmt.where(PullRequestReviewBase.pull_request_status == status)
        if reviewer:
            stmt = stmt.join(PullRequestReviewBase.assignments).where(
                PullRequestReviewAssignment.reviewer == reviewer
            )

        # Get total count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await db.execute(count_stmt)
        total = total_result.scalar() or 0

        # Apply pagination
        stmt = stmt.order_by(desc(PullRequestReviewBase.created_date))
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

        result = await db.execute(stmt)
        bases = result.scalars().all()

        # Convert to response models
        reviews = []
        for base in bases:
            review_dict = self._base_to_response(base)
            reviews.append(review_dict)

        return reviews, total

    async def get_review_by_id(
        self, db: AsyncSession, review_id: int
    ) -> ReviewWithAssignmentsResponse:
        """Get a single review with all assignments"""
        stmt = (
            select(PullRequestReviewBase)
            .options(
                selectinload(PullRequestReviewBase.assignments).selectinload(
                    PullRequestReviewAssignment.reviewer_rel
                ),
                selectinload(PullRequestReviewBase.assignments).selectinload(
                    PullRequestReviewAssignment.assigned_by_rel
                ),
            )
            .where(PullRequestReviewBase.id == review_id)
        )

        result = await db.execute(stmt)
        base = result.scalar_one_or_none()

        if not base:
            raise ReviewNotFoundException(review_id=str(review_id))

        return self._base_to_response(base)

    async def create_review_base(
        self, db: AsyncSession, review_data: dict[str, Any]
    ) -> ReviewBaseResponse:
        """Create a new review base record"""
        base = PullRequestReviewBase(**review_data)
        db.add(base)
        await db.flush()
        await db.refresh(base)

        return ReviewBaseResponse.model_validate(base)

    async def assign_reviewer(
        self,
        db: AsyncSession,
        review_base_id: int,
        assignment_data: AssignReviewerRequest,
        assigned_by: str | None = None,
    ) -> dict[str, Any]:
        """Assign a reviewer to a review"""
        # Check if assignment already exists
        stmt = select(PullRequestReviewAssignment).where(
            and_(
                PullRequestReviewAssignment.review_base_id == review_base_id,
                PullRequestReviewAssignment.reviewer == assignment_data.reviewer,
            )
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            return {"message": "Reviewer already assigned", "assignment": existing.to_dict()}

        # Create new assignment
        assignment = PullRequestReviewAssignment(
            review_base_id=review_base_id,
            reviewer=assignment_data.reviewer,
            assigned_by=assigned_by,
            assigned_date=datetime.now(UTC),
            assignment_status=assignment_data.assignment_status,
        )
        db.add(assignment)
        await db.flush()
        await db.refresh(assignment)

        # Load reviewer info
        await db.refresh(assignment, ["reviewer_rel"])

        return {
            "message": "Reviewer assigned successfully",
            "assignment": assignment.to_dict(),
        }

    async def remove_reviewer(self, db: AsyncSession, review_base_id: int, reviewer: str) -> bool:
        """Remove a reviewer assignment"""
        stmt = select(PullRequestReviewAssignment).where(
            and_(
                PullRequestReviewAssignment.review_base_id == review_base_id,
                PullRequestReviewAssignment.reviewer == reviewer,
            )
        )
        result = await db.execute(stmt)
        assignment = result.scalar_one_or_none()

        if not assignment:
            return False

        await db.delete(assignment)
        return True

    async def update_assignment_status(
        self,
        db: AsyncSession,
        assignment_id: int,
        status: str,
        comments: str | None = None,
    ) -> dict[str, Any]:
        """Update assignment status"""
        stmt = select(PullRequestReviewAssignment).where(
            PullRequestReviewAssignment.id == assignment_id
        )
        result = await db.execute(stmt)
        assignment = result.scalar_one_or_none()

        if not assignment:
            raise ReviewNotFoundException(review_id=str(assignment_id))

        assignment.assignment_status = status
        if comments is not None:
            assignment.reviewer_comments = comments
        assignment.updated_date = datetime.now(UTC)

        await db.flush()
        await db.refresh(assignment)

        return {"message": "Status updated", "assignment": assignment.to_dict()}

    async def delete_review(self, db: AsyncSession, review_base_id: int) -> bool:
        """Delete a review and all its assignments (cascade)"""
        stmt = select(PullRequestReviewBase).where(PullRequestReviewBase.id == review_base_id)
        result = await db.execute(stmt)
        base = result.scalar_one_or_none()

        if not base:
            return False

        await db.delete(base)  # Cascade will delete assignments
        return True

    def _base_to_response(self, base: PullRequestReviewBase) -> ReviewWithAssignmentsResponse:
        """Convert base model to response with assignments"""
        base_dict = base.to_dict()

        # Process assignments
        assignments = []
        completed = 0
        pending = 0

        for assignment in base.assignments:
            assign_dict = assignment.to_dict()

            # Add reviewer info
            if assignment.reviewer_rel:
                assign_dict["reviewer_info"] = {
                    "username": assignment.reviewer_rel.username,
                    "display_name": assignment.reviewer_rel.display_name,
                }

            # Add assigned_by info
            if assignment.assigned_by_rel:
                assign_dict["assigned_by_info"] = {
                    "username": assignment.assigned_by_rel.username,
                    "display_name": assignment.assigned_by_rel.display_name,
                }

            assignments.append(assign_dict)

            if assignment.assignment_status == "completed":
                completed += 1
            else:
                pending += 1

        return ReviewWithAssignmentsResponse(
            **base_dict,
            reviewers=assignments,
            total_reviewers=len(assignments),
            completed_reviewers=completed,
            pending_reviewers=pending,
        )
