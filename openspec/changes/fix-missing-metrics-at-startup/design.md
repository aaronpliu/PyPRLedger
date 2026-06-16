## Context

The `MetricsCollector` registers ~40 metric families on the default Prometheus registry. However, `prometheus_client.generate_latest()` only emits metrics that have received at least one explicit value (`.set()`, `.inc()`, or `.observe()` call). The `startup()` method currently initializes only 4 Gauges (`users_total`, `reviewers_total`, `projects_total`, `repositories_total`). The remaining 30+ metrics are registered but invisible until a business operation first touches them.

This is a subtle gotcha in `prometheus_client` — registered metrics with no values are entirely omitted from the HTTP output, making it appear as if they don't exist.

## Goals / Non-Goals

**Goals:**
- All Gauges emit zero values immediately after app startup
- All Counters emit zero values immediately after app startup
- Existing metrics continue to work unchanged
- Dashboards show "0" instead of "No data" for metrics without real values yet

**Non-Goals:**
- Not changing how metrics are updated at runtime (that still happens in services)
- Not changing the Grafana dashboards
- Not changing Prometheus configuration

## Decisions

### Decision 1: Initialize gauges with a default "all" project label

Several gauges have a `project` label (`active_reviewers`, `pull_requests_open`, `pull_requests_merged`, `review_backlog_count`, `reviewers_load`). Initialize these with `project="all"` as a sentinel value. The actual project-specific values will overwrite this when services call `set()` with real project keys.

### Decision 2: Initialize system disk gauges with path="/"

`system_disk_usage_bytes` and `system_disk_available_bytes` have a `path` label. Initialize with `path="/"`.

### Decision 3: Counter metrics do NOT need explicit inc(0)

Counters with no explicit `.inc()` call also omit output. However, unlike Gauges where zero is meaningful (the thing exists but has no activity), Counters at zero are not actionable in dashboards (a counter that was never incremented tells you nothing). We'll skip pre-initializing Counters — they'll appear when actual operations happen.

## Risks / Trade-offs

- **[Low] Default label values**: Using `project="all"` as default might cause confusion if someone queries for `active_reviewers{project="all"}` — it's not a real project. Mitigation: the value is 0, and real data quickly overwrites it.
- **[Low] Startup overhead**: Adding ~15 extra `.set()` calls in startup adds negligible latency (~microseconds).
