"""RBAC (Role-Based Access Control) service for permission management"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import ForbiddenException
from src.models.rbac import UserRoleAssignment
from src.models.role import Role


if TYPE_CHECKING:
    from datetime import datetime


class RBACService:
    """Service class for RBAC permission checks and management"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def check_permission(
        self,
        auth_user_id: int,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
    ) -> bool:
        """Check if user has permission to perform action on resource

        Permission check order (highest priority first):
        1. Repository-level permissions
        2. Project-level permissions
        3. Global-level permissions

        Args:
            auth_user_id: User ID
            action: Action to check (read, create, update, delete, manage)
            resource_type: Resource type (reviews, scores, projects, repositories, users, etc.)
            resource_id: Resource identifier (project_key or repository_slug)

        Returns:
            True if user has permission, False otherwise
        """
        # Get all active role assignments for user
        stmt = (
            select(UserRoleAssignment)
            .join(Role, UserRoleAssignment.role_id == Role.id)
            .where(
                UserRoleAssignment.auth_user_id == auth_user_id,
            )
        )
        result = await self.db.execute(stmt)
        assignments = result.scalars().all()

        # Filter out expired assignments
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        active_assignments = [a for a in assignments if not a.expires_at or a.expires_at > now]

        if not active_assignments:
            return False

        # Check permissions by level (repository > project > global)
        for level in ["repository", "project", "global"]:
            if level == "global":
                # For global level, match assignments where resource_id is NULL/None
                level_assignments = [
                    a
                    for a in active_assignments
                    if a.resource_type == level and a.resource_id is None
                ]
            else:
                # For project/repository level, match specific resource_id
                level_assignments = [
                    a
                    for a in active_assignments
                    if a.resource_type == level and a.resource_id == resource_id
                ]

            for assignment in level_assignments:
                # Get role permissions
                role_stmt = select(Role).where(Role.id == assignment.role_id)
                role_result = await self.db.execute(role_stmt)
                role = role_result.scalar_one_or_none()

                if not role:
                    continue

                # Parse permissions (may be string or dict depending on DB driver)
                permissions = role.permissions
                if isinstance(permissions, str):
                    import json

                    permissions = json.loads(permissions)

                # Check if action is allowed for this resource type
                resource_permissions = permissions.get(resource_type, [])

                if action in resource_permissions:
                    return True

        return False

    async def require_permission(
        self,
        auth_user_id: int,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
    ) -> None:
        """Require permission or raise ForbiddenException

        Args:
            auth_user_id: User ID
            action: Action to check
            resource_type: Resource type
            resource_id: Resource identifier

        Raises:
            ForbiddenException: If user doesn't have permission
        """
        has_permission = await self.check_permission(
            auth_user_id, action, resource_type, resource_id
        )

        if not has_permission:
            raise ForbiddenException(
                message=f"No permission to {action} {resource_type}",
                detail={
                    "action": action,
                    "resource_type": resource_type,
                    "resource_id": resource_id,
                },
            )

    async def get_user_roles(
        self, auth_user_id: int, resource_type: str | None = None
    ) -> list[dict]:
        """Get all roles assigned to user

        Args:
            auth_user_id: User ID
            resource_type: Optional filter by resource type

        Returns:
            List of role assignments with role details
        """
        stmt = (
            select(UserRoleAssignment, Role)
            .join(Role, UserRoleAssignment.role_id == Role.id)
            .where(UserRoleAssignment.auth_user_id == auth_user_id)
        )

        if resource_type:
            stmt = stmt.where(UserRoleAssignment.resource_type == resource_type)

        result = await self.db.execute(stmt)
        assignments = result.all()

        return [
            {
                "id": assignment.id,
                "role_id": assignment.role_id,
                "role_name": role.name,
                "resource_type": assignment.resource_type,
                "resource_id": assignment.resource_id,
                "granted_by": assignment.granted_by,
                "expires_at": (
                    assignment.expires_at.isoformat() if assignment.expires_at else None
                ),
                "created_at": assignment.created_at.isoformat(),
            }
            for assignment, role in assignments
        ]

    async def assign_role(
        self,
        auth_user_id: int,
        role_id: int,
        resource_type: str,
        resource_id: str | None = None,
        granted_by: int | None = None,
        expires_at: datetime | None = None,
    ) -> UserRoleAssignment:
        """Assign a role to user

        Args:
            auth_user_id: User to assign role to
            role_id: Role ID
            resource_type: Resource scope (global, project, repository)
            resource_id: Resource identifier (optional for global)
            granted_by: User who granted the role
            expires_at: Optional expiration time

        Returns:
            Created UserRoleAssignment

        Raises:
            ForbiddenException: If assignment already exists
        """
        # Check if assignment already exists
        stmt = select(UserRoleAssignment).where(
            UserRoleAssignment.auth_user_id == auth_user_id,
            UserRoleAssignment.role_id == role_id,
            UserRoleAssignment.resource_type == resource_type,
            UserRoleAssignment.resource_id == resource_id,
        )
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            raise ForbiddenException(
                message="Role assignment already exists",
                detail={
                    "auth_user_id": auth_user_id,
                    "role_id": role_id,
                    "resource_type": resource_type,
                },
            )

        # Create new assignment
        assignment = UserRoleAssignment(
            auth_user_id=auth_user_id,
            role_id=role_id,
            resource_type=resource_type,
            resource_id=resource_id,
            granted_by=granted_by,
            expires_at=expires_at,
        )

        self.db.add(assignment)
        await self.db.commit()
        await self.db.refresh(assignment)

        return assignment

    async def revoke_role(
        self,
        auth_user_id: int,
        role_id: int,
        resource_type: str,
        resource_id: str | None = None,
    ) -> bool:
        """Revoke a role from user

        Args:
            auth_user_id: User to revoke role from
            role_id: Role ID
            resource_type: Resource scope
            resource_id: Resource identifier

        Returns:
            True if role was revoked, False if not found
        """
        stmt = select(UserRoleAssignment).where(
            UserRoleAssignment.auth_user_id == auth_user_id,
            UserRoleAssignment.role_id == role_id,
            UserRoleAssignment.resource_type == resource_type,
            UserRoleAssignment.resource_id == resource_id,
        )
        result = await self.db.execute(stmt)
        assignment = result.scalar_one_or_none()

        if not assignment:
            return False

        await self.db.delete(assignment)
        await self.db.commit()

        return True

    async def get_all_roles(self) -> list[Role]:
        """Get all available roles

        Returns:
            List of all roles
        """
        stmt = select(Role).order_by(Role.id)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_role_by_id(self, role_id: int) -> Role | None:
        """Get role by ID

        Args:
            role_id: Role ID

        Returns:
            Role object or None
        """
        stmt = select(Role).where(Role.id == role_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
