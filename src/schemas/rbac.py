"""RBAC schemas for request/response validation"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class RoleCreate(BaseModel):
    """Schema for creating a new role"""

    name: str = Field(..., min_length=3, max_length=64, description="Role name")
    description: str | None = Field(None, description="Role description")
    permissions: dict = Field(
        ...,
        description="Role permissions in format {resource_type: [actions]}",
        example={"reviews": ["read", "create"], "scores": ["read", "update"]},
    )


class RoleUpdate(BaseModel):
    """Schema for updating a role"""

    description: str | None = Field(None, description="Updated description")
    permissions: dict | None = Field(None, description="Updated permissions")


class RoleResponse(BaseModel):
    """Schema for role response"""

    id: int
    name: str
    description: str | None
    permissions: dict
    created_at: str

    class Config:
        from_attributes = True


class RoleAssignmentRequest(BaseModel):
    """Schema for assigning a role to user"""

    role_id: int = Field(..., description="Role ID to assign")
    resource_type: str = Field(
        "global",
        description="Resource scope (global only; project visibility is managed by repository access grants)",
        pattern="^global$",
    )
    resource_id: str | None = Field(
        None,
        description="Deprecated and always null; kept for response compatibility",
    )
    expires_at: datetime | None = Field(
        None, description="Optional expiration time for temporary permissions"
    )


class RoleAssignmentResponse(BaseModel):
    """Schema for role assignment response"""

    id: int
    auth_user_id: int
    role_id: int
    role_name: str | None = Field(None, description="Name of the assigned role")
    resource_type: str
    resource_id: str | None
    granted_by: int | None
    expires_at: str | None
    created_at: str

    class Config:
        from_attributes = True
