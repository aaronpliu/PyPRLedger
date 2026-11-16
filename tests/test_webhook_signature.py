"""Review write requests must be authenticated.

Git providers post PR data without a user token, so they sign the body with
WEBHOOK_SHARED_SECRET. Everything else is refused: an unconfigured deployment
must not accept anonymous writes.
"""

from __future__ import annotations

import time

import pytest
from httpx import AsyncClient

from src.core.config import settings
from src.core.database import get_db_session
from src.main import app
from src.utils.webhook_signature import (
    MAX_CLOCK_SKEW_SECONDS,
    SIGNATURE_HEADER,
    TIMESTAMP_HEADER,
    compute_signature,
    verify_signature,
)


SECRET = "test-webhook-secret"
BODY = b'{"pull_request_id": 1}'


@pytest.fixture(autouse=True)
def _override_db(db_session):
    """Answer the endpoint's session dependency with the test session."""

    async def _session():
        yield db_session

    app.dependency_overrides[get_db_session] = _session
    yield
    app.dependency_overrides.pop(get_db_session, None)


# --- signature helper ---------------------------------------------------------


def test_valid_signature_is_accepted():
    timestamp = str(int(time.time()))
    signature = compute_signature(SECRET, timestamp, BODY)

    assert verify_signature(SECRET, timestamp, signature, BODY)


def test_signature_for_a_different_body_is_rejected():
    timestamp = str(int(time.time()))
    signature = compute_signature(SECRET, timestamp, BODY)

    assert not verify_signature(SECRET, timestamp, signature, b'{"pull_request_id": 2}')


def test_signature_from_a_different_secret_is_rejected():
    timestamp = str(int(time.time()))
    signature = compute_signature("another-secret", timestamp, BODY)

    assert not verify_signature(SECRET, timestamp, signature, BODY)


def test_stale_timestamp_is_rejected():
    old_timestamp = str(int(time.time()) - MAX_CLOCK_SKEW_SECONDS - 60)
    signature = compute_signature(SECRET, old_timestamp, BODY)

    assert not verify_signature(SECRET, old_timestamp, signature, BODY)


def test_missing_parts_are_rejected():
    assert not verify_signature(SECRET, None, "sha256=abc", BODY)
    assert not verify_signature(SECRET, "123", None, BODY)
    assert not verify_signature("", "123", "sha256=abc", BODY)


# --- endpoint guard -----------------------------------------------------------


async def test_anonymous_write_is_refused_when_no_secret_is_configured(
    async_client: AsyncClient, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "WEBHOOK_SHARED_SECRET", "")

    response = await async_client.post("/api/v1/reviews", json={})

    assert response.status_code == 401


async def test_write_with_invalid_signature_is_refused(
    async_client: AsyncClient, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "WEBHOOK_SHARED_SECRET", SECRET)

    response = await async_client.post(
        "/api/v1/reviews",
        json={},
        headers={TIMESTAMP_HEADER: str(int(time.time())), SIGNATURE_HEADER: "sha256=deadbeef"},
    )

    assert response.status_code == 401


async def test_write_with_missing_signature_is_refused(
    async_client: AsyncClient, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "WEBHOOK_SHARED_SECRET", SECRET)

    response = await async_client.post("/api/v1/reviews", json={})

    assert response.status_code == 401


async def test_write_with_valid_signature_passes_authentication(
    async_client: AsyncClient, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "WEBHOOK_SHARED_SECRET", SECRET)

    body = b"{}"
    timestamp = str(int(time.time()))
    response = await async_client.post(
        "/api/v1/reviews",
        content=body,
        headers={
            "Content-Type": "application/json",
            TIMESTAMP_HEADER: timestamp,
            SIGNATURE_HEADER: compute_signature(SECRET, timestamp, body),
        },
    )

    # The payload itself is invalid, but the request is no longer rejected as
    # unauthenticated - which is what this test pins down.
    assert response.status_code != 401


@pytest.mark.parametrize("method", ["get"])
async def test_reads_still_require_a_token(async_client: AsyncClient, method: str) -> None:
    response = await getattr(async_client, method)("/api/v1/reviews")

    assert response.status_code == 401
