"""Authentication service for handling login, registration, and user management"""

from __future__ import annotations

import logging
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


logger = logging.getLogger(__name__)


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
            linked = await self._auto_link_bitbucket_user(auth_user)
            # Only upgrade role if successfully linked to a Bitbucket user
            if linked:
                await self._upgrade_linked_user_role(auth_user.id)

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

        # Auto-assign role based on Bitbucket user association
        has_bitbucket_user = bitbucket_user is not None
        await self._assign_default_role(new_auth_user.id, has_bitbucket_user)

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
            UserinfoResponse with user details including roles
        """
        # Get user roles
        from src.services.rbac_service import RBACService

        rbac_service = RBACService(self.db)
        role_assignments = await rbac_service.get_user_roles(auth_user.id)

        # Extract unique role names
        roles = list({assignment["role_name"] for assignment in role_assignments})

        return UserinfoResponse(
            id=auth_user.id,
            username=auth_user.username,
            email=auth_user.email,
            is_active=auth_user.is_active,
            bitbucket_user_id=auth_user.user_id,
            last_login_at=auth_user.last_login_at,
            created_at=auth_user.created_at,
            roles=roles,
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

    async def _auto_link_bitbucket_user(self, auth_user: AuthUser) -> bool:
        """Auto-link auth user with Bitbucket user by username

        Args:
            auth_user: Auth user to link

        Returns:
            True if successfully linked, False otherwise
        """
        stmt = select(User).where(User.username == auth_user.username)
        result = await self.db.execute(stmt)
        bitbucket_user = result.scalar_one_or_none()

        if bitbucket_user:
            auth_user.user_id = bitbucket_user.id
            await self.db.commit()
            logger.info(
                f"Auto-linked auth_user {auth_user.id} with Bitbucket user {bitbucket_user.id}"
            )
            return True

        logger.debug(f"No Bitbucket user found for username: {auth_user.username}")
        return False

    async def _assign_default_role(self, auth_user_id: int, has_bitbucket_user: bool) -> None:
        """Assign default role to newly registered user

        Args:
            auth_user_id: The newly created auth user ID
            has_bitbucket_user: Whether a matching Bitbucket user was found
        """
        from src.models.role import Role
        from src.services.rbac_service import RBACService

        rbac_service = RBACService(self.db)

        # Determine role based on Bitbucket user association
        # If has Bitbucket user -> reviewer, otherwise -> viewer
        role_name = "reviewer" if has_bitbucket_user else "viewer"

        # Get role by name
        stmt = select(Role).where(Role.name == role_name)
        result = await self.db.execute(stmt)
        role = result.scalar_one_or_none()

        if not role:
            logger.warning(f"{role_name} role not found, skipping auto-assignment")
            return

        try:
            await rbac_service.assign_role(
                auth_user_id=auth_user_id,
                role_id=role.id,
                resource_type="global",
                resource_id=None,
                granted_by=None,  # System assigned
            )
            logger.info(
                f"Auto-assigned {role_name} role to user {auth_user_id} "
                f"(has_bitbucket_user={has_bitbucket_user})"
            )
        except Exception as e:
            logger.error(f"Failed to assign default role to user {auth_user_id}: {e}")
            # Don't fail registration if role assignment fails

    async def _upgrade_linked_user_role(self, auth_user_id: int) -> None:
        """Upgrade user role from viewer to reviewer after Bitbucket user association

        This is called when an auth_user gets linked to a Bitbucket user during login.
        Only upgrades if the user currently has 'viewer' role and doesn't have 'reviewer'.

        Args:
            auth_user_id: The auth user ID to upgrade
        """
        from sqlalchemy import and_

        from src.models.rbac import UserRoleAssignment
        from src.models.role import Role
        from src.services.rbac_service import RBACService

        rbac_service = RBACService(self.db)

        # Get viewer and reviewer roles
        stmt = select(Role).where(Role.name.in_(["viewer", "reviewer"]))
        result = await self.db.execute(stmt)
        roles = {r.name: r for r in result.scalars().all()}

        viewer_role = roles.get("viewer")
        reviewer_role = roles.get("reviewer")

        if not viewer_role or not reviewer_role:
            logger.warning("Viewer or reviewer role not found, skipping upgrade")
            return

        # Check if user has viewer role
        stmt = select(UserRoleAssignment).where(
            and_(
                UserRoleAssignment.auth_user_id == auth_user_id,
                UserRoleAssignment.role_id == viewer_role.id,
                UserRoleAssignment.resource_type == "global",
            )
        )
        result = await self.db.execute(stmt)
        viewer_assignment = result.scalar_one_or_none()

        if not viewer_assignment:
            logger.debug(f"User {auth_user_id} doesn't have viewer role, no upgrade needed")
            return

        # Check if already has reviewer role (avoid duplicate)
        stmt = select(UserRoleAssignment).where(
            and_(
                UserRoleAssignment.auth_user_id == auth_user_id,
                UserRoleAssignment.role_id == reviewer_role.id,
                UserRoleAssignment.resource_type == "global",
            )
        )
        result = await self.db.execute(stmt)
        reviewer_assignment = result.scalar_one_or_none()

        if reviewer_assignment:
            logger.info(f"User {auth_user_id} already has reviewer role")
            # Remove viewer role since they have reviewer
            await self.db.delete(viewer_assignment)
            await self.db.commit()
            logger.info(f"Removed redundant viewer role from user {auth_user_id}")
            return

        try:
            # Remove viewer role
            await self.db.delete(viewer_assignment)

            # Assign reviewer role
            await rbac_service.assign_role(
                auth_user_id=auth_user_id,
                role_id=reviewer_role.id,
                resource_type="global",
                resource_id=None,
                granted_by=None,  # System assigned
            )
            await self.db.commit()

            logger.info(f"Upgraded user {auth_user_id} from viewer to reviewer role")

            # Log audit trail for role upgrade during login
            await self._log_login_role_upgrade_audit(auth_user_id)
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to upgrade role for user {auth_user_id}: {e}")

    async def _log_login_role_upgrade_audit(self, auth_user_id: int) -> None:
        """Log audit trail for role upgrade during login

        Args:
            auth_user_id: The auth user ID that was upgraded
        """
        try:
            from src.services.audit_service import AuditService

            audit_service = AuditService(self.db)
            await audit_service.log_action(
                auth_user_id=None,  # System action
                action="auto_upgrade_role_on_login",
                resource_type="users",
                resource_id=str(auth_user_id),
                old_values={"role": "viewer"},
                new_values={"role": "reviewer", "reason": "bitbucket_user_linked_on_login"},
            )
        except Exception as e:
            logger.warning(f"Failed to log login role upgrade audit: {e}")
