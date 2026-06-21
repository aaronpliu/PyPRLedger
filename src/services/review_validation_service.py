"""Service for validating PR review data integrity"""

import logging
from datetime import datetime, timedelta

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.pull_request import PullRequestReviewRaw
from src.schemas.pull_request import ReviewRawResponse, ReviewValidationSummary
from src.services.review_service import ReviewService
from src.utils.timezone import get_current_time


logger = logging.getLogger(__name__)


class ReviewValidationService:
    """Service for validating PR review data integrity"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_validation_summary(
        self,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        project_key: str | None = None,
    ) -> ReviewValidationSummary:
        """Get validation summary comparing raw vs successful reviews"""

        # Build base query with filters
        base_filters = []
        if date_from:
            base_filters.append(PullRequestReviewRaw.created_date >= date_from)
        if date_to:
            base_filters.append(PullRequestReviewRaw.created_date <= date_to)

        # Count total attempted (all raw records)
        raw_query = select(func.count(PullRequestReviewRaw.id))
        if base_filters:
            raw_query = raw_query.where(*base_filters)
        total_attempted = (await self.db.execute(raw_query)).scalar() or 0

        # Count successful
        success_query = select(func.count(PullRequestReviewRaw.id)).where(
            PullRequestReviewRaw.status == "success"
        )
        if base_filters:
            success_query = success_query.where(*base_filters)
        total_successful = (await self.db.execute(success_query)).scalar() or 0

        # Get failed records with details
        failed_query = select(PullRequestReviewRaw).where(PullRequestReviewRaw.status == "failed")
        if base_filters:
            failed_query = failed_query.where(*base_filters)
        failed_query = failed_query.order_by(desc(PullRequestReviewRaw.created_date))
        failed_records = (await self.db.execute(failed_query)).scalars().all()

        total_failed = total_attempted - total_successful
        success_rate = (total_successful / total_attempted * 100) if total_attempted > 0 else 0

        return ReviewValidationSummary(
            total_attempted=total_attempted,
            total_successful=total_successful,
            total_failed=total_failed,
            success_rate=round(success_rate, 2),
            failed_reviews=[ReviewRawResponse.model_validate(r) for r in failed_records],
            date_range={
                "from": date_from.isoformat() if date_from else None,
                "to": date_to.isoformat() if date_to else None,
            },
        )

    async def retry_failed_review(self, raw_record_id: int) -> dict:
        """Retry a failed review using the stored raw payload.

        On success, the raw record is deleted to keep the validation table clean
        and consistent with pull_request_review_base.
        """

        # Get raw record
        raw_record = await self.db.get(PullRequestReviewRaw, raw_record_id)
        if not raw_record:
            raise ValueError(f"Raw record {raw_record_id} not found")

        if raw_record.status != "failed":
            raise ValueError(
                f"Cannot retry record with status '{raw_record.status}'. Only 'failed' records can be retried."
            )

        logger.info(f"Retrying failed review from raw record {raw_record_id}")

        try:
            # Convert payload back to ReviewCreate
            from src.schemas.pull_request import ReviewCreate

            review_data = ReviewCreate(**raw_record.request_payload)

            # Attempt to process again
            review_service = ReviewService()
            result, created = await review_service.upsert_review(review_data, self.db)

            # On success, delete the raw record to keep validation table clean
            # The successful review is now in pull_request_review_base
            await self.db.delete(raw_record)
            await self.db.commit()

            logger.info(
                f"Successfully retried review {raw_record_id}. Created: {created}. Raw record deleted."
            )

            return {
                "success": True,
                "message": "Review successfully retried and validated",
                "review_id": result.id,
                "pull_request_id": result.pull_request_id,
            }

        except Exception as e:
            # On failure, keep the raw record for future retry attempts
            logger.error(f"Failed to retry review {raw_record_id}: {str(e)}")
            await self.db.rollback()
            raise

    async def delete_raw_record(self, raw_record_id: int) -> dict:
        """Delete a failed raw record by its ID.

        Args:
            raw_record_id: ID of the raw record to delete

        Returns:
            dict: Success confirmation

        Raises:
            ValueError: If the record is not found or has already been processed
        """
        raw_record = await self.db.get(PullRequestReviewRaw, raw_record_id)
        if not raw_record:
            raise ValueError(f"Raw record {raw_record_id} not found")

        if raw_record.status == "success":
            raise ValueError(
                f"Cannot delete record with status '{raw_record.status}'. "
                "Only 'pending' or 'failed' records can be deleted."
            )

        await self.db.delete(raw_record)
        await self.db.commit()

        logger.info(f"Raw record {raw_record_id} deleted successfully")
        return {
            "success": True,
            "message": f"Raw record #{raw_record_id} deleted successfully",
        }

    async def cleanup_old_raw_records(self, days_to_keep: int = 30, batch_size: int = 1000) -> dict:
        """Clean up old raw records to prevent database bloat"""

        cutoff_date = get_current_time() - timedelta(days=days_to_keep)

        # Count records to delete
        count_query = select(func.count(PullRequestReviewRaw.id)).where(
            PullRequestReviewRaw.created_date < cutoff_date
        )
        total_to_delete = (await self.db.execute(count_query)).scalar() or 0

        if total_to_delete == 0:
            return {"deleted_count": 0, "message": "No old records to clean up"}

        # Delete in batches to avoid locking issues
        deleted_count = 0
        while True:
            delete_query = (
                select(PullRequestReviewRaw)
                .where(PullRequestReviewRaw.created_date < cutoff_date)
                .limit(batch_size)
            )
            records = (await self.db.execute(delete_query)).scalars().all()

            if not records:
                break

            for record in records:
                await self.db.delete(record)

            await self.db.commit()
            deleted_count += len(records)

            logger.info(f"Deleted {deleted_count}/{total_to_delete} old raw records")

        return {
            "deleted_count": deleted_count,
            "message": f"Successfully deleted {deleted_count} old raw records",
        }
