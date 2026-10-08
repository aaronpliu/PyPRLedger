"""Tests for the device description a session carries.

The user agent string no longer describes the device it is sent from: Chromium
freezes the browser build, replaces the Android device model with ``K``, and
reports Windows 11 as Windows 10, while Safari pins macOS to 10.15.7. A client
therefore reports a structured record about itself, and the server stores it on
the session. These tests pin the contract:

- the record travels from the request header onto the session and back out
  through the session list;
- a malformed or hostile header is ignored, never trusted and never fatal;
- an approximate record never replaces a precise one, while the reverse upgrade
  always may;
- the record survives the token refresh that rebuilds the session.
"""

from __future__ import annotations

import base64
import json

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.endpoints.auth import CLIENT_DEVICE_HEADER, parse_client_device_header
from src.core.config import settings
from src.core.database import get_db_session
from src.main import app
from src.models.auth_user import AuthUser
from src.schemas.auth import LoginRequest, SessionDeviceInfo
from src.services.auth_service import AuthService
from src.utils.password import hash_password


CHROME_ANDROID_UA = (
    "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Mobile Safari/537.36"
)


def _encode_payload(payload: dict[str, object]) -> str:
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()


def _encode_device(**overrides: object) -> str:
    return _encode_payload(
        {
            "source": "client-hints",
            "category": "mobile",
            "platform": "Android",
            "platform_version": "14.0.0",
            "model": "Pixel 8",
            "browser_full_version": "140.0.7339.80",
            **overrides,
        }
    )


def _precise_device() -> SessionDeviceInfo:
    return SessionDeviceInfo(
        source="client-hints",
        category="mobile",
        platform="Android",
        platform_version="14.0.0",
        model="Pixel 8",
        browser_full_version="140.0.7339.80",
    )


async def _seed_user(db_session: AsyncSession, *, username: str = "device-tester") -> AuthUser:
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


async def _login(
    db_session: AsyncSession,
    auth_user: AuthUser,
    device: SessionDeviceInfo | None = None,
) -> tuple[AuthService, str, str]:
    """Log the user in and return (service, access_token, refresh_token)."""
    service = AuthService(db_session)
    response = await service.authenticate(
        LoginRequest(username=auth_user.username, password="testpassword"),
        user_agent=CHROME_ANDROID_UA,
        device=device,
    )
    return service, response.access_token, response.refresh_token


async def _stored_device(service: AuthService, auth_user: AuthUser) -> SessionDeviceInfo | None:
    sessions = await service.list_sessions(auth_user_id=auth_user.id)
    assert len(sessions) == 1
    return sessions[0].device


def test_the_header_name_is_the_agreed_contract() -> None:
    """The frontend sends this exact name; renaming one side alone breaks it."""
    assert CLIENT_DEVICE_HEADER == "X-Client-Device"


def test_decodes_the_record_a_client_reports() -> None:
    device = parse_client_device_header(_encode_device())

    assert device is not None
    assert device.source == "client-hints"
    assert device.category == "mobile"
    assert device.model == "Pixel 8"
    assert device.platform_version == "14.0.0"
    assert device.browser_full_version == "140.0.7339.80"


def test_decodes_a_record_sent_without_padding() -> None:
    assert parse_client_device_header(_encode_device().rstrip("=")) is not None


def test_accepts_a_record_that_knows_only_the_device_class() -> None:
    """Safari and Firefox have no client hints, so the record is that thin."""
    raw = _encode_payload({"source": "user-agent", "category": "tablet"})

    device = parse_client_device_header(raw)

    assert device is not None
    assert device.source == "user-agent"
    assert device.category == "tablet"
    assert device.model is None
    assert device.platform is None


def test_ignores_a_record_it_cannot_believe() -> None:
    """Display metadata: a broken header is dropped, not rejected or trusted."""
    assert parse_client_device_header("!!! not base64 !!!") is None
    assert parse_client_device_header(base64.urlsafe_b64encode(b"not json").decode()) is None
    assert parse_client_device_header(_encode_device(source="spoofed-source")) is None
    assert parse_client_device_header(_encode_device(category="toaster")) is None
    assert parse_client_device_header(_encode_device(source=None)) is None


def test_ignores_an_absent_or_oversized_header() -> None:
    assert parse_client_device_header(None) is None
    assert parse_client_device_header("") is None
    # A client cannot use this header to grow the session record without bound.
    assert parse_client_device_header("A" * 4096) is None


