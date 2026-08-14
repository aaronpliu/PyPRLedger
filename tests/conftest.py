"""
Pytest configuration and fixtures
"""

from __future__ import annotations

import fnmatch
import time
from collections.abc import AsyncGenerator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.database import Base
from src.main import app


# Test database URL
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


class InMemoryRedis:
    """Dict-backed in-memory Redis client for offline tests.

    Implements the subset of the async redis interface used by the
    application's services, cache utilities, middleware and SSE broker so
    the suite runs without a real Redis server.
    """

    def __init__(self) -> None:
        self._data: dict[str, str] = {}
        self._expires_at: dict[str, float] = {}
        self._hashes: dict[str, dict[str, str]] = {}
        self._lists: dict[str, list[str]] = {}
        self._zsets: dict[str, dict[str, float]] = {}
        self._pubsub_callbacks: dict[str, list[Any]] = {}

    def _purge_expired(self, key: str) -> None:
        expires = self._expires_at.get(key)
        if expires is not None and expires <= time.monotonic():
            self._data.pop(key, None)
            self._expires_at.pop(key, None)

    def _purge_all_expired(self) -> None:
        for key in list(self._data):
            self._purge_expired(key)

    async def ping(self) -> bool:
        return True

    async def get(self, key: str) -> str | None:
        self._purge_expired(key)
        return self._data.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        self._data[key] = value
        self._expires_at.pop(key, None)
        if ex is not None:
            self._expires_at[key] = time.monotonic() + ex
        return True

    async def setex(self, key: str, seconds: int, value: str) -> bool:
        return await self.set(key, value, ex=seconds)

    async def delete(self, *keys: str) -> int:
        count = 0
        for key in keys:
            self._purge_expired(key)
            if key in self._data:
                self._data.pop(key, None)
                self._expires_at.pop(key, None)
                count += 1
        return count

    async def exists(self, *keys: str) -> int:
        return sum(1 for key in keys if key in self._data)

    async def incr(self, key: str) -> int:
        current = int(self._data.get(key, "0")) + 1
        self._data[key] = str(current)
        return current

    async def decr(self, key: str) -> int:
        current = int(self._data.get(key, "0")) - 1
        self._data[key] = str(current)
        return current

    async def expire(self, key: str, seconds: int) -> bool:
        if key not in self._data:
            return False
        self._expires_at[key] = time.monotonic() + seconds
        return True

    async def expireat(self, key: str, timestamp: int) -> bool:
        if key not in self._data:
            return False
        self._expires_at[key] = float(timestamp)
        return True

    async def ttl(self, key: str) -> int:
        self._purge_expired(key)
        if key not in self._data:
            return -2
        expires = self._expires_at.get(key)
        if expires is None:
            return -1
        return max(0, int(expires - time.monotonic()))

    async def keys(self, pattern: str) -> list[str]:
        self._purge_all_expired()
        return [key for key in self._data if fnmatch.fnmatch(key, pattern)]

    async def publish(self, channel: str, message: str) -> int:
        for callback in self._pubsub_callbacks.get(channel, []):
            callback(message)
        return len(self._pubsub_callbacks.get(channel, []))

    def pubsub(self) -> _FakePubSub:
        return _FakePubSub(self)

    def pipeline(self) -> _FakePipeline:
        return _FakePipeline(self)

    async def hset(self, name: str, key: str, value: str) -> int:
        self._hashes.setdefault(name, {})[key] = value
        return 1

    async def hget(self, name: str, key: str) -> str | None:
        return self._hashes.get(name, {}).get(key)

    async def hgetall(self, name: str) -> dict[str, str]:
        return dict(self._hashes.get(name, {}))

    async def hdel(self, name: str, *keys: str) -> int:
        mapping = self._hashes.get(name)
        if not mapping:
            return 0
        count = 0
        for key in keys:
            if key in mapping:
                mapping.pop(key, None)
                count += 1
        return count

    async def lpush(self, name: str, *values: str) -> int:
        self._lists.setdefault(name, [])[0:0] = values
        return len(self._lists[name])

    async def rpush(self, name: str, *values: str) -> int:
        self._lists.setdefault(name, []).extend(values)
        return len(self._lists[name])

    async def lpop(self, name: str) -> str | None:
        items = self._lists.get(name)
        if not items:
            return None
        return items.pop(0)

    async def rpop(self, name: str) -> str | None:
        items = self._lists.get(name)
        if not items:
            return None
        return items.pop()

    async def llen(self, name: str) -> int:
        return len(self._lists.get(name, []))

    async def lrange(self, name: str, start: int = 0, end: int = -1) -> list[str]:
        items = self._lists.get(name, [])
        return items[start:] if end == -1 else items[start : end + 1]

    async def zadd(self, name: str, mapping: dict[str, float]) -> int:
        zset = self._zsets.setdefault(name, {})
        added = 0
        for member, score in mapping.items():
            if member not in zset:
                added += 1
            zset[member] = score
        return added

    async def zrem(self, name: str, *values: str) -> int:
        zset = self._zsets.get(name)
        if not zset:
            return 0
        count = 0
        for value in values:
            if value in zset:
                zset.pop(value, None)
                count += 1
        return count

    async def zrange(
        self,
        name: str,
        start: int = 0,
        end: int = -1,
        desc: bool = False,
        withscores: bool = False,
    ) -> list[Any]:
        zset = self._zsets.get(name, {})
        ordered = sorted(zset.items(), key=lambda item: item[1], reverse=desc)
        selected = ordered[start:] if end == -1 else ordered[start : end + 1]
        if withscores:
            return [{"member": member, "score": score} for member, score in selected]
        return [member for member, _ in selected]

    async def zrank(self, name: str, value: str) -> int | None:
        zset = self._zsets.get(name, {})
        ordered = sorted(zset.items(), key=lambda item: item[1])
        for index, (member, _) in enumerate(ordered):
            if member == value:
                return index
        return None

    async def zscore(self, name: str, value: str) -> float | None:
        return self._zsets.get(name, {}).get(value)

    async def close(self) -> None:
        self._data.clear()
        self._expires_at.clear()
        self._hashes.clear()
        self._lists.clear()
        self._zsets.clear()
        self._pubsub_callbacks.clear()


