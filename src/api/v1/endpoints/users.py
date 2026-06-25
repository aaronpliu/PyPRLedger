import logging
import traceback
from datetime import UTC
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.database import get_db_session
from src.core.exceptions import (
    InvalidCredentialsException,
    UserAlreadyExistsException,
    UserNotFoundException,
)
from src.core.permissions import get_current_user_with_token, require_permission
from src.models.auth_user import AuthUser
from src.models.rbac import UserRoleAssignment
from src.schemas.user import (
    UserCreate,
    UserListResponse,
    UserLogin,
    UserResponse,
    UserStats,
    UserUpdate,
)
from src.services.auth_service import AuthService
from src.services.avatar_service import AvatarService
from src.services.rbac_service import RBACService
from src.services.user_service import UserService
from src.utils.metrics import metrics
from src.utils.timezone import get_current_time


logger = logging.getLogger(__name__)

# Git User (Bitbucket identity) endpoints — mounted at /users/git
git_router = APIRouter()

# Auth User (system login) endpoints — mounted at /users/auth
auth_router = APIRouter()


# Get a user service instance with metrics
def get_user_service() -> UserService:
    """Get a user service instance"""
    return UserService(metrics_collector=metrics)


@git_router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    user_service: Annotated[UserService, Depends(get_user_service)],
    current_user: Annotated[AuthUser, Depends(require_permission("manage", "users"))],
) -> UserResponse:
    """
    Create a new user (requires system_admin role)

    Args:
        user_data: The user data to create
        db: Database session
        user_service: User service instance
        current_user: Authenticated user with manage users permission

    Returns:
        UserResponse: The created user

    Raises:
        UserAlreadyExistsException: If a user with the same username or email already exists
        ForbiddenException: If user lacks manage users permission
    """
    try:
        user = await user_service.create_user(user_data, db)
        metrics.increment_user_count()
        return UserResponse(**user.model_dump())
    except UserAlreadyExistsException as e:
        metrics.increment_error(error_type=e.code, endpoint="POST /api/v1/users")
        raise HTTPException(
            status_code=e.status_code,
            detail={"error": e.code, "message": e.message, "detail": e.detail},
        )
    except Exception:
        metrics.increment_error(error_type="INTERNAL_SERVER_ERROR", endpoint="POST /api/v1/users")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to create user"},
        )


@git_router.get("", response_model=UserListResponse)
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    user_service: Annotated[UserService, Depends(get_user_service)],
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    active: bool | None = Query(None, description="Filter by active status"),
    is_reviewer: bool | None = Query(None, description="Filter by reviewer status"),
    username: str | None = Query(None, description="Filter by username (partial match)"),
    limit: int = Query(500, ge=1, le=1000, description="Maximum number of users to return"),
) -> UserListResponse:
    """
    List users with filtering (requires authentication)

    All authenticated users can view the user list.

    Args:
        active: Filter by active status
        is_reviewer: Filter by reviewer status
        username: Filter by username (partial match)
        limit: Maximum number of users to return
        db: Database session
        user_service: User service instance
        current_user: Authenticated user

    Returns:
        UserListResponse: List of users with pagination info
    """
    try:
        # Use page_size=limit and page=1 to get up to 'limit' users
        users, total = await user_service.list_users(
            active=active,
            is_reviewer=is_reviewer,
            username=username,
            page=1,
            page_size=limit,
            db=db,
        )

        # Handle both ORM objects and dicts from cache
        items = []
        for u in users:
            if hasattr(u, "to_dict"):
                # ORM object - use to_dict() which includes all fields
                user_data = u.to_dict()
            elif isinstance(u, dict):
                # Already a dict from cache - use directly
                user_data = u
            else:
                # Fallback - convert to dict
                user_data = dict(u)
            items.append(UserResponse(**user_data))

        return UserListResponse(
            items=items,
            total=total,
            page=1,
            page_size=limit,
        )
    except Exception as e:
        error_traceback = traceback.format_exc()
        logger.error(f"Failed to list users: {str(e)}\n{error_traceback}")
        metrics.increment_error(error_type="INTERNAL_SERVER_ERROR", endpoint="GET /api/v1/users")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to list users"},
        )


