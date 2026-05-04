"""Pydantic schemas for notification system"""

from datetime import datetime

from pydantic import BaseModel, Field


class NotificationBase(BaseModel):
    """Base schema for notifications"""

    type: str = Field(..., description="Notification type (e.g., review_assigned)")
    title: str = Field(..., min_length=1, max_length=255, description="Notification title")
    message: str = Field(..., min_length=1, description="Notification message content")
    related_id: str | None = Field(None, description="Related entity ID")
    related_type: str | None = Field(None, description="Related entity type")
    priority: str = Field(
        default="normal",
        pattern="^(low|normal|high|urgent)$",
        description="Notification priority level",
    )
    channel: str = Field(
        default="in_app",
        pattern="^(in_app|email|slack)$",
        description="Delivery channel",
    )


class NotificationCreate(NotificationBase):
    """Schema for creating a new notification"""

    user_id: str = Field(..., description="Target user username")


class NotificationResponse(NotificationBase):
    """Schema for notification response with full details"""

    id: int = Field(..., description="Notification ID")
    user_id: str = Field(..., description="User username")
    is_read: bool = Field(..., description="Whether notification has been read")
    created_at: datetime = Field(..., description="Creation timestamp")
    read_at: datetime | None = Field(None, description="Read timestamp")
    expires_at: datetime | None = Field(None, description="Expiration timestamp")

    model_config = {"from_attributes": True}


class NotificationListResponse(BaseModel):
    """Schema for paginated notification list response"""

    items: list[NotificationResponse] = Field(..., description="List of notifications")
    total: int = Field(..., description="Total number of notifications")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")


class NotificationStats(BaseModel):
    """Schema for notification statistics"""

    unread_count: int = Field(..., description="Number of unread notifications")
    total_count: int = Field(..., description="Total number of notifications")
    by_priority: dict[str, int] = Field(
        default_factory=dict,
        description="Count breakdown by priority level",
    )
    by_type: dict[str, int] = Field(
        default_factory=dict,
        description="Count breakdown by notification type",
    )


class NotificationPreferenceBase(BaseModel):
    """Base schema for notification preferences"""

    notification_type: str = Field(..., description="Notification type")
    channel_enabled: bool = Field(default=True, description="Overall channel enabled")
    email_enabled: bool = Field(default=True, description="Email notifications enabled")
    in_app_enabled: bool = Field(default=True, description="In-app notifications enabled")
    slack_enabled: bool = Field(default=False, description="Slack notifications enabled")


class NotificationPreferenceUpdate(BaseModel):
    """Schema for updating notification preferences"""

    channel_enabled: bool | None = Field(None, description="Overall channel enabled")
    email_enabled: bool | None = Field(None, description="Email notifications enabled")
    in_app_enabled: bool | None = Field(None, description="In-app notifications enabled")
    slack_enabled: bool | None = Field(None, description="Slack notifications enabled")


class NotificationPreferenceResponse(NotificationPreferenceBase):
    """Schema for notification preference response"""

    id: int = Field(..., description="Preference ID")
    user_id: str = Field(..., description="User username")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = {"from_attributes": True}


class MarkAsReadRequest(BaseModel):
    """Schema for marking notification as read"""

    pass  # No body needed, just POST to endpoint


class TestNotificationRequest(BaseModel):
    """Schema for sending test notification"""

    type: str = Field(default="test", description="Test notification type")
    title: str = Field(default="Test Notification", description="Test notification title")
    message: str = Field(default="This is a test notification", description="Test message")
    priority: str = Field(default="normal", description="Test notification priority")
