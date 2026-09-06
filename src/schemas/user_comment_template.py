"""Schemas for User Comment Template API"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class UserCommentTemplateCreateRequest(BaseModel):
    """Request schema for creating a personal comment template"""

    name: str = Field(
        ..., min_length=1, max_length=100, description="Template name for identification"
    )
    content: str = Field(
        ..., min_length=1, max_length=5000, description="Template comment content (Markdown)"
    )


class UserCommentTemplateUpdateRequest(BaseModel):
    """Request schema for updating a personal comment template"""

    name: str | None = Field(None, min_length=1, max_length=100, description="New template name")
    content: str | None = Field(
        None, min_length=1, max_length=5000, description="New template comment content (Markdown)"
    )


class UserCommentTemplateResponse(BaseModel):
    """Response schema for a personal comment template"""

    id: int
    name: str
    content: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserCommentTemplateListResponse(BaseModel):
    """List response for personal comment templates"""

    total: int
    items: list[UserCommentTemplateResponse]
