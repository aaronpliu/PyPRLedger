"""RBAC (Role-Based Access Control) service for permission management"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import ForbiddenException
from src.models.rbac import UserRoleAssignment
from src.models.role import Role


if TYPE_CHECKING:
    from datetime import datetime

logger = logging.getLogger(__name__)


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

        logger.debug(
            f"Checking permission: user={auth_user_id}, action={action}, "
            f"resource_type={resource_type}, found {len(assignments)} assignments"
        )

        # Filter out expired assignments
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        active_assignments = [a for a in assignments if not a.expires_at or a.expires_at > now]

        if not active_assignments:
            logger.warning(f"User {auth_user_id} has no active role assignments")
            return False

        # Check permissions by level (repository > project > global)
        for level in ["repository", "project", "global"]:
            if level == "global":
                # For global level, match assignments where resource_id is NULL or empty string
                level_assignments = [
                    a
                    for a in active_assignments
                    if a.resource_type == level and (a.resource_id is None or a.resource_id == "")
                ]
            else:
                # For project/repository level, match specific resource_id
                level_assignments = [
                    a
                    for a in active_assignments
                    if a.resource_type == level and a.resource_id == resource_id
                ]

            logger.debug(f"Level {level}: found {len(level_assignments)} assignments")

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

                logger.debug(
                    f"Checking role '{role.name}' (ID: {role.id}): "
                    f"permissions={list(permissions.keys())}"
                )

                # Check if action is allowed for this resource type
                resource_permissions = permissions.get(resource_type, [])

                if action in resource_permissions:
                    logger.info(
                        f"✓ Permission granted: user={auth_user_id}, "
                        f"action={action}, resource_type={resource_type}, "
                        f"role={role.name}"
                    )
                    return True

        logger.warning(
            f"✗ Permission denied: user={auth_user_id}, action={action}, "
            f"resource_type={resource_type}"
        )
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
                "auth_user_id": assignment.auth_user_id,
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

    # ========================================================================
    # Delegation Methods
    # ========================================================================

    async def delegate_role(
        self,
        delegator_id: int,
        delegatee_id: int,
        role_id: int,
        resource_type: str,
        resource_id: str | None,
        delegation_scope: dict,
        starts_at: datetime,
        expires_at: datetime,
        reason: str | None = None,
    ) -> UserRoleAssignment:
        """Delegate a role from senior user to junior user

        Rules:
        1. Delegator must have the role with same resource_type/resource_id
        2. delegation_scope must be subset of delegator's permissions
        3. starts_at < expires_at
        4. No delegation chains (delegatee cannot re-delegate)
        5. Cannot delegate across different resource types

        Args:
            delegator_id: User who delegates the role
            delegatee_id: User who receives the delegated role
            role_id: Role to delegate
            resource_type: Resource type (must match delegator's)
            resource_id: Resource identifier
            delegation_scope: Specific permissions to delegate
            starts_at: Delegation start time
            expires_at: Delegation end time
            reason: Reason for delegation

        Returns:
            Created UserRoleAssignment with delegation info

        Raises:
            ForbiddenException: If validation fails
            ValueError: If time range is invalid
        """
        from datetime import UTC
        from datetime import datetime as dt

        now = dt.now(UTC)

        # 1. Validate time range
        if starts_at >= expires_at:
            raise ValueError("expires_at must be after starts_at")

        # 2. Check delegator has the role with same resource scope
        delegator_has_role = await self._check_user_has_role(
            delegator_id, role_id, resource_type, resource_id
        )

        if not delegator_has_role:
            raise ForbiddenException(
                message="Delegator does not have this role with the specified resource scope",
                detail={
                    "delegator_id": delegator_id,
                    "role_id": role_id,
                    "resource_type": resource_type,
                    "resource_id": resource_id,
                },
            )

        # 3. Validate delegation_scope is subset of delegator's permissions
        logger.info(f"Validating delegation scope for user {delegator_id}, role {role_id}")

        delegator_permissions = await self._get_user_permissions_for_role(
            delegator_id, role_id, resource_type, resource_id
        )

        logger.info(f"Delegator permissions: {delegator_permissions}")
        logger.info(f"Requested delegation scope: {delegation_scope}")

        if not self._is_permission_subset(delegation_scope, delegator_permissions):
            logger.error(
                f"Permission subset validation failed:\n"
                f"  Requested: {delegation_scope}\n"
                f"  Available: {delegator_permissions}"
            )
            raise ForbiddenException(
                message="Cannot delegate permissions you don't have",
                detail={
                    "requested_scope": delegation_scope,
                    "available_permissions": delegator_permissions,
                },
            )

        # 4. Check delegatee doesn't already have this delegation
        stmt = select(UserRoleAssignment).where(
            and_(
                UserRoleAssignment.auth_user_id == delegatee_id,
                UserRoleAssignment.role_id == role_id,
                UserRoleAssignment.delegator_id == delegator_id,
                UserRoleAssignment.resource_type == resource_type,
                UserRoleAssignment.resource_id == resource_id,
                UserRoleAssignment.is_delegated == True,
            )
        )
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            # Check if it's expired/revoked, allow re-delegation
            if existing.delegation_status in ["expired", "revoked"]:
                logger.info(
                    f"Re-delegating role {role_id} from {delegator_id} to {delegatee_id} "
                    f"(previous delegation was {existing.delegation_status})"
                )
            else:
                raise ForbiddenException(
                    message="Delegation already exists and is active",
                    detail={"assignment_id": existing.id},
                )

        # 5. Determine initial status
        delegation_status = "pending" if starts_at > now else "active"

        # 6. Create delegation assignment
        assignment = UserRoleAssignment(
            auth_user_id=delegatee_id,
            role_id=role_id,
            resource_type=resource_type,
            resource_id=resource_id,
            granted_by=delegator_id,
            delegator_id=delegator_id,
            is_delegated=True,
            delegation_status=delegation_status,
            delegation_scope=delegation_scope,
            delegation_reason=reason,
            starts_at=starts_at,
            expires_at=expires_at,
        )

        self.db.add(assignment)
        await self.db.commit()
        await self.db.refresh(assignment)

        logger.info(
            f"Created delegation: {delegator_id} -> {delegatee_id}, "
            f"role={role_id}, status={delegation_status}"
        )

        # TODO: Send notification to delegatee
        # - Email notification (integrate with third-party email service)
        # - In-site message (when message module is available)
        # await self._send_delegation_notification(delegatee_id, delegator_id, role_id, starts_at, expires_at)

        return assignment

    async def revoke_delegation(
        self,
        assignment_id: int,
        revoked_by: int,
        reason: str | None = None,
    ) -> bool:
        """Revoke a delegation

        Args:
            assignment_id: The delegation assignment ID
            revoked_by: User who is revoking (must be delegator or admin)
            reason: Reason for revocation

        Returns:
            True if revoked, False if not found

        Raises:
            ForbiddenException: If user doesn't have permission to revoke
        """
        from datetime import UTC
        from datetime import datetime as dt

        stmt = select(UserRoleAssignment).where(
            and_(
                UserRoleAssignment.id == assignment_id,
                UserRoleAssignment.is_delegated == True,
            )
        )
        result = await self.db.execute(stmt)
        assignment = result.scalar_one_or_none()

        if not assignment:
            return False

        # Check if already revoked/expired
        if assignment.delegation_status in ["revoked", "expired"]:
            logger.warning(f"Delegation {assignment_id} is already {assignment.delegation_status}")
            return False

        # Only delegator or admin can revoke
        if assignment.delegator_id != revoked_by:
            is_admin = await self.check_permission(revoked_by, "manage", "roles")
            if not is_admin:
                raise ForbiddenException(message="Only delegator or admin can revoke delegation")

        # Update status
        now = dt.now(UTC)
        assignment.delegation_status = "revoked"
        assignment.revoked_by = revoked_by
        assignment.revoked_at = now

        await self.db.commit()

        logger.info(
            f"Revoked delegation {assignment_id}: {assignment.delegator_id} -> "
            f"{assignment.auth_user_id}, revoked_by={revoked_by}"
        )

        # TODO: Send revocation notification
        # await self._send_revocation_notification(assignment.auth_user_id, revoked_by, reason)

        return True

    async def get_delegations(
        self,
        delegator_id: int | None = None,
        delegatee_id: int | None = None,
        status: str | None = None,
        include_expired: bool = False,
    ) -> list[dict]:
        """Get delegation list with filters

        Args:
            delegator_id: Filter by delegator
            delegatee_id: Filter by delegatee
            status: Filter by status (active/expired/revoked/pending)
            include_expired: Include expired/revoked delegations

        Returns:
            List of delegation records with role details
        """
        stmt = (
            select(UserRoleAssignment, Role)
            .join(Role, UserRoleAssignment.role_id == Role.id)
            .where(UserRoleAssignment.is_delegated == True)
        )

        if delegator_id:
            stmt = stmt.where(UserRoleAssignment.delegator_id == delegator_id)
        if delegatee_id:
            stmt = stmt.where(UserRoleAssignment.auth_user_id == delegatee_id)
        if status:
            stmt = stmt.where(UserRoleAssignment.delegation_status == status)

        # By default, exclude expired/revoked unless explicitly requested
        if not include_expired and not status:
            stmt = stmt.where(UserRoleAssignment.delegation_status.in_(["active", "pending"]))

        stmt = stmt.order_by(UserRoleAssignment.created_at.desc())

        result = await self.db.execute(stmt)
        delegations = result.all()

        return [
            {
                "id": assignment.id,
                "auth_user_id": assignment.auth_user_id,  # delegatee
                "role_id": assignment.role_id,
                "role_name": role.name,
                "resource_type": assignment.resource_type,
                "resource_id": assignment.resource_id,
                "granted_by": assignment.granted_by,
                "delegator_id": assignment.delegator_id,
                "is_delegated": assignment.is_delegated,
                "delegation_status": assignment.delegation_status,
                "delegation_scope": assignment.delegation_scope,
                "delegation_reason": assignment.delegation_reason,
                "starts_at": assignment.starts_at.isoformat() if assignment.starts_at else None,
                "expires_at": assignment.expires_at.isoformat() if assignment.expires_at else None,
                "revoked_by": assignment.revoked_by,
                "revoked_at": assignment.revoked_at.isoformat() if assignment.revoked_at else None,
                "created_at": assignment.created_at.isoformat(),
            }
            for assignment, role in delegations
        ]

    async def update_expired_delegations(self) -> int:
        """Update status of expired delegations

        This should be called periodically (e.g., via cron job) to mark
        expired delegations as 'expired'.

        Returns:
            Number of delegations updated
        """
        from datetime import UTC
        from datetime import datetime as dt

        now = dt.now(UTC)

        stmt = select(UserRoleAssignment).where(
            and_(
                UserRoleAssignment.is_delegated == True,
                UserRoleAssignment.delegation_status == "active",
                UserRoleAssignment.expires_at <= now,
            )
        )
        result = await self.db.execute(stmt)
        expired_assignments = result.scalars().all()

        count = 0
        for assignment in expired_assignments:
            assignment.delegation_status = "expired"
            count += 1

        if count > 0:
            await self.db.commit()
            logger.info(f"Marked {count} delegations as expired")

        return count

    # ========================================================================
    # Delegation Helper Methods
    # ========================================================================

    async def _check_user_has_role(
        self,
        user_id: int,
        role_id: int,
        resource_type: str,
        resource_id: str | None,
    ) -> bool:
        """Check if user has a specific role with given resource scope

        For 'global' resource type, resource_id should be NULL or empty string.
        Both NULL and empty string are treated as equivalent for global scope.
        """
        from sqlalchemy import or_

        # Build conditions
        conditions = [
            UserRoleAssignment.auth_user_id == user_id,
            UserRoleAssignment.role_id == role_id,
            UserRoleAssignment.resource_type == resource_type,
        ]

        # Handle resource_id matching (None and '' are equivalent for global)
        if resource_type == "global":
            # For global scope, match both NULL and empty string
            conditions.append(
                or_(
                    UserRoleAssignment.resource_id.is_(None),
                    UserRoleAssignment.resource_id == "",
                )
            )
        else:
            # For project/repository, exact match required
            conditions.append(UserRoleAssignment.resource_id == resource_id)

        stmt = select(UserRoleAssignment).where(and_(*conditions))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def _get_user_permissions_for_role(
        self,
        user_id: int,
        role_id: int,
        resource_type: str,
        resource_id: str | None,
    ) -> dict:
        """Get permissions for a user's specific role assignment

        First verifies that the user actually has this role with the specified
        resource scope, then returns the role's permissions.
        """
        logger.debug(
            f"Getting permissions for user {user_id}, role {role_id}, "
            f"resource_type={resource_type}, resource_id={resource_id}"
        )

        # 1. Verify user has this role with the specified resource scope
        has_role = await self._check_user_has_role(user_id, role_id, resource_type, resource_id)

        logger.debug(f"User {user_id} has role {role_id}: {has_role}")

        if not has_role:
            logger.warning(
                f"User {user_id} does not have role {role_id} with "
                f"resource_type={resource_type}, resource_id={resource_id}"
            )
            return {}

        # 2. Get role definition and return its permissions
        stmt = select(Role).where(Role.id == role_id)
        result = await self.db.execute(stmt)
        role = result.scalar_one_or_none()

        if not role:
            logger.error(f"Role {role_id} not found in database")
            return {}

        permissions = role.permissions
        if isinstance(permissions, str):
            import json

            permissions = json.loads(permissions)

        logger.info(
            f"✓ User {user_id} has role '{role.name}' (ID: {role_id}) with permissions: {list(permissions.keys())}"
        )
        return permissions

    def _is_permission_subset(self, subset: dict, superset: dict) -> bool:
        """Check if subset permissions are within superset

        Args:
            subset: Requested permissions to delegate
            superset: Available permissions from delegator

        Returns:
            True if all subset permissions exist in superset
        """
        for resource, actions in subset.items():
            if resource not in superset:
                return False
            if not set(actions).issubset(set(superset[resource])):
                return False
        return True
