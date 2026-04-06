"""Audit log schemas for request/response validation"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AuditLogQuery(BaseModel):
    """Query parameters for filtering audit logs"""

    auth_user_id: int | None = Field(None, description="Filter by user ID")
    resource_type: str | None = Field(None, description="Filter by resource type")
    resource_id: str | None = Field(None, description="Filter by specific resource ID")
    action: str | None = Field(None, description="Filter by action type")
    request_method: str | None = Field(None, description="Filter by HTTP method")
    response_status: int | None = Field(None, description="Filter by HTTP status code")
    start_date: datetime | None = Field(None, description="Filter logs after this date")
    end_date: datetime | None = Field(None, description="Filter logs before this date")
    limit: int = Field(100, ge=1, le=1000, description="Maximum number of results")
    offset: int = Field(0, ge=0, description="Pagination offset")


class AuditLogResponse(BaseModel):
    """Audit log entry response"""

    id: int
    auth_user_id: int | None
    action: str
    resource_type: str | None
    resource_id: str | None
    old_values: dict | None
    new_values: dict | None
    ip_address: str | None
    user_agent: str | None
    request_method: str | None
    request_path: str | None
    response_status: int | None
    execution_time_ms: int | None
    error_message: str | None
    created_at: str

    class Config:
        from_attributes = True


class AuditExportRequest(BaseModel):
    """Export configuration for audit logs"""

    auth_user_id: int | None = Field(None, description="Filter by user ID")
    resource_type: str | None = Field(None, description="Filter by resource type")
    resource_id: str | None = Field(None, description="Filter by specific resource ID")
    action: str | None = Field(None, description="Filter by action type")
    request_method: str | None = Field(None, description="Filter by HTTP method")
    response_status: int | None = Field(None, description="Filter by HTTP status code")
    start_date: datetime | None = Field(None, description="Filter logs after this date")
    end_date: datetime | None = Field(None, description="Filter logs before this date")
    format: str = Field("csv", pattern="^(csv|json)$", description="Export format")


class AuditStatsResponse(BaseModel):
    """Audit statistics response"""

    period_days: int
    total_actions: int
    actions_by_method: dict[str, int]
    actions_by_type: dict[str, int]
    actions_by_status: dict[str, int]
    top_actors: list[dict]
