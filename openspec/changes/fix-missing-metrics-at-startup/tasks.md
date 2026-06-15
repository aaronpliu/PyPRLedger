## 1. Expand MetricsCollector.startup()

- [ ] 1.1 Read current `startup()` method in `src/utils/metrics.py`
- [ ] 1.2 Add initialization for `active_reviewers.labels(project="all").set(0)`
- [ ] 1.3 Add initialization for `pull_requests_open.labels(project="all").set(0)`
- [ ] 1.4 Add initialization for `pull_requests_merged.labels(project="all").set(0)`
- [ ] 1.5 Add initialization for `review_backlog_count.labels(project="all").set(0)`
- [ ] 1.6 Add initialization for `reviewers_load.labels(project="all").set(0)`
- [ ] 1.7 Add initialization for `system_cpu_usage_percent.set(0)`
- [ ] 1.8 Add initialization for `system_memory_usage_bytes.set(0)`
- [ ] 1.9 Add initialization for `system_memory_available_bytes.set(0)`
- [ ] 1.10 Add initialization for `system_disk_usage_bytes.labels(path="/").set(0)`
- [ ] 1.11 Add initialization for `system_disk_available_bytes.labels(path="/").set(0)`
- [ ] 1.12 Add initialization for `db_connections_active.set(0)`
- [ ] 1.13 Add initialization for `sse_connections_active.set(0)`
- [ ] 1.14 Add initialization for `users_active.set(0)`
- [ ] 1.15 Add initialization for `reviewers_active.set(0)`
- [ ] 1.16 Add initialization for `projects_active.set(0)`

## 2. Verify

- [ ] 2.1 Run `ruff format && ruff check --fix` on changed files
- [ ] 2.2 Run `pytest -v` to confirm no regressions
- [ ] 2.3 Verify via Python that `generate_latest(REGISTRY)` includes all expected metrics after calling `startup()`
