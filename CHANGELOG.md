# Changelog

All notable changes to the PRLedger project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.19.1] - 2026-06-30

**Backend Version**: 1.19.1
**Frontend Version**: 1.14.1

### Added
- add a banner in reviews page
- update page agent icon

### Fixed
- fix permission in 028 db migration script

---

## [1.19.0] - 2026-06-28

**Backend Version**: 1.19.0
**Frontend Version**: 1.14.0

### Added
- enhance the behavior of page agent
- enhance page agent style
- allow page agent to show
- setup llm proxy in backend
- integrate page agent into prledger system

### Fixed
- enhance the diff2html style

---

## [1.18.2] - 2026-06-25

**Backend Version**: 1.18.2
**Frontend Version**: 1.13.2

### Added
- add i18n for git user management
- manage git user in admin

### Fixed
- enhanced user add by admin
- remove review ID since it's hashed for now
- enhance git user creation and remove duplicate endpoint

### Dependencies
- rename UserManagementView

---

## [1.18.1] - 2026-06-21

**Backend Version**: 1.18.1
**Frontend Version**: 1.13.1

### Added
- take public id in url of review details
- enhance review ID for security requirement
- delete failed reviews in admin UI
- enhance permission for system admin
- add new columns in rules table

### Fixed
- upgrade element-plus to 2.14.2

### Documentation
- archied id-obfuscator
- handle ID with security approach
- remove app-name of openspec

---

## [1.18.0] - 2026-06-20

**Backend Version**: 1.18.0
**Frontend Version**: 1.13.0

### Added
- add "app name" as filter in scores page
- navigate to project as per app name from menu

### Documentation
- implement multiple app view and query

---

## [1.17.3] - 2026-06-18

**Backend Version**: 1.17.3
**Frontend Version**: 1.12.1

### Added
- handle metrics

### Fixed
- update env var

### Documentation
- archive wire-all-remaining-metrics
- implement the remaining tasks of wire-all-remaining-metrics
- archived fix-missing-metrics-at-startup
- archived observability

---

## [1.17.2] - 2026-06-15

**Backend Version**: 1.17.2
**Frontend Version**: 1.12.1

### Fixed
- Wired all MetricsCollector gauges to service/endpoint code (user stats, project stats, PR counts, backlog)
- Added system metrics collection background task (CPU, memory, disk via psutil every 60s)
- Added error tracking in middleware (errors_total on exceptions, rate limit errors)
- Fixed PR count queries: now counts distinct PRs correctly across all status types
- Initialized user/project/PR metrics with real database values at startup
- Fixed SQL incompatibility in `func.distinct()` for multi-column distinct counts

---

## [1.17.1] - 2026-06-14

**Backend Version**: 1.17.1
**Frontend Version**: 1.12.1

### Added
- Consolidated Prometheus, Grafana, and AlertManager into standalone `monitoring/` directory
- Standalone `monitoring/docker-compose.yml` for independent monitoring stack deployment
- AlertManager configuration with severity-based routing and optional Slack integration
- Prometheus alert rules for application health (API down, error rate, latency, backlog)
- Prometheus alert rules for infrastructure health (CPU, memory, disk, DB connections)
- Auto-provisioned Grafana dashboards: PRLedger Overview + Review Analytics

### Fixed
- Grafana container restart loop — fixed healthcheck timing and removed deprecated plugin
- AlertManager startup crash — fixed `--test.config` flag removed in AlertManager 0.25+
- AlertManager Slack integration — entrypoint script conditionally generates config
- Metrics exposure — merged MetricsCollector business metrics onto shared registry with Instrumentator
- Prometheus scrape target — entrypoint now handles env var substitution reliably
- Podman port binding — explicit `0.0.0.0:` for external network access
- Docker network consistency — all monitoring services use `code-review-network`

### Changed
- Refactored Prometheus config to use template + entrypoint for config generation
- Simplified Grafana healthcheck to avoid false restarts

### Documentation
- Updated README with monitoring stack deployment instructions
- Updated `monitoring/.env.example` with all configurable variables

### Dependencies
- add environment varaible for monitoring

### Other Changes
- c9ffd90 Merge pull request #24 from aaronpliu/main
- f598cf9 Merge pull request #23 from aaronpliu/feature/PRLedger_NewUI
- 25dafd0 Merge pull request #22 from aaronpliu/feature/PRLedger_NewUI