@git_router.get("/statistics", response_model=UserStats)
async def get_user_statistics(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    user_service: Annotated[UserService, Depends(get_user_service)],
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
) -> UserStats:
    """
    Get user statistics (requires authentication)

    All authenticated users can view statistics.

    Args:
        db: Database session
        user_service: User service instance
        current_user: Authenticated user

    Returns:
        UserStats: User statistics
    """
    try:
        stats = await user_service.get_user_statistics(db)

        # Update metrics
        metrics.set_users_total(stats.total_users)
        metrics.set_users_active(stats.active_users)
        metrics.set_reviewers_total(stats.total_reviewers)
        metrics.set_reviewers_active(stats.active_reviewers)

        return stats
    except Exception:
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR", endpoint="GET /api/v1/users/statistics"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to get user statistics"},
        )


@git_router.get("/active", response_model=UserListResponse)
async def get_active_users(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    user_service: Annotated[UserService, Depends(get_user_service)],
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of users to return"),
) -> UserListResponse:
    """
    Get active users (requires authentication)

    All authenticated users can view active users list.

    Args:
        limit: Maximum number of users to return
        db: Database session
        user_service: User service instance
        current_user: Authenticated user

    Returns:
        UserListResponse: List of active users
    """
    try:
        active_users = await user_service.get_active_users(db, limit)

        return UserListResponse(
            items=[UserResponse(**u.to_dict()) for u in active_users],
            total=len(active_users),
            page=1,
            page_size=limit,
        )
    except Exception:
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR", endpoint="GET /api/v1/users/active"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to get active users"},
        )


@git_router.get("/reviewers", response_model=UserListResponse)
async def get_reviewers(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    user_service: Annotated[UserService, Depends(get_user_service)],
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of reviewers to return"),
) -> UserListResponse:
    """
    Get active reviewers (requires authentication)

    All authenticated users can view reviewers list.

    Args:
        limit: Maximum number of reviewers to return
        db: Database session
        user_service: User service instance
        current_user: Authenticated user

    Returns:
        UserListResponse: List of active reviewers
    """
    try:
        reviewers = await user_service.get_active_reviewers(db, limit)

        return UserListResponse(
            items=[UserResponse(**r) for r in reviewers],
            total=len(reviewers),
            page=1,
            page_size=limit,
        )
    except Exception as e:
        error_traceback = traceback.format_exc()
        logger.error(f"Failed to get reviewers: {str(e)}\n{error_traceback}")
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR", endpoint="GET /api/v1/users/reviewers"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to get reviewers"},
        )


