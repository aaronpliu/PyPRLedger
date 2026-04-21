"""Audit log API endpoints"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.core.permissions import get_current_user_with_token
from src.models.auth_user import AuthUser
from src.schemas.audit import (
    AuditLogResponse,
    AuditStatsResponse,
)
from src.services.audit_service import AuditService
from src.services.rbac_service import RBACService


router = APIRouter(prefix="/audit")


def get_audit_service(db: Annotated[AsyncSession, Depends(get_db_session)]) -> AuditService:
    """Dependency to get audit service instance"""
    return AuditService(db)


@router.get(
    "/logs",
    response_model=dict,
    summary="Query audit logs",
    description="Get audit logs with filtering and pagination",
)
async def list_audit_logs(
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
    actor_id: int | None = Query(None, description="Filter by actor user ID"),
    username: str | None = Query(None, description="Filter by username (partial match)"),
    resource_type: str | None = Query(None, description="Filter by resource type"),
    resource_id: str | None = Query(None, description="Filter by specific resource ID"),
    action: str | None = Query(None, description="Filter by action type"),
    status_filter: str | None = Query(None, alias="status", description="Filter by status"),
    start_date: str | None = Query(None, description="Filter logs after this date (ISO format)"),
    end_date: str | None = Query(None, description="Filter logs before this date (ISO format)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> dict:
    """Query audit logs with filters (requires audit_logs:read permission)"""
    # Check permission
    rbac_service = RBACService(audit_service.db)
    await rbac_service.require_permission(current_user.id, "read", "audit_logs")

    # Parse dates if provided
    parsed_start_date = None
    parsed_end_date = None

    if start_date:
        try:
            parsed_start_date = datetime.fromisoformat(start_date)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid start_date format: {e}",
            ) from e

    if end_date:
        try:
            parsed_end_date = datetime.fromisoformat(end_date)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid end_date format: {e}",
            ) from e

    # Query logs
    logs, total = await audit_service.get_audit_logs(
        auth_user_id=actor_id,
        username=username,
        resource_type=resource_type,
        resource_id=resource_id,
        action=action,
        response_status=int(status_filter) if status_filter and status_filter.isdigit() else None,
        start_date=parsed_start_date,
        end_date=parsed_end_date,
        limit=limit,
        offset=offset,
    )

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "logs": [
            AuditLogResponse(
                id=log.id,
                auth_user_id=log.auth_user_id,
                action=log.action,
                resource_type=log.resource_type,
                resource_id=log.resource_id,
                old_values=log.old_values,
                new_values=log.new_values,
                ip_address=log.ip_address,
                user_agent=log.user_agent,
                request_method=log.request_method,
                request_path=log.request_path,
                response_status=log.response_status,
                execution_time_ms=log.execution_time_ms,
                error_message=log.error_message,
                created_at=log.created_at.isoformat(),
            )
            for log in logs
        ],
    }


@router.get(
    "/logs/{log_id}",
    response_model=AuditLogResponse,
    summary="Get specific audit log entry",
    description="Get details of a specific audit log entry",
)
async def get_audit_log(
    log_id: int,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
) -> AuditLogResponse:
    """Get specific audit log entry (requires audit_logs:read permission)"""
    # Check permission
    rbac_service = RBACService(audit_service.db)
    await rbac_service.require_permission(current_user.id, "read", "audit_logs")

    # Get log entry
    log = await audit_service.get_audit_log_by_id(log_id)
    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit log entry not found",
        )

    return AuditLogResponse(
        id=log.id,
        auth_user_id=log.auth_user_id,
        action=log.action,
        resource_type=log.resource_type,
        resource_id=log.resource_id,
        old_values=log.old_values,
        new_values=log.new_values,
        ip_address=log.ip_address,
        user_agent=log.user_agent,
        request_method=log.request_method,
        request_path=log.request_path,
        response_status=log.response_status,
        execution_time_ms=log.execution_time_ms,
        error_message=log.error_message,
        created_at=log.created_at.isoformat(),
    )


@router.get(
    "/export",
    summary="Export audit logs",
    description="Export audit logs as CSV or JSON",
)
async def export_audit_logs(
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
    actor_id: int | None = Query(None, description="Filter by actor user ID"),
    resource_type: str | None = Query(None, description="Filter by resource type"),
    resource_id: str | None = Query(None, description="Filter by specific resource ID"),
    action: str | None = Query(None, description="Filter by action type"),
    status_filter: str | None = Query(None, alias="status", description="Filter by status"),
    start_date: str | None = Query(None, description="Filter logs after this date"),
    end_date: str | None = Query(None, description="Filter logs before this date"),
    format: str = Query("csv", pattern="^(csv|json)$", description="Export format"),
) -> Response:
    """Export audit logs (requires audit_logs:export permission)"""
    # Check permission
    rbac_service = RBACService(audit_service.db)
    await rbac_service.require_permission(current_user.id, "export", "audit_logs")

    # Parse dates if provided
    parsed_start_date = None
    parsed_end_date = None

    if start_date:
        try:
            parsed_start_date = datetime.fromisoformat(start_date)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid start_date format: {e}",
            ) from e

    if end_date:
        try:
            parsed_end_date = datetime.fromisoformat(end_date)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid end_date format: {e}",
            ) from e

    # Export logs
    exported_data = await audit_service.export_audit_logs(
        actor_id=actor_id,
        resource_type=resource_type,
        resource_id=resource_id,
        action=action,
        status=status_filter,
        start_date=parsed_start_date,
        end_date=parsed_end_date,
        format=format,
    )

    # Set content type based on format
    media_type = "text/csv" if format == "csv" else "application/json"
    filename = f"audit_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format}"

    return Response(
        content=exported_data,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get(
    "/stats",
    response_model=AuditStatsResponse,
    summary="Get audit statistics",
    description="Get audit log statistics for the specified period",
)
async def get_audit_stats(
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
    days: int = Query(30, ge=1, le=365, description="Number of days to calculate stats"),
) -> AuditStatsResponse:
    """Get audit statistics (requires audit_logs:read permission)"""
    # Check permission
    rbac_service = RBACService(audit_service.db)
    await rbac_service.require_permission(current_user.id, "read", "audit_logs")

    # Get statistics
    stats = await audit_service.get_audit_stats(days=days)

    return AuditStatsResponse(**stats)
