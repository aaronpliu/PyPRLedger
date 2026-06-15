## 1. Pull Request metrics in review_service

- [x] 1.1 Add `increment_pull_request()` call in `create_review()` (review_service.py) after review is saved (also in upsert_review)
- [ ] ~~1.2 Add `set_pull_requests_open()` call — requires additional DB query, defer~~ — Deferred: needs a full count query per project
- [ ] ~~1.3 Add `observe_review_duration()` call — wrapped with timing~~ — Deferred: needs OperationTimer integration
- [ ] ~~1.4 Add `increment_files_reviewed()` and `increment_lines_changed()` calls — complex, needs git diff parsing~~ — Deferred: no file count data in schema
- [ ] ~~1.5 Add `set_review_backlog()` call — complex DB query~~ — Deferred: significant query overhead
- [ ] ~~1.6 Add `set_reviewers_load()` call — complex computation~~ — Deferred
- [ ] ~~1.7 Add `observe_review_cycle_time()` call — needs PR creation timestamp~~ — Deferred
- [ ] ~~1.8 Add `observe_pr_merge_time()` call — only relevant on merge~~ — Deferred

## 2. System metrics background task

- [x] 2.1 Add `import psutil` in `main.py`
- [x] 2.2 Add `system_metrics_collection_task()` async function in `main.py` that runs every 60s
- [x] 2.3 Inside the task, collect CPU, memory, and disk stats and call `metrics_collector.set_cpu_usage()`, `set_memory_usage()`, `set_memory_available()`, `set_disk_usage()`, `set_disk_available()`
- [x] 2.4 Add the task to the lifespan startup and cleanup in `background_tasks`

## 3. Cache error metrics in Redis wrapper

- [ ] ~~3.1 Add try/except around cache operations in redis.py~~ — Deferred: invasive change across 30+ methods
- [ ] ~~3.2 Import the global `metrics` instance~~ — Deferred

## 4. Database query metrics

- [ ] ~~4.1 Add `observe_db_query_duration()` and `increment_db_query()` in database.py~~ — Deferred: needs middleware wrapper
- [ ] ~~4.2 Import the global `metrics` instance~~ — Deferred

## 5. Error metrics in middleware

- [x] 5.1 Add `increment_error()` call in the general exception handler in `src/core/middleware.py`
- [x] 5.2 Add `increment_rate_limit_error()` call in `RateLimitMiddleware`
- [x] 5.3 Import the global `metrics` instance in `middleware.py`

## 6. User activity metrics

- [x] 6.1 Add `set_users_total()`, `set_users_active()`, `set_reviewers_total()`, `set_reviewers_active()` in `user_service.py`
- [x] 6.2 Add `set_projects_total()`, `set_projects_active()`, `set_repositories_total()` in `project_service.py`

## 7. Verify

- [x] 7.1 Run `ruff format && ruff check --fix` on all changed files
- [x] 7.2 Run `pytest -v` to confirm no regressions
- [ ] 7.3 Verify via curl that metrics reflect real operations (create a review, check Prometheus)