class _FakePubSub:
    """Minimal async pub/sub stub backed by InMemoryRedis."""

    def __init__(self, redis: InMemoryRedis) -> None:
        self._redis = redis
        self._channels: set[str] = set()
        self._messages: list[dict[str, str]] = []

    async def subscribe(self, *channels: str) -> None:
        self._channels.update(channels)
        for channel in channels:
            self._redis._pubsub_callbacks.setdefault(channel, []).append(self._on_message)

    async def unsubscribe(self, *channels: str) -> None:
        for channel in channels:
            callbacks = self._redis._pubsub_callbacks.get(channel, [])
            self._redis._pubsub_callbacks[channel] = [
                callback for callback in callbacks if callback is not self._on_message
            ]
            self._channels.discard(channel)

    def _on_message(self, message: str) -> None:
        self._messages.append({"type": "message", "data": message})

    async def get_message(self, timeout: float = 0.0) -> dict[str, str] | None:
        if self._messages:
            return self._messages.pop(0)
        return None

    async def close(self) -> None:
        for channel in list(self._channels):
            await self.unsubscribe(channel)


class _FakePipeline:
    """Buffers commands and executes them sequentially on InMemoryRedis."""

    def __init__(self, redis: InMemoryRedis) -> None:
        self._redis = redis
        self._commands: list[tuple[str, tuple[Any, ...]]] = []

    def _queue(self, name: str, args: tuple[Any, ...]) -> _FakePipeline:
        self._commands.append((name, args))
        return self

    def get(self, key: str) -> _FakePipeline:
        return self._queue("get", (key,))

    def setex(self, key: str, seconds: int, value: str) -> _FakePipeline:
        return self._queue("setex", (key, seconds, value))

    def delete(self, *keys: str) -> _FakePipeline:
        return self._queue("delete", keys)

    def incr(self, key: str) -> _FakePipeline:
        return self._queue("incr", (key,))

    def expire(self, key: str, seconds: int) -> _FakePipeline:
        return self._queue("expire", (key, seconds))

    async def execute(self) -> list[Any]:
        results = []
        for name, args in self._commands:
            results.append(await getattr(self._redis, name)(*args))
        return results


@pytest.fixture(autouse=True)
async def redis_client() -> AsyncGenerator[InMemoryRedis, None]:
    """Install an in-memory Redis client for every test.

    Services and middleware obtain the Redis client through
    ``src.utils.redis.get_redis_client()``/``get_redis_pubsub_client()``,
    which read module-global ``_redis_client``/``_pubsub_client`` at call
    time. Setting those globals to the fake therefore satisfies every
    import site without patching individual modules.
    """
    import src.utils.redis as redis_module

    fake = InMemoryRedis()
    original_client = redis_module._redis_client
    original_pubsub = redis_module._pubsub_client
    redis_module._redis_client = fake
    redis_module._pubsub_client = fake
    yield fake
    redis_module._redis_client = original_client
    redis_module._pubsub_client = original_pubsub


@pytest.fixture(scope="function")
async def test_engine():
    """Create a fresh in-memory test database for each test function."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture(scope="function")
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session"""
    async_session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session


# Alias for backward compatibility
@pytest.fixture(scope="function")
async def db(db_session) -> AsyncGenerator[AsyncSession, None]:
    """Alias for db_session - backward compatibility"""
    yield db_session


@pytest.fixture
async def async_client(db_session) -> AsyncClient:
    """Create async test client"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
