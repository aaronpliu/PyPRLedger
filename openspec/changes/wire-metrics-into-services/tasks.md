## 1. Pull Request metrics in review_service

- [ ] 1.1 Add `increment_pull_request()` call in `create_review()` (review_service.py) after review is saved
- [ ] 1.2 Add `set_pull_requests_open()` call in `create_review()` — compute open PR count for the project
- [ ] 1.3 Add `observe_review_duration()` call — wrap the review creation with `OperationTimer` or manual timing
- [ ] 1.4 Add `increment_files_reviewed()` and `increment_lines_changed()` calls — parse diff stats from review data
- [ ] 1.5 Add `set_review_backlog()` call — query and set pending review count after creation
- [ ] 1.6 Add `set_reviewers_load()` call — compute average active PRs per reviewer
- [ ] 1.7 Add `observe_review_cycle_time()` call — measure time from PR creation to first review (if available)
- [ ] 1.8 Add `observe_pr_merge_time()` call — measure time from PR creation to merge (if merging)

## 2. System metrics background task

- [ ] 2.1 Add `import psutil` in `main.py`
- [ ] 2.2 Add `system_metrics_collection_task()` async function in `main.py` that runs every 60s
- [ ] 2.3 Inside the task, collect CPU, memory, and disk stats and call `metrics_collector.set_cpu_usage()`, `set_memory_usage()`, `set_memory_available()`, `set_disk_usage()`, `set_disk_available()`
- [ ] 2.4 Add the task to the lifespan startup and cleanup in `background_tasks`

## 3. Cache error metrics in Redis wrapper

- [ ] 3.1 Add try/except around cache operations in `src/utils/redis.py` that calls `metrics.cache_errors_total.labels(...).inc()` on errors
- [ ] 3.2 Import the global `metrics` instance in `redis.py`

## 4. Database query metrics

- [ ] 4.1 Add `observe_db_query_duration()` and `increment_db_query()` calls in `src/core/database.py` query execution paths
- [ ] 4.2 Import the global `metrics` instance in `database.py`

## 5. Error metrics in middleware

- [ ] 5.1 Add `increment_error()` call in the general exception handler in `src/core/middleware.py`
- [ ] 5.2 Add `increment_rate_limit_error()` call in `RateLimitMiddleware`
- [ ] 5.3 Import the global `metrics` instance in `middleware.py`

## 6. User activity metrics

- [ ] 6.1 Add `set_users_active()` call in `user_service.py` where user stats are computed
- [ ] 6.2 Add `set_projects_active()` call in `project_service.py` where project stats are computed

## 7. Verify

- [ ] 7.1 Run `ruff format && ruff check --fix` on all changed files
- [ ] 7.2 Run `pytest -v` to confirm no regressions
- [ ] 7.3 Verify via curl that metrics reflect real operations (create a review, check Prometheus)
