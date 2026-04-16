"""Schemas for role delegation"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class DelegationCreate(BaseModel):
    """Schema for creating a role delegation"""

    delegatee_id: int = Field(..., description="User ID to delegate role to")
    role_id: int = Field(..., description="Role ID to delegate")
    resource_type: str = Field(
        ...,
        description="Resource type (must match delegator's resource type)",
        pattern="^(global|project|repository)$",
    )
    resource_id: str | None = Field(
        None,
        description="Resource identifier (NULL for global, project_key or repository_slug otherwise)",
    )
    delegation_scope: dict = Field(
        ...,
        description="Specific permissions to delegate (subset of delegator's permissions)",
        example={"reviews": ["read", "create"], "scores": ["read"]},
    )
    starts_at: datetime = Field(..., description="Delegation start time")
    expires_at: datetime = Field(..., description="Delegation end time")
    reason: str | None = Field(
        None,
        description="Reason for delegation",
        max_length=500,
    )

    @field_validator("expires_at")
    @classmethod
    def expires_after_starts(cls, v: datetime, info) -> datetime:
        """Ensure expires_at is after starts_at"""
        if "starts_at" in info.data and v <= info.data["starts_at"]:
            raise ValueError("expires_at must be after starts_at")
        return v


class DelegationResponse(BaseModel):
    """Schema for delegation response"""

    id: int
    auth_user_id: int  # delegatee
    delegatee_username: str | None = None
    delegatee_display_name: str | None = None
    role_id: int
    role_name: str | None = None
    resource_type: str
    resource_id: str | None
    granted_by: int | None
    delegator_id: int | None
    delegator_username: str | None = None
    delegator_display_name: str | None = None
    is_delegated: bool
    delegation_status: str | None
    delegation_scope: dict | None
    delegation_reason: str | None
    starts_at: str | None
    expires_at: str | None
    revoked_by: int | None
    revoked_at: str | None
    created_at: str

    class Config:
        from_attributes = True


class DelegationRevoke(BaseModel):
    """Schema for revoking a delegation"""

    reason: str | None = Field(
        None,
        description="Reason for revocation",
        max_length=500,
    )


class DelegationListQuery(BaseModel):
    """Query parameters for listing delegations"""

    delegator_id: int | None = Field(None, description="Filter by delegator")
    delegatee_id: int | None = Field(None, description="Filter by delegatee")
    status: str | None = Field(
        None,
        description="Filter by status (active/expired/revoked/pending)",
        pattern="^(active|expired|revoked|pending)$",
    )
    include_expired: bool = Field(
        False,
        description="Include expired/revoked delegations in results",
    )
