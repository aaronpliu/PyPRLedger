## 1. Events and call sites

- [ ] 1.1 Add `src/services/notification/events.py`: a frozen `NotificationEvent` dataclass (`type`, `key`, `occurred_at`, `payload`, `usernames`, `project_key`, `repository_slug`) and the closed `EventType` list (`review.assigned`, `review.comment_added`, `release.published`, `release_note.mentioned`, `task.assigned`)
- [ ] 1.2 Add `notify(event)` to `NotificationService` as the single entry point; it resolves recipients, writes the in-app rows, and enqueues external deliveries
- [ ] 1.3 Replace the `NotificationCreate(channel="in_app", …)` construction in `src/services/auto_assign_service.py:321-332` with `notify(event)`
- [ ] 1.4 Replace the two constructions in `src/services/multi_reviewer_service.py:848-859` and `:908-919` with `notify(event)`
- [ ] 1.5 Keep the current in-app payload (type, title, message, priority, related id/type) identical, so the existing bell menu and its tests do not change
- [ ] 1.6 Tests: an event creates the same in-app row as before / an unknown event type is rejected at construction / a call site no longer names a channel

## 2. Data model and migration

- [ ] 2.1 `src/models/notification_gateway.py`: `NotificationEndpoint` (`kind`, non-secret config JSON, `config_encrypted`, `timeout_seconds`, `verify_ssl`, `ca_bundle_path`, `proxy_url`, `concurrency`, `qps_limit`, `enabled`, `created_by`, timestamps)
- [ ] 2.2 Same module: `NotificationTemplate` (`event_type`, `channel_kind`, `subject_tpl`, `body_tpl`, `format`, `endpoint_id` nullable for the kind default, `enabled`)
- [ ] 2.3 Same module: `NotificationSubscription` (`recipient_kind`, `recipient`, `scope_type`, `scope_value`, `event_types` JSON, `channels` JSON, `enabled`)
- [ ] 2.4 Same module: `NotificationDelivery` (`event_type`, `event_key`, `recipient`, `channel_kind`, `endpoint_id`, rendered subject/body, `payload` JSON, `status`, `attempts`, `next_attempt_at`, `last_error`, `dedupe_key` unique, timestamps) with the index the worker claims on
- [ ] 2.5 Widen `Notification.channel` from `ENUM('in_app','email','slack')` to `VARCHAR(32)` in `src/models/notification.py:61`, keeping the three existing values valid
- [ ] 2.6 Add `NotificationPreferenceChannel` (per user, per notification type, per channel) and backfill it from the four existing booleans of `NotificationPreference`
- [ ] 2.7 Alembic revision creating the four tables, widening `channel`, and backfilling preferences; verify the downgrade restores the enum for a database that only holds the original three values
- [ ] 2.8 Register the new models in `src/models/__init__.py`
- [ ] 2.9 Tests: the backfill maps `email_enabled=False` to a missing email channel row / the dedupe key is unique / a delivery can be claimed and marked sent

## 3. Endpoints and secrets

- [ ] 3.1 `src/services/notification/crypto.py`: derive a Fernet key from `SECRET_KEY` and expose `encrypt` / `decrypt` / `redact`
- [ ] 3.2 `src/services/notification/endpoints.py`: CRUD, a `mask()` that replaces every secret with a placeholder, and a save that keeps the stored secret when the placeholder comes back
- [ ] 3.3 Validate an endpoint at save time by kind: URL scheme, host allowlist, timeout range, template compile, TLS/CA options
- [ ] 3.4 `validate_host()`: scheme restricted to http/https, resolved addresses rejected when link-local or loopback unless allowlisted, redirect following disabled
- [ ] 3.5 `redact()` applied to every stored `last_error` and to the test-send report
- [ ] 3.6 Tests: a secret never appears in a read response / a placeholder keeps the stored secret / a `javascript:` URL is rejected / a link-local host is rejected / a quoted credential is redacted from an error

## 4. Rendering