@auth_router.get("", response_model=dict)
async def list_auth_users(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    active: bool | None = Query(None, description="Filter by active status"),
    username: str | None = Query(None, description="Filter by username (partial match)"),
    limit: int = Query(500, ge=1, le=500, description="Maximum number of users to return"),
) -> dict:
    """
    Get authentication users for delegation and RBAC (requires authentication)

    This endpoint returns AuthUser records (system login users), not Bitbucket users.
    Used for role delegation and other RBAC operations.

    All authenticated users can view auth users for delegation purposes.

    Args:
        active: Filter by active status
        username: Filter by username (partial match)
        limit: Maximum number of users to return
        db: Database session
        current_user: Authenticated user

    Returns:
        dict: List of auth users with their role summaries
    """
    try:
        from sqlalchemy import and_, select

        # Build query with eager loading of role assignments
        stmt = select(AuthUser).options(
            selectinload(AuthUser.role_assignments).selectinload(UserRoleAssignment.role)
        )

        # Apply filters
        conditions = []
        if active is not None:
            conditions.append(AuthUser.is_active == active)
        if username:
            conditions.append(AuthUser.username.like(f"%{username}%"))

        if conditions:
            stmt = stmt.where(and_(*conditions))

        # Order by username and limit
        stmt = stmt.order_by(AuthUser.username).limit(limit)

        result = await db.execute(stmt)
        auth_users = result.scalars().all()

        # Convert to response format with role summaries
        users_data = []
        now = get_current_time()

        for auth_user in auth_users:
            user_dict = auth_user.to_dict()

            # Extract only ACTIVE role names (exclude expired/revoked delegations)
            role_names = []
            for assignment in auth_user.role_assignments:
                if not assignment.role:
                    continue

                # Check if assignment is active
                is_active = True

                # For delegated roles, check delegation_status
                if assignment.is_delegated:
                    if assignment.delegation_status != "active":
                        is_active = False

                # Check expiration time
                if is_active and assignment.expires_at:
                    expires_at = assignment.expires_at
                    # If expires_at is naive (no timezone), assume it's UTC
                    if expires_at.tzinfo is None:
                        expires_at = expires_at.replace(tzinfo=UTC)

                    if expires_at <= now:
                        is_active = False

                # Only include active assignments
                if is_active:
                    role_names.append(assignment.role.name)

            user_dict["roles"] = role_names
            user_dict["role_display"] = ", ".join(role_names) if role_names else "No Role"
            user_dict["git_user_id"] = auth_user.user_id  # Link to Bitbucket user
            users_data.append(user_dict)

        return {
            "items": users_data,
            "total": len(users_data),
        }
    except Exception as e:
        error_traceback = traceback.format_exc()
        logger.error(f"Failed to list auth users: {str(e)}\n{error_traceback}")
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR", endpoint="GET /api/v1/users/auth-users"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to list auth users"},
        )


@git_router.post("/login", response_model=dict)
async def login(
    credentials: UserLogin,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> dict:
    """
    Authenticate a user

    Args:
        credentials: User login credentials
        db: Database session
        user_service: User service instance

    Returns:
        dict: Authentication result with user info and token

    Raises:
        InvalidCredentialsException: If credentials are invalid
    """
    try:
        user = await user_service.validate_credentials(
            username=credentials.username, password=credentials.password, db=db
        )

        return {
            "success": True,
            "user_id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "is_reviewer": user.is_reviewer,
        }
    except InvalidCredentialsException as e:
        metrics.increment_error(error_type=e.code, endpoint="POST /api/v1/users/login")
        raise HTTPException(
            status_code=e.status_code, detail={"error": e.code, "message": e.message}
        )
    except Exception:
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR", endpoint="POST /api/v1/users/login"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to authenticate user"},
        )


@git_router.get("/{git_user_id}", response_model=UserResponse)
async def get_user(
    git_user_id: int,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    user_service: Annotated[UserService, Depends(get_user_service)],
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
) -> UserResponse:
    """
    Get a git user by ID (requires authentication)

    All authenticated users can view git user details.

    Args:
        git_user_id: The git user ID
        db: Database session
        user_service: User service instance
        current_user: Authenticated user

    Returns:
        UserResponse: The requested user

    Raises:
        UserNotFoundException: If the user doesn't exist
    """
    try:
        user = await user_service.get_user_by_id(git_user_id, db)
        if not user:
            metrics.increment_error(
                error_type="NOT_FOUND", endpoint=f"GET /api/v1/users/git/{git_user_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "NOT_FOUND", "message": f"User with ID {git_user_id} not found"},
            )
        return UserResponse(**user)
    except Exception:
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR", endpoint=f"GET /api/v1/users/git/{git_user_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to get user"},
        )


@git_router.get("/username/{username}", response_model=UserResponse)
async def get_user_by_username(
    username: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    user_service: Annotated[UserService, Depends(get_user_service)],
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
) -> UserResponse:
    """
    Get a user by username (requires authentication)

    All authenticated users can view user details by username.

    Args:
        username: The username
        db: Database session
        user_service: User service instance
        current_user: Authenticated user

    Returns:
        UserResponse: The requested user

    Raises:
        UserNotFoundException: If the user doesn't exist
    """
    try:
        user = await user_service.get_user_by_username(username, db)
        if not user:
            metrics.increment_error(
                error_type="NOT_FOUND", endpoint=f"GET /api/v1/users/username/{username}"
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "NOT_FOUND",
                    "message": f"User with username '{username}' not found",
                },
            )
        return UserResponse(**user)
    except Exception:
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR", endpoint=f"GET /api/v1/users/username/{username}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to get user by username"},
        )


