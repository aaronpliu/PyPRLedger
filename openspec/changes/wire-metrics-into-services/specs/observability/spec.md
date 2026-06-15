## ADDED Requirements

### Requirement: Application metrics actively updated by business logic
All metrics registered by `MetricsCollector` SHALL be updated by corresponding service or endpoint code during normal application operation. Metrics that reflect counts (review_total, pull_requests_total, etc.) SHALL increment when the corresponding entity is created. Metrics that reflect instantaneous state (active_reviewers, pull_requests_open, etc.) SHALL be set when the state is computed. Metrics that reflect durations (review_duration_seconds, db_query_duration_seconds, etc.) SHALL be observed when the operation completes.

#### Scenario: Pull request metrics update on review creation
- **WHEN** a code review is created
- **THEN** `pull_requests_total` SHALL increment
- **AND** `pull_requests_open` SHALL reflect the updated count
- **AND** `review_total` SHALL increment (if reviewer is assigned)

#### Scenario: System metrics collected periodically
- **WHEN** the application has been running for more than 60 seconds
- **THEN** `system_cpu_usage_percent`, `system_memory_usage_bytes`, `system_memory_available_bytes`, `system_disk_usage_bytes`, and `system_disk_available_bytes` SHALL have been updated at least once

#### Scenario: Error metrics updated on exceptions
- **WHEN** an application exception occurs
- **THEN** `errors_total` SHALL increment
- **WHEN** a rate limit is triggered
- **THEN** `errors_rate_limited_total` SHALL increment

#### Scenario: Cache error metrics updated on failures
- **WHEN** a Redis cache operation fails
- **THEN** `cache_errors_total` SHALL increment with the appropriate `cache_type` and `error_type` labels

#### Scenario: Database query metrics updated
- **WHEN** a database query is executed
- **THEN** `db_queries_total` SHALL increment
- **AND** `db_query_duration_seconds` SHALL observe the query duration

#### Scenario: User activity metrics updated
- **WHEN** user statistics are computed
- **THEN** `users_active` SHALL be set to the current count
- **AND** `projects_active` SHALL be set to the current count
