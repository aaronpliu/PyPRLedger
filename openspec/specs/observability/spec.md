# Observability

## Purpose

Define the monitoring infrastructure for PRLedger — metrics collection via Prometheus, visualization via Grafana, and alerting via AlertManager — as a standalone, independently deployable stack.

## Requirements

### Requirement: Centralized monitoring configuration
The system SHALL provide a standalone `monitoring/` directory at the project root containing all configuration files for Prometheus, Grafana, and AlertManager, enabling the monitoring stack to be managed and deployed independently from the application stack.

#### Scenario: Standalone monitoring directory exists
- **WHEN** a developer navigates to the project root
- **THEN** a `monitoring/` directory SHALL exist containing `docker-compose.yml`, `prometheus/`, `alertmanager/`, and `grafana/` subdirectories

#### Scenario: Deployment from monitoring directory
- **WHEN** a developer runs `docker compose -f monitoring/docker-compose.yml up -d`
- **THEN** Prometheus, Grafana, and AlertManager containers SHALL start and become healthy

### Requirement: Prometheus metrics scraping
The Prometheus configuration SHALL scrape the PRLedger API at `http://api:8000/api/metrics` with a default scrape interval of 10 seconds, and SHALL also scrape Prometheus self-metrics at `http://localhost:9090/metrics`.

#### Scenario: API metrics scraping
- **WHEN** Prometheus is running and the API container is healthy
- **THEN** the `PRLedger` scrape target SHALL appear as UP in Prometheus target status within 30 seconds

#### Scenario: Prometheus self-monitoring
- **WHEN** Prometheus is running
- **THEN** the `prometheus` scrape target SHALL appear as UP in Prometheus target status

### Requirement: Alert rules for application health
The system SHALL define Prometheus alert rules for application-level concerns, including: API down, elevated error rate (>5% over 5 minutes), elevated latency (P99 > 2s), and growing review backlog (>50 pending).

#### Scenario: Alert rules defined
- **WHEN** Prometheus loads its configuration
- **THEN** the rule files in `prometheus/rules/` SHALL be evaluated at the configured evaluation interval

#### Scenario: Alert triggers on API down
- **WHEN** the API endpoint is unreachable for more than 1 minute
- **THEN** a `PRLedgerDown` alert SHALL fire at severity `critical`

#### Scenario: Alert triggers on high error rate
- **WHEN** the ratio of 5xx errors to total requests exceeds 5% over a 5-minute window
- **THEN** an `APIErrorRateHigh` alert SHALL fire at severity `warning`

### Requirement: Alert rules for infrastructure health
The system SHALL define Prometheus alert rules for infrastructure-level concerns, including: high CPU usage (>80%), low disk space (<10%), high memory usage (>90%), and elevated database connections (>80% of pool).

#### Scenario: Infrastructure alert rules defined
- **WHEN** Prometheus loads its configuration
- **THEN** infrastructure alert rules SHALL be in separate rule files from application alert rules

### Requirement: AlertManager notification routing
AlertManager SHALL route alerts by severity: `critical` alerts SHALL be sent to all configured receivers, `warning` alerts SHALL be sent to Slack (if configured) and console, `info` alerts SHALL be logged to console only.

#### Scenario: Console receiver works by default
- **WHEN** any alert fires and no Slack webhook is configured
- **THEN** the alert SHALL be logged to AlertManager container stdout

#### Scenario: Slack receiver works when configured
- **WHEN** `SLACK_WEBHOOK_URL` environment variable is set and an alert fires
- **THEN** the alert SHALL be delivered to the configured Slack channel

### Requirement: Grafana with auto-provisioned Prometheus datasource
Grafana SHALL automatically configure a Prometheus datasource pointing to `http://prometheus:9090` on startup, without manual configuration.

#### Scenario: Prometheus datasource auto-configured
- **WHEN** Grafana starts for the first time
- **THEN** the Prometheus datasource SHALL appear in Grafana's datasource list with URL `http://prometheus:9090`

