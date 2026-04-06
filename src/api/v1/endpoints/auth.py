"""Authentication API endpoints"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
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
    description="Logout current user (client should discard token)",
)
async def logout() -> dict[str, str]:
    """Logout endpoint

    Note: With JWT tokens, logout is primarily client-side (discard token).
    Server-side token blacklisting can be added later if needed.
    """
    return {"message": "Logged out successfully. Please discard your token."}
