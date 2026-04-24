"""Authentication service for handling login, registration, and user management"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from jose import ExpiredSignatureError, JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.exceptions import (
    AppException,
    ErrorCode,
    InvalidCredentialsException,
    InvalidTokenException,
    NotFoundException,
    TokenExpiredException,
    UserInactiveException,
)
from src.models.auth_user import AuthUser
from src.models.user import User
from src.schemas.auth import (
    AuthSessionResponse,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserinfoResponse,
)
from src.utils.jwt import create_access_token, decode_access_token
from src.utils.password import hash_password, verify_password
from src.utils.redis import get_redis_client


logger = logging.getLogger(__name__)


REFRESH_SESSION_KEY_PREFIX = "auth:refresh_session"


class AuthService:
    """Service class for authentication operations"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.redis_client = get_redis_client()

    @staticmethod
    def _get_refresh_session_key(session_id: str) -> str:
        return f"{REFRESH_SESSION_KEY_PREFIX}:{session_id}"

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _generate_session_id() -> str:
        return uuid4().hex

    @staticmethod
    def _build_refresh_token(session_id: str) -> str:
        return f"{session_id}.{secrets.token_urlsafe(48)}"

    @staticmethod
    def _extract_session_id_from_refresh_token(refresh_token: str) -> str:
        session_id, separator, _ = refresh_token.partition(".")
        if not session_id or not separator:
            raise InvalidTokenException("Invalid refresh token")
        return session_id

    @staticmethod
    def _get_refresh_expires_in_seconds() -> int:
        return settings.REFRESH_TOKEN_IDLE_TIMEOUT_MINUTES * 60

    async def _store_refresh_session(
        self,
        auth_user: AuthUser,
        session_id: str,
        refresh_token: str,
        created_at: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        session_data = {
            "auth_user_id": auth_user.id,
            "username": auth_user.username,
            "refresh_token_hash": self._hash_token(refresh_token),
            "created_at": created_at or now,
            "last_activity_at": now,
            "ip_address": ip_address,
            "user_agent": user_agent,
        }
        await self.redis_client.setex(
            self._get_refresh_session_key(session_id),
            self._get_refresh_expires_in_seconds(),
            json.dumps(session_data),
        )

    async def _get_refresh_session(self, session_id: str) -> dict[str, str | None] | None:
        session_data = await self.redis_client.get(self._get_refresh_session_key(session_id))
        if not session_data:
            return None
        try:
            return json.loads(session_data)
        except json.JSONDecodeError as exc:
            logger.warning("Failed to decode refresh session for session_id=%s", session_id)
            await self.redis_client.delete(self._get_refresh_session_key(session_id))
            raise InvalidTokenException("Invalid refresh session") from exc

    async def _delete_refresh_session(self, session_id: str) -> None:
        await self.redis_client.delete(self._get_refresh_session_key(session_id))

    async def _write_refresh_session_data(
        self,
        session_id: str,
        session_data: dict[str, str | None],
        expires_in_seconds: int,
    ) -> None:
        await self.redis_client.setex(
            self._get_refresh_session_key(session_id),
            expires_in_seconds,
            json.dumps(session_data),
        )

    @staticmethod
    def _parse_datetime(value: str) -> datetime:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed

    async def _create_token_response(
        self,
        auth_user: AuthUser,
        session_id: str,
        created_at: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> TokenResponse:
        refresh_token = self._build_refresh_token(session_id)
        await self._store_refresh_session(
            auth_user,
            session_id,
            refresh_token,
            created_at=created_at,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        access_token = create_access_token(
            subject=auth_user.id,
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
            extra_data={
                "username": auth_user.username,
                "sid": session_id,
                "typ": "access",
            },
        )
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            refresh_expires_in=self._get_refresh_expires_in_seconds(),
        )

    async def _get_auth_user_by_id(self, auth_user_id: int) -> AuthUser:
        stmt = select(AuthUser).where(AuthUser.id == auth_user_id)
        result = await self.db.execute(stmt)
        auth_user = result.scalar_one_or_none()
        if not auth_user:
            raise InvalidTokenException("Authenticated user not found")
        if not auth_user.is_active:
            raise UserInactiveException(username=auth_user.username)
        return auth_user

    async def authenticate(
        self,
        login_data: LoginRequest,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> TokenResponse:
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
            linked = await self._auto_link_git_user(auth_user)
            # Only upgrade role if successfully linked to a Bitbucket user
            if linked:
                await self._upgrade_linked_user_role(auth_user.id)

        # Update last login time
        auth_user.last_login_at = datetime.now(UTC)
        await self.db.commit()

        return await self._create_token_response(
            auth_user,
            self._generate_session_id(),
            ip_address=ip_address,
            user_agent=user_agent,
        )

    async def _get_system_setting(self, setting_key: str, default_value: str = "true") -> str:
        """Get system setting value with Redis cache and database fallback

        This implements the same hybrid approach as RBACService to avoid circular dependencies.

        Args:
            setting_key: The setting identifier (e.g., 'registration_enabled')
            default_value: Default value if setting doesn't exist

        Returns:
            The setting value as string
        """
        from src.models.system_setting import SystemSetting

        cache_key = f"system:settings:{setting_key}"

        try:
            # Step 1: Try Redis cache first
            cached_value = await self.redis_client.get(cache_key)
            if cached_value is not None:
                logger.debug(f"[AuthService] Cache hit for setting '{setting_key}': {cached_value}")
                return cached_value

            # Step 2: Cache miss - read from database
            logger.debug(
                f"[AuthService] Cache miss for setting '{setting_key}', reading from database"
            )
            stmt = select(SystemSetting).where(
                SystemSetting.setting_key == setting_key,
                SystemSetting.is_active == True,
            )
            result = await self.db.execute(stmt)
            setting = result.scalar_one_or_none()

            if setting:
                # Found in database - cache it
                value = setting.setting_value
                await self.redis_client.setex(cache_key, 86400 * 365, value)  # Cache for 1 year
                logger.info(f"[AuthService] Loaded setting '{setting_key}' from database: {value}")
                return value

            # Step 3: Setting doesn't exist - create with default value
            logger.info(
                f"[AuthService] Setting '{setting_key}' not found, creating with default: {default_value}"
            )
            new_setting = SystemSetting(
                setting_key=setting_key,
                setting_value=default_value,
                description=f"Auto-created system setting: {setting_key}",
                is_active=True,
            )
            self.db.add(new_setting)
            await self.db.commit()
            await self.db.refresh(new_setting)

            # Cache the default value
            await self.redis_client.setex(cache_key, 86400 * 365, default_value)
            logger.info(
                f"[AuthService] Created and cached default setting '{setting_key}': {default_value}"
            )
            return default_value

        except Exception as e:
            logger.error(f"[AuthService] Failed to get setting '{setting_key}': {e}")
            raise

    async def register(
        self,
        register_data: RegisterRequest,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> TokenResponse:
        """Register a new user

        Args:
            register_data: Registration data

        Returns:
            TokenResponse with JWT token

        Raises:
            AppException: If username already exists or registration is disabled
        """
        # Check if registration is enabled using hybrid DB+Redis approach
        try:
            reg_enabled_value = await self._get_system_setting("registration_enabled", "true")
            if reg_enabled_value.lower() == "false":
                logger.warning(
                    f"Registration attempt while disabled - IP: {ip_address}, Username: {register_data.username}"
                )
                raise AppException(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="User registration is currently disabled",
                    status_code=403,
                )
        except AppException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to check registration setting: {e}. Defaulting to DISABLED for security."
            )
            raise AppException(
                code=ErrorCode.SERVICE_UNAVAILABLE,
                message="Registration service temporarily unavailable",
                status_code=503,
            ) from e

        # Check if username already exists
        stmt = select(AuthUser).where(AuthUser.username == register_data.username)
        result = await self.db.execute(stmt)
        existing_user = result.scalar_one_or_none()

        if existing_user:
            raise AppException(
                code=ErrorCode.RESOURCE_ALREADY_EXISTS,
                message=f"Username '{register_data.username}' already exists",
                status_code=400,
            )

        # Try to find matching Bitbucket user
        git_user = None
        if register_data.username:
            stmt = select(User).where(User.username == register_data.username)
            result = await self.db.execute(stmt)
            git_user = result.scalar_one_or_none()

        # If git user exists, mark them as reviewer
        if git_user and not git_user.is_reviewer:
            git_user.is_reviewer = True
            logger.info(
                f"Marked existing git user '{git_user.username}' as reviewer during registration"
            )
            # Flush the git user update to ensure it's persisted before creating auth_user
            await self.db.flush()

        # Create new auth user
        hashed_password = hash_password(register_data.password)
        new_auth_user = AuthUser(
            username=register_data.username,
            email=register_data.email,
            password_hash=hashed_password,
            user_id=git_user.id if git_user else None,
            is_active=True,
        )

        self.db.add(new_auth_user)
        await self.db.commit()
        await self.db.refresh(new_auth_user)

        # Auto-assign role based on Bitbucket user association
        has_git_user = git_user is not None
        await self._assign_default_role(new_auth_user.id, has_git_user)

        return await self._create_token_response(
            new_auth_user,
            self._generate_session_id(),
            ip_address=ip_address,
            user_agent=user_agent,
        )

    async def refresh_tokens(
        self,
        refresh_token: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> TokenResponse:
        """Refresh access and refresh tokens using a valid refresh session."""
        session_id = self._extract_session_id_from_refresh_token(refresh_token)
        session_data = await self._get_refresh_session(session_id)
        if not session_data:
            raise TokenExpiredException("Session expired due to inactivity")

        expected_hash = session_data.get("refresh_token_hash")
        if not expected_hash or not hmac.compare_digest(
            expected_hash, self._hash_token(refresh_token)
        ):
            await self._delete_refresh_session(session_id)
            raise InvalidTokenException("Invalid refresh token")

        auth_user = await self._get_auth_user_by_id(int(session_data["auth_user_id"]))
        return await self._create_token_response(
            auth_user,
            session_id,
            created_at=session_data.get("created_at"),
            ip_address=session_data.get("ip_address") or ip_address,
            user_agent=session_data.get("user_agent") or user_agent,
        )

    async def logout(self, token: str | None = None, refresh_token: str | None = None) -> None:
        """Invalidate the refresh session for the current login session."""
        session_id: str | None = None

        if refresh_token:
            try:
                session_id = self._extract_session_id_from_refresh_token(refresh_token)
            except InvalidTokenException:
                session_id = None

        if not session_id and token:
            try:
                payload = decode_access_token(token)
                session_id = payload.get("sid")
            except JWTError:
                session_id = None

        if session_id:
            await self._delete_refresh_session(session_id)

    async def get_session_id_from_token(self, token: str) -> str:
        """Extract the session id from an access token."""
        try:
            payload = decode_access_token(token)
            if payload.get("typ") != "access":
                raise InvalidTokenException("Invalid token type")
            session_id = payload.get("sid")
            if not session_id:
                raise InvalidTokenException("Session missing from token")
            return session_id
        except ExpiredSignatureError as exc:
            raise TokenExpiredException() from exc
        except JWTError as exc:
            raise InvalidTokenException() from exc

    async def sync_session_client_context(
        self,
        token: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Backfill client metadata for the active session without extending TTL."""
        session_id = await self.get_session_id_from_token(token)
        session_data = await self._get_refresh_session(session_id)
        if not session_data:
            return

        expires_in_seconds = await self.redis_client.ttl(self._get_refresh_session_key(session_id))
        if expires_in_seconds <= 0:
            return

        updated = False
        if ip_address and session_data.get("ip_address") != ip_address:
            session_data["ip_address"] = ip_address
            updated = True
        if user_agent and session_data.get("user_agent") != user_agent:
            session_data["user_agent"] = user_agent
            updated = True

        if updated:
            await self._write_refresh_session_data(session_id, session_data, expires_in_seconds)

    async def list_sessions(
        self,
        auth_user_id: int | None = None,
        username: str | None = None,
        current_session_id: str | None = None,
    ) -> list[AuthSessionResponse]:
        """List active refresh sessions, optionally filtered by auth user or username."""
        session_keys = await self.redis_client.keys(f"{REFRESH_SESSION_KEY_PREFIX}:*")
        sessions: list[AuthSessionResponse] = []

        for session_key in session_keys:
            session_id = session_key.removeprefix(f"{REFRESH_SESSION_KEY_PREFIX}:")
            session_data = await self._get_refresh_session(session_id)
            if not session_data:
                continue

            session_auth_user_id = int(session_data["auth_user_id"])
            session_username = session_data.get("username", "")

            # Apply filters
            if auth_user_id is not None and session_auth_user_id != auth_user_id:
                continue

            if username is not None and username.lower() not in session_username.lower():
                continue

            expires_in_seconds = await self.redis_client.ttl(session_key)
            if expires_in_seconds < 0:
                continue

            sessions.append(
                AuthSessionResponse(
                    session_id=session_id,
                    auth_user_id=session_auth_user_id,
                    username=session_username,
                    ip_address=session_data.get("ip_address"),
                    user_agent=session_data.get("user_agent"),
                    created_at=self._parse_datetime(session_data["created_at"]),
                    last_activity_at=self._parse_datetime(session_data["last_activity_at"]),
                    expires_in_seconds=expires_in_seconds,
                    is_current=session_id == current_session_id,
                )
            )

        sessions.sort(key=lambda session: session.last_activity_at, reverse=True)
        return sessions

    async def revoke_session(self, session_id: str) -> None:
        """Revoke a refresh session by session id."""
        deleted_count = await self.redis_client.delete(self._get_refresh_session_key(session_id))
        if deleted_count == 0:
            raise NotFoundException(message=f"Session {session_id} not found")

    async def revoke_user_session(self, auth_user_id: int, session_id: str) -> None:
        """Revoke a session only if it belongs to the specified user."""
        session_data = await self._get_refresh_session(session_id)
        if not session_data:
            raise NotFoundException(message=f"Session {session_id} not found")
        if int(session_data["auth_user_id"] or 0) != auth_user_id:
            raise InvalidTokenException("Session does not belong to the current user")
        await self._delete_refresh_session(session_id)

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
            if payload.get("typ") != "access":
                raise InvalidTokenException("Invalid token type")
            user_id: str = payload.get("sub")
            session_id: str | None = payload.get("sid")
            if user_id is None:
                raise InvalidTokenException()
            if not session_id:
                raise InvalidTokenException("Session missing from token")
        except ExpiredSignatureError as e:
            raise TokenExpiredException() from e
        except JWTError as e:
            raise InvalidTokenException() from e

        session_data = await self._get_refresh_session(session_id)
        if not session_data:
            raise TokenExpiredException("Session expired due to inactivity")

        return await self._get_auth_user_by_id(int(user_id))

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

        git_username = None
        if auth_user.user_id:
            stmt = select(User).where(User.id == auth_user.user_id)
            result = await self.db.execute(stmt)
            git_user = result.scalar_one_or_none()
            git_username = git_user.username if git_user else None

        return UserinfoResponse(
            id=auth_user.id,
            username=auth_user.username,
            email=auth_user.email,
            is_active=auth_user.is_active,
            git_user_id=auth_user.user_id,
            git_username=git_username,
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

    async def _auto_link_git_user(self, auth_user: AuthUser) -> bool:
        """Auto-link auth user with Bitbucket user by username

        Args:
            auth_user: Auth user to link

        Returns:
            True if successfully linked, False otherwise
        """
        stmt = select(User).where(User.username == auth_user.username)
        result = await self.db.execute(stmt)
        git_user = result.scalar_one_or_none()

        if git_user:
            auth_user.user_id = git_user.id
            await self.db.commit()
            logger.info(f"Auto-linked auth_user {auth_user.id} with Bitbucket user {git_user.id}")
            return True

        logger.debug(f"No Bitbucket user found for username: {auth_user.username}")
        return False

    async def _assign_default_role(self, auth_user_id: int, has_git_user: bool) -> None:
        """Assign default role to newly registered user

        Args:
            auth_user_id: The newly created auth user ID
            has_git_user: Whether a matching Bitbucket user was found
        """
        from src.models.role import Role
        from src.services.rbac_service import RBACService

        rbac_service = RBACService(self.db)

        # Determine role based on Bitbucket user association
        # If has Bitbucket user -> reviewer, otherwise -> viewer
        role_name = "reviewer" if has_git_user else "viewer"

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
                f"(has_git_user={has_git_user})"
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
                new_values={"role": "reviewer", "reason": "git_user_linked_on_login"},
            )
        except Exception as e:
            logger.warning(f"Failed to log login role upgrade audit: {e}")
