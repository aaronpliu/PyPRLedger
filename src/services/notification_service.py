"""Notification service for managing user notifications"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.models.notification import Notification, NotificationPreference
from src.schemas.notification import (
    NotificationCreate,
    NotificationListResponse,
    NotificationPreferenceUpdate,
    NotificationResponse,
    NotificationStats,
)
from src.utils.metrics import MetricsCollector
from src.utils.redis import get_redis_client


logger = logging.getLogger(__name__)


class NotificationService:
    """Service for managing notifications and preferences"""

    def __init__(self, metrics: MetricsCollector | None = None):
        self.metrics = metrics or MetricsCollector()
        self.redis_client = get_redis_client()

    async def create_notification(
        self,
        db: AsyncSession,
        notification_data: NotificationCreate,
    ) -> NotificationResponse:
        """Create a new notification for a user"""
        # Check rate limit
        await self._check_rate_limit(notification_data.user_id)

        # Calculate expiration date
        expires_at = datetime.now() + timedelta(days=settings.NOTIFICATION_RETENTION_DAYS)

        # Create notification
        notification = Notification(
            user_id=notification_data.user_id,
            type=notification_data.type,
            title=notification_data.title,
            message=notification_data.message,
            related_id=notification_data.related_id,
            related_type=notification_data.related_type,
            priority=notification_data.priority,
            channel=notification_data.channel,
            expires_at=expires_at,
        )

        db.add(notification)
        await db.flush()
        await db.refresh(notification)

        # Invalidate unread count cache
        await self._invalidate_unread_count_cache(notification_data.user_id)

        # Log creation
        logger.info(
            f"Notification created: user={notification_data.user_id}, type={notification_data.type}"
        )

        # Increment metrics
        self.metrics.increment_notification_created(
            type=notification_data.type,
            priority=notification_data.priority,
            channel=notification_data.channel,
        )

        return NotificationResponse.model_validate(notification)

    async def get_user_notifications(
        self,
        db: AsyncSession,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
        is_read: bool | None = None,
        notification_type: str | None = None,
        priority: str | None = None,
    ) -> NotificationListResponse:
        """Get paginated notifications for a user with filters"""
        # Build query
        stmt = select(Notification).where(Notification.user_id == user_id)

        # Apply filters
        if is_read is not None:
            stmt = stmt.where(Notification.is_read == is_read)
        if notification_type:
            stmt = stmt.where(Notification.type == notification_type)
        if priority:
            stmt = stmt.where(Notification.priority == priority)

        # Order by created_at descending
        stmt = stmt.order_by(Notification.created_at.desc())

        # Get total count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_result = await db.execute(count_stmt)
        total = count_result.scalar() or 0

        # Apply pagination
        offset = (page - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size)

        # Execute query
        result = await db.execute(stmt)
        notifications = result.scalars().all()

        # Convert to response
        items = [NotificationResponse.model_validate(n) for n in notifications]

        return NotificationListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get_notification_by_id(
        self,
        db: AsyncSession,
        notification_id: int,
        user_id: str,
    ) -> NotificationResponse:
        """Get a single notification by ID (user must own it)"""
        stmt = select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )
        result = await db.execute(stmt)
        notification = result.scalar_one_or_none()

        if not notification:
            raise ValueError(f"Notification {notification_id} not found")

        return NotificationResponse.model_validate(notification)

    async def mark_as_read(
        self,
        db: AsyncSession,
        notification_id: int,
        user_id: str,
    ) -> NotificationResponse:
        """Mark a notification as read"""
        stmt = select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )
        result = await db.execute(stmt)
        notification = result.scalar_one_or_none()

        if not notification:
            raise ValueError(f"Notification {notification_id} not found")

        notification.mark_as_read()
        await db.flush()
        await db.refresh(notification)

        # Invalidate unread count cache
        await self._invalidate_unread_count_cache(user_id)

        # Increment metrics
        self.metrics.increment_notification_read()

        return NotificationResponse.model_validate(notification)

    async def mark_all_as_read(
        self,
        db: AsyncSession,
        user_id: str,
    ) -> int:
        """Mark all notifications as read for a user"""
        # Update all unread notifications
        stmt = select(Notification).where(
            Notification.user_id == user_id, Notification.is_read == False
        )
        result = await db.execute(stmt)
        notifications = result.scalars().all()

        count = 0
        for notification in notifications:
            notification.mark_as_read()
            count += 1

        await db.flush()

        # Invalidate unread count cache
        await self._invalidate_unread_count_cache(user_id)

        # Increment metrics
        self.metrics.increment_notification_read()

        logger.info(f"Marked {count} notifications as read for user {user_id}")
        return count

    async def delete_notification(
        self,
        db: AsyncSession,
        notification_id: int,
        user_id: str,
    ) -> bool:
        """Delete a notification (soft delete by removing from DB)"""
        stmt = select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )
        result = await db.execute(stmt)
        notification = result.scalar_one_or_none()

        if not notification:
            return False

        await db.delete(notification)
        await db.flush()

        # Invalidate unread count cache
        await self._invalidate_unread_count_cache(user_id)

        # Increment metrics
        self.metrics.increment_notification_deleted()

        logger.info(f"Deleted notification {notification_id} for user {user_id}")
        return True

    async def get_unread_count(
        self,
        db: AsyncSession,
        user_id: str,
    ) -> int:
        """Get count of unread notifications for a user"""
        # Try cache first
        cache_key = f"notification:unread:{user_id}"
        try:
            cached = await self.redis_client.get(cache_key)
            if cached:
                self.metrics.increment_cache_hit(cache_type="notification_unread")
                return int(cached)
        except Exception as e:
            logger.warning(f"Redis cache error: {e}")

        # Query database
        stmt = select(func.count()).where(
            Notification.user_id == user_id,
            Notification.is_read == False,
        )
        result = await db.execute(stmt)
        count = result.scalar() or 0

        # Cache result (60 seconds TTL)
        try:
            await self.redis_client.setex(cache_key, 60, str(count))
        except Exception as e:
            logger.warning(f"Failed to cache unread count: {e}")

        self.metrics.increment_cache_miss(cache_type="notification_unread")
        return count

    async def get_notification_stats(
        self,
        db: AsyncSession,
        user_id: str,
    ) -> NotificationStats:
        """Get notification statistics for a user"""
        # Total count
        total_stmt = select(func.count()).where(Notification.user_id == user_id)
        total_result = await db.execute(total_stmt)
        total_count = total_result.scalar() or 0

        # Unread count
        unread_stmt = select(func.count()).where(
            Notification.user_id == user_id,
            Notification.is_read == False,
        )
        unread_result = await db.execute(unread_stmt)
        unread_count = unread_result.scalar() or 0

        # Count by priority
        priority_stmt = (
            select(Notification.priority, func.count())
            .where(Notification.user_id == user_id)
            .group_by(Notification.priority)
        )
        priority_result = await db.execute(priority_stmt)
        by_priority = {row[0]: row[1] for row in priority_result}

        # Count by type
        type_stmt = (
            select(Notification.type, func.count())
            .where(Notification.user_id == user_id)
            .group_by(Notification.type)
        )
        type_result = await db.execute(type_stmt)
        by_type = {row[0]: row[1] for row in type_result}

        return NotificationStats(
            unread_count=unread_count,
            total_count=total_count,
            by_priority=by_priority,
            by_type=by_type,
        )

    async def update_preferences(
        self,
        db: AsyncSession,
        user_id: str,
        notification_type: str,
        updates: NotificationPreferenceUpdate,
    ) -> NotificationPreference:
        """Update notification preferences for a user"""
        # Find existing preference or create new one
        stmt = select(NotificationPreference).where(
            NotificationPreference.user_id == user_id,
            NotificationPreference.notification_type == notification_type,
        )
        result = await db.execute(stmt)
        preference = result.scalar_one_or_none()

        if not preference:
            # Create new preference with defaults
            preference = NotificationPreference(
                user_id=user_id,
                notification_type=notification_type,
            )
            db.add(preference)
            await db.flush()

        # Apply updates
        if updates.channel_enabled is not None:
            preference.channel_enabled = updates.channel_enabled
        if updates.email_enabled is not None:
            preference.email_enabled = updates.email_enabled
        if updates.in_app_enabled is not None:
            preference.in_app_enabled = updates.in_app_enabled
        if updates.slack_enabled is not None:
            preference.slack_enabled = updates.slack_enabled

        await db.flush()
        await db.refresh(preference)

        logger.info(f"Updated preferences for user {user_id}, type {notification_type}")
        return preference

    async def get_preferences(
        self,
        db: AsyncSession,
        user_id: str,
    ) -> list[NotificationPreference]:
        """Get all notification preferences for a user"""
        stmt = select(NotificationPreference).where(NotificationPreference.user_id == user_id)
        result = await db.execute(stmt)
        return result.scalars().all()

    async def get_preference(
        self,
        db: AsyncSession,
        user_id: str,
        notification_type: str,
    ) -> NotificationPreference | None:
        """Get specific notification preference for a user"""
        stmt = select(NotificationPreference).where(
            NotificationPreference.user_id == user_id,
            NotificationPreference.notification_type == notification_type,
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def cleanup_expired_notifications(self, db: AsyncSession) -> int:
        """Remove expired notifications (background task)"""
        now = datetime.now()

        # Delete expired notifications
        stmt = delete(Notification).where(Notification.expires_at <= now)
        result = await db.execute(stmt)
        count = result.rowcount

        await db.commit()

        logger.info(f"Cleaned up {count} expired notifications")
        self.metrics.increment_notification_deleted()

        return count

    async def _check_rate_limit(self, user_id: str) -> None:
        """Check if user has exceeded notification rate limit"""
        cache_key = f"notification:rate:{user_id}:{datetime.now().strftime('%Y-%m-%d')}"

        try:
            current_count = await self.redis_client.get(cache_key)
            current_count = int(current_count) if current_count else 0

            if current_count >= settings.NOTIFICATION_MAX_PER_DAY:
                raise ValueError(
                    f"Rate limit exceeded: max {settings.NOTIFICATION_MAX_PER_DAY} notifications per day"
                )

            # Increment counter (expire at end of day)
            await self.redis_client.incr(cache_key)
            await self.redis_client.expireat(
                cache_key,
                int((datetime.now().replace(hour=23, minute=59, second=59)).timestamp()),
            )
        except Exception as e:
            logger.warning(f"Rate limit check failed: {e}")
            # Don't block on Redis errors

    async def _invalidate_unread_count_cache(self, user_id: str) -> None:
        """Invalidate unread count cache for a user"""
        cache_key = f"notification:unread:{user_id}"
        try:
            await self.redis_client.delete(cache_key)
        except Exception as e:
            logger.warning(f"Failed to invalidate cache: {e}")
