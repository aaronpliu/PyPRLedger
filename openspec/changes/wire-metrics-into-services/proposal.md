## Why

The `MetricsCollector` defines ~40 metric families for comprehensive observability, but only ~6 are actually wired into the application's business logic. Metrics like `pull_requests_open`, `review_backlog_count`, `db_query_duration_seconds`, `errors_total`, and `system_*` are registered and initialized to 0, but never updated by service/endpoint code. Grafana dashboards show "0" for these because `.inc()`, `.set()`, and `.observe()` are never called. Wiring them requires adding simple one-liner calls at the right places in the existing service layer.

## What Changes

- Add `increment_pull_request()` calls in review creation flows
- Add `set_pull_requests_open()` / `set_pull_requests_merged()` in review workflows
- Add `set_review_backlog()` / `set_reviewers_load()` calls where relevant
- Add `observe_review_duration()` / `observe_review_cycle_time()` / `observe_pr_merge_time()` timing calls
- Add `increment_error()` / `increment_rate_limit_error()` in exception handlers
- Add `increment_files_reviewed()` / `increment_lines_changed()` in review creation
- Add `set_users_active()` / `set_projects_active()` in their respective services
- Add `observe_db_query_duration()` / `increment_db_query()` in database middleware
- Add `increment_notification_created/read/deleted()` in notification service
- Add `set_cpu_usage/set_memory/set_disk()` calls in a periodic system metrics collector
- Add `increment_cache_error()` in cache error paths

## Capabilities

### New Capabilities
*None — this wires existing metrics into existing code paths.*

### Modified Capabilities
- `observability`: Update requirement that all registered metrics must be actively updated by service/endpoint code.

## Impact

- ~10-15 files modified, each with 1-5 line additions
- No API changes, no schema changes, no config changes
- No new dependencies
- Metrics previously stuck at 0 will now reflect real application state
- Dashboards and alert rules become fully functional