---

## [1.17.0] - 2026-06-13

**Backend Version**: 1.17.0
**Frontend Version**: 1.12.0

### Added
- optimize "create rule" dialog
- add auto assignment rule UI with openspec
- add auto assignmen rule
- add codegraph and openspec support

### Fixed
- enhance auto_assign

---

## [1.16.2] - 2026-06-10

**Backend Version**: 1.16.2
**Frontend Version**: 1.11.2

### Added
- openspec archive
- enhance review association
- add openspec

### Fixed
- add i18n for prompt of add score button

### Changed
- [Refactor] update git user and auth user endpoints
- [Refactor] enhance system function on user cascaded deletion

### Documentation
- archived /users endpoint refactor

---

## [1.16.1] - 2026-06-07

**Backend Version**: 1.16.1
**Frontend Version**: 1.11.1

### Added
- enhanced associated reviews dialog to quickly look up from candidate reviews

### Changed
- [Refactor] enhance database connection and update default value
- [Refactor] optimize sse connection and enhance exception handling

### Other Changes
- 6ec1cb8 Merge pull request #21 from aaronpliu/main
- 596d5de Merge pull request #20 from aaronpliu/feature/PRLedger_NewUI
- 70fbda2 Merge pull request #19 from aaronpliu/feature/PRLedger_NewUI

---

## [1.16.0] - 2026-06-06

**Backend Version**: 1.16.0
**Frontend Version**: 1.11.0

### Added
- Show review ID in reviews page
- Support to deassociate reviews
- Support to associate any 2 of reviews for comparison

### Fixed
- Align card size for scores and associated reviews consistently

---

## [1.15.2] - 2026-06-03

**Backend Version**: 1.15.2
**Frontend Version**: 1.10.1

### Added
- add a pin to mark the reviews
- enhance the archive for task assignment
- add archived filter for task assignment

### Fixed
- sorting issue as per severity
- fix sse connection

---

## [1.15.1] - 2026-05-31

**Backend Version**: 1.15.1
**Frontend Version**: 1.10.0

### Added
- support date range filter in reviews and task assignement page
- enhance sse event handling

### Fixed
- enhance the lable of time period in task assignment analytics
- enhance the chart lable display in dashboard
- enhance redis connection
- enhance the filter
- applied fix for CVE-2026-48710
- update html  issue
- enhance the chart display in full screen

### Changed
- [Refactor] enhance score table to display
- [Refactor] enhance review information table to show PR meta info

---

## [1.15.0] - 2026-05-28

**Backend Version**: 1.15.0
**Frontend Version**: 1.9.5

### Added
- fine-tune chart in full screen
- add chart to show issues as per severity and enhance charts with full screen
- enhance to take screenshot for AI review result
- enhanced global search

### Fixed
- fix style issue of PR meta info in screenshot
- optimize error handling for sse connection
- fix filter of severity issue in task assignment page
- enhance API request
- fix filter of severity issue in reviews
- enhance notification polling
- enhanced sse connection and exception handling
- update field name
- enhance database connection and logging

---

## [1.14.1] - 2026-05-22

**Backend Version**: 1.14.1
**Frontend Version**: 1.9.1

### Fixed
- **SSE connection tracking**: Fixed admin user connection cleanup — `_sse_event_generator` now receives the correct `tracking_username` from `stream_reviews`, preventing stale connection accumulation and 429 errors for admin users
- **SSE filter for non-admin users**: Removed 403 block; any authenticated user can now connect. Non-admin users without a linked Bitbucket account receive no events silently instead of being rejected
- **ECharts initialization**: Fixed `LineChart.vue` to wait for `onMounted` before rendering, eliminating DOM width/height warnings on the Task Assignment Analytics page
- **ECharts grid API**: Replaced deprecated `grid.containLabel: true` with modern `grid.outerBounds` in `BarChart.vue` and `LineChart.vue` (ECharts v6 compatibility)

### Other Changes
- 487e657 Import SSEReviewCreatedEvent type in TaskAssignmentView

---

## [1.14.0] - 2026-05-21

**Backend Version**: 1.14.0
**Frontend Version**: 1.9.0

### Added
- add SSE for reviews and task assignment page
- add agent team for the system

