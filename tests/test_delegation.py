"""Tests for role delegation functionality"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.auth_user import AuthUser
from src.models.rbac import UserRoleAssignment
from src.models.role import Role
from src.services.rbac_service import RBACService


@pytest.fixture
async def test_roles(db: AsyncSession) -> dict[str, Role]:
    """Create test roles"""
    roles_data = [
        {
            "name": "viewer",
            "description": "Read-only access",
            "permissions": {
                "reviews": ["read"],
                "scores": ["read"],
            },
        },
        {
            "name": "reviewer",
            "description": "Can review and score",
            "permissions": {
                "reviews": ["read", "create"],
                "scores": ["read", "create", "update"],
            },
        },
        {
            "name": "review_admin",
            "description": "Admin privileges",
            "permissions": {
                "reviews": ["read", "create", "update", "delete"],
                "scores": ["read", "create", "update", "delete"],
                "users": ["read", "manage"],
                "roles": ["read", "manage"],
            },
        },
    ]

    roles = {}
    for data in roles_data:
        role = Role(**data)
        db.add(role)
        await db.flush()
        roles[data["name"]] = role

    await db.commit()
    return roles


@pytest.fixture
async def test_users(db: AsyncSession) -> dict[str, AuthUser]:
    """Create test users"""
    from src.utils.auth import hash_password

    users_data = [
        {"username": "admin_user", "email": "admin@test.com"},
        {"username": "senior_user", "email": "senior@test.com"},
        {"username": "junior_user", "email": "junior@test.com"},
    ]

    users = {}
    for data in users_data:
        user = AuthUser(
            username=data["username"],
            email=data["email"],
            password_hash=hash_password("password123"),
        )
        db.add(user)
        await db.flush()
        users[data["username"]] = user

    await db.commit()
    return users


@pytest.fixture
async def rbac_service(db: AsyncSession) -> RBACService:
    """Create RBAC service instance"""
    return RBACService(db)


class TestRoleDelegation:
    """Test suite for role delegation functionality"""

    @pytest.mark.asyncio
    async def test_create_delegation_success(
        self,
        db: AsyncSession,
        rbac_service: RBACService,
        test_roles: dict[str, Role],
        test_users: dict[str, AuthUser],
    ):
        """Test successful role delegation"""
        admin_user = test_users["admin_user"]
        junior_user = test_users["junior_user"]
        reviewer_role = test_roles["reviewer"]

        # First assign reviewer role to admin
        await rbac_service.assign_role(
            auth_user_id=admin_user.id,
            role_id=reviewer_role.id,
            resource_type="global",
            resource_id=None,
        )

        # Create delegation
        now = datetime.now(UTC)
        delegation = await rbac_service.delegate_role(
            delegator_id=admin_user.id,
            delegatee_id=junior_user.id,
            role_id=reviewer_role.id,
            resource_type="global",
            resource_id=None,
            delegation_scope={"reviews": ["read"], "scores": ["read"]},
            starts_at=now,
            expires_at=now + timedelta(days=30),
            reason="Test delegation",
        )

        assert delegation.is_delegated is True
        assert delegation.delegator_id == admin_user.id
        assert delegation.auth_user_id == junior_user.id
        assert delegation.delegation_status == "active"
        assert delegation.delegation_reason == "Test delegation"

    @pytest.mark.asyncio
    async def test_delegation_permission_subset_validation(
        self,
        db: AsyncSession,
        rbac_service: RBACService,
        test_roles: dict[str, Role],
        test_users: dict[str, AuthUser],
    ):
        """Test that delegation scope must be subset of delegator's permissions"""
        from src.core.exceptions import ForbiddenException

        senior_user = test_users["senior_user"]
        junior_user = test_users["junior_user"]
        viewer_role = test_roles["viewer"]

        # Assign viewer role to senior user (only has read permissions)
        await rbac_service.assign_role(
            auth_user_id=senior_user.id,
            role_id=viewer_role.id,
            resource_type="global",
            resource_id=None,
        )

        # Try to delegate write permissions (which senior doesn't have)
        now = datetime.now(UTC)
        with pytest.raises(ForbiddenException) as exc_info:
            await rbac_service.delegate_role(
                delegator_id=senior_user.id,
                delegatee_id=junior_user.id,
                role_id=viewer_role.id,
                resource_type="global",
                resource_id=None,
                delegation_scope={
                    "reviews": ["read", "create"],  # create not in viewer permissions
                },
                starts_at=now,
                expires_at=now + timedelta(days=30),
            )

        assert "Cannot delegate permissions you don't have" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_delegation_time_range_validation(
        self,
        db: AsyncSession,
        rbac_service: RBACService,
        test_roles: dict[str, Role],
        test_users: dict[str, AuthUser],
    ):
        """Test that expires_at must be after starts_at"""
        admin_user = test_users["admin_user"]
        junior_user = test_users["junior_user"]
        reviewer_role = test_roles["reviewer"]

        await rbac_service.assign_role(
            auth_user_id=admin_user.id,
            role_id=reviewer_role.id,
            resource_type="global",
            resource_id=None,
        )

        now = datetime.now(UTC)
        with pytest.raises(ValueError) as exc_info:
            await rbac_service.delegate_role(
                delegator_id=admin_user.id,
                delegatee_id=junior_user.id,
                role_id=reviewer_role.id,
                resource_type="global",
                resource_id=None,
                delegation_scope={"reviews": ["read"]},
                starts_at=now + timedelta(days=10),  # starts in future
                expires_at=now + timedelta(days=5),  # expires before start
            )

        assert "expires_at must be after starts_at" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_delegation_requires_delegator_has_role(
        self,
        db: AsyncSession,
        rbac_service: RBACService,
        test_roles: dict[str, Role],
        test_users: dict[str, AuthUser],
    ):
        """Test that delegator must have the role being delegated"""
        from src.core.exceptions import ForbiddenException

        senior_user = test_users["senior_user"]
        junior_user = test_users["junior_user"]
        reviewer_role = test_roles["reviewer"]

        # Senior user doesn't have reviewer role
        now = datetime.now(UTC)
        with pytest.raises(ForbiddenException) as exc_info:
            await rbac_service.delegate_role(
                delegator_id=senior_user.id,
                delegatee_id=junior_user.id,
                role_id=reviewer_role.id,
                resource_type="global",
                resource_id=None,
                delegation_scope={"reviews": ["read"]},
                starts_at=now,
                expires_at=now + timedelta(days=30),
            )

        assert "Delegator does not have this role" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_revoke_delegation(
        self,
        db: AsyncSession,
        rbac_service: RBACService,
        test_roles: dict[str, Role],
        test_users: dict[str, AuthUser],
    ):
        """Test revoking a delegation"""
        admin_user = test_users["admin_user"]
        junior_user = test_users["junior_user"]
        reviewer_role = test_roles["reviewer"]

        # Create delegation
        await rbac_service.assign_role(
            auth_user_id=admin_user.id,
            role_id=reviewer_role.id,
            resource_type="global",
            resource_id=None,
        )

        now = datetime.now(UTC)
        delegation = await rbac_service.delegate_role(
            delegator_id=admin_user.id,
            delegatee_id=junior_user.id,
            role_id=reviewer_role.id,
            resource_type="global",
            resource_id=None,
            delegation_scope={"reviews": ["read"]},
            starts_at=now,
            expires_at=now + timedelta(days=30),
        )

        # Revoke delegation
        result = await rbac_service.revoke_delegation(
            assignment_id=delegation.id,
            revoked_by=admin_user.id,
            reason="No longer needed",
        )

        assert result is True

        # Verify status updated
        from sqlalchemy import select

        stmt = select(UserRoleAssignment).where(UserRoleAssignment.id == delegation.id)
        result_obj = await db.execute(stmt)
        updated = result_obj.scalar_one()

        assert updated.delegation_status == "revoked"
        assert updated.revoked_by == admin_user.id
        assert updated.revoked_at is not None

    @pytest.mark.asyncio
    async def test_get_delegations_filter(
        self,
        db: AsyncSession,
        rbac_service: RBACService,
        test_roles: dict[str, Role],
        test_users: dict[str, AuthUser],
    ):
        """Test filtering delegations"""
        admin_user = test_users["admin_user"]
        senior_user = test_users["senior_user"]
        junior_user = test_users["junior_user"]
        reviewer_role = test_roles["reviewer"]

        await rbac_service.assign_role(
            auth_user_id=admin_user.id,
            role_id=reviewer_role.id,
            resource_type="global",
            resource_id=None,
        )

        now = datetime.now(UTC)
        # Create multiple delegations
        await rbac_service.delegate_role(
            delegator_id=admin_user.id,
            delegatee_id=senior_user.id,
            role_id=reviewer_role.id,
            resource_type="global",
            resource_id=None,
            delegation_scope={"reviews": ["read"]},
            starts_at=now,
            expires_at=now + timedelta(days=30),
        )

        await rbac_service.delegate_role(
            delegator_id=admin_user.id,
            delegatee_id=junior_user.id,
            role_id=reviewer_role.id,
            resource_type="global",
            resource_id=None,
            delegation_scope={"reviews": ["read"]},
            starts_at=now,
            expires_at=now + timedelta(days=30),
        )

        # Filter by delegator
        delegations = await rbac_service.get_delegations(delegator_id=admin_user.id)
        assert len(delegations) == 2

        # Filter by delegatee
        delegations = await rbac_service.get_delegations(delegatee_id=senior_user.id)
        assert len(delegations) == 1
        assert delegations[0]["auth_user_id"] == senior_user.id

    @pytest.mark.asyncio
    async def test_update_expired_delegations(
        self,
        db: AsyncSession,
        rbac_service: RBACService,
        test_roles: dict[str, Role],
        test_users: dict[str, AuthUser],
    ):
        """Test automatic expiration of delegations"""
        admin_user = test_users["admin_user"]
        junior_user = test_users["junior_user"]
        reviewer_role = test_roles["reviewer"]

        await rbac_service.assign_role(
            auth_user_id=admin_user.id,
            role_id=reviewer_role.id,
            resource_type="global",
            resource_id=None,
        )

        # Create delegation that already expired
        past_time = datetime.now(UTC) - timedelta(days=10)
        delegation = await rbac_service.delegate_role(
            delegator_id=admin_user.id,
            delegatee_id=junior_user.id,
            role_id=reviewer_role.id,
            resource_type="global",
            resource_id=None,
            delegation_scope={"reviews": ["read"]},
            starts_at=past_time - timedelta(days=20),
            expires_at=past_time,  # Already expired
        )

        # Update expired delegations
        count = await rbac_service.update_expired_delegations()

        assert count >= 1

        # Verify status changed
        from sqlalchemy import select

        stmt = select(UserRoleAssignment).where(UserRoleAssignment.id == delegation.id)
        result = await db.execute(stmt)
        updated = result.scalar_one()

        assert updated.delegation_status == "expired"

    @pytest.mark.asyncio
    async def test_delegation_pending_status(
        self,
        db: AsyncSession,
        rbac_service: RBACService,
        test_roles: dict[str, Role],
        test_users: dict[str, AuthUser],
    ):
        """Test delegation with future start time has 'pending' status"""
        admin_user = test_users["admin_user"]
        junior_user = test_users["junior_user"]
        reviewer_role = test_roles["reviewer"]

        await rbac_service.assign_role(
            auth_user_id=admin_user.id,
            role_id=reviewer_role.id,
            resource_type="global",
            resource_id=None,
        )

        future_time = datetime.now(UTC) + timedelta(days=7)
        delegation = await rbac_service.delegate_role(
            delegator_id=admin_user.id,
            delegatee_id=junior_user.id,
            role_id=reviewer_role.id,
            resource_type="global",
            resource_id=None,
            delegation_scope={"reviews": ["read"]},
            starts_at=future_time,
            expires_at=future_time + timedelta(days=30),
        )

        assert delegation.delegation_status == "pending"

    @pytest.mark.asyncio
    async def test_activate_pending_delegations(
        self,
        db: AsyncSession,
        rbac_service: RBACService,
        test_roles: dict[str, Role],
        test_users: dict[str, AuthUser],
    ):
        """Test automatic activation of pending delegations when start time is reached"""
        from sqlalchemy import select

        admin_user = test_users["admin_user"]
        junior_user = test_users["junior_user"]
        reviewer_role = test_roles["reviewer"]

        await rbac_service.assign_role(
            auth_user_id=admin_user.id,
            role_id=reviewer_role.id,
            resource_type="global",
            resource_id=None,
        )

        # Create delegation with past start time (should be activated)
        past_start = datetime.now(UTC) - timedelta(hours=1)
        delegation = await rbac_service.delegate_role(
            delegator_id=admin_user.id,
            delegatee_id=junior_user.id,
            role_id=reviewer_role.id,
            resource_type="global",
            resource_id=None,
            delegation_scope={"reviews": ["read"]},
            starts_at=past_start,
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )

        # Verify it was created as active (since start time is in the past)
        assert delegation.delegation_status == "active"

        # Now test manual pending -> active transition
        # Create a delegation and manually set it to pending
        future_start = datetime.now(UTC) + timedelta(days=1)
        delegation2 = await rbac_service.delegate_role(
            delegator_id=admin_user.id,
            delegatee_id=junior_user.id,
            role_id=reviewer_role.id,
            resource_type="project",
            resource_id="TEST-PROJ",
            delegation_scope={"reviews": ["read"]},
            starts_at=future_start,
            expires_at=future_start + timedelta(days=30),
        )

        # Verify it's pending
        assert delegation2.delegation_status == "pending"

        # Manually update starts_at to past to simulate time passing
        stmt = select(UserRoleAssignment).where(UserRoleAssignment.id == delegation2.id)
        result = await db.execute(stmt)
        assignment = result.scalar_one()
        assignment.starts_at = datetime.now(UTC) - timedelta(hours=1)
        await db.commit()

        # Activate pending delegations
        count = await rbac_service.activate_pending_delegations()

        assert count >= 1

        # Verify status changed to active
        stmt = select(UserRoleAssignment).where(UserRoleAssignment.id == delegation2.id)
        result = await db.execute(stmt)
        updated = result.scalar_one()

        assert updated.delegation_status == "active"

    @pytest.mark.asyncio
    async def test_prevent_duplicate_active_delegation(
        self,
        db: AsyncSession,
        rbac_service: RBACService,
        test_roles: dict[str, Role],
        test_users: dict[str, AuthUser],
    ):
        """Test that duplicate active delegations are prevented"""
        from src.core.exceptions import ForbiddenException

        admin_user = test_users["admin_user"]
        junior_user = test_users["junior_user"]
        reviewer_role = test_roles["reviewer"]

        await rbac_service.assign_role(
            auth_user_id=admin_user.id,
            role_id=reviewer_role.id,
            resource_type="global",
            resource_id=None,
        )

        now = datetime.now(UTC)
        # Create first delegation
        await rbac_service.delegate_role(
            delegator_id=admin_user.id,
            delegatee_id=junior_user.id,
            role_id=reviewer_role.id,
            resource_type="global",
            resource_id=None,
            delegation_scope={"reviews": ["read"]},
            starts_at=now,
            expires_at=now + timedelta(days=30),
        )

        # Try to create duplicate
        with pytest.raises(ForbiddenException) as exc_info:
            await rbac_service.delegate_role(
                delegator_id=admin_user.id,
                delegatee_id=junior_user.id,
                role_id=reviewer_role.id,
                resource_type="global",
                resource_id=None,
                delegation_scope={"reviews": ["read"]},
                starts_at=now,
                expires_at=now + timedelta(days=30),
            )

        assert "Delegation already exists" in str(exc_info.value)