- [ ] 4.1 `src/services/notification/rendering.py`: strict variable substitution over the event's declared fields, with no expression evaluation
- [ ] 4.2 Template lookup: endpoint-specific template first, then the kind default; a missing template is a save-time error for the pair `(event_type, channel_kind)`
- [ ] 4.3 Reject a template naming an unknown variable at save time, reporting the variable
- [ ] 4.4 Per-format output: plain text, Markdown (webhook/IM), HTML plus a text alternative (mail)
- [ ] 4.5 Default templates for the five event types in all three formats, seeded by the migration or by a first-run helper
- [ ] 4.6 Tests: unknown variable rejected on save / content containing `{{ }}` is inserted verbatim / a rendering failure marks only that delivery / a Markdown template produces the IM body

## 5. Recipients and subscriptions

- [ ] 5.1 `src/services/notification/recipients.py`: resolve explicit usernames through the account directory, loading them in one query per event rather than one per recipient
- [ ] 5.2 `NotificationContact` (per user, per channel kind, address) so an IM identifier is not forced into `user.email_address`; email falls back to `user.email_address`
- [ ] 5.3 Resolve subscriptions by scope: `global`, `project`, `repository`, `release`, intersecting `event_types` and `channels`
- [ ] 5.4 Skip a recipient that has no address for a channel, without affecting their other channels
- [ ] 5.5 Deduplicate a person who is both an account holder and a subscriber for the same scope
- [ ] 5.6 Tests: explicit usernames resolve / an external subscriber receives a project event / an external subscriber does not receive another project's event / a recipient without an address is skipped only for that channel / a person subscribed twice receives once

## 6. Outbox and delivery worker

- [ ] 6.1 `src/services/notification/outbox.py`: `enqueue()` writing one row per recipient and channel with its `dedupe_key`, tolerating a duplicate key as a no-op
- [ ] 6.2 `claim()` using `SELECT … FOR UPDATE SKIP LOCKED` ordered by `next_attempt_at`, bounded batch, marking `sending` with a lease so a crashed worker's rows recover
- [ ] 6.3 `mark_sent()` / `mark_failed()` with backoff scheduling (30 s, 2 min, 10 min, 1 h, 6 h) and a terminal `dead` state
- [ ] 6.4 Per-endpoint circuit breaker: consecutive failures open it for a cooling window; deliveries are deferred, not attempted
- [ ] 6.5 Per-endpoint concurrency and QPS caps enforced in the worker
- [ ] 6.6 Worker loop in `src/services/notification/worker.py`, started from the lifespan (`src/main.py:169`) behind `NOTIFICATION_WORKER_ENABLED`, with an adaptive idle backoff and a clean shutdown
- [ ] 6.7 Retention pruning of terminal rows older than the retention window, as a lifespan task alongside the existing cleanups
- [ ] 6.8 Metrics in `src/utils/metrics.py`: `delivery_total{endpoint,status}`, `delivery_latency_seconds`, `endpoint_health`
- [ ] 6.9 Tests: a duplicate enqueue creates one row / a claimed row is not claimed twice / a failure schedules the next attempt with backoff / the fourth failure is `dead` with its content preserved / an open breaker defers instead of attempting / a restart recovers a `sending` row past its lease

## 7. Connectors

- [ ] 7.1 `src/services/notification/connectors/base.py`: the protocol (`kind`, `validate`, `render`, `send`) and the registry
- [ ] 7.2 `in_app`: write through `NotificationService` and publish to `SSEBroker` so the bell menu still updates in realtime
- [ ] 7.3 `webhook`: `httpx` POST, per-endpoint headers, body from the template, optional signing strategy (`none`, `header-token`, `hmac-sha256-timestamp`), no redirect following, response excerpt bounded
- [ ] 7.4 `smtp`: `aiosmtplib` with STARTTLS / SSL / plain as configured, HTML plus text alternative, `From` from `EMAIL_FROM` + `EMAIL_FROM_NAME`, per-endpoint timeout
- [ ] 7.5 Register the three connectors and resolve them by `kind`, so an unknown kind fails validation at save time
- [ ] 7.6 Tests: a webhook posts the rendered body to the configured URL / signing produces the documented header / a non-2xx response fails the delivery with the status in the error / SMTP failure with an unreachable host fails fast within the timeout / in-app still writes when every external connector raises