### Other Changes
- c7536fc Merge pull request #18 from aaronpliu/main
- c7f089c Merge pull request #17 from aaronpliu/feature/PRLedger_NewUI
- 5481125 Merge pull request #16 from aaronpliu/feature/PRLedger_NewUI
- cbc0645 Merge pull request #15 from aaronpliu/feature/PRLedger_NewUI
- bbb5c6f Merge pull request #14 from aaronpliu/feature/PRLedger_NewUI
- 7b85f93 Merge pull request #13 from aaronpliu/feature/PRLedger_NewUI

---

## [1.13.5] - 2026-05-20

**Backend Version**: 1.13.5
**Frontend Version**: 1.8.5

### Added
- hide swagger in prod
- update table index for /reviews to identify duplicate rows
- update PR URL
- add statement and tips for task assignment analytics charts

### Fixed
- update source_branch length
- update GET /users query parameters

---

## [1.13.2] - 2026-05-12

**Backend Version**: 1.13.2
**Frontend Version**: 1.8.2

### Fixed
- enhance performance issue to handle timezone
- fix line color for line chart when theme change
- enhance exceptions
- fix frontend build issue
- enhance auth user and git user status

---

## [1.13.1] - 2026-05-10

**Backend Version**: 1.13.1
**Frontend Version**: 1.8.1

### Added
- activate or deactive user
- add a refresh button in PAT page

### Fixed
- enhance git user
- continue to enhance permission for users
- enhance permission for /users endpoint
- enhance timezone for PAT

### Dependencies
- enhance profile window size

---

## [1.13.0] - 2026-05-10

**Backend Version**: 1.13.0
**Frontend Version**: 1.8.0

### Added
- add personal access token
- add avatar in admin page

### Fixed
- optimize the statistics card in task assignment analytics page
- add i18n for system settings button
- add i18n for review validation

---

## [1.12.0] - 2026-05-08

**Backend Version**: 1.12.0
**Frontend Version**: 1.7.0

### Added
- support avatar in profile

---

## [1.11.1] - 2026-05-07

**Backend Version**: 1.11.1
**Frontend Version**: 1.6.1

### Fixed
- enhance background pic display with high quality
- update import error
- expand git_code_diff to medium text
- enhance the error message popup when multiple error occurred

---

## [1.11.0] - 2026-05-06

**Backend Version**: 1.11.0
**Frontend Version**: 1.6.0

### Added
- [may] add background pic for login
- [may] enhance the statistics chart of task assignment
- [may] add task assignment analytics

### Fixed
- fix i18n nesting mismatch issue
- [may] Better cross-browser compatibility

---

## [1.10.1] - 2026-05-05

**Backend Version**: 1.10.1
**Frontend Version**: 1.5.1

### Bug Fixes
- **Multiple Reviewers Display** - Enhanced multiple reviewers display in task assignment page
- **i18n for Score List & Analytics** - Enhanced internationalization for score list and analytics page
- **Null/Undefined Handling** - Fixed null and undefined issue for notifications
- **Reviewer Comments** - Fixed reviewer comments issue
- **Notification Indicator** - Enhanced indicator display for notifications
- **AI Review Results i18n** - Enhanced internationalization for AI review results

### Improvements
- **Unassigned Filter** - Enhanced "unassigned" filter
- **Scores Page Avatars** - Enhanced avatars for PR user and reviewer in Scores management page

---


## [1.10.0] - 2026-05-05

**Backend Version**: 1.10.0
**Frontend Version**: 1.5.0

### Features
- **Review Scores** - Added scores for each review
- **Notifications** - Implemented notifications system

### Bug Fixes
- **i18n for Score List & Analytics** - Enhanced internationalization
- **No AI Review Result UI** - Enhanced display when no AI review result
- **Import Error** - Resolved import error (amy)
- **Review Navigation** - Fixed navigation in review details
- **Pagination Optimization** - Optimized pagination in backend
- **Unassigned Task** - Enhanced "Unassigned" task by review admin
- **Single/Multiple Reviewer Scoring** - Enhanced scoring for single or multiple reviewers

### Improvements
- **Unscored Reviews Priority** - Refactored to show unscored reviews in priority
- **Implementation Docs** - Consolidated phase4 implementation documentation

---


## [1.9.1] - 2026-05-03

**Backend Version**: 1.9.1
**Frontend Version**: 1.4.1

