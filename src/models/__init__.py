"""Database models package.

This module imports all database models to ensure they are registered
with SQLAlchemy before any relationships are resolved.
"""

from src.models.audit_log import AuditLog
from src.models.auth_user import AuthUser
from src.models.organization import OrganizationGroup
from src.models.project import Project
from src.models.project_registry import ProjectRegistry
from src.models.pull_request import (
    PullRequestReviewAssignment,
    PullRequestReviewBase,
)
from src.models.rbac import UserRoleAssignment
from src.models.repository import Repository
from src.models.role import Role
from src.models.system_setting import SystemSetting
from src.models.user import User


__all__ = [
    "Project",
    "Repository",
    "User",
    "PullRequestReviewBase",
    "PullRequestReviewAssignment",
    "AuthUser",
    "Role",
    "OrganizationGroup",
    "UserRoleAssignment",
    "AuditLog",
    "ProjectRegistry",
    "SystemSetting",
]
