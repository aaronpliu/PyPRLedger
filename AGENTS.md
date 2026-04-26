# Agent Guidelines for PyPRLedger

This document provides essential guidelines for AI agents contributing to PyPRLedger. For full documentation, see README.md.

## Tech Stack

- Python 3.12+, FastAPI, async/await throughout
- MySQL + SQLAlchemy 2.0 (async), Alembic migrations
- Redis caching, Prometheus metrics, Grafana dashboards
- Pydantic v2, SQLModel, JWT auth, RBAC with delegation

## Quick Commands

```bash
# Dev server
uv run uvicorn src.main:app --reload

# Tests
pytest -v
pytest --cov=src

# Lint/format
ruff format && ruff check --fix

# Migrations
alembic revision --autogenerate -m "desc"
alembic upgrade head

# Docker
docker-compose up -d
docker-compose logs -f api
```

## Critical Rules

### 1. Import Order (Ruff/PEP 8)
```python
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter
from sqlalchemy import select

from src.core.config import settings
from src.models.user import User
from src.services.user_service import UserService

if TYPE_CHECKING:
    from src.models.pull_request import PullRequestReview
```

### 2. Async Database Pattern
```python
async def get_user(db: AsyncSession, user_id: int):
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()
```
- **Never** forget `await` on DB operations
- Use `Depends(get_db_session)` in endpoints for auto commit/rollback
- Call `await db.flush()` before `await db.refresh()`

### 3. SQLAlchemy 2.0 Models
```python
class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_date: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC)
    )
```
- Always use `Mapped[type]` + `mapped_column()`
- Use `lambda: datetime.now(UTC)` for timestamps
- Define `foreign_keys` in relationships
- Add indexes via `__table_args__`

### 4. Pydantic Schemas
```python
class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    model_config = {"from_attributes": True}

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)

class UserResponse(UserBase):
    id: int
```
- Inherit from base schemas
- Set `from_attributes = True` for ORM compatibility
- Use `Field(..., description="...")` for docs
- Use `model_dump(exclude_unset=True)` for PATCH

### 5. API Endpoint Pattern
```python
router = APIRouter(prefix="/users", tags=["users"])

@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_in: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[UserService, Depends(get_user_service)],
):
    user = await service.create_user(db, user_in)
    metrics.increment("user.created")
    return user
```
- Use `Annotated` + `Depends` for DI
- Increment metrics for all operations
- Return proper HTTP status codes

### 6. Exception Handling
```python
# Define in src/core/exceptions.py
class UserNotFoundException(NotFoundException):
    def __init__(self, user_id: int | None = None, username: str | None = None):
        if user_id:
            super().__init__(message=f"User with ID {user_id} not found", detail={"user_id": user_id})

# Raise in code
raise UserNotFoundException(user_id=user_id)
```
- Extend from `AppException` hierarchy
- Include structured `detail` for debugging
- Use i18n message keys when needed

### 7. Service Layer
```python
class UserService:
    def __init__(self, metrics: MetricsCollector | None = None):
        self.redis_client = get_redis_client()
        self.metrics = metrics or MetricsCollector()

    async def get_user_by_id(self, db: AsyncSession, user_id: int) -> UserResponse:
        cache_key = f"user:{user_id}"
        cached = await cache.get_json(cache_key)
        if cached:
            self.metrics.increment("cache.hit", labels={"resource": "user"})
            return UserResponse(**cached)
        # DB query...
        await cache.set_json(cache_key, response.model_dump(), expire=settings.CACHE_TTL_USERS)
        return response
```
- Return schemas, not ORM models
- Cache reads, invalidate on writes
- Increment metrics

### 8. Caching (RedisCache)
```python
# Key patterns: entity:ID, list:resource:param:page:N:size:M, stats:resource:metric
await cache.set_json(f"user:{user_id}", data, expire=settings.CACHE_TTL_USERS)
data = await cache.get_json(f"user:{user_id}")
await cache.delete(f"user:{user_id}")  # Invalidate on write
```
- Always wrap in try/except, log warnings
- Use TTL from settings
- Delete on mutations

### 9. Logging
```python
logger = get_logger(__name__)
logger.info("Review created", extra={
    "review_id": review.id,
    "user_id": user.id,
    "project_key": project_key,
})
```
- Use structured logging with `extra`
- Appropriate levels: DEBUG/INFO/WARNING/ERROR/CRITICAL
- Include correlation IDs in production

### 10. Configuration
```python
from src.core.config import settings

# Access: settings.DATABASE_HOST, settings.CACHE_TTL_USERS, etc.
```
- All config via `Settings` class in `src/core/config.py`
- Use `@lru_cache` singleton pattern
- Environment variables from `.env`

## Testing

```python
# Use async fixtures from tests/conftest.py
@pytest.mark.asyncio
async def test_create_user(async_client: AsyncClient, db_session: AsyncSession):
    response = await async_client.post("/api/v1/users/", json={...})
    assert response.status_code == 201
```
- `asyncio_mode = auto` in pytest.ini
- SQLite in-memory DB: `sqlite+aiosqlite:///:memory:`
- Fixtures: `async_client`, `db_session`, `test_engine`

## Pre-PR Checklist

- [ ] `ruff format` and `ruff check --fix` pass
- [ ] All type hints present, no `Any` abuse
- [ ] All DB ops are async with proper `await`
- [ ] Cache invalidation on writes
- [ ] Metrics incremented for operations
- [ ] Structured logging with `extra`
- [ ] Proper exception types used
- [ ] Response models match schemas
- [ ] Tests added/updated: `pytest -v`
- [ ] Pre-commit passes: `pre-commit run --all-files`
- [ ] Migration generated if schema changed: `alembic revision --autogenerate`

## Project Structure

```
src/
├── api/v1/endpoints/  # Route handlers (use Depends for db/service)
├── core/              # Config, DB, exceptions, middleware
├── models/            # SQLAlchemy ORM (Mapped, mapped_column)
├── schemas/           # Pydantic v2 (from_attributes=True)
├── services/          # Business logic (caching, metrics)
├── utils/             # redis, metrics, log, jwt, i18n
└── main.py            # App factory, lifespan, middleware, handlers
tests/                 # pytest with async fixtures
alembic/versions/      # DB migrations
```

## Common Pitfalls

- **No comments** - Let code be self-explanatory
- **No blocking calls** - Everything async (DB, Redis, I/O)
- **Don't manually manage sessions** in endpoints (use `Depends`)
- **Don't forget cache invalidation** on create/update/delete
- **Don't use `model_dump()` without `exclude_unset=True`** for PATCH
- **Don't return ORM models** - convert to Pydantic schemas

## Key Files

- `src/main.py:73` - Lifespan context (startup/shutdown)
- `src/core/database.py:132` - `get_db_session()` dependency
- `src/core/exceptions.py:58` - `AppException` base class
- `src/utils/redis.py:87` - `RedisCache` class
- `src/utils/metrics.py` - Metrics collector

## Environment

See `.env.example` for all variables. Key: `DATABASE_*`, `REDIS_*`, `SECRET_KEY`, `CACHE_TTL_*`.
