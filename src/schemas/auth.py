"""Authentication schemas for request/response validation"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field, field_validator


# A device description is stored in the session and rendered in a table cell, so
# nothing in it needs to be longer than this.
MAX_DEVICE_FIELD_LENGTH = 64


class LoginRequest(BaseModel):
    """Login request schema"""

    username: str = Field(..., min_length=3, max_length=64, description="Username")
    password: str = Field(..., min_length=6, description="Password")


class TokenResponse(BaseModel):
    """Token response schema"""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="Opaque refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")
    refresh_expires_in: int = Field(
        ..., description="Refresh token idle expiration time in seconds"
    )


class UserinfoResponse(BaseModel):
    """Current user info response schema"""

    id: int
    username: str
    email: str | None = None
    is_active: bool
    git_user_id: int | None = None
    git_username: str | None = None
    avatar_url: str | None = Field(None, max_length=500, description="User avatar URL")
    last_login_at: datetime | None = None
    created_at: datetime
    must_change_password: bool = Field(
        default=False,
        description="Indicates if user must change password on next login",
    )
    roles: list[str] = Field(
        default_factory=list,
        description="List of role names assigned to the user",
    )


class RegisterRequest(BaseModel):
    """User registration request schema"""

    username: str = Field(..., min_length=3, max_length=64)
    email: EmailStr | None = None
    password: str = Field(..., min_length=8)


class ChangePasswordRequest(BaseModel):
    """Change password request schema"""

    old_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, description="New password")


class AdminPasswordResetRequest(BaseModel):
    """Admin password reset request schema"""

    new_password: str = Field(..., min_length=8, description="New initial password")
    force_change: bool = Field(
        default=True,
        description="Force user to change password on next login",
    )


class TokenRefreshRequest(BaseModel):
    """Token refresh request (for future use with refresh tokens)"""

    refresh_token: str = Field(..., description="Refresh token")


class LogoutRequest(BaseModel):
    """Logout request payload"""

    refresh_token: str | None = Field(None, description="Refresh token to revoke")


class SessionDeviceInfo(BaseModel):
    """Structured device metadata a client reports about itself.

    The user agent string no longer describes the device it is sent from:
    Chromium freezes the browser build (``Chrome/140.0.0.0``), replaces the
    Android device model with ``K``, and reports Windows 11 as Windows 10, while
    Safari pins macOS to 10.15.7 and reports an iPad as a Mac. User-Agent Client
    Hints carry the real values, but only Chromium exposes them — so ``source``
    records which of the two the values came from, and the session list shows
    the difference.

    Client-supplied and therefore untrusted: every field is length-capped, and
    the values are only ever rendered — never used to authenticate or authorize.
    """

    source: Literal["client-hints", "user-agent"] = Field(
        description="Where the values came from: precise client hints, or the user agent"
    )
    category: Literal["desktop", "mobile", "tablet"] | None = Field(
        default=None, description="Device class, corrected from the user agent when needed"
    )
    platform: str | None = Field(default=None, max_length=MAX_DEVICE_FIELD_LENGTH)
    platform_version: str | None = Field(default=None, max_length=MAX_DEVICE_FIELD_LENGTH)
    model: str | None = Field(default=None, max_length=MAX_DEVICE_FIELD_LENGTH)
    browser_full_version: str | None = Field(default=None, max_length=MAX_DEVICE_FIELD_LENGTH)

    @field_validator(
        "platform",
        "platform_version",
        "model",
        "browser_full_version",
        mode="before",
    )
    @classmethod
    def _sanitize(cls, value: Any) -> str | None:
        """Trim an overlong value and drop a wrongly-typed one.

        One strange field should cost that field, not the whole record: the
        useful parts of a device description are still worth keeping.
        """
        if value is None:
            return None
        if not isinstance(value, str):
            return None
        return value.strip()[:MAX_DEVICE_FIELD_LENGTH] or None


class AuthSessionResponse(BaseModel):
    """Active refresh session metadata"""

    session_id: str
    auth_user_id: int
    username: str
    ip_address: str | None = None
    user_agent: str | None = None
    device: SessionDeviceInfo | None = None
    created_at: datetime
    last_activity_at: datetime
    expires_in_seconds: int
    is_current: bool = False
