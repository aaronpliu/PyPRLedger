"""Role delegation API endpoints"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.core.permissions import get_current_user_with_token
from src.models.auth_user import AuthUser
from src.schemas.delegation import (
    DelegationCreate,
    DelegationListQuery,
    DelegationResponse,
    DelegationRevoke,
)
from src.services.rbac_service import RBACService


router = APIRouter(prefix="/delegations", tags=["role-delegations"])


def get_rbac_service(
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> RBACService:
    """Dependency to get RBAC service"""
    return RBACService(db)


@router.post("", response_model=DelegationResponse, status_code=201)
async def create_delegation(
    data: DelegationCreate,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    rbac_service: Annotated[RBACService, Depends(get_rbac_service)],
) -> DelegationResponse:
    """Create a role delegation

    Allows a user with a role to delegate specific permissions to another user
    for a defined time period.

    **Requirements**:
    - Current user must have the role being delegated
    - delegation_scope must be a subset of current user's permissions
    - starts_at must be before expires_at
    - No delegation chains allowed

    **Example**:
    ```json
    {
        "delegatee_id": 123,
        "role_id": 2,
        "resource_type": "global",
        "resource_id": null,
        "delegation_scope": {
            "reviews": ["read", "create"],
            "scores": ["read"]
        },
        "starts_at": "2026-04-12T00:00:00Z",
        "expires_at": "2026-05-12T23:59:59Z",
        "reason": "Temporary coverage during vacation"
    }
    ```
    """
    # Check if current user has permission to manage roles
    await rbac_service.require_permission(current_user.id, "manage", "roles")

    # Create delegation
    assignment = await rbac_service.delegate_role(
        delegator_id=current_user.id,
        delegatee_id=data.delegatee_id,
        role_id=data.role_id,
        resource_type=data.resource_type,
        resource_id=data.resource_id,
        delegation_scope=data.delegation_scope,
        starts_at=data.starts_at,
        expires_at=data.expires_at,
        reason=data.reason,
    )

    # Get role name for response
    role = await rbac_service.get_role_by_id(assignment.role_id)
    result = assignment.to_dict()
    result["role_name"] = role.name if role else None

    return DelegationResponse(**result)


@router.get("", response_model=list[DelegationResponse])
async def list_delegations(
    query: Annotated[DelegationListQuery, Depends()],
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    rbac_service: Annotated[RBACService, Depends(get_rbac_service)],
) -> list[DelegationResponse]:
    """List role delegations

    Returns delegations based on filters. Users can view:
    - Their own delegations (as delegator or delegatee)
    - All delegations (if they have admin permissions)

    **Query Parameters**:
    - `delegator_id`: Filter by delegator user ID
    - `delegatee_id`: Filter by delegatee user ID
    - `status`: Filter by status (active/expired/revoked/pending)
    - `include_expired`: Include expired/revoked delegations (default: false)

    **Examples**:
    - GET /delegations?delegator_id=1  (delegations I created)
    - GET /delegations?delegatee_id=2  (delegations I received)
    - GET /delegations?status=active   (only active delegations)
    - GET /delegations?include_expired=true  (include history)
    """
    # Check permissions
    is_admin = await rbac_service.check_permission(current_user.id, "manage", "roles")

    # If not admin, only allow viewing own delegations
    if not is_admin:
        if query.delegator_id and query.delegator_id != current_user.id:
            from src.core.exceptions import ForbiddenException

            raise ForbiddenException(message="You can only view your own delegations")
        if query.delegatee_id and query.delegatee_id != current_user.id:
            from src.core.exceptions import ForbiddenException

            raise ForbiddenException(message="You can only view your own delegations")
        # Force filter to current user
        if not query.delegator_id and not query.delegatee_id:
            query.delegatee_id = current_user.id

    delegations = await rbac_service.get_delegations(
        delegator_id=query.delegator_id,
        delegatee_id=query.delegatee_id,
        status=query.status,
        include_expired=query.include_expired,
    )

    return [DelegationResponse(**d) for d in delegations]


@router.delete("/{assignment_id}")
async def revoke_delegation(
    assignment_id: int,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    rbac_service: Annotated[RBACService, Depends(get_rbac_service)],
    data: DelegationRevoke | None = None,
) -> dict:
    """Revoke a role delegation

    Revokes an active delegation. Only the delegator or system admin can revoke.

    **Path Parameters**:
    - `assignment_id`: The delegation assignment ID to revoke

    **Request Body** (optional):
    - `reason`: Reason for revocation

    **Response**:
    - Success message

    **Note**: This does not delete the delegation record, it only marks it as 'revoked'
    for audit trail purposes.
    """
    success = await rbac_service.revoke_delegation(
        assignment_id=assignment_id,
        revoked_by=current_user.id,
        reason=data.reason if data else None,
    )

    if not success:
        from src.core.exceptions import NotFoundException

        raise NotFoundException(message="Delegation not found or already revoked")

    return {"message": "Delegation revoked successfully"}


@router.get("/users/{user_id}", response_model=list[DelegationResponse])
async def get_user_delegations(
    user_id: int,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    rbac_service: Annotated[RBACService, Depends(get_rbac_service)],
    direction: str = Query(
        "received",
        description="Direction: 'sent' (delegations created by user) or 'received' (delegations received by user)",
        pattern="^(sent|received)$",
    ),
    include_expired: bool = Query(False, description="Include expired/revoked"),
) -> list[DelegationResponse]:
    """Get delegations for a specific user

    **Path Parameters**:
    - `user_id`: The user ID

    **Query Parameters**:
    - `direction`: 'sent' or 'received' (default: received)
    - `include_expired`: Include expired/revoked delegations

    **Permission**:
    - Users can view their own delegations
    - Admins can view any user's delegations
    """
    # Check permissions
    is_admin = await rbac_service.check_permission(current_user.id, "manage", "roles")
    if not is_admin and user_id != current_user.id:
        from src.core.exceptions import ForbiddenException

        raise ForbiddenException(message="You can only view your own delegations")

    delegator_id = user_id if direction == "sent" else None
    delegatee_id = user_id if direction == "received" else None

    delegations = await rbac_service.get_delegations(
        delegator_id=delegator_id,
        delegatee_id=delegatee_id,
        include_expired=include_expired,
    )

    return [DelegationResponse(**d) for d in delegations]


@router.post("/cleanup-expired")
async def cleanup_expired_delegations(
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    rbac_service: Annotated[RBACService, Depends(get_rbac_service)],
) -> dict:
    """Manually trigger cleanup of expired delegations

    Updates the status of all expired delegations from 'active' to 'expired'.
    This is typically run automatically via cron job, but can be triggered manually.

    **Permission**: Requires system admin role

    **Response**:
    - Number of delegations updated
    """
    # Only admins can trigger cleanup
    await rbac_service.require_permission(current_user.id, "manage", "roles")

    count = await rbac_service.update_expired_delegations()

    return {
        "message": f"Updated {count} expired delegations",
        "updated_count": count,
    }
