"""Authentication API endpoints"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.core.permissions import get_current_user_with_token
from src.models.auth_user import AuthUser
from src.schemas.auth import (
    AuthSessionResponse,
    ChangePasswordRequest,
    LoginRequest,
    LogoutRequest,
    RegisterRequest,
    TokenRefreshRequest,
    TokenResponse,
    UserinfoResponse,
)
from src.services.auth_service import AuthService
from src.services.rbac_service import RBACService


router = APIRouter(prefix="/auth")


def get_request_client_context(request: Request) -> tuple[str | None, str | None]:
    """Extract client IP and user agent for session metadata."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    ip_address = forwarded_for.split(",")[0].strip() if forwarded_for else None
    if not ip_address and request.client:
        ip_address = request.client.host
    return ip_address, request.headers.get("User-Agent")


def get_auth_service(db: Annotated[AsyncSession, Depends(get_db_session)]) -> AuthService:
    """Dependency to get auth service instance"""
    return AuthService(db)


def get_rbac_service(db: Annotated[AsyncSession, Depends(get_db_session)]) -> RBACService:
    """Dependency to get RBAC service instance"""
    return RBACService(db)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="User login",
    description="Authenticate user with username and password, returns JWT token",
)
async def login(
    request: Request,
    login_data: LoginRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    """Login endpoint"""
    ip_address, user_agent = get_request_client_context(request)
    return await auth_service.authenticate(
        login_data,
        ip_address=ip_address,
        user_agent=user_agent,
    )


@router.post(
    "/register",
    response_model=TokenResponse,
    summary="User registration",
    description="Register a new user account",
    status_code=status.HTTP_201_CREATED,
)
async def register(
    request: Request,
    register_data: RegisterRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    """Registration endpoint"""
    ip_address, user_agent = get_request_client_context(request)
    return await auth_service.register(
        register_data,
        ip_address=ip_address,
        user_agent=user_agent,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
    description="Refresh the access token using a valid refresh token",
)
async def refresh_tokens(
    request: Request,
    refresh_request: TokenRefreshRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    """Refresh token endpoint."""
    ip_address, user_agent = get_request_client_context(request)
    return await auth_service.refresh_tokens(
        refresh_request.refresh_token,
        ip_address=ip_address,
        user_agent=user_agent,
    )


@router.get(
    "/me",
    response_model=UserinfoResponse,
    summary="Get current user info",
    description="Get information about the currently authenticated user",
)
async def get_current_user_info(
    request: Request,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> UserinfoResponse:
    """Get current user info endpoint

    Note: This endpoint requires authentication. The actual auth check
    will be implemented with dependency injection in the next iteration.
    For now, it expects a token in the Authorization header.
    """
    # Extract token from header
    authorization = request.headers.get("Authorization")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.split(" ")[1]

    try:
        auth_user = await auth_service.get_current_user(token)
        return await auth_service.get_user_info(auth_user)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


@router.post(
    "/change-password",
    summary="Change password",
    description="Change the password for the currently authenticated user",
)
async def change_password(
    request: Request,
    password_data: ChangePasswordRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> dict[str, str]:
    """Change password endpoint"""
    # Extract token from header
    authorization = request.headers.get("Authorization")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.split(" ")[1]

    try:
        auth_user = await auth_service.get_current_user(token)
        await auth_service.change_password(
            auth_user,
            password_data.old_password,
            password_data.new_password,
        )
        return {"message": "Password changed successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post(
    "/logout",
    summary="User logout",
    description="Logout current user and revoke the active refresh session",
)
async def logout(
    request: Request,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    logout_request: LogoutRequest | None = None,
) -> dict[str, str]:
    """Logout endpoint

    Revokes the server-side refresh session so the current login can no longer
    mint new access tokens.
    """
    authorization = request.headers.get("Authorization")
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]

    await auth_service.logout(
        token=token,
        refresh_token=logout_request.refresh_token if logout_request else None,
    )
    return {"message": "Logged out successfully."}


@router.get(
    "/sessions/me",
    response_model=list[AuthSessionResponse],
    summary="List my active sessions",
    description="List all active refresh sessions belonging to the current user",
)
async def list_my_sessions(
    request: Request,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> list[AuthSessionResponse]:
    """List active sessions for the current user."""
    authorization = request.headers.get("Authorization")
    current_session_id: str | None = None

    if authorization and authorization.startswith("Bearer "):
        current_session_id = await auth_service.get_session_id_from_token(
            authorization.split(" ")[1]
        )

    return await auth_service.list_sessions(
        auth_user_id=current_user.id,
        current_session_id=current_session_id,
    )


@router.get(
    "/sessions",
    response_model=list[AuthSessionResponse],
    summary="List active sessions",
    description="Administrative session inventory for active refresh sessions",
)
async def list_sessions(
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    rbac_service: Annotated[RBACService, Depends(get_rbac_service)],
    auth_user_id: int | None = Query(
        default=None,
        description="Optional auth user ID filter",
    ),
) -> list[AuthSessionResponse]:
    """List active sessions for operations and support."""
    await rbac_service.require_permission(current_user.id, "manage", "users")
    return await auth_service.list_sessions(auth_user_id=auth_user_id)


@router.delete(
    "/sessions/{session_id}",
    summary="Revoke a session",
    description="Administrative endpoint to revoke an active refresh session immediately",
)
async def revoke_session(
    session_id: str,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    rbac_service: Annotated[RBACService, Depends(get_rbac_service)],
) -> dict[str, str]:
    """Revoke an active session by session id."""
    await rbac_service.require_permission(current_user.id, "manage", "users")
    await auth_service.revoke_session(session_id)
    return {"message": "Session revoked successfully."}


@router.delete(
    "/sessions/me/{session_id}",
    summary="Revoke one of my sessions",
    description="Allow a user to revoke one of their own active sessions",
)
async def revoke_my_session(
    session_id: str,
    current_user: Annotated[AuthUser, Depends(get_current_user_with_token)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> dict[str, str]:
    """Revoke one of the current user's active sessions by session id."""
    await auth_service.revoke_user_session(current_user.id, session_id)
    return {"message": "Session revoked successfully."}
