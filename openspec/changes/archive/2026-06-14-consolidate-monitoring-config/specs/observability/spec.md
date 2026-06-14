## ADDED Requirements

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
