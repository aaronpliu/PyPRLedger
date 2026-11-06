## ADDED Requirements

### Requirement: Business code notifies, it does not choose channels

The system SHALL expose a single notification entry point that accepts a domain event and its payload. Business code MUST NOT select a delivery channel, build a per-channel message body, or call a transport directly.

#### Scenario: An event is raised by a business flow
- **WHEN** a reviewer is assigned, a release is published, or a note mentions somebody
- **THEN** the calling code SHALL raise one event carrying the event type and its payload
- **AND** the calling code SHALL NOT name a channel or construct a formatted message

#### Scenario: A new channel is added later
- **WHEN** an operator enables a channel that business code has never heard of
- **THEN** the existing call sites SHALL deliver to it without modification

### Requirement: Outbound delivery is decoupled from the request

Creating a notification and delivering it to an external system SHALL be separate steps. The request that raised the event MUST NOT wait on a third-party endpoint, and MUST NOT fail because that endpoint is unreachable, slow, or misconfigured.

#### Scenario: The mail relay is unreachable
- **WHEN** an event is raised while the configured SMTP host refuses connections
- **THEN** the originating request SHALL complete successfully
- **AND** the in-app notification SHALL still be stored
- **AND** the external delivery SHALL be recorded as pending and retried later

#### Scenario: The process restarts with deliveries outstanding
- **WHEN** the application restarts while deliveries are queued
- **THEN** the pending deliveries SHALL still be deliverable after startup
- **AND** no queued delivery SHALL be lost by the restart

#### Scenario: An endpoint hangs
- **WHEN** a third-party endpoint accepts the connection but never responds
- **THEN** the delivery SHALL be abandoned after the endpoint's configured timeout
- **AND** other deliveries SHALL continue to be processed

### Requirement: A channel is configured, not coded

An external message channel SHALL be described by an endpoint record that an administrator can create and edit at runtime. Adding an HTTP-based channel (an internal IM gateway, a vendor webhook, a relay) MUST NOT require a code change or a redeploy.

#### Scenario: A new intranet IM is registered
- **WHEN** an administrator adds an endpoint with a URL, headers, a request body template and a channel kind
- **THEN** events routed to that channel SHALL be posted to that endpoint
- **AND** no application code SHALL have been changed

#### Scenario: An endpoint is disabled
- **WHEN** an administrator disables an endpoint
- **THEN** no further deliveries SHALL be sent to it
- **AND** deliveries already queued for it SHALL be parked rather than retried indefinitely

#### Scenario: An endpoint is edited
- **WHEN** the URL, credentials, timeout or template of an endpoint change
- **THEN** subsequent deliveries SHALL use the new values without a restart

### Requirement: Endpoint credentials are write-only

Credentials stored on an endpoint (SMTP password, token, webhook signing secret) SHALL be encrypted at rest, SHALL be excluded from API responses and logs, and SHALL be changeable without being readable back.

#### Scenario: The endpoint list is read
- **WHEN** an administrator opens the notification settings
- **THEN** each endpoint SHALL be shown with its non-secret configuration
- **AND** every secret SHALL be represented by a placeholder rather than its value

#### Scenario: A delivery fails with an authentication error
- **WHEN** the provider quotes the credential back in its error response
- **THEN** the stored error SHALL have the credential redacted
- **AND** the redacted error SHALL be what the admin page shows

#### Scenario: A secret is left unchanged
- **WHEN** an endpoint is saved with the secret field still holding the placeholder
- **THEN** the previously stored secret SHALL be kept

### Requirement: Delivery is idempotent

Each delivery SHALL be identified by the event, the recipient and the channel. Re-processing the same delivery (a retry, a replayed row, a duplicate event) MUST NOT produce a second message to the recipient.

#### Scenario: A retry follows a timeout
- **WHEN** a delivery times out after the remote side actually accepted it
- **THEN** the retry SHALL be suppressed by the delivery's identity
- **AND** the recipient SHALL NOT receive the message twice

#### Scenario: The same event is raised twice
- **WHEN** the same event type with the same identifier and payload is raised again within the deduplication window
- **THEN** only one delivery per recipient and channel SHALL be created

### Requirement: Failures are retried, then parked and replayable

A failed delivery SHALL be retried with a growing delay for a bounded number of attempts, after which it SHALL be parked as failed rather than dropped. A parked delivery SHALL be visible to an administrator and replayable.

#### Scenario: A transient failure recovers
- **WHEN** an endpoint fails and later succeeds within the retry budget
- **THEN** the delivery SHALL be marked delivered
- **AND** the attempt count and the last error SHALL remain recorded

