## 1. Review detail metrics

- [ ] 1.1 Add `increment_files_reviewed()` and `increment_lines_changed()` calls in `review_service.py` where files and line counts are available during review creation
- [ ] 1.2 Add `observe_review_cycle_time()` call in `review_service.py` at review creation, measuring from PR creation timestamp
- [ ] 1.3 Add `set_pull_requests_merged()` call at PR merge status transition in `review_service.py` or `reviews.py`
- [ ] 1.4 Add `observe_pr_merge_time()` call at merge time, measuring from PR creation timestamp

## 2. Cache error metrics

- [ ] 2.1 Wire metrics instance into `RedisCache` in `src/utils/redis.py` (import global `metrics` instance)
- [ ] 2.2 Add `metrics.increment_cache_error(cache_type="redis", error_type=...)` call in each `except` block across all `RedisCache` methods

## 3. Reviewer load metrics

- [ ] 3.1 Add `set_active_reviewers(project, count)` call in `user_service.py` where reviewer counts are computed
- [ ] 3.2 Add `set_reviewers_load(project, load)` call, computing `review_backlog_count / max(active_reviewers, 1)`

## 4. Database metrics via SQLAlchemy events

- [ ] 4.1 Add SQLAlchemy `before_execute` / `after_execute` event listeners on the engine in `src/core/database.py` to increment `db_queries_total` and observe `db_query_duration_seconds`
- [ ] 4.2 Add SQLAlchemy pool `checkout` event listener to set `db_connections_active` reflecting current pool usage

## 5. Verify

- [ ] 5.1 Run `ruff format && ruff check --fix` on all changed files
- [ ] 5.2 Run `pytest -v` to confirm no regressions
- [ ] 5.3 Verify via Python that `generate_latest(REGISTRY)` includes non-zero values for all previously-dormant metrics after exercising relevant code paths
