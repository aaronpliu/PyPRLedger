## Context

The `MetricsCollector` defines ~40 metric families. After our `startup()` fix, all Gauges initialize to 0 and appear in Prometheus output. However, only `review_total` (sparingly), `sse_*`, and `reviewers_active` ever get updated by running code. The remaining ~30 metrics stay at 0 forever. This design wires each metric into the code path where the relevant business operation occurs.

## Goals / Non-Goals

**Goals:**
- Every metric in `MetricsCollector` gets `.inc()`, `.set()`, or `.observe()` called at least once during normal operation
- Metrics reflect actual business state (review counts, PR counts, error rates, etc.)
- Grafana dashboards show real data, not zeros
- Alert rules can fire based on real conditions

**Non-Goals:**
- Not adding new metrics (the 40 existing ones are sufficient)
- Not restructuring how metrics are collected
- Not adding external monitoring agents (e.g., node_exporter for system metrics)

## Decisions

### Decision 1: Add metric calls at the point of the business operation

Each metric should be updated at the exact moment the thing it measures happens. For example:
- `increment_pull_request()` → when a PR review is created (in `review_service.py`)
- `set_review_backlog()` → computed and set after each review creation/update
- `observe_db_query_duration()` → in the database middleware
- `set_cpu_usage()` → via a lightweight background task in `main.py`

### Decision 2: System metrics collected via lightweight background task

Metrics like `system_cpu_usage_percent`, `system_memory_*`, and `system_disk_*` require periodic polling. Add a lightweight async background task in `main.py` (similar to the existing delegation_status_cleanup_task) that runs every 60s and collects system stats using `psutil`.

### Decision 3: Cache error metrics in cache wrapper

`cache_errors_total` should be incremented in the Redis cache wrapper's error paths rather than in individual services.

## Metrics Wiring Map

```
Metric                           Where to Wire
───────────────────────────────  ──────────────────────────────
review_total                     review_service.create_review (already wired, guarded by reviewer)
review_duration_seconds          review_service — wrap review creation with OperationTimer
active_reviewers                 user_service — set after querying active reviewer count
review_score                     review_score_service (already wired)

users_total                      user_service (already wired via inc/dec)
users_active                     user_service — set when computing user stats
reviewers_total                  user_service (already wired)
reviewers_active                 users endpoint (already wired)

projects_total                   project_service (already wired)
projects_active                  project_service — set when querying project stats
repositories_total               project_service (already wired)

pull_requests_total              review_service — after PR review is created
pull_requests_open               review_service — set after computing open PR count
pull_requests_merged             review_service — set when PR is merged

cache_hits_total                 redis.py — cache hit paths (already wired by services)
cache_misses_total               redis.py — cache miss paths (already wired)
cache_errors_total               redis.py — catch cache error exceptions

db_connections_active            database.py — set when creating/checking pool (already in startup)
db_query_duration_seconds        database.py or middleware — wrap queries with OperationTimer
db_queries_total                 database middleware — after each query

system_cpu_usage_percent         main.py — new background task (60s interval)
system_memory_usage_bytes        main.py — new background task
system_memory_available_bytes    main.py — new background task
system_disk_usage_bytes          main.py — new background task
system_disk_available_bytes      main.py — new background task

errors_total                     core/middleware.py — in exception handler
errors_rate_limited_total        rate limit middleware — when rate limit triggers

files_reviewed_total             review_service — after review created
lines_changed_total              review_service — after review created

review_cycle_time_seconds        review_service — measure time from PR creation to review
pr_merge_time_seconds            review_service — measure time from PR creation to merge
review_backlog_count             review_service — compute and set after review operations
reviewers_load                   review_service — compute and set after review operations

notification_created_total       notification_service (already wired)
notification_read_total          notification_service (already wired)
notification_deleted_total       notification_service (already wired)

sse_connections_active           sse endpoint (already wired)
sse_connections_total            sse endpoint (already wired)
sse_events_published_total       review_service (already wired)
sse_events_filtered_total        sse endpoint (already wired)
```

## Risks / Trade-offs

- **[Low] Background task overhead:** System metrics polling every 60s is negligible (psutil calls are fast). But it's a new async task that needs proper lifecycle management.
- **[Low] Middleware latency:** Adding `db_query_duration` observation in middleware adds ~microseconds per query. Negligible.
- **[Medium] Codebase diff:** ~15 files changed. Each change is small (1-5 lines), but the total footprint is spread across the codebase. Review carefully.