def test_drops_one_bad_field_instead_of_the_whole_record() -> None:
    """The rest of a device description is still worth keeping."""
    truncated = parse_client_device_header(_encode_device(model="x" * 200))
    assert truncated is not None
    assert truncated.model is not None
    assert len(truncated.model) == 64

    mistyped = parse_client_device_header(_encode_device(model=12345))
    assert mistyped is not None
    assert mistyped.model is None
    assert mistyped.platform == "Android"


async def test_login_stores_the_reported_device(db_session: AsyncSession) -> None:
    auth_user = await _seed_user(db_session)
    service, _, _ = await _login(db_session, auth_user, device=_precise_device())

    assert await _stored_device(service, auth_user) == _precise_device()


async def test_login_without_a_reported_device_still_succeeds(
    db_session: AsyncSession,
) -> None:
    """Older clients send nothing, and their sessions must keep working."""
    auth_user = await _seed_user(db_session)
    service, access_token, _ = await _login(db_session, auth_user)

    assert await _stored_device(service, auth_user) is None
    assert access_token


async def test_sync_backfills_a_device_onto_a_session_that_lacks_one(
    db_session: AsyncSession,
) -> None:
    auth_user = await _seed_user(db_session)
    service, access_token, _ = await _login(db_session, auth_user)
    assert await _stored_device(service, auth_user) is None

    await service.sync_session_client_context(access_token, device=_precise_device())

    assert await _stored_device(service, auth_user) == _precise_device()


async def test_an_approximate_record_never_replaces_a_precise_one(
    db_session: AsyncSession,
) -> None:
    """Chromium reports precise values; a later user-agent guess must not undo it."""
    auth_user = await _seed_user(db_session)
    service, access_token, _ = await _login(db_session, auth_user, device=_precise_device())

    await service.sync_session_client_context(
        access_token,
        device=SessionDeviceInfo(source="user-agent", category="tablet"),
    )

    stored = await _stored_device(service, auth_user)
    assert stored is not None
    assert stored.source == "client-hints"
    assert stored.platform_version == "14.0.0"
    assert stored.model == "Pixel 8"


async def test_a_precise_record_replaces_an_approximate_one(
    db_session: AsyncSession,
) -> None:
    auth_user = await _seed_user(db_session)
    service, access_token, _ = await _login(
        db_session,
        auth_user,
        device=SessionDeviceInfo(source="user-agent", category="tablet"),
    )

    await service.sync_session_client_context(access_token, device=_precise_device())

    stored = await _stored_device(service, auth_user)
    assert stored is not None
    assert stored.source == "client-hints"
    assert stored.platform_version == "14.0.0"


async def test_token_refresh_keeps_the_device(db_session: AsyncSession) -> None:
    """Refreshing rebuilds the stored session, so the device has to be carried."""
    auth_user = await _seed_user(db_session)
    service, _, refresh_token = await _login(db_session, auth_user, device=_precise_device())

    await service.refresh_tokens(refresh_token)

    assert await _stored_device(service, auth_user) == _precise_device()


async def test_login_header_reaches_the_session(db_session: AsyncSession) -> None:
    """The header the frontend attaches is what the endpoint reads."""
    auth_user = await _seed_user(db_session)

    async def _db_override():
        yield db_session

    app.dependency_overrides[get_db_session] = _db_override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"{settings.API_V1_STR}/auth/login",
                json={"username": auth_user.username, "password": "testpassword"},
                headers={CLIENT_DEVICE_HEADER: _encode_device(), "User-Agent": CHROME_ANDROID_UA},
            )
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert response.status_code == 200
    assert await _stored_device(AuthService(db_session), auth_user) == _precise_device()


async def test_a_malformed_device_header_does_not_block_a_login(
    db_session: AsyncSession,
) -> None:
    """The header is display metadata; it must never cost someone their login."""
    auth_user = await _seed_user(db_session)

    async def _db_override():
        yield db_session

    app.dependency_overrides[get_db_session] = _db_override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"{settings.API_V1_STR}/auth/login",
                json={"username": auth_user.username, "password": "testpassword"},
                headers={CLIENT_DEVICE_HEADER: "garbage", "User-Agent": CHROME_ANDROID_UA},
            )
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert response.status_code == 200
    assert await _stored_device(AuthService(db_session), auth_user) is None