## 8. API and admin UI

- [ ] 8.1 Schemas in `src/schemas/notification_gateway.py`; every secret field is write-only and masked on read
- [ ] 8.2 Endpoints in `src/api/v1/endpoints/notification_admin.py` mounted under `/rbac/settings/notifications`: endpoint CRUD, template CRUD, subscription CRUD, delivery log query, replay, test send — all behind `manage settings`
- [ ] 8.3 Replay: reset a `dead` delivery to `pending` with a fresh retry budget, keeping its history
- [ ] 8.4 Test send: render a sample event for the endpoint and return status, latency and a bounded response excerpt
- [ ] 8.5 Delivery log filters: recipient, status, endpoint, event type, time range, with paging
- [ ] 8.6 Frontend types in `frontend/src/api/notifications.ts` (endpoints, templates, subscriptions, deliveries)
- [ ] 8.7 `views/admin/SystemSettingsView.vue`: a notifications section — endpoint list and editor, template editor with variable hints, subscription list, delivery log with replay, test-send button
- [ ] 8.8 Warn in the UI when the deployment still uses the documented default `SECRET_KEY`, since endpoint secrets depend on it
- [ ] 8.9 `views/notifications/NotificationPreferenceView.vue`: render the per-channel matrix from the configured channels instead of four fixed switches
- [ ] 8.10 Locale strings in `en`, `zh-CN`, `zh-TW`
- [ ] 8.11 Tests: an endpoint save sends the secret only once / the list never renders a secret / a disabled endpoint is not offered as a channel / replay resets a dead delivery / the preference page shows the configured channels

## 9. Configuration and documentation

- [ ] 9.1 Add `SMTP_USE_TLS` and `SMTP_USE_SSL` to `Settings` (`src/core/config.py:392`) — they exist in `.env.example:177` and are currently dropped by `extra="ignore"`
- [ ] 9.2 Add `NOTIFICATION_WORKER_ENABLED`, `NOTIFICATION_WORKER_BATCH_SIZE`, `NOTIFICATION_WORKER_INTERVAL_SECONDS`, `NOTIFICATION_DELIVERY_MAX_ATTEMPTS` with defaults that behave like today when the feature is unused
- [ ] 9.3 Fix `docs/NOTIFICATION_EMAIL_CONFIGURATION.md`: remove the claim that Email/Slack are "Ready", state what is actually required to enable them now, and point at the endpoint registry instead of editing `.env`
- [ ] 9.4 Write `docs/NOTIFICATION_GATEWAY.md`: the event → outbox → connector flow, how to register an intranet IM endpoint, the signing strategies, the SSRF/CA/proxy rules, and how to read the delivery log
- [ ] 9.5 Update `.env.example` to match `Settings` exactly, with a comment that runtime channel configuration lives in the admin page
- [ ] 9.6 Add the new tables and the worker to `docs/PROJECT_STRUCTURE.md`

## 10. Verification

- [ ] 10.1 Backend: full `pytest`, `ruff format --check` and `ruff check src tests`
- [ ] 10.2 Frontend: `vitest` suite and `vue-tsc --noEmit`
- [ ] 10.3 Manual: with no endpoint configured, assigning a reviewer behaves exactly as before (in-app only, no errors in the log)
- [ ] 10.4 Manual: register a local webhook receiver, assign a reviewer, and confirm a delivery arrives, is logged, and is not duplicated on a forced retry
- [ ] 10.5 Manual: point an endpoint at an unreachable host, confirm the request still returns promptly, the delivery is retried with growing delays, and the admin page shows the failure
- [ ] 10.6 Manual: restart the container with pending deliveries and confirm they are delivered after startup
- [ ] 10.7 Manual: subscribe an external address to a project, publish a release, and confirm only that project's event reaches it