@git_router.put("/{git_user_id}", response_model=UserResponse)
async def update_user(
    git_user_id: int,
    user_update: UserUpdate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    user_service: Annotated[UserService, Depends(get_user_service)],
    current_user: Annotated[AuthUser, Depends(require_permission("manage", "users"))],
) -> UserResponse:
    """
    Update a git user (requires system_admin role)

    Args:
        git_user_id: The git user ID
        user_update: The update data
        db: Database session
        user_service: User service instance
        current_user: Authenticated user with manage users permission

    Returns:
        UserResponse: The updated user

    Raises:
        UserNotFoundException: If the user doesn't exist
        ForbiddenException: If user lacks manage users permission
    """
    try:
        user = await user_service.update_user(git_user_id, user_update, db)
        return UserResponse(**user)
    except UserNotFoundException as e:
        metrics.increment_error(error_type=e.code, endpoint=f"PUT /api/v1/users/git/{git_user_id}")
        raise HTTPException(
            status_code=e.status_code,
            detail={"error": e.code, "message": e.message, "detail": e.detail},
        )
    except UserAlreadyExistsException as e:
        metrics.increment_error(error_type=e.code, endpoint=f"PUT /api/v1/users/git/{git_user_id}")
        raise HTTPException(
            status_code=e.status_code,
            detail={"error": e.code, "message": e.message, "detail": e.detail},
        )
    except Exception:
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR", endpoint=f"PUT /api/v1/users/git/{git_user_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to update user"},
        )


@git_router.patch("/{git_user_id}/toggle-reviewer", response_model=UserResponse)
async def toggle_reviewer_status(
    git_user_id: int,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    user_service: Annotated[UserService, Depends(get_user_service)],
    current_user: Annotated[AuthUser, Depends(require_permission("manage", "users"))],
) -> UserResponse:
    """
    Toggle reviewer status for a git user (requires system_admin role)

    Args:
        git_user_id: The git user ID
        db: Database session
        user_service: User service instance
        current_user: Authenticated user with manage users permission

    Returns:
        UserResponse: The updated user

    Raises:
        UserNotFoundException: If the user doesn't exist
        ForbiddenException: If user lacks manage users permission
    """
    try:
        user = await user_service.toggle_reviewer_status(git_user_id, db)
        return UserResponse(**user)
    except UserNotFoundException as e:
        metrics.increment_error(
            error_type=e.code, endpoint=f"PATCH /api/v1/users/git/{git_user_id}/toggle-reviewer"
        )
        raise HTTPException(
            status_code=e.status_code,
            detail={"error": e.code, "message": e.message, "detail": e.detail},
        )
    except Exception:
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR",
            endpoint=f"PATCH /api/v1/users/git/{git_user_id}/toggle-reviewer",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": "Failed to toggle reviewer status",
            },
        )


@auth_router.patch("/{auth_user_id}/activate")
async def activate_user(
    auth_user_id: int,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    user_service: Annotated[UserService, Depends(get_user_service)],
    current_user: Annotated[AuthUser, Depends(require_permission("manage", "users"))],
) -> dict:
    """
    Activate an auth user (requires system_admin role)

    Args:
        auth_user_id: The AuthUser ID (system login user)
        db: Database session
        user_service: User service instance
        current_user: Authenticated user with manage users permission

    Returns:
        dict: The updated auth user data

    Raises:
        UserNotFoundException: If the auth user doesn't exist
        ForbiddenException: If user lacks manage users permission
    """
    try:
        user = await user_service.activate_user(auth_user_id, db)
        return user
    except UserNotFoundException as e:
        metrics.increment_error(
            error_type=e.code, endpoint=f"PATCH /api/v1/users/auth/{auth_user_id}/activate"
        )
        raise HTTPException(
            status_code=e.status_code,
            detail={"error": e.code, "message": e.message, "detail": e.detail},
        )
    except Exception as e:
        logger.error(f"Failed to activate auth user {auth_user_id}: {e}", exc_info=True)
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR",
            endpoint=f"PATCH /api/v1/users/auth/{auth_user_id}/activate",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": f"Failed to activate auth user: {str(e)}",
            },
        )


