"""Audit logging service for tracking system actions"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.audit_log import AuditLog


if TYPE_CHECKING:
    pass


class AuditService:
    """Service class for audit logging operations"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def log_action(
        self,
        auth_user_id: int | None,
        action: str,
        resource_type: str | None = None,
        resource_id: str | None = None,
        old_values: dict | None = None,
        new_values: dict | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        request_method: str | None = None,
        request_path: str | None = None,
        response_status: int | None = None,
        execution_time_ms: int | None = None,
        error_message: str | None = None,
    ) -> AuditLog:
        """Log an action to audit trail

        Args:
            auth_user_id: User ID who performed the action (None for system actions)
            action: Action type (create, update, delete, login, etc.)
            resource_type: Type of resource affected (reviews, scores, users, etc.)
            resource_id: Identifier of the specific resource
            old_values: Previous state of the resource (for updates)
            new_values: New state of the resource (for creates/updates)
            ip_address: Client IP address
            user_agent: Client user agent string
            request_method: HTTP method (GET, POST, etc.)
            request_path: API endpoint path
            response_status: HTTP response status code
            execution_time_ms: Request execution time in milliseconds
            error_message: Error details if action failed

        Returns:
            Created AuditLog instance
        """
        audit_log = AuditLog(
            auth_user_id=auth_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            old_values=old_values,
            new_values=new_values,
            ip_address=ip_address,
            user_agent=user_agent,
            request_method=request_method,
            request_path=request_path,
            response_status=response_status,
            execution_time_ms=execution_time_ms,
            error_message=error_message,
        )

        self.db.add(audit_log)
        await self.db.commit()
        await self.db.refresh(audit_log)

        return audit_log

    async def get_audit_logs(
        self,
        auth_user_id: int | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        action: str | None = None,
        request_method: str | None = None,
        response_status: int | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[AuditLog], int]:
        """Query audit logs with filters

        Args:
            auth_user_id: Filter by user ID
            resource_type: Filter by resource type
            resource_id: Filter by specific resource ID
            action: Filter by action type
            request_method: Filter by HTTP method
            response_status: Filter by HTTP status code
            start_date: Filter logs after this date
            end_date: Filter logs before this date
            limit: Maximum number of results
            offset: Pagination offset

        Returns:
            Tuple of (list of AuditLog, total count)
        """
        # Build base query
        stmt = select(AuditLog)
        count_stmt = select(func.count(AuditLog.id))

        # Apply filters
        conditions = []

        if auth_user_id is not None:
            conditions.append(AuditLog.auth_user_id == auth_user_id)

        if resource_type is not None:
            conditions.append(AuditLog.resource_type == resource_type)

        if resource_id is not None:
            conditions.append(AuditLog.resource_id == resource_id)

        if action is not None:
            conditions.append(AuditLog.action == action)

        if request_method is not None:
            conditions.append(AuditLog.request_method == request_method)

        if response_status is not None:
            conditions.append(AuditLog.response_status == response_status)

        if start_date is not None:
            conditions.append(AuditLog.created_at >= start_date)

        if end_date is not None:
            conditions.append(AuditLog.created_at <= end_date)

        if conditions:
            stmt = stmt.where(and_(*conditions))
            count_stmt = count_stmt.where(and_(*conditions))

        # Get total count
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar_one()

        # Apply ordering and pagination
        stmt = stmt.order_by(desc(AuditLog.created_at))
        stmt = stmt.limit(limit).offset(offset)

        # Execute query
        result = await self.db.execute(stmt)
        logs = result.scalars().all()

        return list(logs), total

    async def get_audit_log_by_id(self, log_id: int) -> AuditLog | None:
        """Get specific audit log entry by ID

        Args:
            log_id: Audit log ID

        Returns:
            AuditLog instance or None if not found
        """
        stmt = select(AuditLog).where(AuditLog.id == log_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def export_audit_logs(
        self,
        auth_user_id: int | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        action: str | None = None,
        request_method: str | None = None,
        response_status: int | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        format: str = "csv",
    ) -> bytes:
        """Export audit logs as CSV or JSON

        Args:
            auth_user_id: Filter by user ID
            resource_type: Filter by resource type
            resource_id: Filter by specific resource ID
            action: Filter by action type
            request_method: Filter by HTTP method
            response_status: Filter by HTTP status code
            start_date: Filter logs after this date
            end_date: Filter logs before this date
            format: Export format (csv or json)

        Returns:
            Exported data as bytes
        """
        # Get all matching logs (no pagination for export)
        logs, _ = await self.get_audit_logs(
            auth_user_id=auth_user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            request_method=request_method,
            response_status=response_status,
            start_date=start_date,
            end_date=end_date,
            limit=10000,  # Reasonable limit for export
            offset=0,
        )

        if format.lower() == "json":
            return self._export_json(logs)
        else:
            return self._export_csv(logs)

    def _export_csv(self, logs: list[AuditLog]) -> bytes:
        """Export logs as CSV"""
        output = io.StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow(
            [
                "ID",
                "User ID",
                "Action",
                "Resource Type",
                "Resource ID",
                "Method",
                "Path",
                "Status",
                "IP Address",
                "Execution Time (ms)",
                "Timestamp",
                "Error Message",
            ]
        )

        # Write data rows
        for log in logs:
            writer.writerow(
                [
                    log.id,
                    log.auth_user_id or "",
                    log.action,
                    log.resource_type or "",
                    log.resource_id or "",
                    log.request_method or "",
                    log.request_path or "",
                    log.response_status or "",
                    log.ip_address or "",
                    log.execution_time_ms or "",
                    log.created_at.isoformat(),
                    log.error_message or "",
                ]
            )

        return output.getvalue().encode("utf-8")

    def _export_json(self, logs: list[AuditLog]) -> bytes:
        """Export logs as JSON"""
        data = [
            {
                "id": log.id,
                "auth_user_id": log.auth_user_id,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "old_values": log.old_values,
                "new_values": log.new_values,
                "ip_address": log.ip_address,
                "user_agent": log.user_agent,
                "request_method": log.request_method,
                "request_path": log.request_path,
                "response_status": log.response_status,
                "execution_time_ms": log.execution_time_ms,
                "error_message": log.error_message,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ]

        return json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")

    async def get_audit_stats(
        self,
        days: int = 30,
    ) -> dict:
        """Get audit statistics for the specified period

        Args:
            days: Number of days to calculate stats for

        Returns:
            Dictionary with statistics
        """
        from datetime import timedelta

        start_date = datetime.now() - timedelta(days=days)

        # Total actions
        total_stmt = select(func.count(AuditLog.id)).where(AuditLog.created_at >= start_date)
        total_result = await self.db.execute(total_stmt)
        total_actions = total_result.scalar_one()

        # Actions by HTTP method
        method_stmt = (
            select(AuditLog.request_method, func.count(AuditLog.id))
            .where(AuditLog.created_at >= start_date)
            .group_by(AuditLog.request_method)
        )
        method_result = await self.db.execute(method_stmt)
        actions_by_method = {row[0]: row[1] for row in method_result.all() if row[0]}

        # Actions by type
        action_stmt = (
            select(AuditLog.action, func.count(AuditLog.id))
            .where(AuditLog.created_at >= start_date)
            .group_by(AuditLog.action)
        )
        action_result = await self.db.execute(action_stmt)
        actions_by_type = {row[0]: row[1] for row in action_result.all()}

        # Actions by status code
        status_stmt = (
            select(AuditLog.response_status, func.count(AuditLog.id))
            .where(AuditLog.created_at >= start_date)
            .group_by(AuditLog.response_status)
        )
        status_result = await self.db.execute(status_stmt)
        actions_by_status = {str(row[0]): row[1] for row in status_result.all() if row[0]}

        # Top actors
        actor_stmt = (
            select(AuditLog.auth_user_id, func.count(AuditLog.id))
            .where(AuditLog.created_at >= start_date)
            .group_by(AuditLog.auth_user_id)
            .order_by(desc(func.count(AuditLog.id)))
            .limit(10)
        )
        actor_result = await self.db.execute(actor_stmt)
        top_actors = [
            {"user_id": row[0], "action_count": row[1]} for row in actor_result.all() if row[0]
        ]

        return {
            "period_days": days,
            "total_actions": total_actions,
            "actions_by_method": actions_by_method,
            "actions_by_type": actions_by_type,
            "actions_by_status": actions_by_status,
            "top_actors": top_actors,
        }
