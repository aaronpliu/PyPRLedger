## Why

The `wire-metrics-into-services` change wired 29 of 40 metrics registered by `MetricsCollector`, but 11 metric update paths remain completely inactive — they are registered and initialized to 0 but never called by any code path. Grafana dashboards show stale zeros for these metrics, and alert rules depending on them are non-functional. This change closes the final gap.

## What Changes

- Add `increment_cache_error()` calls to all `except` blocks in `src/utils/redis.py`
- Add `increment_files_reviewed()` and `increment_lines_changed()` calls in review creation flow
- Add `set_active_reviewers()` call where active reviewer count is computed
- Add `set_reviewers_load()` call using existing backlog/reviewer data
- Add `set_pull_requests_merged()` call on PR merge status changes
- Add `observe_review_cycle_time()` call measuring PR creation to review time
- Add `observe_pr_merge_time()` call measuring PR creation to merge time
- Add SQLAlchemy event listeners for `set_db_connections_active()`, `increment_db_query()`, and `observe_db_query_duration()`

## Capabilities

### New Capabilities
*None — all target metrics are already registered and defined.*

### Modified Capabilities
- `observability`: Update the "Application metrics actively updated by business logic" requirement to cover the 11 remaining inactive metric paths

## Impact

- 4-8 files modified, each with small additions (1-10 lines)
- New SQLAlchemy event listeners for database metrics
- No API changes, no schema changes, no new dependencies
- All 40 metrics become fully active and reflective of real application state
