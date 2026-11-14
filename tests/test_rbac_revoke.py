"""The system_admin role assignment survives every revoke attempt."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import ForbiddenException
from src.models.auth_user import AuthUser
from src.models.role import Role
from src.services.rbac_service import RBACService
from src.utils.password import hash_password


@pytest.fixture
async def rbac_service(db: AsyncSession) -> RBACService:
    return RBACService(db)


@pytest.fixture
async def admin_user(db: AsyncSession) -> AuthUser:
    user = AuthUser(
        username="sys_admin_holder",
        email="sysadmin@test.com",
        password_hash=hash_password("password123"),
    )
    db.add(user)
    await db.commit()
    return user


@pytest.fixture
async def roles(db: AsyncSession) -> dict[str, Role]:
    roles = {}
    for name in ("system_admin", "viewer"):
        role = Role(name=name, description=name)
        db.add(role)
        await db.flush()
        roles[name] = role
    await db.commit()
    return roles


@pytest.mark.asyncio
async def test_system_admin_role_cannot_be_revoked(
    db: AsyncSession, rbac_service: RBACService, admin_user: AuthUser, roles: dict[str, Role]
):
    await rbac_service.assign_role(
        auth_user_id=admin_user.id,
        role_id=roles["system_admin"].id,
        resource_type="global",
        resource_id=None,
    )

    with pytest.raises(ForbiddenException):
        await rbac_service.revoke_role(
            auth_user_id=admin_user.id,
            role_id=roles["system_admin"].id,
            resource_type="global",
            resource_id=None,
        )

    # the assignment is still there
    remaining = await rbac_service.get_user_roles(admin_user.id)
    assert [item["role_name"] for item in remaining] == ["system_admin"]


@pytest.mark.asyncio
async def test_other_roles_still_revocable(
    db: AsyncSession, rbac_service: RBACService, admin_user: AuthUser, roles: dict[str, Role]
):
    await rbac_service.assign_role(
        auth_user_id=admin_user.id,
        role_id=roles["viewer"].id,
        resource_type="global",
        resource_id=None,
    )

    assert await rbac_service.revoke_role(
        auth_user_id=admin_user.id,
        role_id=roles["viewer"].id,
        resource_type="global",
        resource_id=None,
    )
    assert await rbac_service.get_user_roles(admin_user.id) == []
