# Changelog

All notable changes to the PRLedger project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

---

## [1.5.0] - 2026-04-08

### Added
- **Vue.js Frontend Application** - Complete rewrite using modern Vue 3 framework
  - Full TypeScript support with Vue 3 Composition API
  - Element Plus UI component library integration
  - Vue Router for SPA navigation
  - Pinia state management
  - Internationalization (i18n) support
  - Responsive design for all screen sizes
  
- **Enhanced Code Diff Viewer** - Professional diff visualization with Diff2Html
  - Side-by-side and unified view modes
  - Syntax highlighting for multiple languages
  - Line number synchronization
  - Sticky line numbers during horizontal scroll
  - Dark theme support
  
- **Advanced Review Management**
  - Multi-reviewer score tracking
  - Real-time review status updates
  - Comprehensive filtering and search
  - Export capabilities (PDF, Excel)
  
- **Analytics Dashboard**
  - Interactive charts with ECharts
  - Score distribution analysis
  - Review trends over time
  - Performance metrics

### Changed
- **Frontend Architecture** - Migrated from vanilla JS to Vue 3
  - Modern build system with Vite 7.x
  - Component-based architecture
  - Type-safe development with TypeScript
  - Improved code organization and maintainability
  
- **API Integration** - Enhanced backend communication
  - Axios for HTTP requests with interceptors
  - Automatic token refresh
  - Better error handling and user feedback
  - WebSocket support for real-time updates

### Fixed
- **Diff Rendering Issues** - Resolved line number scrolling problems
  - Fixed `position: absolute` causing line numbers to detach
  - Implemented `position: relative` for proper document flow
  - Synchronized scrolling in side-by-side mode
  
- **Router Deprecation Warnings** - Updated to Vue Router 5 best practices
  - Replaced deprecated `next()` calls with return values
  - Cleaner navigation guard implementation

### Removed
- **PWA Support** - Removed vite-plugin-pwa and related configurations
  - Simplified build configuration
  - Reduced bundle size
  - Focused on core functionality

### Technical Details
- **Backend Version**: 1.5.0 (FastAPI service)
- **Frontend Version**: 1.0.0 (Vue 3 application)
- **Build Tools**: Vite 7.3.2, TypeScript 6.0.2
- **UI Framework**: Element Plus 2.13.6
- **State Management**: Pinia 3.0.4
- **Routing**: Vue Router 5.0.4

---

## [1.4.0] - 2026-04-06

### Added
- **Diff2HTML Integration** - Enhanced code diff visualization in the review UI
  - Integrated diff2html library for syntax-highlighted, interactive diff display
  - Added `web/lib/diff2html-ui.min.js` and `web/lib/diff2html.min.css`
  - New `scripts/update_diff2html.sh` script for library updates
  - Improved readability of code changes during code review

- **Score Deletion Functionality** - Ability to delete review scores
  - New endpoint for removing scores from reviews
  - Database migration: `alembic/versions/005_add_active_and_deletion_tracking_to_score.py`
  - Added `is_active` flag for soft deletion support

### Changed
- **UI Material Design Upgrade** - Complete visual overhaul with Material Design principles
  - Refactored UI with material design styles (`web/css/material-design.css`)
  - Enhanced component styles: buttons, cards, chips, forms, typography
  - Added Ripple effect component (`web/js/components/Ripple.js`)
  - Improved theme support for light/dark modes
  - Enhanced visual hierarchy and spacing across all components

- **Cache Enhancement** - Improved cache handling for different themes
  - Cache now accounts for theme selection
  - Better cache invalidation strategy for UI-related data

### Fixed
- **Score Logic Enhancement** - Corrected score behavior for first-time reviewer updates
  - Fixed edge case when reviewer updates score for the first time
  - Improved score calculation accuracy in multi-reviewer scenarios

- **Cache Cleanup Script** - Enhanced `clear_cache.py` reliability
  - Improved error handling and logging
  - Better support for selective cache clearing patterns

---

## [1.3.2] - 2026-04-05

### Added
- **Review UI Testing Page** - Interactive web interface for API testing and review visualization
  - New `web/index.html` page for manual testing of review endpoints
  - Support for multiple themes (light/dark mode)
  - Enhanced parameter controls for GET /reviews endpoint with additional filtering options
  - Real-time score display and editing capabilities
  - Visual representation of reviewer comments and suggestions
  