### Features
- **Toggle for Scored Reviews** - Added toggle button to hide/show scored reviews
- **Bulk Task Assignment** - Added bulk operation for task assignment

### Bug Fixes
- **Remove Change PR Status** - Removed the "Change PR Status" feature
- **Bulk Operation Enhancements** - Enhanced bulk operation for reviews
- **Multiple Reviewers Display** - Enhanced display for multiple reviewers on same PR
- **i18n Enhancements** - Enhanced internationalization for all pages
- **Chart Labels & Axes** - Enhanced labels and x/y axis display
- **Dark Theme Dashboard** - Enhanced dashboard in dark theme
- **Score Calculation Fix** - Fixed score issue on first-time scoring
- **Create Tag Script** - Fixed create_tag script issues

---


## [1.9.0] - 2026-05-02

**Backend Version**: 1.9.0
**Frontend Version**: 1.4.0

### Features
- **PR Review Validation** - Added validation for pull request reviews
- **Release Manager Skill** - Automated release workflow integration
  - New `release-manager` skill for consistent version management
  - Automated changelog generation and dependency synchronization
  - Git tag creation with proper annotations

### Bug Fixes
- **Audit Logs** - Enhanced audit logging functionality
- **Admin Theme & Filtering** - Fixed theme issues and improved admin page filtering
- **PR Review Validation** - Enhanced validation of PR review insertions
- **Code Diff Display** - Improved code diff display styling
- **Theme & Code Diff** - Enhanced theme and code diff styling (multiple improvements)
- **Web Directory Cleanup** - Removed obsolete `web/` directory
- **Console Element Issues** - Fixed console issues with Element Plus component sliding

---


## [Unreleased]

### Added
- **Release Manager Skill** - Automated release workflow integration
  - New `release-manager` skill for consistent version management
  - Automated changelog generation and dependency synchronization
  - Git tag creation with proper annotations

- **Admin Password Reset** - Enhanced admin user management
  - Admins can now reset passwords for other users
  - New endpoint `POST /api/v1/admin/users/{user_id}/reset-password`
  - Force password change on next login option

- **Enhanced Score Management** - Improved score display and analytics
  - Enhanced score table with better filtering and sorting
  - Improved score analytics dashboard with advanced charts
  - Better score visualization in review details

- **Timezone Support** - Comprehensive timezone handling
  - Added `timezone.py` utility module for timezone conversions
  - Proper UTC timestamp handling across all models
  - Enhanced datetime display with timezone awareness

- **UI Navigation Enhancements** - Improved user experience
  - Added floating navigation in review details page
  - Better AI review result styling
  - Improved data lazy loading performance

### Fixed
- **Reviewer Visibility** - Fixed visible reviews filtering for reviewer role
- **Database Connection** - Enhanced connection handling and error recovery
- **AI Review Integration** - Fixed AI review ID handling and theme compatibility
- **Platform Compatibility** - Added tzdata dependency for cross-platform stability

### Technical Details
- **Backend Version**: 1.8.0 (FastAPI service)
- **Frontend Version**: 1.3.0 (Vue 3 application)
- **Database Migrations**: New migration for admin password reset functionality
- **Dependencies**: Added tzdata for timezone support

---

## [1.7.1] - 2026-04-26

### Changed
- **Version Bump**: Backend updated to v1.7.1, Frontend updated to v1.2.1
- **Configuration**: Removed unused `PROJECT_VERSION` field from `Settings` and `.env.example` to prevent future drift

---

## [1.7.0] - 2026-04-22

### Added
- **System Settings Management** - Centralized system configuration
  - New `system_setting` table for storing system-wide settings
  - Admin UI for managing system settings
  - Backend CRUD endpoints for system settings

- **Enhanced Admin Dashboard** - Comprehensive admin overview
  - New admin dashboard view with key metrics
  - Project registry management in admin page
  - Enhanced delegation query and management

- **Session Management** - User login session tracking
  - Manage user login sessions by user and admin
  - Enhanced session info display
  - Enhanced logged token and refresh mechanism

- **PR ID Hyperlinks** - Quick navigation to pull requests
  - Hyperlink for PR ID in task assignment page
  - Enhanced PR URL handling with `usePrUrl` composable

- **Code Diff Enhancements** - Improved diff visualization
  - Show code diff with diff2html in task assignment details page
  - Enhanced code diff styles referencing theme color
  - Optimized UI display for user-agent

