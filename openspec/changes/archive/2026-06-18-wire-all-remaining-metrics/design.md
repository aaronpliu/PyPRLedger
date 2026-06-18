## Context

The `MetricsCollector` registers ~40 metric families. The `wire-metrics-into-services` change wired 29 of these into active code paths. 11 remain orphaned — registered and initialized to 0 in `startup()`, but never `.inc()`, `.set()`, or `.observe()` is called anywhere in the application. This design wires the remaining 11, grouped by the architectural approach needed.

## Goals / Non-Goals

**Goals:**
- Wire all 11 remaining inactive metric update paths
- Ensure every metric defined in `MetricsCollector` reflects real application state during normal operation
- Group wiring by architectural pattern (direct calls vs. event listeners vs. SQLAlchemy hooks)

**Non-Goals:**
- No new metric definitions (all metrics already exist)
- No restructuring of the `MetricsCollector` class
- No new external dependencies
- No changes to API endpoints, schemas, or database models

## Decisions

### Decision 1: Direct injection for review detail and cache error metrics

**Approach:** Add direct `metrics.increment_*()` calls at the exact point the measured event occurs.

**Rationale:**
- `increment_cache_error()` — each `except` block in `RedisCache` methods already logs warnings. Adding a metrics call next to the log is a one-liner and keeps the error tracking co-located with error handling.
- `increment_files_reviewed()` / `increment_lines_changed()` — the review creation flow in `review_service.py` already has access to file/line data. Adding `.inc()` calls is trivial.

**Alternatives considered:**
- AOP/decorator approach — overkill for 3-5 injection points

### Decision 2: Compute reviewer load from existing data sources

**Approach:** `set_active_reviewers()` and `set_reviewers_load()` should be set in `user_service.py` where reviewer counts are already computed via `get_user_statistics()`. `set_reviewers_load()` = `review_backlog_count / active_reviewers`.

**Rationale:**
- `get_user_statistics()` already queries `active_reviewers` and other counts — adding `.set()` calls there is the path of least resistance
- No new queries needed; reuse existing DB results

### Decision 3: PR lifecycle metrics via event hooks

**Approach:** Add metrics calls at PR status transition points:
- `set_pull_requests_merged()` — when a PR review status changes to "merged" in `reviews.py` endpoint or `review_service.py`
- `observe_review_cycle_time()` — measure `now - pr_created_at` at review creation time; compute from the pull request's creation timestamp
- `observe_pr_merge_time()` — measure `now - pr_created_at` at merge time

**Rationale:**
- These require access to the PR's creation timestamp, which is available in the review creation flow
- Computed outside the hot path (not per-request, per-review cycle)

### Decision 4: Database metrics via SQLAlchemy events

**Approach:** Use SQLAlchemy's `before_execute` and `after_execute` event listeners on the engine to count queries and observe durations. Add a pool checkout listener for `db_connections_active`.

**Rationale:**
- Wrapping every `db.execute()` call manually is error-prone and invasive
- SQLAlchemy events provide a clean, centralized hook
- The engine is created once in `DatabaseManager` — one-time listener setup

**Implementation sketch:**
```python
@event.listens_for(Engine, "before_execute")
def before_execute(conn, clause, multiparams, params, execution_options):
    conn.info["query_start_time"] = time.monotonic()

@event.listens_for(Engine, "after_execute")
def after_execute(conn, clause, multiparams, params, execution_options, result):
    if metrics := getattr(conn, "_metrics", None):
        metrics.increment_db_query()
        if start := conn.info.pop("query_start_time", None):
            metrics.observe_db_query_duration(time.monotonic() - start)
```

For active connections, use SQLAlchemy's pool events:
```python
@event.listens_for(Pool, "checkout")
def on_checkout(dbapi_conn, conn_record, conn_proxy):
    # set db_connections_active using pool.size() or pool.checkedin()
```

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| **SQLAlchemy events add per-query overhead** (microseconds) | Negligible — `time.monotonic()` + increment calls are <1µs each |
| **Cache error wiring touches many except blocks** in `redis.py` | Each addition is a single line next to existing `logger.warning()` calls; mechanical and safe |
| **PR merge detection depends on status transition** — merging may not always go through the same code path | Audit `reviews.py` and `review_service.py` for all status transitions; cover the known paths |
| **`reviewers_load` could divide by zero** (no active reviewers) | Guard with `max(active_reviewers, 1)` or set to 0 when no reviewers are active |
