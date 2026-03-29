# Changelog

All notable changes to the PRLedger project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-03-25

### Added
- **Enhanced Review Score Update Endpoint** - New composite key-based score update functionality
  - New `PUT /api/v1/reviews/score` endpoint for precise review score updates
  - Uses complete business key combination for record identification:
    - `project_key` - Project identifier
    - `repository_slug` - Repository slug  
    - `pull_request_id` - Pull request ID
    - `source_filename` - Source filename being reviewed (mandatory)
    - `reviewer` - Reviewer username
  - In-place score update without creating new iterations
  - Prevents cross-project and cross-repository data collisions
  - All parameters mandatory to ensure precise record targeting

- **Version Management Improvements**
  - Direct version reading from `pyproject.toml` using Python's built-in `tomllib`
  - No longer requires package installation (`pip install -e .`) for version detection
  - Works seamlessly in pure development mode with `uvicorn src.main:app --reload`
  - Single source of truth maintained in `pyproject.toml`
  - Automatic fallback to `1.0.0-dev` if file read fails

### Changed
- **SQLAlchemy Boolean Query Syntax** - Updated all boolean column comparisons
  - Changed from `column == True` to `column.is_(True)` across all service methods
  - Ensures proper SQL generation for boolean identity checks
  - Improves compatibility with nullable boolean columns
  - Applied to all `is_latest_review` queries in review service
  - Fixed "Review not found" errors caused by incorrect boolean comparison

- **API Route Ordering** - Reorganized review endpoints for correct route matching
  - Moved `/score` endpoint before parameterized routes like `/{pull_request_id}`
  - Prevents FastAPI from treating "score" as a path parameter value
  - Ensures deterministic route resolution

- **Review Service Method Signature** - Made `source_filename` mandatory
  - Changed from `source_filename: str | None` to `source_filename: str`
  - Enforces complete composite key lookup for all score updates
  - Aligns with database unique constraint requirements

### Technical Details
- **Composite Key Pattern**: Full business key ensures data integrity across multi-tenant deployments
- **Performance**: Single UPDATE query, no INSERT operations or iteration increments
- **Type Safety**: Proper SQLAlchemy `.is_()` usage for boolean comparisons
- **Development Workflow**: Simplified version management without package installation overhead

---

## [Unreleased]

### Changed
- **Consolidated Review Endpoints** - Merged `POST /api/v1/reviews` and `POST /api/v1/reviews/upsert` into a single upsert endpoint
  - Removed separate `create_review` endpoint to simplify API design
  - Kept only `upsert_review` endpoint at `POST /api/v1/reviews` which handles both create and update operations
  - The endpoint now automatically detects if a review exists and creates or updates accordingly
  - Returns HTTP 201 Created for new reviews, HTTP 200 OK for updated reviews
  - Updated documentation in README.md and PROJECT_STRUCTURE.md

### Technical Details
- Single endpoint reduces API surface area and maintenance overhead
- Upsert logic handled by `ReviewService.upsert_review()` method
- Backward compatible behavior - existing clients can continue using the endpoint

---

## [1.0.1] - 2026-03-21

### Added
- **Logging System** - Comprehensive logging configuration with daily rotation and 30-day retention
  - New `src/conf/logging.yaml` for centralized logging configuration
  - New `src/utils/log.py` utility module with `setup_logging()` and `get_logger()` functions
  - Dual log files: `logs/app.log` (all INFO+ logs) and `logs/error.log` (ERROR logs only)
  - Detailed log format including timestamp, logger name, level, message, filename, and line number
  - Component-specific log levels (uvicorn, sqlalchemy, application)
  - Automatic log directory creation
  - Support for custom config paths and environment files
  - Documentation: `src/conf/LOGGING_GUIDE.md`

- **PyYAML Dependency** - Added `pyyaml>=6.0` to support YAML-based logging configuration

### Fixed
- **SQLAlchemy Model Circular Dependency** - Resolved critical startup error preventing application initialization
  - Fixed circular reference between `PullRequestReview` and `User` models
  - Removed duplicate `Base` class definition in `src/models/user.py`
  - Unified all models to use single `Base` from `src/core/database.py`
  - Used string-free relationship definitions to enable lazy loading
  - Removed explicit `poolclass=QueuePool` from async engine configuration
  - Applied SQLAlchemy 2.0 compatibility fixes (using `text()` for raw SQL)

- **Pydantic v2 Compatibility** - Updated all schema validators to use Pydantic v2 syntax
  - Replaced deprecated `@validator` with `@field_validator` across all schemas
  - Fixed field name mismatch in `ReviewFilter` (`pull_request_status` instead of `status`)
  - Corrected parameter order in service layer method calls

- **Parameter Order Issues** - Fixed function signature violations in service methods
  - Ensured database session parameter comes before optional pagination parameters
  - Aligned API endpoint calls with corrected service method signatures

### Changed
- **Main Application** - Updated `src/main.py` to use new centralized logging system
  - Replaced basic logging config with `setup_logging()` from `src.utils.log`
  - Now uses `get_logger(__name__)` for consistent logger instances

---

## [1.0.0] - 2026-03-21

### Added
- Initial release of PRLedger
- Complete RESTful API for pull request code review result storage management
- User, project, repository, and review management endpoints
- Async database operations with SQLAlchemy 2.0
- Redis caching integration
- Prometheus metrics collection
- Grafana dashboard configuration
- Alembic database migration support
- Docker and docker-compose deployment configuration
- Comprehensive API documentation with OpenAPI/Swagger

---

## Version History Summary

| Version | Date | Key Changes |
|---------|------|-------------|
| 1.1.0 | 2026-03-25 | Enhanced score update endpoint, version management improvements, SQLAlchemy boolean query fixes |
| Unreleased | 2026-03-21 | Logging system, critical bug fixes, Pydantic v2 migration |
| 1.0.1 | 2026-03-21 | Logging system, critical bug fixes, Pydantic v2 migration |
| 1.0.0 | 2026-03-21 | Initial release with core functionality |

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
