# Contributing to PRLedger

Thank you for your interest in contributing! This document outlines the process and standards for contributing to this project.

## Development Setup

```bash
# Clone the repository
git clone https://github.com/aaronliu00/PyPRLedger.git
cd PyPRLedger

# Install dependencies (requires uv)
uv sync

# Set up environment
cp .env.example .env
# Edit .env with your database, Redis, and Git provider settings

# Run database migrations
alembic upgrade head

# Start the dev server
uv run uvicorn src.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

## Tech Stack

- **Backend**: Python 3.12+, FastAPI, SQLAlchemy 2.0 (async), Pydantic v2
- **Frontend**: Vue 3, TypeScript, Element Plus, Vite
- **Database**: MySQL with Alembic migrations
- **Cache**: Redis
- **Package Manager**: uv (Python), npm (frontend)

## Coding Standards

### Python (Backend)

- Follow PEP 8, enforced by `ruff`
- Run before committing:
  ```bash
  ruff format && ruff check --fix
  ```
- Use `async/await` for all I/O operations
- Use `Mapped[type]` + `mapped_column()` for SQLAlchemy models
- Use `Annotated` + `Depends` for dependency injection in endpoints
- Return Pydantic schemas from services, never ORM models directly
- Add type hints everywhere — avoid `Any`

### TypeScript / Vue (Frontend)

- Use Composition API with `<script setup lang="ts">`
- Use `ref`, `computed`, `watch` from Vue 3
- Follow existing naming conventions for components and composables

### Import Order

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

## Pull Request Process

1. Fork the repository and create a branch from `main`
2. Make your changes with clear, focused commits
3. Ensure all checks pass:
   ```bash
   ruff format && ruff check --fix
   pytest -v
   ```
4. Update documentation if applicable
5. Include a database migration if the schema changed:
   ```bash
   alembic revision --autogenerate -m "describe the change"
   ```
6. Open a Pull Request and fill out the PR template

## Commit Messages

Use conventional commit format:

```
type(scope): short description

Longer description if needed.

Closes #123
```

Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `ci`, `perf`

## Reporting Issues

- Use the **Bug Report** template for bugs
- Use the **Feature Request** template for new features
- Search existing issues first to avoid duplicates
- For security vulnerabilities, see [SECURITY.md](SECURITY.md)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