@auth_router.patch("/{auth_user_id}/deactivate")
async def deactivate_user(
    auth_user_id: int,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    user_service: Annotated[UserService, Depends(get_user_service)],
    current_user: Annotated[AuthUser, Depends(require_permission("manage", "users"))],
) -> dict:
    """
    Deactivate an auth user (requires system_admin role)

    Args:
        auth_user_id: The AuthUser ID (system login user)
        db: Database session
        user_service: User service instance
        current_user: Authenticated user with manage users permission

    Returns:
        dict: The updated auth user data

    Raises:
        UserNotFoundException: If the auth user doesn't exist
        ForbiddenException: If user lacks manage users permission
    """
    try:
        user = await user_service.deactivate_user(auth_user_id, db)
        return user
    except UserNotFoundException as e:
        metrics.increment_error(
            error_type=e.code, endpoint=f"PATCH /api/v1/users/auth/{auth_user_id}/deactivate"
        )
        raise HTTPException(
            status_code=e.status_code,
            detail={"error": e.code, "message": e.message, "detail": e.detail},
        )
    except Exception as e:
        logger.error(f"Failed to deactivate auth user {auth_user_id}: {e}", exc_info=True)
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR",
            endpoint=f"PATCH /api/v1/users/auth/{auth_user_id}/deactivate",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": f"Failed to deactivate auth user: {str(e)}",
            },
        )


@auth_router.delete("/{auth_user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_auth_user(
    auth_user_id: int,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    user_service: Annotated[UserService, Depends(get_user_service)],
    current_user: Annotated[AuthUser, Depends(require_permission("manage", "users"))],
) -> None:
    """
    Delete an auth user (requires system_admin role)

    Cascades to role assignments, audit logs, personal access tokens.
    Revokes all active refresh sessions.
    Does NOT delete the linked git user.

    Args:
        auth_user_id: The AuthUser ID (system login user)
        db: Database session
        user_service: User service instance
        current_user: Authenticated user with manage users permission

    Returns:
        None: Successful deletion returns 204 No Content

    Raises:
        UserNotFoundException: If the auth user doesn't exist
        ForbiddenException: If user lacks manage users permission
    """
    try:
        # Revoke all active sessions for this user before deletion
        auth_service = AuthService(db)
        sessions = await auth_service.list_sessions(auth_user_id=auth_user_id)
        for session in sessions:
            try:
                await auth_service.revoke_session(session.session_id)
            except Exception:
                logger.warning(
                    f"Failed to revoke session {session.session_id} for auth user {auth_user_id}"
                )
                continue

        deleted = await user_service.delete_auth_user(auth_user_id, db)
        if not deleted:
            metrics.increment_error(
                error_type="NOT_FOUND", endpoint=f"DELETE /api/v1/users/auth/{auth_user_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "NOT_FOUND",
                    "message": f"Auth user with ID {auth_user_id} not found",
                },
            )
    except Exception:
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR", endpoint=f"DELETE /api/v1/users/auth/{auth_user_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to delete auth user"},
        )


@git_router.delete("/{git_user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_git_user(
    git_user_id: int,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    user_service: Annotated[UserService, Depends(get_user_service)],
    current_user: Annotated[AuthUser, Depends(require_permission("manage", "users"))],
) -> None:
    """
    Delete a git user (requires system_admin role)

    Args:
        git_user_id: The git user ID
        db: Database session
        user_service: User service instance
        current_user: Authenticated user with manage users permission

    Returns:
        None: Successful deletion returns 204 No Content

    Raises:
        UserNotFoundException: If the user doesn't exist
        ForbiddenException: If user lacks manage users permission
    """
    try:
        deleted = await user_service.delete_user(git_user_id, db)
        if not deleted:
            metrics.increment_error(
                error_type="NOT_FOUND", endpoint=f"DELETE /api/v1/users/git/{git_user_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "NOT_FOUND",
                    "message": f"Git user with ID {git_user_id} not found",
                },
            )
    except Exception:
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR", endpoint=f"DELETE /api/v1/users/git/{git_user_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to delete git user"},
        )


