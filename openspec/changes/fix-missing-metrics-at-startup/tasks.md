## 1. Expand MetricsCollector.startup()

- [x] 1.1 Read current `startup()` method in `src/utils/metrics.py`
- [x] 1.2 Add initialization for `active_reviewers.labels(project="all").set(0)`
- [x] 1.3 Add initialization for `pull_requests_open.labels(project="all").set(0)`
- [x] 1.4 Add initialization for `pull_requests_merged.labels(project="all").set(0)`
- [x] 1.5 Add initialization for `review_backlog_count.labels(project="all").set(0)`
- [x] 1.6 Add initialization for `reviewers_load.labels(project="all").set(0)`
- [x] 1.7 Add initialization for `system_cpu_usage_percent.set(0)`
- [x] 1.8 Add initialization for `system_memory_usage_bytes.set(0)`
- [x] 1.9 Add initialization for `system_memory_available_bytes.set(0)`
- [x] 1.10 Add initialization for `system_disk_usage_bytes.labels(path="/").set(0)`
- [x] 1.11 Add initialization for `system_disk_available_bytes.labels(path="/").set(0)`
- [x] 1.12 Add initialization for `db_connections_active.set(0)`
- [x] 1.13 Add initialization for `sse_connections_active.set(0)`
- [x] 1.14 Add initialization for `users_active.set(0)`
- [x] 1.15 Add initialization for `reviewers_active.set(0)`
- [x] 1.16 Add initialization for `projects_active.set(0)`

## 2. Verify

- [x] 2.1 Run `ruff format && ruff check --fix` on changed files
- [x] 2.2 Run `pytest -v` to confirm no regressions
- [x] 2.3 Verify via Python that `generate_latest(REGISTRY)` includes all expected metrics after calling `startup()`
