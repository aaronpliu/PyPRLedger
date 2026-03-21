# Changelog

All notable changes to PyCodeReviewSaver will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - 2026-03-21

### Added
- **Logging System** - Comprehensive logging configuration with daily rotation and 30-day retention
  - Created `src/conf/logging.yaml` for centralized logging configuration
  - Created `src/utils/log.py` utility module with `setup_logging()` and `get_logger()` functions
  - Implemented dual log output: `logs/app.log` (all logs) and `logs/error.log` (errors only)
  - Added detailed log format including timestamp, logger name, level, message, filename, and line number
  - Integrated logging system into `src/main.py`
  - Added PyYAML dependency (v6.0+) for YAML configuration parsing
  - Created comprehensive logging documentation in `src/conf/LOGGING_GUIDE.md`

### Fixed
- **Database Connection Pool Configuration** - Fixed asyncio engine compatibility issues
  - Removed explicit `QueuePool` specification from `create_async_engine()` in `src/core/database.py`
  - Implemented dynamic pool configuration based on `DATABASE_POOL_SIZE` setting
  - Added support for `NullPool` when pool size is 0
  - Ensured proper parameter handling to avoid passing pool-specific parameters to `NullPool`

- **SQLAlchemy 2.0 SQL Syntax** - Updated raw SQL execution to comply with SQLAlchemy 2.0 requirements
  - Added `from sqlalchemy import text` import in `src/core/database.py`
  - Wrapped raw SQL strings with `text()` function for `execute()` calls
  - Fixed database connection test query: `await conn.execute(text("SELECT 1"))`

- **Pydantic v2 Validator Migration** - Migrated all schema validators from deprecated `@validator` to `@field_validator`
  - Updated `src/schemas/pull_request.py`:
    - `ReviewBase`: Converted `normalize_status()` validator
    - `ReviewFilter`: Converted `validate_status()` validator
  - Updated `src/schemas/project.py`:
    - `ProjectBase`: Converted `validate_name()` validator
  - Updated `src/schemas/repository.py`:
    - `RepositoryBase`: Converted `validate_name()` validator
    - `RepositoryUpdate`: Converted `validate_description()` validator
  - Updated `src/schemas/user.py`:
    - `UserBase`: Converted `validate_email()` validator
    - `UserCreate`: Converted `validate_password()` and `validate_email()` validators
  - Updated imports to use `from pydantic import field_validator`

- **Model Circular Dependencies** - Resolved SQLAlchemy model initialization errors
  - Fixed circular reference between `PullRequestReview` and `User` models
  - Removed redundant `Base` class definition from `src/models/user.py`
  - Unified all models to use single `Base` from `src/core/database.py`
  - Updated relationship definitions to omit string class names, relying on `Mapped["ClassName"]` type annotations
  - Fixed relationships in:
    - `src/models/pull_request.py`: All `PullRequestReview` relationships
    - `src/models/user.py`: All `User` relationships with `PullRequestReview`

- **Service Layer Parameter Order** - Corrected method call parameter ordering
  - Fixed `review_service.list_reviews()` call in `src/api/v1/endpoints/reviews.py`
  - Changed from `list_reviews(filters, page, page_size, db)` to `list_reviews(filters, db, page, page_size)`
  - Aligned with actual method signature in service layer

- **Field Name Mismatch** - Fixed incorrect field reference in review filtering
  - Changed `filters.status` to `filters.pull_request_status` in `src/services/review_service.py`
  - Aligned with `ReviewFilter` schema definition

- **Error Logging Enhancement** - Improved error tracking in API endpoints
  - Added detailed exception logging in `src/api/v1/endpoints/reviews.py`
  - Included full traceback in error logs for better debugging
  - Added logger instance to reviews endpoint

### Changed
- **Dependencies** - Updated project dependencies
  - Added `pyyaml>=6.0` to `pyproject.toml` for YAML configuration support
  - Ran `uv sync` to install new dependency

### Documentation
- Created `src/conf/LOGGING_GUIDE.md` with comprehensive logging documentation
  - Configuration options and examples
  - Usage guidelines and best practices
  - Troubleshooting section
  - Log format specifications
  - Maintenance procedures

---

## [1.0.0] - Previous Releases

### Initial Release Features
- FastAPI-based RESTful API for Pull Request code review management
- MySQL database integration with SQLAlchemy ORM
- Redis caching layer for performance optimization
- Prometheus metrics collection and Grafana visualization
- Alembic database migration support
- Docker and docker-compose deployment configuration
- User, Project, Repository, and Pull Request Review management
- Health check endpoints for container probes
- CORS middleware configuration
- Rate limiting middleware
- Async/await support throughout the codebase
- OpenAPI documentation (Swagger UI at `/api/docs`)

---

## Version History Summary

| Version | Date | Key Changes |
|---------|------|-------------|
| Unreleased | 2026-03-21 | Logging system, critical bug fixes, Pydantic v2 migration |
| 1.0.0 | Previous | Initial release with core functionality |

## Upgrade Notes

### Breaking Changes in Unreleased Version

#### 1. Logging System Integration
If you have custom logging configurations, you may need to merge them with the new centralized logging system:

```bash
# The logging system now requires PyYAML
pip install pyyaml>=6.0
```

#### 2. Database Configuration
The database connection pool configuration has changed. Update your `.env` file if needed:

```env
# Old configuration (if explicitly set)
DATABASE_POOL_CLASS=QueuePool  # No longer supported

# New behavior - automatic based on DATABASE_POOL_SIZE
DATABASE_POOL_SIZE=20  # Set to 0 to disable pooling
```

#### 3. Schema Validators
All Pydantic validators have been migrated to v2 syntax. If you have custom schemas:

```python
# Old (deprecated)
from pydantic import validator

@validator('field')
def validate_field(cls, v):
    return v

# New (required)
from pydantic import field_validator

@field_validator('field')
def validate_field(cls, v):
    return v
```

### Migration Guide

1. **Update dependencies**:
   ```bash
   pip install pyyaml>=6.0
   ```

2. **Run database migrations** (if applicable):
   ```bash
   alembic upgrade head
   ```

3. **Restart application** to pick up new logging configuration:
   ```bash
   uvicorn src.main:app --reload
   ```

4. **Verify logs** are being written correctly:
   ```bash
   tail -f logs/app.log
   tail -f logs/error.log
   ```

## Known Issues

- None at this time

## Contributors

- Core development and maintenance
- Bug fixes and feature enhancements

---

For more information about the logging system, see `src/conf/LOGGING_GUIDE.md`.

For API documentation, visit `/api/docs` when the application is running.

For deployment instructions, see `DEPLOYMENT_GUIDE.md` and `README.md`.
