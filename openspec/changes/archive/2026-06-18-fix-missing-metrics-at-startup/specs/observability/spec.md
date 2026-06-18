## ADDED Requirements

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
