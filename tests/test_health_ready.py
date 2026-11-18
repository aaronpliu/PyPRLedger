"""Tests for the health endpoints.

`/api/health` is the liveness probe and answers from the process alone; the
readiness probe is what the load balancer should trust, so it has to really
probe MySQL and Redis and say not-ready when either is down.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import patch

import pytest


class FakeSession:
    """A session whose execute succeeds or fails as the test says."""

    def __init__(self, ok: bool) -> None:
        self.ok = ok

    async def execute(self, _query: object) -> None:
        if not self.ok:
            raise RuntimeError("database down")


def fake_db(ok: bool):
    @asynccontextmanager
    async def factory():
        yield FakeSession(ok)

    return factory


class FakeRedis:
    def __init__(self, ok: bool) -> None:
        self.ok = ok

    async def ping(self) -> bool:
        if not self.ok:
            raise RuntimeError("redis down")
        return True


@pytest.mark.asyncio
async def test_liveness_answers_without_touching_dependencies(async_client) -> None:
    # even with both dependencies patched to fail, liveness stays green - it is
    # the process probe, not the dependency probe
    with (
        patch("src.main.get_db_context", fake_db(ok=False)),
        patch("src.main.get_redis_client", lambda: FakeRedis(ok=False)),
    ):
        response = await async_client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert "version" in body


@pytest.mark.asyncio
async def test_readiness_reports_ready_when_both_dependencies_answer(async_client) -> None:
    with (
        patch("src.main.get_db_context", fake_db(ok=True)),
        patch("src.main.get_redis_client", lambda: FakeRedis(ok=True)),
    ):
        response = await async_client.get("/api/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["checks"] == {"database": "ok", "redis": "ok"}


@pytest.mark.asyncio
async def test_readiness_says_not_ready_when_database_is_down(async_client) -> None:
    with (
        patch("src.main.get_db_context", fake_db(ok=False)),
        patch("src.main.get_redis_client", lambda: FakeRedis(ok=True)),
    ):
        response = await async_client.get("/api/health/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unavailable"
    assert body["checks"]["database"] == "unavailable"
    assert body["checks"]["redis"] == "ok"


@pytest.mark.asyncio
async def test_readiness_says_not_ready_when_redis_is_down(async_client) -> None:
    with (
        patch("src.main.get_db_context", fake_db(ok=True)),
        patch("src.main.get_redis_client", lambda: FakeRedis(ok=False)),
    ):
        response = await async_client.get("/api/health/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["checks"]["database"] == "ok"
    assert body["checks"]["redis"] == "unavailable"