### Requirement: Grafana dashboards auto-provisioned
Grafana SHALL automatically load dashboard JSON files from the `grafana/dashboards/` directory on startup, making them available in the Grafana UI without manual import.

#### Scenario: Dashboards loaded on startup
- **WHEN** Grafana starts
- **THEN** at least the `PRLedger Overview` dashboard SHALL be available in the Grafana UI

#### Scenario: Adding new dashboards
- **WHEN** a new `.json` dashboard file is added to `monitoring/grafana/dashboards/`
- **THEN** after a Grafana restart or provisioning reload, the new dashboard SHALL appear in the UI

### Requirement: Standalone docker-compose with shared network
The monitoring `docker-compose.yml` SHALL declare `code-review-network` as an external network, and SHALL document in comments that the user must create this network before deploying.

#### Scenario: Docker network prerequisite documented
- **WHEN** a developer reads the monitoring `docker-compose.yml`
- **THEN** the file SHALL contain comments explaining the network requirement

#### Scenario: Stack starts on shared network
- **WHEN** the user creates `code-review-network` and runs `docker compose -f monitoring/docker-compose.yml up -d`
- **THEN** all three containers SHALL be attached to `code-review-network`

### Requirement: Removal of root-level monitoring files
After consolidation, the root-level `prometheus.yml` file and `grafana/` directory SHALL be removed, and the Prometheus/Grafana services SHALL be removed from the root `docker-compose.yml`.

#### Scenario: Root files removed
- **WHEN** the change is applied
- **THEN** `prometheus.yml` SHALL not exist at the project root

#### Scenario: Root compose cleaned
- **WHEN** the change is applied
- **THEN** the root `docker-compose.yml` SHALL NOT contain `prometheus` or `grafana` service definitions, their volumes, or their network attachments

#### Scenario: Deprecation notice exists
- **WHEN** a developer reads the root `docker-compose.yml`
- **THEN** a comment SHALL reference `monitoring/docker-compose.yml` as the new location for the monitoring stack

### Requirement: Metrics initilize at startup
The system SHALL initialize all Gauge metrics to 0 in the `startup()` method so they appear in Prometheus output immediately after application launch.

#### Scenario: All gauges appear after startup
- **WHEN** the application starts and `startup()` is called
- **THEN** every Gauge metric registered by `MetricsCollector` SHALL appear in the `/api/metrics` endpoint output with a value of 0

#### Scenario: Default label values used for labeled gauges
- **WHEN** a Gauge has a `project` label
- **THEN** it SHALL be initialized with `project="all"` at startup
- **WHEN** a Gauge has a `path` label
- **THEN** it SHALL be initialized with `path="/"` at startup

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
- **AND** `db_connections_active` SHALL reflect the current number of active connections

#### Scenario: User activity metrics updated
- **WHEN** user statistics are computed
- **THEN** `users_active` SHALL be set to the current count
- **AND** `projects_active` SHALL be set to the current count

#### Scenario: PR lifecycle metrics updated
- **WHEN** a pull request review is created
- **THEN** `review_cycle_time_seconds` SHALL observe the time since the pull request was created
- **WHEN** a pull request status changes to merged
- **THEN** `pr_merge_time_seconds` SHALL observe the time since the pull request was created
- **AND** `pull_requests_merged` SHALL be set to reflect the current merged count

#### Scenario: Review detail metrics updated
- **WHEN** a code review is created with files and line changes
- **THEN** `files_reviewed_total` SHALL increment by the number of files reviewed
- **AND** `lines_changed_total` SHALL increment by the number of lines changed

#### Scenario: Reviewer load metrics updated
- **WHEN** reviewer statistics are computed
- **THEN** `active_reviewers` SHALL reflect the current count of active reviewers per project
- **AND** `reviewers_load` SHALL reflect the average number of reviews per active reviewer
