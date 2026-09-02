"""Tests for the sliding idle session timeout (heartbeat).

Verifies the semantics agreed for the idle-timeout redesign:
- An active user's session TTL is only extended by an explicit heartbeat
  (touch_session), driven by real user activity on the frontend.
- Token refresh and ordinary traffic must NOT extend the TTL, so background
  polling cannot keep an idle session alive.
- Once the session is gone (user idle past the timeout), touch_session
  surfaces the same failure the refresh flow would.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.exceptions import InvalidTokenException, TokenExpiredException
from src.main import app
from src.models.auth_user import AuthUser
from src.schemas.auth import LoginRequest
from src.services.auth_service import AuthService
from src.utils.password import hash_password
from src.utils.redis import get_redis_client


IDLE_TIMEOUT_SECONDS = settings.REFRESH_TOKEN_IDLE_TIMEOUT_MINUTES * 60


async def _seed_user(db_session: AsyncSession, *, username: str = "idle-tester") -> AuthUser:
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


async def _login(db_session: AsyncSession, auth_user: AuthUser) -> tuple[AuthService, str, str]:
    """Log the user in and return (service, access_token, refresh_token)."""
    service = AuthService(db_session)
    response = await service.authenticate(
        LoginRequest(username=auth_user.username, password="testpassword")
    )
    return service, response.access_token, response.refresh_token


def _session_key(service: AuthService, refresh_token: str) -> str:
    session_id = service._extract_session_id_from_refresh_token(refresh_token)
    return service._get_refresh_session_key(session_id)


async def _remaining_ttl(service: AuthService, refresh_token: str) -> int:
    """Remaining TTL (seconds) of the refresh session for a given refresh token."""
    return await get_redis_client().ttl(_session_key(service, refresh_token))


async def _shrink_ttl(service: AuthService, refresh_token: str, seconds: int) -> None:
    """Simulate most of the idle window already having elapsed."""
    await get_redis_client().expire(_session_key(service, refresh_token), seconds)


async def test_touch_session_resets_ttl_to_full_idle_timeout(db_session: AsyncSession) -> None:
    """Real activity restores the full idle window instead of force-logging-out."""
    auth_user = await _seed_user(db_session)
    service, access_token, refresh_token = await _login(db_session, auth_user)

    await _shrink_ttl(service, refresh_token, 600)
    assert 599 <= await _remaining_ttl(service, refresh_token) <= 600

    await service.touch_session(access_token)

    ttl = await _remaining_ttl(service, refresh_token)
    assert IDLE_TIMEOUT_SECONDS - 5 <= ttl <= IDLE_TIMEOUT_SECONDS


async def test_touch_session_raises_when_session_expired(db_session: AsyncSession) -> None:
    """Idle past the timeout → session is gone → touch_session fails like refresh."""
    auth_user = await _seed_user(db_session)
    service, access_token, refresh_token = await _login(db_session, auth_user)

    await service.logout(refresh_token=refresh_token)

    try:
        await service.touch_session(access_token)
    except TokenExpiredException:
        pass
    else:  # pragma: no cover - failure to raise is the regression
        raise AssertionError("touch_session should raise TokenExpiredException for a dead session")


async def test_touch_session_rejects_non_access_token(db_session: AsyncSession) -> None:
    """Refresh tokens must not be accepted by the heartbeat."""
    auth_user = await _seed_user(db_session)
    service, _, refresh_token = await _login(db_session, auth_user)

    try:
        await service.touch_session(refresh_token)
    except (TokenExpiredException, InvalidTokenException):
        pass
    else:  # pragma: no cover - failure to raise is the regression
        raise AssertionError("touch_session should reject a non-access token")


async def test_token_refresh_does_not_extend_ttl(db_session: AsyncSession) -> None:
    """Refresh must preserve the remaining TTL — regression guard for v1.20.5 fix."""
    auth_user = await _seed_user(db_session)
    service, _, refresh_token = await _login(db_session, auth_user)

    await _shrink_ttl(service, refresh_token, 600)
    await service.refresh_tokens(refresh_token)

    # TTL still ~10 min, NOT reset back to the full idle timeout.
    ttl = await _remaining_ttl(service, refresh_token)
    assert 590 <= ttl <= 600


async def test_heartbeat_route_registered() -> None:
    """POST /api/v1/auth/heartbeat exists on the app router."""
    route = next((r for r in app.routes if r.path == "/api/v1/auth/heartbeat"), None)
    assert route is not None, "POST /api/v1/auth/heartbeat route missing"
    assert "POST" in route.methods
