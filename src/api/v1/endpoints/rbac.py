"""RBAC management API endpoints"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.core.permissions import get_current_user_with_token
from src.models.auth_user import AuthUser
from src.schemas.rbac import (
    RoleAssignmentRequest,
    RoleAssignmentResponse,
    RoleCreate,
    RoleResponse,
    RoleUpdate,
)
from src.services.rbac_service import RBACService


router = APIRouter(prefix="/rbac", tags=["RBAC Management"])


def get_rbac_service(db: Annotated[AsyncSession, Depends(get_db_session)]) -> RBACService:
    """Dependency to get RBAC service instance"""
    return RBACService(db)


# Role Management Endpoints
@router.get(
    "/roles",
    response_model=list[RoleResponse],
    summary="Get all roles",
    description="List all available roles in the system",
)
async def list_roles(
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    rbac_service: Annotated[RBACService, Depends(get_rbac_service)],
) -> list[RoleResponse]:
    """List all roles (requires system admin)"""
    # Check if user has system admin permission
    await rbac_service.require_permission(current_user.id, "manage", "settings")

    roles = await rbac_service.get_all_roles()
    return [
        RoleResponse(
            id=role.id,
            name=role.name,
            description=role.description,
            permissions=role.permissions,
            created_at=role.created_at.isoformat(),
        )
        for role in roles
    ]


@router.get(
    "/roles/{role_id}",
    response_model=RoleResponse,
    summary="Get role by ID",
    description="Get details of a specific role",
)
async def get_role(
    role_id: int,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    rbac_service: Annotated[RBACService, Depends(get_rbac_service)],
) -> RoleResponse:
    """Get role details (requires system admin)"""
    await rbac_service.require_permission(current_user.id, "manage", "settings")

    role = await rbac_service.get_role_by_id(role_id)
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

    return RoleResponse(
        id=role.id,
        name=role.name,
        description=role.description,
        permissions=role.permissions,
        created_at=role.created_at.isoformat(),
    )


@router.post(
    "/roles",
    response_model=RoleResponse,
    summary="Create new role",
    description="Create a new role with custom permissions",
    status_code=status.HTTP_201_CREATED,
)
async def create_role(
    role_data: RoleCreate,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    rbac_service: Annotated[RBACService, Depends(get_rbac_service)],
) -> RoleResponse:
    """Create new role (requires system admin)"""
    from sqlalchemy import select

    from src.models.role import Role

    await rbac_service.require_permission(current_user.id, "manage", "settings")

    # Check if role name already exists
    stmt = select(Role).where(Role.name == role_data.name)
    result = await rbac_service.db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Role '{role_data.name}' already exists",
        )

    # Create new role
    new_role = Role(
        name=role_data.name,
        description=role_data.description,
        permissions=role_data.permissions,
    )

    rbac_service.db.add(new_role)
    await rbac_service.db.commit()
    await rbac_service.db.refresh(new_role)

    return RoleResponse(
        id=new_role.id,
        name=new_role.name,
        description=new_role.description,
        permissions=new_role.permissions,
        created_at=new_role.created_at.isoformat(),
    )


@router.put(
    "/roles/{role_id}",
    response_model=RoleResponse,
    summary="Update role",
    description="Update role permissions and description",
)
async def update_role(
    role_id: int,
    role_data: RoleUpdate,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    rbac_service: Annotated[RBACService, Depends(get_rbac_service)],
) -> RoleResponse:
    """Update role (requires system admin)"""
    await rbac_service.require_permission(current_user.id, "manage", "settings")

    role = await rbac_service.get_role_by_id(role_id)
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

    # Update fields
    if role_data.description is not None:
        role.description = role_data.description
    if role_data.permissions is not None:
        role.permissions = role_data.permissions

    await rbac_service.db.commit()
    await rbac_service.db.refresh(role)

    return RoleResponse(
        id=role.id,
        name=role.name,
        description=role.description,
        permissions=role.permissions,
        created_at=role.created_at.isoformat(),
    )


# Role Assignment Endpoints
@router.get(
    "/users/{auth_user_id}/roles",
    response_model=list[RoleAssignmentResponse],
    summary="Get user roles",
    description="Get all roles assigned to a specific user",
)
async def get_user_roles(
    auth_user_id: int,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    rbac_service: Annotated[RBACService, Depends(get_rbac_service)],
) -> list[RoleAssignmentResponse]:
    """Get user's role assignments"""
    # Users can view their own roles, admins can view any user's roles
    if current_user.id != auth_user_id:
        await rbac_service.require_permission(current_user.id, "read", "users")

    assignments = await rbac_service.get_user_roles(auth_user_id)
    return assignments


@router.post(
    "/users/{auth_user_id}/roles",
    response_model=RoleAssignmentResponse,
    summary="Assign role to user",
    description="Assign a role to a user with specific resource scope",
    status_code=status.HTTP_201_CREATED,
)
async def assign_role_to_user(
    auth_user_id: int,
    assignment_data: RoleAssignmentRequest,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    rbac_service: Annotated[RBACService, Depends(get_rbac_service)],
) -> RoleAssignmentResponse:
    """Assign role to user (requires system admin or user management permission)"""
    await rbac_service.require_permission(current_user.id, "manage", "users")

    try:
        assignment = await rbac_service.assign_role(
            auth_user_id=auth_user_id,
            role_id=assignment_data.role_id,
            resource_type=assignment_data.resource_type,
            resource_id=assignment_data.resource_id,
            granted_by=current_user.id,
            expires_at=assignment_data.expires_at,
        )

        return RoleAssignmentResponse(
            id=assignment.id,
            auth_user_id=assignment.auth_user_id,
            role_id=assignment.role_id,
            resource_type=assignment.resource_type,
            resource_id=assignment.resource_id,
            granted_by=assignment.granted_by,
            expires_at=(assignment.expires_at.isoformat() if assignment.expires_at else None),
            created_at=assignment.created_at.isoformat(),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.delete(
    "/users/{auth_user_id}/roles/{role_id}",
    summary="Revoke role from user",
    description="Remove a role assignment from a user",
)
async def revoke_role_from_user(
    auth_user_id: int,
    role_id: int,
    resource_type: str,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    rbac_service: Annotated[RBACService, Depends(get_rbac_service)],
    resource_id: str | None = None,
) -> dict[str, str]:
    """Revoke role from user (requires system admin or user management permission)"""
    await rbac_service.require_permission(current_user.id, "manage", "users")

    success = await rbac_service.revoke_role(
        auth_user_id=auth_user_id,
        role_id=role_id,
        resource_type=resource_type,
        resource_id=resource_id,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role assignment not found",
        )

    return {"message": "Role revoked successfully"}
