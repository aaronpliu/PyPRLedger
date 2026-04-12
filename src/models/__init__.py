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
    PullRequestReview,
)  # Legacy model (kept for backward compatibility)
from src.models.rbac import UserRoleAssignment
from src.models.repository import Repository
from src.models.review import (
    PullRequestReviewAssignment,
    PullRequestReviewBase,
)  # New multi-reviewer models
from src.models.role import Role
from src.models.user import User


__all__ = [
    "Project",
    "Repository",
    "User",
    "PullRequestReview",  # Legacy
    "PullRequestReviewBase",  # New
    "PullRequestReviewAssignment",  # New
    "AuthUser",
    "Role",
    "OrganizationGroup",
    "UserRoleAssignment",
    "AuditLog",
    "ProjectRegistry",
]
