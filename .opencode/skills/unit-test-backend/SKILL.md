---
name: unit-test-backend
description: Auto-generate or update backend pytest unit tests when new features are added or code changes in src/. Use when the user says "add tests", "write tests", "unit test", "test backend", "pytest", or when a backend service, endpoint, model, schema, or utility needs unit test coverage.
---

# Unit Test Backend

Auto-generate or update backend pytest tests for the PyPRLedger project so every new feature or code change lands with test coverage.

## When to Use

- A new feature or code change affects `src/` — services, endpoints, models, schemas, or utils
- The user asks to "add tests", "write tests", "unit test", "test backend", or mentions "pytest"
- An existing test file needs new cases for changed behavior
- Coverage regressed after a backend change and needs to be restored

## Phase 1: Detect Changes

Find which source files changed:

```bash
git diff --name-only HEAD~1 -- src/   # most recent change
git status --short                    # uncommitted changes
```

Map each changed source file to the test file that should cover it:

| Changed file | Test file |
|---|---|
| `src/services/foo.py` | `tests/test_foo.py` |
| `src/api/v1/endpoints/foo.py` | `tests/test_foo.py` (or an endpoint test file) |
| `src/models/foo.py` | covered via service/endpoint tests; add if critical logic |
| `src/utils/*.py` | `tests/test_<name>.py` |

## Phase 2: Check for Existing Tests

- If the mapped test file **exists**, read it and ADD new test cases covering the new/changed behavior. Keep the existing style.
- If it **does not exist**, CREATE it following the project conventions below.

## Phase 3: Write Tests Following Project Conventions

- Use fixtures from `tests/conftest.py`: `db_session`, `async_client`, `test_engine`, `db`
- Async tests: use `@pytest.mark.asyncio` (or rely on `asyncio_mode = auto` from `pytest.ini`)
- Test happy path, edge cases, and error states
- For **services**: instantiate the service, call its methods, assert on returned schemas (never ORM models)
- For **endpoints**: use `async_client` with the `Depends(get_db_session)` wiring already provided by the app
- Follow AGENTS.md: import order, no blocking calls, structured assertions
- Use `pytest.raises(...)` for expected exceptions
- Name test functions `test_<behavior>_<state>` and give them docstrings

### Service test pattern

Mirror `tests/test_notification_service.py`:

```python
"""Tests for notification service"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.schemas.notification import NotificationCreate
from src.services.notification_service import NotificationService


@pytest.mark.asyncio
async def test_create_notification(db_session: AsyncSession):
    """Test creating a new notification"""
    service = NotificationService()

    notification_data = NotificationCreate(
        user_id="test_user",
        type="review_assigned",
        title="New Review Assigned",
        message="You have been assigned to review PR #123",
        related_id="123",
        related_type="pull_request",
        priority="high",
    )

    result = await service.create_notification(db_session, notification_data)

    assert result.user_id == "test_user"
    assert result.type == "review_assigned"
    assert result.title == "New Review Assigned"
    assert result.is_read is False
    assert result.priority == "high"
```

### Endpoint test pattern

Mirror `tests/test_sse.py`:

```python
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_my_endpoint_returns_200(async_client: AsyncClient, db_session: AsyncSession):
    response = await async_client.get("/api/v1/my-resource/")
    assert response.status_code == 200
    body = response.json()
    assert body["detail"]["error"] == "EXPECTED_ERROR"
```

### Utility test pattern

Mirror `tests/test_id_obfuscator.py` — plain synchronous tests are fine for pure functions, but keep the import order and docstring conventions.

## Phase 4: Run and Verify

```bash
uv run pytest tests/test_<name>.py -v      # new/changed file
uv run pytest                                # full suite
uv run pytest --cov=src                      # coverage not regressed
```

Fix failures before finishing.

## Phase 5: Checklist

- [ ] Coverage maintained or improved (`pytest --cov=src`)
- [ ] All tests green (`uv run pytest`)
- [ ] Ruff passes: `uv run ruff format && uv run ruff check`
- [ ] No skipped tests (`@pytest.mark.skip`)
- [ ] Meaningful assertions — no `assert True`
- [ ] Follows import order and async conventions from AGENTS.md
