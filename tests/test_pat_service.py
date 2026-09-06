"""Tests for PATService expired token cleanup"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.personal_access_token import PersonalAccessToken
from src.services.pat_service import PATService
from src.utils.timezone import get_current_time


async def _add_token(
    db: AsyncSession,
    name: str,
    expires_at,
    is_active: bool = True,
) -> PersonalAccessToken:
    token = PersonalAccessToken(
        auth_user_id=1,
        name=name,
        token_hash=f"hash-{name}",
        prefix=f"pat_{name}"[:12],
        expires_at=expires_at,
        is_active=is_active,
    )
    db.add(token)
    await db.flush()
    return token


async def _remaining_names(db: AsyncSession) -> list[str]:
    result = await db.execute(select(PersonalAccessToken.name).order_by(PersonalAccessToken.name))
    return list(result.scalars().all())


async def test_cleanup_deletes_tokens_expired_over_30_days(db_session: AsyncSession) -> None:
    """Tokens whose expiry passed >30 days ago are deleted regardless of is_active."""
    now = get_current_time()
    await _add_token(db_session, "old-expired-active", now - timedelta(days=100))
    await _add_token(db_session, "old-expired-inactive", now - timedelta(days=60), is_active=False)
    await _add_token(db_session, "recent-expired", now - timedelta(days=10))
    await _add_token(db_session, "future", now + timedelta(days=30))
    await _add_token(db_session, "never-expires", None)
    await db_session.commit()

    deleted = await PATService(db_session).cleanup_expired_tokens()

    assert deleted == 2
    remaining = await _remaining_names(db_session)
    assert remaining == ["future", "never-expires", "recent-expired"]


async def test_cleanup_respects_custom_threshold(db_session: AsyncSession) -> None:
    """older_than_days parameter controls the retention window."""
    now = get_current_time()
    await _add_token(db_session, "forty-five-days", now - timedelta(days=45))
    await db_session.commit()

    service = PATService(db_session)

    # Not yet eligible under a 60-day window
    assert await service.cleanup_expired_tokens(older_than_days=60) == 0
    assert await _remaining_names(db_session) == ["forty-five-days"]

    # Eligible under the default 30-day window
    assert await service.cleanup_expired_tokens() == 1
    assert await _remaining_names(db_session) == []


async def test_cleanup_keeps_recently_expired_and_active_tokens(db_session: AsyncSession) -> None:
    """Tokens still within the grace period or not expired survive cleanup."""
    now = get_current_time()
    await _add_token(db_session, "expired-yesterday", now - timedelta(days=1))
    await _add_token(db_session, "active-far-future", now + timedelta(days=365))
    await db_session.commit()

    assert await PATService(db_session).cleanup_expired_tokens() == 0
    remaining = await _remaining_names(db_session)
    assert remaining == ["active-far-future", "expired-yesterday"]
