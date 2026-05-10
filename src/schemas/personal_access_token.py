"""Schemas for Personal Access Token API"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PATCreateRequest(BaseModel):
    """Request schema for creating a new personal access token"""

    name: str = Field(
        ..., min_length=1, max_length=100, description="Token name for identification"
    )
    expires_in_days: int | None = Field(
        None,
        ge=1,
        le=365,
        description="Days until token expires (1-365). None means use default (90 days)",
    )


class PATResponse(BaseModel):
    """Response schema for token metadata (no token value)"""

    id: int
    name: str
    prefix: str
    created_at: datetime
    expires_at: datetime | None
    last_used_at: datetime | None
    is_active: bool

    class Config:
        from_attributes = True


class PATCreationResponse(PATResponse):
    """Special response for token creation (includes token once)"""

    token: str = Field(..., description="Full token value (shown only once)")


class PATListResponse(BaseModel):
    """Paginated list response"""

    total: int
    items: list[PATResponse]