@auth_router.post("/{username}/avatar", status_code=status.HTTP_200_OK)
async def upload_avatar(
    username: str,
    file: Annotated[UploadFile, File(description="Avatar image file")],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
) -> dict:
    """
    Upload user avatar

    Users can upload their own avatar. System admins can upload avatars for any user.

    Args:
        username: The auth username
        file: Avatar image file (JPEG, PNG, WebP, or GIF, max 5MB)
        db: Database session
        current_user: Authenticated user

    Returns:
        dict: {"avatar_url": "..."}

    Raises:
        HTTPException: If user not found, file validation fails, or insufficient permissions
    """
    try:
        # Check permissions: users can update their own avatar, admins can update any
        if current_user.username != username:
            rbac_service = RBACService(db)
            has_permission = await rbac_service.check_permission(
                auth_user_id=current_user.id,
                action="manage",
                resource_type="users",
            )
            if not has_permission:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "error": "FORBIDDEN",
                        "message": "You can only update your own avatar. System administrators can update any user's avatar.",
                    },
                )

        # Get auth user from database
        result = await db.execute(select(AuthUser).where(AuthUser.username == username))
        auth_user = result.scalar_one_or_none()

        if not auth_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "NOT_FOUND", "message": f"User '{username}' not found"},
            )

        # Upload new avatar using auth_user ID
        avatar_service = AvatarService()
        avatar_url = await avatar_service.upload_avatar(auth_user.id, file)

        # Delete old avatar if exists
        if auth_user.avatar_url:
            avatar_service.delete_avatar(auth_user.avatar_url)

        # Update auth user record
        auth_user.avatar_url = avatar_url
        await db.commit()
        await db.refresh(auth_user)

        return {"avatar_url": avatar_url}

    except Exception as e:
        logger.error(f"Failed to upload avatar for user {username}: {str(e)}")
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR", endpoint=f"POST /api/v1/users/{username}/avatar"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to upload avatar"},
        )


@auth_router.delete("/{username}/avatar", status_code=status.HTTP_200_OK)
async def delete_avatar(
    username: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
) -> dict:
    """
    Delete user avatar

    Users can delete their own avatar. System admins can delete any user's avatar.

    Args:
        username: The auth username
        db: Database session
        current_user: Authenticated user

    Returns:
        dict: {"avatar_url": null}

    Raises:
        HTTPException: If user not found or insufficient permissions
    """
    try:
        # Check permissions: users can delete their own avatar, admins can delete any
        if current_user.username != username:
            rbac_service = RBACService(db)
            has_permission = await rbac_service.check_permission(
                auth_user_id=current_user.id,
                action="manage",
                resource_type="users",
            )
            if not has_permission:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "error": "FORBIDDEN",
                        "message": "You can only delete your own avatar. System administrators can delete any user's avatar.",
                    },
                )

        # Get auth user from database
        result = await db.execute(select(AuthUser).where(AuthUser.username == username))
        auth_user = result.scalar_one_or_none()

        if not auth_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "NOT_FOUND", "message": f"User '{username}' not found"},
            )

        # Delete avatar file if exists
        if auth_user.avatar_url:
            avatar_service = AvatarService()
            avatar_service.delete_avatar(auth_user.avatar_url)
            auth_user.avatar_url = None
            await db.commit()

        return {"avatar_url": None}

    except Exception as e:
        logger.error(f"Failed to delete avatar for user {username}: {str(e)}")
        metrics.increment_error(
            error_type="INTERNAL_SERVER_ERROR", endpoint=f"DELETE /api/v1/users/{username}/avatar"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": "Failed to delete avatar"},
        )