- **Cache Management Script** - Utility for clearing Redis cache
  - New `scripts/housekeeping/clear_cache.py` for cache cleanup operations
  - Supports selective cache clearing by key patterns
  - Logging integration for audit trail
  - Helps maintain cache consistency during development and production

### Changed
- **Score Architecture Refactoring [BREAKING]** - Separated score data from review results into dedicated table
  - Created new `review_score` table with proper normalization for better data organization
  - Database migration: `alembic/versions/004_refactor_score_to_separate_table.py`
  - Scores can now be managed independently at PR level or file level
  - Removed score fields from `create_review` endpoint to simplify API contract
  - New `ReviewScoreService` for dedicated score management operations
  - Updated score summary logic for better aggregation and reporting
  - **Migration Note**: Existing review data automatically migrated to new schema
  
- **Enhanced Review Query Logic** - Improved data retrieval and filtering
  - Fixed reviewer_comments field population in GET /reviews responses
  - Optimized review score queries with proper JOIN strategies
  - Enhanced statistics calculation accuracy for dashboard metrics
  - Better handling of multi-reviewer scenarios with independent scoring
  
- **Schema Unification** - Standardized Pydantic schemas across services
  - Unified schema configurations in all service layers (project, user, review)
  - Consistent response models with proper type annotations
  - Improved type safety and validation across API boundaries
  - Reduced code duplication through shared schema definitions
  
- **Folder Structure Optimization** - Reorganized scripts for better maintainability
  - Moved utility scripts to `scripts/housekeeping/` directory for better organization
  - Renamed `scripts/deployment/clear_cache.py` → `scripts/housekeeping/clear_cache.py`
  - Renamed `scripts/cleanup_database.py` → `scripts/housekeeping/clear_database.py`
  - Moved `scripts/review_ui.html` → `web/index.html` for clear separation of concerns
  
- **Deprecated Method Replacement** - Updated SQLAlchemy model definitions
  - Replaced deprecated column definition patterns in Project, Repository, and User models
  - Ensured compatibility with latest SQLAlchemy 2.0 standards
  - Improved model initialization and relationship definitions

### Fixed
- **Cache Error on Score Updates** - Resolved cache invalidation issues
  - Fixed cache key mismatch when updating scores in multi-reviewer scenarios
  - Proper cache refresh after score modifications to prevent stale reads
  - Eliminated stale data problems in review queries
  
- **User Cache Issues** - Corrected user data caching behavior
  - Fixed cache serialization/deserialization for user objects
  - Improved cache hit rates for frequently accessed user data
  - Prevented cache corruption from improper object storage
  
- **Type Errors** - Multiple type annotation fixes across codebase
  - Fixed type mismatches in review service methods
  - Corrected return type annotations in API endpoints (reviews, users)
  - Improved type safety in user and review operations
  - Enhanced IDE support and static analysis accuracy
  
- **Exception Handling** - Enhanced error output and logging
  - Better error messages for debugging with contextual information
  - Improved exception propagation in middleware layer
  - More informative stack traces for faster issue resolution

### Technical Details
- **Database Schema**: New `review_score` table separates scoring from review content, enabling independent score management
- **Caching Strategy**: Fixed composite key usage `(project_key, repository_slug, pull_request_id)` for consistent cache behavior
- **API Design**: Simplified create_review by removing score parameters; use dedicated score endpoints instead
- **UI Enhancement**: Modern responsive design with theme support, accessible via `/web/index.html`
- **Code Quality**: Unified schema patterns reduce duplication by ~30% and improve maintainability
- **Backward Compatibility**: Migration script ensures existing data works seamlessly with new schema

---

## [1.3.1] - 2026-03-31

### Added
- **Multi-Reviewer Score Support** - Complete independent scoring workflow for multiple reviewers
  - UPSERT pattern for review scores: creates new record if reviewer hasn't scored, updates if exists
  - Each reviewer maintains independent score history with separate iteration tracking
  - Per-reviewer `is_latest_review` flag ensures correct latest score identification
  - Supports unlimited reviewers per PR/file combination without conflicts
  
