"""Pydantic schemas for auto-assignment rule management"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from src.utils.ai_review_utils import ISSUE_SEVERITIES


def _normalize_issue_severity(conditions: dict | None) -> dict | None:
    """Trim, lower-case and check the severity list a rule matches on.

    The AI review reports a severity per issue; a rule matches when any finding is at
    one of the levels it lists. Anything else is a typo that would silently never
    match, so it is rejected here instead.
    """
    if not conditions:
        return conditions

    severities = conditions.get("issue_severity")
    if severities is None:
        return conditions
    if not isinstance(severities, list) or not severities:
        raise ValueError("issue_severity must be a non-empty list of severities")

    normalized: list[str] = []
    for severity in severities:
        level = str(severity).strip().lower()
        if level not in ISSUE_SEVERITIES:
            raise ValueError(
                f"Unknown issue severity '{severity}'. Must be one of: "
                f"{', '.join(ISSUE_SEVERITIES)}"
            )
        if level not in normalized:
            normalized.append(level)

    return {**conditions, "issue_severity": normalized}


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
        "pull_request_user, source_branch_prefix, target_branch, pull_request_status, "
        "issue_severity (critical, high, medium, low)",
        example={
            "project_key": ["PROJ-A"],
            "repository_slug": ["frontend-store"],
            "issue_severity": ["critical", "high"],
        },
    )
    assign_to: list[str] = Field(
        ...,
        min_length=1,
        description="List of git usernames to assign when this rule matches",
        example=["alice", "bob"],
    )
    starts_at: datetime | None = Field(None, description="Optional start date for rule validity")
    expires_at: datetime | None = Field(None, description="Optional end date for rule validity")
    is_active: bool = Field(default=True, description="Whether this rule is active")

    @field_validator("conditions")
    @classmethod
    def validate_conditions(cls, value: dict) -> dict:
        """Reject severities the engine could never match on."""
        return _normalize_issue_severity(value) or {}


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
        description="Match conditions as JSON. ``issue_severity`` matches the severities "
        "of the issues the AI review reported (critical, high, medium, low)",
    )
    assign_to: list[str] | None = Field(
        None,
        min_length=1,
        description="List of git usernames to assign when this rule matches",
    )
    starts_at: datetime | None = Field(None, description="Optional start date for rule validity")
    expires_at: datetime | None = Field(None, description="Optional end date for rule validity")
    is_active: bool | None = Field(None, description="Whether this rule is active")

    @field_validator("conditions")
    @classmethod
    def validate_conditions(cls, value: dict | None) -> dict | None:
        """Reject severities the engine could never match on."""
        return _normalize_issue_severity(value)


class AutoAssignRuleResponse(BaseModel):
    """Schema for auto-assignment rule response"""

    id: int
    name: str
    description: str | None = None
    priority: int
    conditions: dict
    assign_to: list[str]
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
