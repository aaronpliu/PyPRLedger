"""Login lockout: too many failed attempts must block the username briefly.

The counter lives in Redis so it is shared by every API worker, which means a
credential-stuffing run against one worker cannot be spread across the others.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.exceptions import AccountLockedException, InvalidCredentialsException
from src.models.auth_user import AuthUser
from src.schemas.auth import LoginRequest
from src.services.auth_service import AuthService
from src.utils.password import hash_password


async def _seed_user(db_session: AsyncSession, *, username: str = "lockout-tester") -> AuthUser:
    auth_user = AuthUser(
        username=username,
        email=f"{username}@example.com",
        password_hash=hash_password("testpassword"),
        is_active=True,
    )
    db_session.add(auth_user)
    await db_session.commit()
    await db_session.refresh(auth_user)
    return auth_user


async def test_repeated_failures_lock_the_username(db_session: AsyncSession, monkeypatch) -> None:
    monkeypatch.setattr(settings, "LOGIN_MAX_FAILED_ATTEMPTS", 3)
    auth_user = await _seed_user(db_session)
    service = AuthService(db_session)

    for _ in range(3):
        with pytest.raises(InvalidCredentialsException):
            await service.authenticate(
                LoginRequest(username=auth_user.username, password="wrong-password")
            )

    # Even the correct password is refused while the lockout window runs
    with pytest.raises(AccountLockedException) as excinfo:
        await service.authenticate(
            LoginRequest(username=auth_user.username, password="testpassword")
        )

    assert "minute" in str(excinfo.value.detail)


async def test_successful_login_clears_the_counter(db_session: AsyncSession, monkeypatch) -> None:
    monkeypatch.setattr(settings, "LOGIN_MAX_FAILED_ATTEMPTS", 3)
    auth_user = await _seed_user(db_session, username="lockout-reset")
    service = AuthService(db_session)

    for _ in range(2):
        with pytest.raises(InvalidCredentialsException):
            await service.authenticate(
                LoginRequest(username=auth_user.username, password="wrong-password")
            )

    await service.authenticate(LoginRequest(username=auth_user.username, password="testpassword"))

    # The counter is gone, so two more failures do not trip the lockout
    for _ in range(2):
        with pytest.raises(InvalidCredentialsException):
            await service.authenticate(
                LoginRequest(username=auth_user.username, password="wrong-password")
            )


async def test_unknown_usernames_are_counted_too(db_session: AsyncSession, monkeypatch) -> None:
    monkeypatch.setattr(settings, "LOGIN_MAX_FAILED_ATTEMPTS", 2)
    service = AuthService(db_session)

    for _ in range(2):
        with pytest.raises(InvalidCredentialsException):
            await service.authenticate(LoginRequest(username="nobody-here", password="whatever"))

    # Guessing against a non-existent name is no cheaper than a real one
    with pytest.raises(AccountLockedException):
        await service.authenticate(LoginRequest(username="nobody-here", password="whatever"))


async def test_lockout_key_is_case_insensitive(db_session: AsyncSession, monkeypatch) -> None:
    monkeypatch.setattr(settings, "LOGIN_MAX_FAILED_ATTEMPTS", 2)
    await _seed_user(db_session, username="CaseTester")
    service = AuthService(db_session)

    for _ in range(2):
        with pytest.raises(InvalidCredentialsException):
            await service.authenticate(
                LoginRequest(username="casetester", password="wrong-password")
            )

    with pytest.raises(AccountLockedException):
        await service.authenticate(LoginRequest(username="casetester", password="wrong-password"))
