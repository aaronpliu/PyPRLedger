"""Service for managing Personal Access Tokens"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from datetime import timedelta
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import AppException, ErrorCode
from src.models.personal_access_token import PersonalAccessToken
from src.utils.redis import get_redis_client
from src.utils.timezone import get_current_time


if TYPE_CHECKING:
    from src.models.auth_user import AuthUser


logger = logging.getLogger(__name__)

# Constants
TOKEN_PREFIX = "pat_"
TOKEN_LENGTH = 64  # bytes
MAX_TOKENS_PER_USER = 10
DEFAULT_EXPIRY_DAYS = 90
RATE_LIMIT_WINDOW = 3600  # 1 hour
RATE_LIMIT_MAX = 5  # 5 creations per hour


class PATService:
    """Service for managing Personal Access Tokens"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.redis_client = get_redis_client()

    async def create_token(
        self,
        auth_user_id: int,
        name: str,
        expires_in_days: int | None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[str, PersonalAccessToken]:
        """
        Create a new personal access token

        Returns:
            Tuple of (full_token_string, token_record)
        """
        # Check rate limit
        await self._check_rate_limit(auth_user_id)

        # Check token count limit
        await self._check_token_limit(auth_user_id)

        # Generate token
        raw_token = TOKEN_PREFIX + secrets.token_urlsafe(TOKEN_LENGTH)
        token_hash = self._hash_token(raw_token)
        prefix = raw_token[:12]  # Store first 12 chars for identification

        # Calculate expiry
        if expires_in_days is None:
            expires_in_days = DEFAULT_EXPIRY_DAYS

        now = get_current_time()
        expires_at = now + timedelta(days=expires_in_days)

        # Create record
        token_record = PersonalAccessToken(
            auth_user_id=auth_user_id,
            name=name,
            token_hash=token_hash,
            prefix=prefix,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        self.db.add(token_record)
        await self.db.commit()
        await self.db.refresh(token_record)

        logger.info(
            "PAT created",
            extra={
                "token_id": token_record.id,
                "user_id": auth_user_id,
                "token_name": name,
            },
        )

        return raw_token, token_record

    async def validate_token(self, token_string: str) -> PersonalAccessToken | None:
        """
        Validate a personal access token

        Returns:
            PersonalAccessToken record if valid, None otherwise
        """
        if not token_string.startswith(TOKEN_PREFIX):
            return None

        # Extract prefix
        prefix = token_string[:12]

        # Find by prefix
        result = await self.db.execute(
            select(PersonalAccessToken)
            .where(PersonalAccessToken.prefix == prefix)
            .where(PersonalAccessToken.is_active == True)
        )
        token_record = result.scalar_one_or_none()

        if not token_record:
            return None

        # Verify hash
        token_hash = self._hash_token(token_string)
        if not self._constant_time_compare(token_record.token_hash, token_hash):
            return None

        # Check expiration
        if token_record.expires_at:
            now = get_current_time()
            if token_record.expires_at < now:
                # Mark as inactive
                token_record.is_active = False
                await self.db.commit()
                logger.warning("PAT expired", extra={"token_id": token_record.id})
                return None

        # Update last used
        token_record.last_used_at = get_current_time()
        await self.db.commit()

        return token_record

    async def authenticate_with_token(
        self,
        token_string: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuthUser:
        """
        Authenticate user using personal access token

        Args:
            token_string: The full PAT string (pat_xxx...)
            ip_address: Client IP address for logging
            user_agent: User agent string for logging

        Returns:
            AuthUser object if authentication succeeds

        Raises:
            AppException: If token is invalid or expired
        """
        from src.models.auth_user import AuthUser

        token_record = await self.validate_token(token_string)

        if not token_record:
            raise AppException(
                error_code=ErrorCode.AUTHENTICATION_FAILED,
                message="Invalid or expired personal access token",
            )

        # Fetch the auth user
        result = await self.db.execute(
            select(AuthUser).where(AuthUser.id == token_record.auth_user_id)
        )
        auth_user = result.scalar_one_or_none()

        if not auth_user:
            raise AppException(
                error_code=ErrorCode.AUTHENTICATION_FAILED,
                message="User not found",
            )

        # Log authentication
        logger.info(
            "PAT authentication successful",
            extra={
                "user_id": auth_user.id,
                "username": auth_user.username,
                "token_id": token_record.id,
                "ip_address": ip_address,
            },
        )

        return auth_user

    async def list_tokens(
        self,
        auth_user_id: int,
        include_expired: bool = False,
    ) -> list[PersonalAccessToken]:
        """List tokens for a user"""
        query = select(PersonalAccessToken).where(PersonalAccessToken.auth_user_id == auth_user_id)

        if not include_expired:
            query = query.where(PersonalAccessToken.is_active == True)
        else:
            # Include expired tokens from last 3 months
            now = get_current_time()
            three_months_ago = now - timedelta(days=90)
            query = query.where(
                (PersonalAccessToken.is_active == True)
                | (PersonalAccessToken.expires_at >= three_months_ago)
            )

        query = query.order_by(PersonalAccessToken.created_at.desc())
        result = await self.db.execute(query)
        return result.scalars().all()

    async def revoke_token(self, auth_user_id: int, token_id: int) -> bool:
        """Revoke a token (verify ownership)"""
        result = await self.db.execute(
            select(PersonalAccessToken)
            .where(PersonalAccessToken.id == token_id)
            .where(PersonalAccessToken.auth_user_id == auth_user_id)
        )
        token_record = result.scalar_one_or_none()

        if not token_record:
            return False

        token_record.is_active = False
        await self.db.commit()

        logger.info(
            "PAT revoked",
            extra={
                "token_id": token_id,
                "user_id": auth_user_id,
            },
        )

        return True

    async def cleanup_expired_tokens(self) -> int:
        """
        Delete tokens that expired more than 3 months ago

        Returns:
            Number of deleted tokens
        """
        now = get_current_time()
        three_months_ago = now - timedelta(days=90)

        result = await self.db.execute(
            select(PersonalAccessToken)
            .where(PersonalAccessToken.expires_at < three_months_ago)
            .where(PersonalAccessToken.is_active == False)
        )
        expired_tokens = result.scalars().all()

        count = len(expired_tokens)
        for token in expired_tokens:
            await self.db.delete(token)

        await self.db.commit()

        if count > 0:
            logger.info("Cleaned up expired PATs", extra={"count": count})

        return count

    async def get_token_count(self, auth_user_id: int) -> int:
        """Count active tokens for a user"""
        result = await self.db.execute(
            select(PersonalAccessToken)
            .where(PersonalAccessToken.auth_user_id == auth_user_id)
            .where(PersonalAccessToken.is_active == True)
        )
        return len(result.scalars().all())

    # Private methods

    def _hash_token(self, token: str) -> str:
        """Hash token using SHA-256"""
        return hashlib.sha256(token.encode()).hexdigest()

    def _constant_time_compare(self, a: str, b: str) -> bool:
        """Constant-time comparison to prevent timing attacks"""
        return hmac.compare_digest(a.encode(), b.encode())

    async def _check_rate_limit(self, auth_user_id: int):
        """Check if user has exceeded token creation rate limit"""
        key = f"pat_rate_limit:{auth_user_id}"
        current = await self.redis_client.get(key)

        if current and int(current) >= RATE_LIMIT_MAX:
            raise AppException(
                error_code=ErrorCode.RATE_LIMIT_EXCEEDED,
                message=f"Token creation rate limit exceeded. Max {RATE_LIMIT_MAX} tokens per hour.",
            )

        # Increment counter
        pipe = self.redis_client.pipeline()
        pipe.incr(key)
        pipe.expire(key, RATE_LIMIT_WINDOW)
        await pipe.execute()

    async def _check_token_limit(self, auth_user_id: int):
        """Check if user has reached maximum token limit"""
        count = await self.get_token_count(auth_user_id)

        if count >= MAX_TOKENS_PER_USER:
            raise AppException(
                error_code=ErrorCode.VALIDATION_ERROR,
                message=f"Maximum {MAX_TOKENS_PER_USER} active tokens allowed per user.",
            )