- **Score Analytics Dashboard** - Enhanced analytics visualization
  - Improved score distribution charts
  - Better performance metrics display

- **i18n Enhancements** - Expanded internationalization support
  - Updated translations for en, zh-CN, zh-TW
  - Enhanced search for audit logs and sessions

- **Multi-Git Provider Support** - Broader Git provider compatibility
  - Replaced specific prefix of git provider to support more providers

### Changed
- **Task Assignment Workflow** - Improved task assignment experience
  - Enhanced sequence for task assignment
  - Highlight unassigned tasks with obvious tags
  - Allow PR user to view self-raised PR
  - Show more recent reviews
  - Add "next" button in reviews detail page for quick navigation
  - Enable switching reviews in details page

- **Filter Enhancements** - Better filtering capabilities
  - Optimize user filter
  - Add app_name as filter
  - Enhance filter styles and fix app name display

- **UI/UX Improvements** - Visual refinements across the application
  - Update styles of login and registry page
  - Optimize dashboard display
  - Optimize banner in code reviews page
  - Optimize records display as per resolution
  - Update menu style in admin layout

- **Permission Updates** - Refined access control
  - Enhance admin page access
  - Update permission for TAM page
  - Fix permission and score for reviewer
  - Update permission to view task assignment

### Fixed
- **Deprecated API Parameters** - Updated deprecated `Query()` parameter usage
- **Docker Configuration** - Fixed Dockerfile and nginx.conf issues
- **User Role Management** - Resolved user role management issues
- **Admin Route** - Fixed admin route issue after rename
- **Pagination** - Resolved pagination issues
- **Build Issues** - Fixed frontend build problems
- **Dependency Vulnerabilities** - Replaced xlsx with exceljs to avoid vulnerabilities
- **Delegation Status** - Handle delegation status transition with lifespan
- **Comments Component** - Fixed comments component display issue
- **PR User/Reviewer Filter** - Updated filter logic
- **Copyright/Version Display** - Fixed copyright and version info show in pages

### Technical Details
- **Backend Version**: 1.7.0 (FastAPI service)
- **Frontend Version**: 1.2.0 (Vue 3 application)
- **Database Migrations**: Added system settings table (migration 015), project registry permissions (migration 013), AI review ID column (migration 014)
- **Dependencies**: Replaced xlsx with exceljs for security

---

## [1.6.0] - 2026-04-13

### Added
- **Multi-Reviewer Review Architecture** - Split review persistence into base review and reviewer assignment tables
  - Added `pull_request_review_base` for shared PR review data
  - Added `pull_request_review_assignment` for reviewer-specific assignment state
  - Added migration coverage for the new review model and permission updates

- **Review Assignment and Delegation Flows** - Expanded review administration workflow across backend and UI
  - Added reviewer assignment tracking with assignment status and reviewer comments
  - Added frontend task assignment and role delegation management support
  - Added backend support for delegated review administration flows

### Changed
- **Backend Review Mapping** - Refactored ORM and service layers to use the new base-plus-assignment schema
  - Updated review, project, repository, and user relationships to target the new tables
  - Flattened base and assignment data at the service boundary to preserve the existing API response shape
  - Updated project statistics and assignment endpoints for the new schema

- **Release Metadata** - Aligned backend and frontend version surfaces for the new release
  - Backend version bumped to 1.6.0
  - Frontend version bumped to 1.1.0
  - Documentation updated to reflect the new release

### Fixed
- **Legacy Review Compatibility** - Removed stale single-table review assumptions after the schema refactor
  - Fixed assignment flows that previously depended on `pull_request_review.reviewer IS NULL`
  - Fixed mixed review model imports after consolidating canonical models
  - Fixed review statistics queries against the refactored tables

### Technical Details
- **Backend Version**: 1.6.0 (FastAPI service)
- **Frontend Version**: 1.1.0 (Vue 3 application)
- **Database Migrations**: Added multi-reviewer and permission updates through migrations 011 and 012

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
| 1.7.0 | 2026-04-22 | System settings, admin dashboard, session management, PR hyperlinks, diff enhancements, i18n updates |
| 1.6.0 | 2026-04-13 | Multi-reviewer review table split, assignment workflow, role delegation, release metadata alignment |
| 1.5.0 | 2026-04-08 | Vue.js frontend application, advanced review management, analytics dashboard |
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
