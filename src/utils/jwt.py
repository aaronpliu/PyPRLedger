"""JWT Token utilities for authentication"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt

from src.core.config import settings


def create_access_token(
    subject: str | int,
    expires_delta: timedelta | None = None,
    extra_data: dict[str, Any] | None = None,
) -> str:
    """Create JWT access token

    Args:
        subject: User identifier (user ID or username)
        expires_delta: Token expiration time
        extra_data: Additional data to include in token

    Returns:
        Encoded JWT token string
    """
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode: dict[str, Any] = {"exp": expire, "sub": str(subject)}

    if extra_data:
        to_encode.update(extra_data)

    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )

    return encoded_jwt


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate JWT access token

    Args:
        token: JWT token string

    Returns:
        Decoded token payload

    Raises:
        JWTError: If token is invalid or expired
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        return payload
    except JWTError as e:
        raise JWTError(f"Invalid or expired token: {e}") from e


def verify_token_subject(token: str, expected_subject: str | int) -> bool:
    """Verify that token belongs to expected user

    Args:
        token: JWT token string
        expected_subject: Expected user ID or username

    Returns:
        True if token subject matches expected subject
    """
    try:
        payload = decode_access_token(token)
        return str(payload.get("sub")) == str(expected_subject)
    except JWTError:
        return False
