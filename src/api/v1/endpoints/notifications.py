"""API endpoints for notification management"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.core.permissions import get_current_user_with_token
from src.models.auth_user import AuthUser
from src.schemas.notification import (
    MarkAsReadRequest,
    NotificationCreate,
    NotificationListResponse,
    NotificationPreferenceUpdate,
    NotificationResponse,
    NotificationStats,
    TestNotificationRequest,
)
from src.services.notification_service import NotificationService


router = APIRouter(prefix="/notifications", tags=["notifications"])


def get_notification_service() -> NotificationService:
    """Dependency to get notification service instance"""
    return NotificationService()


@router.get("/", response_model=NotificationListResponse)
async def list_notifications(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    is_read: bool | None = Query(default=None, description="Filter by read status"),
    notification_type: str | None = Query(default=None, description="Filter by notification type"),
    priority: str | None = Query(default=None, description="Filter by priority level"),
) -> NotificationListResponse:
    """
    Get user's notifications with pagination and filters

    Returns paginated list of notifications for the authenticated user.
    Supports filtering by read status, notification type, and priority.

    Args:
        db: Database session
        current_user: Authenticated user
        service: Notification service
        page: Page number (default: 1)
        page_size: Items per page (default: 20, max: 100)
        is_read: Filter by read status (optional)
        notification_type: Filter by type (optional)
        priority: Filter by priority (optional)

    Returns:
        NotificationListResponse: Paginated notification list
    """
    try:
        return await service.get_user_notifications(
            db=db,
            user_id=current_user.username,
            page=page,
            page_size=page_size,
            is_read=is_read,
            notification_type=notification_type,
            priority=priority,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": str(e)},
        )


@router.get("/unread-count")
async def get_unread_count(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> dict:
    """
    Get count of unread notifications

    Returns the number of unread notifications for the authenticated user.
    Results are cached for 60 seconds for performance.

    Args:
        db: Database session
        current_user: Authenticated user
        service: Notification service

    Returns:
        dict: {"unread_count": int}
    """
    try:
        count = await service.get_unread_count(db=db, user_id=current_user.username)
        return {"unread_count": count}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": str(e)},
        )


@router.get("/stats", response_model=NotificationStats)
async def get_notification_stats(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> NotificationStats:
    """
    Get notification statistics

    Returns aggregated statistics including unread count, total count,
    breakdown by priority, and breakdown by notification type.

    Args:
        db: Database session
        current_user: Authenticated user
        service: Notification service

    Returns:
        NotificationStats: Aggregated statistics
    """
    try:
        return await service.get_notification_stats(db=db, user_id=current_user.username)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": str(e)},
        )


@router.get("/{notification_id}", response_model=NotificationResponse)
async def get_notification(
    notification_id: int,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> NotificationResponse:
    """
    Get a single notification by ID

    Returns detailed information about a specific notification.
    Users can only access their own notifications.

    Args:
        notification_id: Notification ID
        db: Database session
        current_user: Authenticated user
        service: Notification service

    Returns:
        NotificationResponse: Notification details

    Raises:
        HTTPException: 404 if notification not found or not owned by user
    """
    try:
        return await service.get_notification_by_id(
            db=db,
            notification_id=notification_id,
            user_id=current_user.username,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NOT_FOUND", "message": str(e)},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": str(e)},
        )


@router.post("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_as_read(
    notification_id: int,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
    request: MarkAsReadRequest = None,
) -> NotificationResponse:
    """
    Mark a notification as read

    Updates the notification's read status and timestamp.
    Users can only mark their own notifications as read.

    Args:
        notification_id: Notification ID
        db: Database session
        current_user: Authenticated user
        service: Notification service
        request: Empty request body (not used)

    Returns:
        NotificationResponse: Updated notification

    Raises:
        HTTPException: 404 if notification not found or not owned by user
    """
    try:
        return await service.mark_as_read(
            db=db,
            notification_id=notification_id,
            user_id=current_user.username,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NOT_FOUND", "message": str(e)},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": str(e)},
        )


@router.post("/read-all")
async def mark_all_notifications_as_read(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> dict:
    """
    Mark all notifications as read

    Bulk operation to mark all unread notifications as read for the user.

    Args:
        db: Database session
        current_user: Authenticated user
        service: Notification service

    Returns:
        dict: {"marked_count": int, "message": str}
    """
    try:
        count = await service.mark_all_as_read(db=db, user_id=current_user.username)
        return {
            "marked_count": count,
            "message": f"Successfully marked {count} notification{'s' if count != 1 else ''} as read",
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": str(e)},
        )


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: int,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> dict:
    """
    Delete a notification

    Permanently removes a notification from the database.
    Users can only delete their own notifications.

    Args:
        notification_id: Notification ID
        db: Database session
        current_user: Authenticated user
        service: Notification service

    Returns:
        dict: {"message": str}

    Raises:
        HTTPException: 404 if notification not found or not owned by user
    """
    try:
        success = await service.delete_notification(
            db=db,
            notification_id=notification_id,
            user_id=current_user.username,
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "NOT_FOUND", "message": "Notification not found"},
            )

        return {"message": "Notification deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": str(e)},
        )


@router.get("/preferences")
async def get_notification_preferences(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> list[dict]:
    """
    Get user's notification preferences

    Returns all notification preferences configured for the user.

    Args:
        db: Database session
        current_user: Authenticated user
        service: Notification service

    Returns:
        list[dict]: List of notification preferences
    """
    try:
        preferences = await service.get_preferences(db=db, user_id=current_user.username)
        return [pref.to_dict() for pref in preferences]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": str(e)},
        )


@router.put("/preferences/{notification_type}")
async def update_notification_preference(
    notification_type: str,
    updates: NotificationPreferenceUpdate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> dict:
    """
    Update notification preferences

    Updates or creates notification preferences for a specific notification type.

    Args:
        notification_type: Type of notification (e.g., 'review_assigned')
        updates: Preference updates (partial update supported)
        db: Database session
        current_user: Authenticated user
        service: Notification service

    Returns:
        dict: Updated preference data

    Raises:
        HTTPException: 422 if validation fails
    """
    try:
        preference = await service.update_preferences(
            db=db,
            user_id=current_user.username,
            notification_type=notification_type,
            updates=updates,
        )
        return preference.to_dict()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": str(e)},
        )


@router.post("/test")
async def send_test_notification(
    request: TestNotificationRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> NotificationResponse:
    """
    Send a test notification to the current user

    Creates a test notification for debugging and testing purposes.
    Rate limited to prevent abuse.

    Args:
        request: Test notification parameters
        db: Database session
        current_user: Authenticated user
        service: Notification service

    Returns:
        NotificationResponse: Created test notification

    Raises:
        HTTPException: 429 if rate limit exceeded
    """
    try:
        notification_data = NotificationCreate(
            user_id=current_user.username,
            type=request.type,
            title=request.title,
            message=request.message,
            priority=request.priority,
            channel="in_app",
        )

        return await service.create_notification(db=db, notification_data=notification_data)
    except ValueError as e:
        # Rate limit exceeded
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"error": "RATE_LIMIT_EXCEEDED", "message": str(e)},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": str(e)},
        )
