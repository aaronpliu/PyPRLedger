"""Permission dependencies for FastAPI route protection"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.models.auth_user import AuthUser
from src.services.auth_service import AuthService
from src.services.rbac_service import RBACService


def get_current_user_with_token(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuthUser:
    """Dependency to get current authenticated user from JWT token

    Extracts token from Authorization header and validates it.

    Args:
        request: FastAPI request object
        db: Database session

    Returns:
        AuthUser object

    Raises:
        HTTPException: If not authenticated or token is invalid
    """
    from fastapi import HTTPException, status

    authorization = request.headers.get("Authorization")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.split(" ")[1]
    auth_service = AuthService(db)

    try:
        return auth_service.get_current_user(token)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


def require_permission(
    action: str,
    resource_type: str,
    resource_id_param: str | None = None,
) -> Callable:
    """Create dependency that requires specific permission

    Usage:
        @router.post("/reviews")
        async def create_review(
            review_data: ReviewCreate,
            current_user: AuthUser = Depends(require_permission("create", "reviews")),
        ):
            pass

        # For resource-specific permissions:
        @router.get("/projects/{project_key}")
        async def get_project(
            project_key: str,
            current_user: AuthUser = Depends(require_permission("read", "projects", "project_key")),
        ):
            pass

    Args:
        action: Required action (read, create, update, delete, manage)
        resource_type: Resource type (reviews, scores, projects, etc.)
        resource_id_param: Name of path parameter containing resource ID

    Returns:
        Dependency callable
    """

    async def permission_checker(
        request: Request,
        db: Annotated[AsyncSession, Depends(get_db_session)],
        current_user: AuthUser = Depends(get_current_user_with_token),
    ) -> AuthUser:
        # Extract resource_id from path parameters if specified
        resource_id = None
        if resource_id_param:
            resource_id = request.path_params.get(resource_id_param)

        rbac_service = RBACService(db)

        try:
            await rbac_service.require_permission(
                auth_user_id=current_user.id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
            )
        except Exception as e:
            from fastapi import HTTPException, status

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(e),
            ) from e

        return current_user

    return permission_checker


# Pre-defined common permission dependencies
CurrentUser = Annotated[AuthUser, Depends(get_current_user_with_token)]

RequireReviewRead = Depends(require_permission("read", "reviews"))
RequireReviewCreate = Depends(require_permission("create", "reviews"))
RequireReviewUpdate = Depends(require_permission("update", "reviews"))
RequireReviewDelete = Depends(require_permission("delete", "reviews"))

RequireScoreRead = Depends(require_permission("read", "scores"))
RequireScoreCreate = Depends(require_permission("create", "scores"))
RequireScoreUpdate = Depends(require_permission("update", "scores"))
RequireScoreDelete = Depends(require_permission("delete", "scores"))

RequireProjectRead = Depends(require_permission("read", "projects"))
RequireProjectManage = Depends(require_permission("manage", "projects"))

RequireUserRead = Depends(require_permission("read", "users"))
RequireUserManage = Depends(require_permission("manage", "users"))

RequireSystemAdmin = Depends(require_permission("manage", "settings"))
