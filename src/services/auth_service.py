"""Authentication service for handling login, registration, and user management"""

from __future__ import annotations

from datetime import UTC, datetime

from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.exceptions import (
    AppException,
    ErrorCode,
    InvalidCredentialsException,
    UserInactiveException,
)
from src.models.auth_user import AuthUser
from src.models.user import User
from src.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserinfoResponse
from src.utils.jwt import create_access_token, decode_access_token
from src.utils.password import hash_password, verify_password


class AuthService:
    """Service class for authentication operations"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def authenticate(self, login_data: LoginRequest) -> TokenResponse:
        """Authenticate user with username and password

        Args:
            login_data: Login credentials

        Returns:
            TokenResponse with JWT token

        Raises:
            InvalidCredentialsException: If credentials are invalid
            UserInactiveException: If user account is inactive
        """
        # Find auth user by username
        stmt = select(AuthUser).where(AuthUser.username == login_data.username)
        result = await self.db.execute(stmt)
        auth_user = result.scalar_one_or_none()

        if not auth_user:
            raise InvalidCredentialsException()

        # Verify password
        if not verify_password(login_data.password, auth_user.password_hash):
            raise InvalidCredentialsException()

        # Check if user is active
        if not auth_user.is_active:
            raise UserInactiveException(username=login_data.username)

        # Auto-associate with Bitbucket user if not already linked
        if not auth_user.user_id:
            await self._auto_link_bitbucket_user(auth_user)

        # Update last login time
        auth_user.last_login_at = datetime.now(UTC)
        await self.db.commit()

        # Create JWT token
        access_token = create_access_token(
            subject=auth_user.id,
            extra_data={"username": auth_user.username},
        )

        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def register(self, register_data: RegisterRequest) -> TokenResponse:
        """Register a new user

        Args:
            register_data: Registration data

        Returns:
            TokenResponse with JWT token

        Raises:
            AppException: If username already exists
        """
        # Check if username already exists
        stmt = select(AuthUser).where(AuthUser.username == register_data.username)
        result = await self.db.execute(stmt)
        existing_user = result.scalar_one_or_none()

        if existing_user:
            raise AppException(
                code=ErrorCode.USER_ALREADY_EXISTS,
                message=f"Username '{register_data.username}' already exists",
                status_code=400,
            )

        # Try to find matching Bitbucket user
        bitbucket_user = None
        if register_data.username:
            stmt = select(User).where(User.username == register_data.username)
            result = await self.db.execute(stmt)
            bitbucket_user = result.scalar_one_or_none()

        # Create new auth user
        hashed_password = hash_password(register_data.password)
        new_auth_user = AuthUser(
            username=register_data.username,
            email=register_data.email,
            password_hash=hashed_password,
            user_id=bitbucket_user.id if bitbucket_user else None,
            is_active=True,
        )

        self.db.add(new_auth_user)
        await self.db.commit()
        await self.db.refresh(new_auth_user)

        # Auto-assign reviewer role to newly registered user
        await self._assign_default_role(new_auth_user.id)

        # Create JWT token
        access_token = create_access_token(
            subject=new_auth_user.id,
            extra_data={"username": new_auth_user.username},
        )

        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def get_current_user(self, token: str) -> AuthUser:
        """Get current authenticated user from JWT token

        Args:
            token: JWT access token

        Returns:
            AuthUser object

        Raises:
            InvalidCredentialsException: If token is invalid
        """
        try:
            payload = decode_access_token(token)
            user_id: str = payload.get("sub")
            if user_id is None:
                raise InvalidCredentialsException()
        except JWTError as e:
            raise InvalidCredentialsException() from e

        # Fetch user from database
        stmt = select(AuthUser).where(AuthUser.id == int(user_id))
        result = await self.db.execute(stmt)
        auth_user = result.scalar_one_or_none()

        if not auth_user:
            raise InvalidCredentialsException()

        if not auth_user.is_active:
            raise UserInactiveException(username=auth_user.username)

        return auth_user

    async def get_user_info(self, auth_user: AuthUser) -> UserinfoResponse:
        """Get user information for response

        Args:
            auth_user: Authenticated user

        Returns:
            UserinfoResponse with user details
        """
        return UserinfoResponse(
            id=auth_user.id,
            username=auth_user.username,
            email=auth_user.email,
            is_active=auth_user.is_active,
            bitbucket_user_id=auth_user.user_id,
            last_login_at=auth_user.last_login_at,
            created_at=auth_user.created_at,
        )

    async def change_password(
        self,
        auth_user: AuthUser,
        old_password: str,
        new_password: str,
    ) -> bool:
        """Change user password

        Args:
            auth_user: Authenticated user
            old_password: Current password
            new_password: New password

        Returns:
            True if password changed successfully

        Raises:
            InvalidCredentialsException: If old password is incorrect
        """
        # Verify old password
        if not verify_password(old_password, auth_user.password_hash):
            raise InvalidCredentialsException()

        # Hash and update new password
        auth_user.password_hash = hash_password(new_password)
        await self.db.commit()

        return True

    async def _auto_link_bitbucket_user(self, auth_user: AuthUser) -> None:
        """Auto-link auth user with Bitbucket user by username

        Args:
            auth_user: Auth user to link
        """
        stmt = select(User).where(User.username == auth_user.username)
        result = await self.db.execute(stmt)
        bitbucket_user = result.scalar_one_or_none()

        if bitbucket_user:
            auth_user.user_id = bitbucket_user.id
            await self.db.commit()

    async def _assign_default_role(self, auth_user_id: int) -> None:
        """Assign default 'reviewer' role to newly registered user

        Args:
            auth_user_id: The newly created auth user ID
        """
        import logging

        from src.models.role import Role
        from src.services.rbac_service import RBACService

        logger = logging.getLogger(__name__)
        rbac_service = RBACService(self.db)

        # Get reviewer role by name
        stmt = select(Role).where(Role.name == "reviewer")
        result = await self.db.execute(stmt)
        reviewer_role = result.scalar_one_or_none()

        if not reviewer_role:
            logger.warning("Reviewer role not found, skipping auto-assignment")
            return

        try:
            await rbac_service.assign_role(
                auth_user_id=auth_user_id,
                role_id=reviewer_role.id,
                resource_type="global",
                resource_id=None,
                granted_by=None,  # System assigned
            )
            logger.info(f"Auto-assigned reviewer role to user {auth_user_id}")
        except Exception as e:
            logger.error(f"Failed to assign default role to user {auth_user_id}: {e}")
            # Don't fail registration if role assignment fails
