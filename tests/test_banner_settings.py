"""Tests for the reviews page banners.

The banners are a collection: several can be scheduled at once, each with its own
display window. They used to be four scalar settings describing exactly one
banner, so these tests also pin what happens to an installation that still has
those keys and has never opened the new editor.

The permission gate is opened in the fixture below: `require_permission` is
shared by every settings endpoint, and what is under test here is the banner
shape rather than the gate. The settings store underneath stays the real one, so
the round trip is a genuine read and write.
"""

from __future__ import annotations

import json

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.endpoints.rbac import (
    BANNER_SETTING_KEY,
    MAX_BANNERS,
    get_rbac_service,
)
from src.core.database import get_db_session
from src.core.permissions import get_current_user_with_token
from src.main import app
from src.models.auth_user import AuthUser
from src.services.rbac_service import RBACService


BANNER_URL = "/api/v1/rbac/settings/banner"


@pytest.fixture
def banner_client(async_client: AsyncClient, db_session: AsyncSession):
    """A client whose permission gate is open, over the real settings store."""

    class OpenRBACService(RBACService):
        async def require_permission(self, *args, **kwargs) -> None:
            return None

    async def _service() -> RBACService:
        return OpenRBACService(db_session)

    async def _current_user() -> AuthUser:
        return AuthUser(id=1, username="tester", email="tester@example.com")

    async def _db_session():
        yield db_session

    app.dependency_overrides[get_rbac_service] = _service
    app.dependency_overrides[get_current_user_with_token] = _current_user
    app.dependency_overrides[get_db_session] = _db_session
    yield async_client
    app.dependency_overrides.pop(get_rbac_service, None)
    app.dependency_overrides.pop(get_current_user_with_token, None)
    app.dependency_overrides.pop(get_db_session, None)


async def _store(db_session: AsyncSession, key: str, value: str) -> None:
    """Put a value in the settings store the way the application would."""
    service = RBACService(db_session)
    # A setting comes into existence by being read; update only touches existing rows.
    await service.get_setting(key, default_value="")
    await service.update_setting(setting_key=key, setting_value=value)


async def _banners(client: AsyncClient) -> list[dict]:
    response = await client.get(BANNER_URL)
    assert response.status_code == 200
    return response.json()["banners"]


async def test_no_banner_is_configured_at_first(banner_client: AsyncClient) -> None:
    assert await _banners(banner_client) == []


async def test_the_legacy_single_banner_is_folded_into_the_list(
    banner_client: AsyncClient, db_session: AsyncSession
) -> None:
    """An installation that never opened the editor keeps the banner it had."""
    await _store(db_session, "banner_enabled", "true")
    await _store(db_session, "banner_content", "Code freeze on Friday")
    await _store(db_session, "banner_start_date", "2026-10-01T00:00:00+08:00")
    await _store(db_session, "banner_end_date", "")

    banners = await _banners(banner_client)

    assert len(banners) == 1
    assert banners[0]["content"] == "Code freeze on Friday"
    assert banners[0]["enabled"] is True
    assert banners[0]["start_date"] == "2026-10-01T00:00:00+08:00"
    # The list shape carries the newer fields too, so the editor opens on a whole item.
    assert banners[0]["level"] == "info"
    assert banners[0]["priority"] == 0
    assert banners[0]["link_url"] == ""


async def test_a_folded_banner_keeps_the_same_identity_between_reads(
    banner_client: AsyncClient, db_session: AsyncSession
) -> None:
    """A dismissal is keyed on the banner, so a derived id has to be stable."""
    await _store(db_session, "banner_content", "Same words")

    first = await _banners(banner_client)
    second = await _banners(banner_client)

    assert first[0]["id"] == second[0]["id"]


