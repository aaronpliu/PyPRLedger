"""Pydantic schemas for auto-assignment rule management"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AutoAssignRuleCreate(BaseModel):
    """Schema for creating an auto-assignment rule"""

    name: str = Field(..., min_length=1, max_length=128, description="Human-readable rule name")
    description: str | None = Field(None, max_length=1000, description="Optional rule description")
    priority: int = Field(
        default=100, ge=0, le=9999, description="Rule priority (lower = evaluated first)"
    )
    conditions: dict = Field(
        ...,
        description="Match conditions as JSON. Supported keys: project_key, repository_slug, "
        "pull_request_user, source_branch_prefix, target_branch, pull_request_status",
        example={
            "project_key": ["PROJ-A"],
            "repository_slug": ["frontend-store"],
        },
    )
    assign_to: list[str] = Field(
        ...,
        min_length=1,
        description="List of git usernames to assign when this rule matches",
        example=["alice", "bob"],
    )
    max_assignments: int = Field(
        default=0,
        ge=0,
        description="Maximum reviewers to assign (0 = assign all from list)",
    )
    starts_at: datetime | None = Field(None, description="Optional start date for rule validity")
    expires_at: datetime | None = Field(None, description="Optional end date for rule validity")
    is_active: bool = Field(default=True, description="Whether this rule is active")


class AutoAssignRuleUpdate(BaseModel):
    """Schema for updating an auto-assignment rule"""

    name: str | None = Field(
        None, min_length=1, max_length=128, description="Human-readable rule name"
    )
    description: str | None = Field(None, max_length=1000, description="Optional rule description")
    priority: int | None = Field(
        None, ge=0, le=9999, description="Rule priority (lower = evaluated first)"
    )
    conditions: dict | None = Field(
        None,
        description="Match conditions as JSON",
    )
    assign_to: list[str] | None = Field(
        None,
        min_length=1,
        description="List of git usernames to assign when this rule matches",
    )
    max_assignments: int | None = Field(
        None,
        ge=0,
        description="Maximum reviewers to assign (0 = assign all from list)",
    )
    starts_at: datetime | None = Field(None, description="Optional start date for rule validity")
    expires_at: datetime | None = Field(None, description="Optional end date for rule validity")
    is_active: bool | None = Field(None, description="Whether this rule is active")


class AutoAssignRuleResponse(BaseModel):
    """Schema for auto-assignment rule response"""

    id: int
    name: str
    description: str | None = None
    priority: int
    conditions: dict
    assign_to: list[str]
    max_assignments: int
    starts_at: datetime | None = None
    expires_at: datetime | None = None
    is_active: bool
    created_by: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AutoAssignRuleToggleResponse(BaseModel):
    """Schema for toggle endpoint response"""

    id: int
    name: str
    is_active: bool
    message: str

    model_config = {"from_attributes": True}


class AutoAssignRuleListResponse(BaseModel):
    """Schema for paginated rule list response"""

    items: list[AutoAssignRuleResponse]
    total: int
    page: int
    page_size: int
