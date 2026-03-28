# Agent Guidelines for PyPRLedger

This document provides guidelines for AI agents operating in this repository.

## Project Overview

PyPRLedger is a FastAPI-based Pull Request Code Review System with MySQL, Redis, and Prometheus integration. It uses Python 3.12+ with async/await patterns throughout.

## Build/Lint/Test Commands

### Running the Application

```bash
# Development server with auto-reload
uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Or using the module syntax
python -m uvicorn src.main:app --reload
```

### Running Tests

```bash
# Run all tests
pytest

# Run a single test file
pytest tests/test_users.py

# Run a single test by name
pytest tests/test_users.py::test_create_user

# Run with verbose output
pytest -v

# Run with coverage (if pytest-cov is installed)
pytest --cov=src --cov-report=html
```

### Linting and Formatting

```bash
# Format code with ruff
ruff format

# Lint with ruff (auto-fix where possible)
ruff check --fix

# Run both before committing
ruff format && ruff check --fix

# Run pre-commit hooks manually
pre-commit run --all-files
```

## Code Style Guidelines

### General Principles

- **Type hints are required** - Use Python 3.12+ type hints everywhere
- **Prefer async/await** - All database and I/O operations should be async
- **Avoid comments** - Let code be self-explanatory; don't add comments unless absolutely necessary
- **Use `from __future__ import annotations`** for forward references

### Imports

Standard import order (per Ruff/PEP 8):

```python
from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.exceptions import NotFoundException
from src.models.user import User
from src.schemas.user import UserResponse
from src.services.user_service import UserService
from src.utils.metrics import metrics
```

- Use `from __future__ import annotations` at the top of every file
- Use `TYPE_CHECKING` block for imports only needed for type hints:
  ```python
  from typing import TYPE_CHECKING
  if TYPE_CHECKING:
      from src.models.pull_request import PullRequestReview
  ```
- Group: stdlib → third-party → local (src)

### Naming Conventions

- **Classes**: `PascalCase` (e.g., `UserService`, `PullRequestReview`)
- **Functions/methods**: `snake_case` (e.g., `get_user_by_id`, `_get_cache_key`)
- **Variables**: `snake_case` (e.g., `user_id`, `cache_key`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `CACHE_TTL_USERS`)
- **Private methods**: Prefix with `_` (e.g., `_get_user_from_cache`)
- **Database models**: Use `PascalCase` class names, `snake_case` column names

### Pydantic Schemas

- Use `BaseModel` from Pydantic v2
- Define base schemas with common fields, then extend:
  ```python
  class UserBase(BaseModel):
      username: str = Field(..., min_length=3, max_length=64)
      
  class UserCreate(UserBase):
      password: str | None = Field(None, min_length=8)
  ```
- Always set `from_attributes = True` for ORM compatibility:
  ```python
  class Config:
      from_attributes = True
  ```
- Use `field_validator` for custom validation:
  ```python
  @field_validator("username")
  def username_alphanumeric(cls, v):
      if not all(c.isalnum() or c == "_" for c in v):
          raise ValueError("Username must be alphanumeric")
      return v.lower()
  ```

### SQLAlchemy Models

- Use SQLAlchemy 2.0 style with `Mapped` and `mapped_column`:
  ```python
  class User(Base):
      __tablename__ = "user"
      
      id: Mapped[int] = mapped_column(Integer, primary_key=True)
      username: Mapped[str] = mapped_column(String(64), unique=True)
  ```
- Add indexes using `__table_args__`:
  ```python
  __table_args__ = (
      Index("idx_username", "username"),
  )
  ```

### Error Handling

- Use custom exception classes inheriting from `AppException`
- Define error codes in `ErrorCode` class in `src/core/exceptions.py`
- Specific exceptions should extend base exceptions:
  ```python
  class UserNotFoundException(NotFoundException):
      def __init__(self, user_id: int):
          super().__init__(
              message=f"User with ID {user_id} not found",
              detail={"user_id": user_id},
          )
  ```
- Catch specific exceptions in API endpoints, let generic ones bubble up

### API Endpoints

- Use `APIRouter` for grouping routes
- Use `Annotated` with `Depends` for dependency injection:
  ```python
  @router.get("/{user_id}")
  async def get_user(
      user_id: int,
      db: Annotated[AsyncSession, Depends(get_db_session)],
      user_service: Annotated[UserService, Depends(get_user_service)],
  ) -> UserResponse:
  ```
- Use status codes: `status.HTTP_201_CREATED` for creation, `status.HTTP_204_NO_CONTENT` for deletion
- Return proper response models; use `response_model` parameter
- Include metrics tracking for errors and operations

### Configuration

- Use Pydantic `BaseSettings` for configuration
- Store in `src/core/config.py`
- Use `Field` with defaults for environment variables:
  ```python
  DATABASE_HOST: str = Field(default="localhost")
  DATABASE_PORT: int = Field(default=3306)
  ```
- Use `@lru_cache` for singleton pattern:
  ```python
  @lru_cache
  def get_settings() -> Settings:
      return Settings()
  ```

### Logging

- Use module-level loggers:
  ```python
  logger = logging.getLogger(__name__)
  ```
- Use appropriate levels: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
- Include structured data in `extra` parameter:
  ```python
  logger.error("Failed operation", extra={"user_id": user_id})
  ```

### Redis/Caching

- Use cache keys with prefixes: `user:123`, `users:list:active:1:20`
- Set appropriate TTL using settings: `settings.CACHE_TTL_USERS`
- Wrap cache operations in try/except with warning-level logging on failure

### Testing

- Use `pytest` with `pytest.ini` configuration: `asyncio_mode = auto`
- Use `AsyncClient` from `httpx` with `ASGITransport` for testing
- Use in-memory SQLite for tests: `sqlite+aiosqlite:///:memory:`
- Follow test structure in `tests/conftest.py`

### File Organization

```
src/
├── __init__.py          # Version info
├── main.py              # FastAPI app setup
├── core/
│   ├── config.py        # Settings
│   ├── database.py      # DB connection
│   ├── exceptions.py    # Custom exceptions
│   └── middleware.py   # Custom middleware
├── models/              # SQLAlchemy models
├── schemas/             # Pydantic schemas
├── services/            # Business logic
├── api/
│   └── v1/
│       ├── api.py      # Router aggregation
│       └── endpoints/  # Route handlers
└── utils/               # Utilities (redis, metrics, logging)
```

## Database

- MySQL for persistent storage
- Use `sqlmodel` for ORM
- Async operations with `sqlalchemy.ext.asyncio`
- Define foreign keys explicitly in relationships