"""Authentication API endpoints"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    LogoutRequest,
    RegisterRequest,
    TokenRefreshRequest,
    TokenResponse,
    UserinfoResponse,
)
from src.services.auth_service import AuthService


router = APIRouter(prefix="/auth")


def get_auth_service(db: Annotated[AsyncSession, Depends(get_db_session)]) -> AuthService:
    """Dependency to get auth service instance"""
    return AuthService(db)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="User login",
    description="Authenticate user with username and password, returns JWT token",
)
async def login(
    login_data: LoginRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    """Login endpoint"""
    return await auth_service.authenticate(login_data)


@router.post(
    "/register",
    response_model=TokenResponse,
    summary="User registration",
    description="Register a new user account",
    status_code=status.HTTP_201_CREATED,
)
async def register(
    register_data: RegisterRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    """Registration endpoint"""
    return await auth_service.register(register_data)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
    description="Refresh the access token using a valid refresh token",
)
async def refresh_tokens(
    refresh_request: TokenRefreshRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    """Refresh token endpoint."""
    return await auth_service.refresh_tokens(refresh_request.refresh_token)


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