async def test_banners_round_trip_through_the_endpoint(banner_client: AsyncClient) -> None:
    payload = {
        "banners": [
            {
                "id": "release-notes",
                "enabled": True,
                "content": "Release 1.27 is out",
                "start_date": "2026-10-01T00:00:00+08:00",
                "end_date": "2026-10-31T23:59:59+08:00",
                "level": "success",
                "link_url": "https://git.local/notes",
                "link_label": "Notes",
                "priority": 5,
            },
            {"enabled": False, "content": "Second notice", "level": "warning"},
        ]
    }

    put = await banner_client.put(BANNER_URL, json=payload)
    assert put.status_code == 200

    banners = await _banners(banner_client)
    assert [banner["content"] for banner in banners] == ["Release 1.27 is out", "Second notice"]

    first, second = banners
    assert first == payload["banners"][0]
    assert second["level"] == "warning"
    assert second["priority"] == 0
    # Saved without an id, so one is derived from what the banner says.
    assert second["id"]


async def test_a_derived_id_survives_a_re_save(banner_client: AsyncClient) -> None:
    payload = {"banners": [{"content": "Unchanged", "enabled": True}]}

    await banner_client.put(BANNER_URL, json=payload)
    first = (await _banners(banner_client))[0]["id"]
    await banner_client.put(BANNER_URL, json=payload)
    second = (await _banners(banner_client))[0]["id"]

    assert first == second


async def test_validation_refuses_what_a_banner_could_not_render(
    banner_client: AsyncClient,
) -> None:
    cases = [
        {"banners": [{"content": "   "}]},
        {"banners": [{"content": "x", "start_date": "not-a-date"}]},
        {"banners": [{"content": "x", "link_url": "javascript:alert(1)"}]},
        {"banners": [{"content": "x" * 501}]},
        {"banners": [{"content": "x"}] * (MAX_BANNERS + 1)},
        {"banners": "not a list"},
        {"banners": ["not an object"]},
    ]

    for payload in cases:
        response = await banner_client.put(BANNER_URL, json=payload)
        assert response.status_code == 400, payload


async def test_the_legacy_write_shape_still_replaces_the_banners(
    banner_client: AsyncClient,
) -> None:
    """A page that predates the list shape sends one banner's fields."""
    response = await banner_client.put(
        BANNER_URL,
        json={"enabled": True, "content": "Only one", "start_date": "", "end_date": ""},
    )

    assert response.status_code == 200
    banners = await _banners(banner_client)
    assert [banner["content"] for banner in banners] == ["Only one"]
    assert banners[0]["enabled"] is True


async def test_a_partial_legacy_write_cannot_wipe_the_banners(
    banner_client: AsyncClient,
) -> None:
    await banner_client.put(BANNER_URL, json={"banners": [{"content": "Keep me"}]})

    response = await banner_client.put(BANNER_URL, json={"enabled": False})

    assert response.status_code == 400
    assert [banner["content"] for banner in await _banners(banner_client)] == ["Keep me"]


async def test_unreadable_stored_banners_fall_back_to_the_legacy_keys(
    banner_client: AsyncClient, db_session: AsyncSession
) -> None:
    """A hand-edited row should not take the settings page down."""
    await _store(db_session, "banner_content", "Still the old one")
    await _store(db_session, BANNER_SETTING_KEY, "{not json")

    banners = await _banners(banner_client)

    assert [banner["content"] for banner in banners] == ["Still the old one"]


async def test_one_unusable_stored_banner_does_not_lose_the_others(
    banner_client: AsyncClient, db_session: AsyncSession
) -> None:
    stored = json.dumps([{"content": "Good"}, {"content": ""}, "junk"])
    await _store(db_session, BANNER_SETTING_KEY, stored)

    banners = await _banners(banner_client)

    assert [banner["content"] for banner in banners] == ["Good"]


async def test_the_permission_gate_still_applies(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """The list shape must not have opened the endpoint up."""

    async def _current_user() -> AuthUser:
        return AuthUser(id=999, username="nobody", email="nobody@example.com")

    async def _db_session():
        yield db_session

    # The real RBAC service answers the gate here, so it needs a database; only
    # the user is faked, and that user holds no role.
    app.dependency_overrides[get_current_user_with_token] = _current_user
    app.dependency_overrides[get_db_session] = _db_session
    try:
        response = await async_client.put(BANNER_URL, json={"banners": []})
    finally:
        app.dependency_overrides.pop(get_current_user_with_token, None)
        app.dependency_overrides.pop(get_db_session, None)

    assert response.status_code == 403
