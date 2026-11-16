"""Tests for notification service"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.schemas.notification import (
    NotificationCreate,
    NotificationPreferenceUpdate,
)
from src.services.notification_service import NotificationService


@pytest.mark.asyncio
async def test_create_notification(db_session: AsyncSession):
    """Test creating a new notification"""
    service = NotificationService()

    # Create notification
    notification_data = NotificationCreate(
        user_id="test_user",
        type="review_assigned",
        title="New Review Assigned",
        message="You have been assigned to review PR #123",
        related_id="123",
        related_type="pull_request",
        priority="high",
    )

    result = await service.create_notification(db_session, notification_data)

    assert result.user_id == "test_user"
    assert result.type == "review_assigned"
    assert result.title == "New Review Assigned"
    assert result.is_read is False
    assert result.priority == "high"


@pytest.mark.asyncio
async def test_get_user_notifications(db_session: AsyncSession):
    """Test getting paginated notifications for a user"""
    service = NotificationService()

    # Create test notifications
    for i in range(5):
        notification_data = NotificationCreate(
            user_id="test_user",
            type="test",
            title=f"Test Notification {i}",
            message=f"Message {i}",
        )
        await service.create_notification(db_session, notification_data)

    # Get first page
    result = await service.get_user_notifications(
        db_session,
        user_id="test_user",
        page=1,
        page_size=3,
    )

    assert result.total == 5
    assert len(result.items) == 3
    assert result.page == 1
    assert result.page_size == 3


@pytest.mark.asyncio
async def test_mark_as_read(db_session: AsyncSession):
    """Test marking a notification as read"""
    service = NotificationService()

    # Create notification
    notification_data = NotificationCreate(
        user_id="test_user",
        type="test",
        title="Test",
        message="Test message",
    )
    created = await service.create_notification(db_session, notification_data)

    # Mark as read
    result = await service.mark_as_read(db_session, created.id, "test_user")

    assert result.is_read is True
    assert result.read_at is not None


@pytest.mark.asyncio
async def test_mark_all_as_read(db_session: AsyncSession):
    """Test marking all notifications as read"""
    service = NotificationService()

    # Create multiple notifications
    for i in range(3):
        notification_data = NotificationCreate(
            user_id="test_user",
            type="test",
            title=f"Test {i}",
            message=f"Message {i}",
        )
        await service.create_notification(db_session, notification_data)

    # Mark all as read
    count = await service.mark_all_as_read(db_session, "test_user")

    assert count == 3


@pytest.mark.asyncio
async def test_get_unread_count(db_session: AsyncSession):
    """Test getting unread notification count"""
    service = NotificationService()

    # Create notifications
    for i in range(5):
        notification_data = NotificationCreate(
            user_id="test_user",
            type="test",
            title=f"Test {i}",
            message=f"Message {i}",
        )
        await service.create_notification(db_session, notification_data)

    # Mark 2 as read
    notifications = await service.get_user_notifications(
        db_session, "test_user", page=1, page_size=5
    )
    await service.mark_as_read(db_session, notifications.items[0].id, "test_user")
    await service.mark_as_read(db_session, notifications.items[1].id, "test_user")

    # Get unread count
    unread_count = await service.get_unread_count(db_session, "test_user")

    assert unread_count == 3


@pytest.mark.asyncio
async def test_delete_notification(db_session: AsyncSession):
    """Test deleting a notification"""
    service = NotificationService()

    # Create notification
    notification_data = NotificationCreate(
        user_id="test_user",
        type="test",
        title="Test",
        message="Test message",
    )
    created = await service.create_notification(db_session, notification_data)

    # Delete notification
    result = await service.delete_notification(db_session, created.id, "test_user")

    assert result is True

    # Verify it's deleted
    with pytest.raises(ValueError):
        await service.get_notification_by_id(db_session, created.id, "test_user")


@pytest.mark.asyncio
async def test_update_preferences(db_session: AsyncSession):
    """Test updating notification preferences"""
    service = NotificationService()

    # Update preferences
    updates = NotificationPreferenceUpdate(
        email_enabled=False,
        slack_enabled=True,
    )
    preference = await service.update_preferences(
        db_session,
        user_id="test_user",
        notification_type="review_assigned",
        updates=updates,
    )

    assert preference.user_id == "test_user"
    assert preference.notification_type == "review_assigned"
    assert preference.email_enabled is False
    assert preference.slack_enabled is True


@pytest.mark.asyncio
async def test_get_preferences(db_session: AsyncSession):
    """Test getting user preferences"""
    service = NotificationService()

    # Create preferences
    updates1 = NotificationPreferenceUpdate(email_enabled=False)
    await service.update_preferences(
        db_session,
        user_id="test_user",
        notification_type="review_assigned",
        updates=updates1,
    )

    updates2 = NotificationPreferenceUpdate(in_app_enabled=False)
    await service.update_preferences(
        db_session,
        user_id="test_user",
        notification_type="review_completed",
        updates=updates2,
    )

    # Get all preferences
    preferences = await service.get_preferences(db_session, "test_user")

    assert len(preferences) == 2


@pytest.mark.asyncio
async def test_get_notification_stats(db_session: AsyncSession):
    """Test getting notification statistics"""
    service = NotificationService()

    # Create notifications with different priorities
    for i in range(3):
        notification_data = NotificationCreate(
            user_id="test_user",
            type="review_assigned",
            title=f"Test {i}",
            message=f"Message {i}",
            priority="high" if i < 2 else "normal",
        )
        await service.create_notification(db_session, notification_data)

    # Get stats
    stats = await service.get_notification_stats(db_session, "test_user")

    assert stats.total_count == 3
    assert stats.unread_count == 3
    assert stats.by_priority["high"] == 2
    assert stats.by_priority["normal"] == 1
    assert stats.by_type["review_assigned"] == 3


@pytest.mark.asyncio
async def test_notification_authorization(db_session: AsyncSession):
    """Test that users can only access their own notifications"""
    service = NotificationService()

    # Create notification for user1
    notification_data = NotificationCreate(
        user_id="user1",
        type="test",
        title="User1 Notification",
        message="Message",
    )
    created = await service.create_notification(db_session, notification_data)

    # User2 should not be able to access user1's notification
    with pytest.raises(ValueError):
        await service.get_notification_by_id(db_session, created.id, "user2")

    # User2 should not be able to mark user1's notification as read
    with pytest.raises(ValueError):
        await service.mark_as_read(db_session, created.id, "user2")


# --- SSE publication ----------------------------------------------------------
# Creating a notification tells the user's open SSE connections to refresh, so
# the bell reacts within a moment instead of waiting for the next poll.


@pytest.mark.asyncio
async def test_create_notification_publishes_an_sse_event(
    db_session: AsyncSession,
):
    """The created notification is pushed onto the notification channel."""
    import json
    from unittest.mock import AsyncMock

    from src.services.sse_broker import NOTIFICATION_CHANNEL

    service = NotificationService()
    service.redis_client.publish = AsyncMock()

    notification_data = NotificationCreate(
        user_id="test_user",
        type="review_assigned",
        title="New Review Assigned",
        message="You have been assigned to review PR #123",
        priority="high",
    )
    created = await service.create_notification(db_session, notification_data)

    service.redis_client.publish.assert_awaited_once()
    channel, raw_payload = service.redis_client.publish.await_args.args
    assert channel == NOTIFICATION_CHANNEL

    payload = json.loads(raw_payload)
    assert payload["event"] == "notification"
    assert payload["user_id"] == "test_user"
    assert payload["id"] == created.id
    assert payload["type"] == "review_assigned"


@pytest.mark.asyncio
async def test_create_notification_survives_a_redis_outage(db_session: AsyncSession):
    """A failed publish must not fail (or roll back) the notification itself."""
    from unittest.mock import AsyncMock

    service = NotificationService()
    service.redis_client.publish = AsyncMock(side_effect=RuntimeError("redis down"))

    notification_data = NotificationCreate(
        user_id="test_user",
        type="review_assigned",
        title="New Review Assigned",
        message="You have been assigned to review PR #123",
    )
    created = await service.create_notification(db_session, notification_data)

    assert created.id is not None
    assert created.user_id == "test_user"
