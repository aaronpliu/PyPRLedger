"""Authentication schemas for request/response validation"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


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


class AuthSessionResponse(BaseModel):
    """Active refresh session metadata"""

    session_id: str
    auth_user_id: int
    username: str
    ip_address: str | None = None
    user_agent: str | None = None
    created_at: datetime
    last_activity_at: datetime
    expires_in_seconds: int
    is_current: bool = False
