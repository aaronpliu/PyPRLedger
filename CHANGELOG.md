# Changelog

All notable changes to the PRLedger project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.0] - 2026-03-29

### Added
- **Project Registry System** - Revolutionary virtual app_name architecture for multi-project management
  - New `project_registry` table mapping `(project_key, repository_slug)` pairs to application names
  - Virtual column pattern: `app_name` computed at query time, not stored in review table
  - Default app assignment: "Unknown" for unregistered projects
  - Auto-registration mechanism creates entries on first access
  - Support for logical grouping of multiple projects under single applications
  - Database migration: `alembic/versions/002_create_project_registry.py`
  
- **Multi-App Query Support** - Enhanced filtering capabilities
  - New query parameter `app_names` accepts comma-separated values (e.g., `?app_names=member,tv,football`)
  - Batch resolution of app_names for optimal performance
  - Single query loads reviews from multiple applications simultaneously
  - Automatic injection of `app_name` field into all review responses
  
- **Project Registry Service** - Comprehensive CRUD operations
  - New service: `ProjectRegistryService` with full lifecycle management
  - Methods:
    - `get_app_name()` - Resolve app for single project pair
    - `get_app_names_batch()` - Batch resolution for multiple projects (performance optimized)
    - `list_projects_by_app()` - Retrieve all projects in an application
    - `register_project()` - Register project-repo pair to app
    - `unregister_project()` - Remove from registry
    - `update_project_app()` - Move project to different app
    - `list_all_apps()` - List all apps with project counts
    - `auto_register_project()` - Automatic registration with default app
  
- **Admin API Endpoints** - Registry management interfaces (authentication TODO)
  - `GET /api/v1/apps` - List all registered applications with project counts
  - `GET /api/v1/apps/{app_name}/projects` - List projects in specific app
  - `GET /api/v1/projects/{project_key}/{repository_slug}/app-name` - Get app for project
  - `POST /api/v1/admin/registry/register` - Register project to app (admin only)
  - `PUT /api/v1/admin/registry/update` - Move project to different app (admin only)
  - `DELETE /api/v1/admin/registry/unregister` - Remove project from registry (admin only)
  
- **Enhanced Review Response Schema** - Complete entity information
  - New `app_name` field in `ReviewResponse` schema (virtual, resolved at runtime)
  - Positioned before nested objects for consistent response structure
  - Default value "Unknown" ensures field always present
  - Includes full entity enrichment: `project`, `repository`, `pull_request_user_info`, `reviewer_info`
  
- **Database Models & Relationships**
  - New model: `ProjectRegistry` with proper foreign keys and indexes
  - Unique constraint on `(project_key, repository_slug)` ensures one-to-one app mapping
  - Composite index on `(app_name, project_key, repository_slug)` for fast app-based queries
  - Updated `Project` model with `registry_entries` relationship
  - Bidirectional associations enable efficient navigation

### Changed
- **Review Service Enhancement** - App-aware filtering and enrichment
  - `list_reviews()` method now accepts optional `app_names` parameter
  - Intelligent query building:
    1. If `app_names` provided: Query registry for matching project-repo pairs
    2. Build OR conditions for all matching pairs
    3. Execute single optimized SQL query (no N+1 problem)
  - `list_reviews_with_entities()` injects `app_name` into each enriched review dict
  - Batch resolution prevents repeated database lookups
  - Cache strategy: Disabled for app-filtered queries to ensure fresh data
  
- **API Endpoint Updates** - Backward compatible enhancements
  - `GET /api/v1/reviews` now supports optional `app_names` query parameter
  - All review responses include complete entity information (no more null values)
  - Fixed eager loading: Added missing `repository` relationship with `selectinload`
  - Dual-path enrichment logic handles both ORM objects and cached dictionaries
  
- **Router Configuration** - Expanded API surface
  - New router: `project_registry` included in main API
  - Updated `src/api/v1/api.py` to register new endpoints
  - Proper tag categorization for OpenAPI documentation
  
- **Alembic Migration Fix** - Corrected Path usage in env.py
  - Fixed `Path.parent` property access (was incorrectly called as method)
  - Changed from `Path.parent(Path.parent(__file__))` to `str(Path(__file__).parent.parent)`
  - Ensures proper Python path resolution for migration scripts

### Improved
- **Performance Optimizations**
  - Batch app_name resolution reduces database round trips
  - Composite indexes enable efficient app-based filtering
  - Eager loading with `selectinload` prevents N+1 query problem
  - Strategic caching disabled for dynamic app assignments
  
- **Data Integrity** - Strong referential constraints
  - Foreign key to `project.project_key` with CASCADE delete
  - Unique constraint prevents duplicate app assignments
  - Automatic population during migration ensures no orphaned projects
  
- **Developer Experience** - Intuitive multi-project management
  - Logical application boundaries without physical table proliferation
  - Simple admin APIs for registry management
  - Clear separation between configuration (registry) and data (reviews)

### Technical Details
- **Virtual Column Pattern**: `app_name` not stored in `pull_request_review` table
- **Query-Time Resolution**: App name computed via JOIN or application logic
- **Default Behavior**: Unregistered projects → "Unknown" app
- **Auto-Registration**: Enabled on first access, configurable default
- **Multi-App Queries**: Comma-separated parameter supports unlimited apps
- **Backward Compatibility**: Existing APIs function without `app_names` parameter
- **Migration Strategy**: Existing data auto-populated to "Unknown" app during upgrade

---

## [1.2.0] - 2026-03-25

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