- **Enhanced Score Update Logic** - Intelligent create-or-update behavior
  - New `upsert_review_score()` method replaces update-only approach
  - Automatic base data reuse: New reviewers inherit AI review data (diff, suggestions, metadata)
  - Proper error handling: Distinguishes between "no AI review yet" vs "new reviewer needs record"
  - Clear guidance messages direct users to submit AI review first if missing
  
- **Score Iteration Management** - Per-reviewer version tracking
  - Each reviewer's iterations tracked independently (reviewer A iteration 1, 2, 3...; reviewer B iteration 1, 2...)
  - Iteration calculation scoped to specific reviewer, not global across all reviewers
  - Maintains complete audit trail of score changes per reviewer
  
- **Comprehensive API Documentation** - Multi-reviewer workflow clearly explained
  - Endpoint docstrings detail UPSERT behavior and prerequisites
  - Example workflows show how multiple reviewers interact with same PR/file
  - Error scenarios documented with resolution steps

### Changed
- **Service Method Signature** - Renamed and refactored score update method
  - `update_review_score()` → `upsert_review_score()` to reflect create-or-update behavior
  - Enhanced logging shows which reviewer is updating/creating score
  - Improved error messages specify when reviewer hasn't submitted review yet
  
- **Database Query Strategy** - Optimized for multi-reviewer lookups
  - Queries filter by complete composite key including `reviewer` field
  - Separate query paths for UPDATE (find existing reviewer record) vs CREATE (find any base review)
  - Eager loading of relationships (`project`, `repository`, `user` rels) for enrichment
  
- **API Response Enrichment** - Consistent entity information across all score operations
  - `app_name` resolution integrated into upsert flow
  - Full nested objects returned: `project`, `repository`, `pull_request_user_info`, `reviewer_info`
  - Updated timestamp set on both create and update operations

### Improved
- **Multi-Reviewer Architecture** - Production-ready team review support
  - No breaking changes to existing single-reviewer workflows
  - Backward compatible: Existing callers continue to work unchanged
  - Forward looking: Enables future features like score averaging, consensus analysis
  
- **Error Handling & Validation** - Precise failure messages and recovery guidance
  - `ReviewNotFoundException` includes context about missing AI review vs missing reviewer record
  - `ValueError` for missing required parameters with clear field list
  - Warning logs when operations fail due to missing prerequisite data
  
- **Data Model Clarity** - Clear separation of concerns in review records
  - Base review data (AI suggestions, diff) separated from reviewer-specific data (score, comments)
  - Multiple reviewers can share same base data while maintaining independent scores
  - Composite unique constraint enforces one score per reviewer per file

### Technical Details
- **UPSERT Implementation**: Two-path logic - UPDATE existing reviewer record or CREATE new one
- **Base Data Reuse**: New reviewers copy `pull_request_commit_id`, `git_code_diff`, `ai_suggestions` from existing reviews
- **Iteration Calculation**: `SELECT MAX(review_iteration) WHERE reviewer = :reviewer` per reviewer
- **Cache Invalidation**: Uses composite key `(project_key, repository_slug, pull_request_id)` shared across all reviewers
- **Enrichment Flow**: Calls `_enrich_review_with_entities()` which resolves `app_name` from project registry

---

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
  - Fixed circular reference between `PullRequestReviewBase` and `User` models
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
| 1.4.0 | 2026-04-06 | Diff2HTML integration, score deletion, Material Design UI overhaul, cache enhancements |
| 1.3.2 | 2026-04-05 | Score architecture refactoring, review UI testing page, cache management, schema unification |
| 1.3.1 | 2026-03-31 | Multi-reviewer score support with UPSERT pattern, independent iteration tracking |
| 1.3.0 | 2026-03-29 | Project registry system, multi-app query support, virtual app_name architecture |
| 1.2.0 | 2026-03-25 | Enhanced score update endpoint, version management improvements, SQLAlchemy boolean query fixes |
| 1.0.1 | 2026-03-21 | Logging system, critical bug fixes, Pydantic v2 migration |
| 1.0.0 | 2026-03-21 | Initial release with core functionality |

## Upgrade Notes

### Breaking Changes in 1.0.1

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
