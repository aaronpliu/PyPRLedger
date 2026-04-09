from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from src.core.database import Base


if TYPE_CHECKING:
    from src.models.auth_user import AuthUser


class AuditLog(Base):
    """Audit log model for tracking all API requests and user actions

    Records comprehensive information about system activities for security,
    compliance, and analytics purposes. Data is exported to Prometheus/Grafana.
    """

    __tablename__ = "audit_log"

    # Primary key (using BIGINT for high volume)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # User information
    auth_user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("auth_user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="User who performed the action (NULL for system actions)",
    )

    # Action details
    action: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="Action performed (e.g., login, create_review)",
    )
    resource_type: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
        comment="Type of resource affected (review, score, user, etc.)",
    )
    resource_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        index=True,
        comment="Identifier of the resource affected",
    )

    # Change tracking
    old_values: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="Values before the change"
    )
    new_values: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="Values after the change"
    )

    # Request context
    ip_address: Mapped[str | None] = mapped_column(
        String(45), nullable=True, comment="Client IP address (supports IPv6)"
    )
    user_agent: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Browser/client user agent string"
    )
    request_method: Mapped[str | None] = mapped_column(
        String(10), nullable=True, comment="HTTP method (GET, POST, etc.)"
    )
    request_path: Mapped[str | None] = mapped_column(
        String(256), nullable=True, index=True, comment="API endpoint path"
    )
    response_status: Mapped[int | None] = mapped_column(
        Integer, nullable=True, index=True, comment="HTTP response status code"
    )

    # Performance metrics
    execution_time_ms: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Request execution time in milliseconds"
    )

    # Error information
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Error message if request failed"
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC),
        index=True,
    )

    # Relationships
    auth_user: Mapped[AuthUser | None] = relationship("AuthUser", back_populates="audit_logs")

    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, action='{self.action}', user_id={self.auth_user_id})>"

    def to_dict(self) -> dict:
        """Convert audit log to dictionary"""
        return {
            "id": self.id,
            "auth_user_id": self.auth_user_id,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "old_values": self.old_values,
            "new_values": self.new_values,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "request_method": self.request_method,
            "request_path": self.request_path,
            "response_status": self.response_status,
            "execution_time_ms": self.execution_time_ms,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat(),
        }