#### Scenario: The retry budget is exhausted
- **WHEN** a delivery fails on its final attempt
- **THEN** it SHALL be parked with its last error and its rendered content preserved
- **AND** it SHALL NOT be retried until it is replayed

#### Scenario: An endpoint trips the circuit breaker
- **WHEN** an endpoint fails repeatedly in a short window
- **THEN** further deliveries to it SHALL be deferred instead of attempted
- **AND** the endpoint SHALL be reported as unhealthy until it succeeds again

### Requirement: Recipients include people without an account

The system SHALL resolve recipients from both the account directory (email and messaging identifiers) and a subscription list that can hold external addresses not backed by any account. Subscription SHALL be scoped so that an external recipient receives only the events of the projects or repositories they subscribed to.

#### Scenario: An external recipient is subscribed to a project
- **WHEN** an event belonging to that project is raised
- **THEN** the external address SHALL be included in the fan-out
- **AND** it SHALL receive the channel it subscribed to

#### Scenario: An external recipient is subscribed elsewhere
- **WHEN** an event belonging to a different project is raised
- **THEN** the external address SHALL NOT be included

#### Scenario: An account has no address for a channel
- **WHEN** a recipient is subscribed to a channel but has no address for it
- **THEN** that recipient SHALL be skipped for that channel
- **AND** the remaining channels SHALL still be delivered

### Requirement: In-app delivery is the always-available fallback

In-app notification SHALL NOT depend on any external endpoint being configured or reachable. When every external channel fails, the recipient SHALL still find the message in the product.

#### Scenario: No external channel is configured
- **WHEN** the instance runs with no endpoint configured
- **THEN** in-app notifications SHALL be created as they are today
- **AND** no delivery SHALL be attempted or reported as an error

#### Scenario: Every external channel fails
- **WHEN** all configured endpoints are failing
- **THEN** the in-app notification SHALL still exist and be marked unread
- **AND** the failures SHALL be recorded against the external deliveries only

### Requirement: Rendering is per channel and isolated

A message SHALL be rendered separately for each channel from a template stored with the endpoint or as a default for its kind. Rendering MUST be restricted to a documented variable set, and a rendering failure MUST affect only that delivery.

#### Scenario: One channel's template is broken
- **WHEN** the template for one channel fails to render for an event
- **THEN** that delivery SHALL be parked with the rendering error
- **AND** the other channels of the same event SHALL still be delivered

#### Scenario: A template references an unknown variable
- **WHEN** a template names a variable the event does not provide
- **THEN** the template SHALL be rejected when it is saved
- **AND** the reason SHALL be shown to the administrator

#### Scenario: An event carries content the template must not interpret
- **WHEN** event content contains markup or template syntax
- **THEN** it SHALL be inserted as data, not evaluated

### Requirement: Outbound calls are confined to configured endpoints

Every outbound request SHALL go to an endpoint an administrator configured. The system SHALL restrict schemes to HTTP and HTTPS, SHALL NOT follow redirects to unconfigured hosts, SHALL apply a timeout, and SHALL NOT treat an endpoint as trusted merely because it is reachable.

#### Scenario: A redirect leaves the configured host
- **WHEN** an endpoint responds with a redirect to another host
- **THEN** the redirect SHALL NOT be followed

#### Scenario: An endpoint points at a link-local address
- **WHEN** an administrator configures an endpoint whose host resolves to a link-local or loopback address that is not explicitly allowed
- **THEN** the endpoint SHALL be rejected when it is saved or when it is used

#### Scenario: An internal certificate authority signs the endpoint
- **WHEN** the endpoint presents a certificate from an internal CA
- **THEN** the administrator SHALL be able to supply the CA bundle for that endpoint
- **AND** certificate verification SHALL remain on by default

### Requirement: Delivery is observable and auditable

Every delivery attempt SHALL leave a record of its recipient, channel, endpoint, status, attempt count, last error and timestamps. The system SHALL expose counters and latency for deliveries per endpoint, and a test send SHALL report the endpoint's response to the administrator.

#### Scenario: An administrator investigates a missing message
- **WHEN** the delivery log is queried for a recipient
- **THEN** every delivery SHALL be listed with its status and last error
- **AND** a parked delivery SHALL be replayable from the same view

#### Scenario: A test send is performed
- **WHEN** an administrator sends a test message to an endpoint
- **THEN** the result SHALL report success or the failure reason
- **AND** it SHALL include the response status and a bounded excerpt of the response body

#### Scenario: Deliveries are monitored
- **WHEN** deliveries succeed or fail
- **THEN** counters SHALL be incremented per endpoint and status
- **AND** the delivery latency SHALL be recorded
