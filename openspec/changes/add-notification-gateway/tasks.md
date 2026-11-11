# Notification gateway — task plan

> Status: 2026-11-08 — three decisions settled: 1.5 (keep the polling bell menu, no SSE publish), 5.5 (seed templates for the two live event types only), 9.8 (extract `NotificationSettingsCard.vue`). `proposal.md` / `design.md` were corrected accordingly (10.7). No `DECISION` items remain; all other tasks are unchecked and no implementation code has started.
> Scope of this revision: the task list plus proposal/design wording fixes. Items marked `TREE`
> record a fact verified against the current codebase that changes the task.
>
> TREE notes reflect the tree at 2026-11-08. Key files: `src/services/notification_service.py:35-79`,
> `src/models/notification.py:61`, `src/core/config.py:385-401`, `src/main.py:147-201`,
> `src/services/sse_broker.py:19,89-188,253-267`, `tests/conftest.py:21,319-335`,
> `frontend/src/components/common/NotificationBell.vue:85,92-114`.

## Delivery stages

| Stage | Groups | Outcome | Gate before the next stage |
|---|---|---|---|
| 0 | 1 | Everything the later groups assume exists | Deps install, a channel outside the enum passes a schema/type round trip, router is reachable, test strategy for MySQL-only SQL is agreed |
| 1 | 2, 3 | Business code raises events; schema and migration are in place | Assigning a reviewer still produces exactly the old in-app row; `alembic upgrade`/`downgrade` on a three-value DB both succeed |
| 2 | 4, 5, 6 | Safe endpoint config, templates and recipient resolution, all unit-testable without a network | No secret in any read response; unknown template variable rejected at save; subscription scope isolation passes |
| 3 | 7, 8 | Outbox, worker and connectors deliver without touching the request path | Duplicate enqueue is one row; restart recovers a leased row; unreachable host does not slow an assignment |
| 4 | 9, 10 | Admin API/UI, preferences, config and docs | No-endpoint deployment behaves like today; admin page never renders a secret |
| 5 | 11 | Full automated and manual verification | All checks in group 11 pass |

Groups within a stage can proceed in parallel where they do not read each other's tables.

---

## Stage 0

### 1. Preconditions (new — none of these were in the original list)

- [ ] 1.1 Add `aiosmtplib` and a direct `cryptography` dependency to `pyproject.toml`; `httpx>=0.28.1` is already present at `pyproject.toml:45`, and `cryptography` currently arrives only indirectly through `python-jose[cryptography]` (`:52`) — Fernet must not rely on a transitive dependency
- [ ] 1.2 Audit and widen every runtime `channel` constraint in one change: the regex in `src/schemas/notification.py:21-25` and the union in `frontend/src/api/notifications.ts:13`. TREE: `alembic/versions/018_create_notification_tables.py:53` created the enum; leave that historical migration untouched and let the new revision widen it — add a comment in `018` pointing at the new revision. The preference page's fixed labels are handled in 9.10
- [ ] 1.3 Define the `EventType → notification.type` mapping table and the compatibility rule: the dotted name is internal to the gateway, the stored in-app row keeps the existing underscore `type` and the exact existing payload. TREE: the live call sites write `review_assigned` (`auto_assign_service.py:323`, `multi_reviewer_service.py:850`) and `review_completed` (`multi_reviewer_service.py:910`), so the mapping must include `review.assigned → review_assigned` **and `review.completed → review_completed`**; the latter has no dotted counterpart in the original event list. This resolves the conflict between original 1.1 and 1.5
- [ ] 1.4 Register the new admin router in `src/api/v1/api.py:4-25,31-83`; the existing `rbac.py` router already carries `prefix="/rbac"`, so the new module's paths must not repeat it
- [x] 1.5 In-app transport decision (settled 2026-11-08): keep the existing polling bell menu; no SSE publish in this change. TREE: `SSEBroker` has no `publish` method, subscribes only to `reviews:created`, and `_fan_out` hardcodes `event: review_created`; the bell menu polls (`NotificationBell.vue:85,92-114`). If realtime is wanted later, open a separate change to extend `SSEBroker` with a generic publish/event name and a bell listener
- [ ] 1.6 Establish the test strategy for MySQL-only behaviour before writing those tests: TREE: `tests/conftest.py:21,319-335` uses in-memory SQLite with `create_all` (no `FOR UPDATE SKIP LOCKED`, no Alembic). Decide between a MySQL-marked fixture, a documented MySQL-only test job, or a claim abstraction with a SQLite-compatible fake; document the choice in `tests/README.md`
- [ ] 1.7 Decide the naming of the admin "test send" action: TREE: `POST /notifications/test` already exists (`src/api/v1/endpoints/notifications.py:401-410`) and creates an in-app notification. Keep that endpoint's contract and name the new endpoint-level action distinctly (e.g. `POST /rbac/settings/notifications/endpoints/{id}/test-send`) to avoid two "test" endpoints with different meanings
- [ ] 1.8 Record the four existing `NOTIFICATION_*` settings (`config.py:385-389`) as the namespace to extend, and confirm the default `SECRET_KEY` warning source (`config.py:188`)

## Stage 1

### 2. Events and call sites

- [ ] 2.1 Add `src/services/notification/events.py`: a frozen `NotificationEvent` dataclass (`type`, `key`, `occurred_at`, `payload`, `usernames`, `project_key`, `repository_slug`), the closed `EventType` list (`review.assigned`, `review.completed`, `review.comment_added`, `release.published`, `release_note.mentioned`, `task.assigned`), and the mapping table from 1.3. TREE: `review.completed` is new here but required by the existing `multi_reviewer_service.py:910` call site; the last four types have no producer today and are declared for subscription/template authoring only, not for live events
- [ ] 2.2 Add `notify(event)` to `NotificationService` as the single entry point; it resolves recipients, writes the in-app rows, and enqueues external deliveries
- [ ] 2.3 Replace the `NotificationCreate(channel="in_app", …)` construction in `src/services/auto_assign_service.py:321-332` with `notify(event)`
- [ ] 2.4 Replace the two constructions in `src/services/multi_reviewer_service.py:848-859` (`review_assigned`) and `:908-919` (`review_completed`) with `notify(event)`, using two distinct event types per 1.3
- [ ] 2.5 Migrate the fourth call site, `POST /notifications/test` (`src/api/v1/endpoints/notifications.py:401-410`), or explicitly document why it stays a direct in-app writer; it was missing from the original list
- [ ] 2.6 Keep the current in-app payload (type, title, message, priority, related id/type) byte-for-byte identical via the 1.3 mapping, so the existing bell menu and its tests do not change
- [ ] 2.7 Tests: an event creates the same in-app row as before / an unknown event type is rejected at construction / all four call sites no longer name a channel / the dotted event type maps to the stored underscore type

### 3. Data model and migration

- [ ] 3.1 `src/models/notification_gateway.py`: `NotificationEndpoint` (`kind`, non-secret config JSON, `config_encrypted`, `timeout_seconds`, `verify_ssl`, `ca_bundle_path`, `proxy_url`, `concurrency`, `qps_limit`, `enabled`, `created_by`, timestamps)
- [ ] 3.2 Same module: `NotificationTemplate` (`event_type`, `channel_kind`, `subject_tpl`, `body_tpl`, `format`, `endpoint_id` nullable for the kind default, `enabled`)
- [ ] 3.3 Same module: `NotificationSubscription` (`recipient_kind`, `recipient`, `scope_type`, `scope_value`, `event_types` JSON, `channels` JSON, `enabled`)
- [ ] 3.4 Same module: `NotificationDelivery` (`event_type`, `event_key`, `recipient`, `channel_kind`, `endpoint_id`, rendered subject/body, `payload` JSON, `status`, `attempts`, `next_attempt_at`, `last_error`, `dedupe_key` unique, timestamps) with the index the worker claims on
- [ ] 3.5 Widen `Notification.channel` from `ENUM('in_app','email','slack')` to `VARCHAR(32)` in `src/models/notification.py:61`, keeping the three existing values valid
- [ ] 3.6 Add `NotificationPreferenceChannel` (per user, per notification type, per channel) and backfill it from the four existing booleans of `NotificationPreference`
- [ ] 3.7 Add `NotificationContact` (per user, per channel kind, address) — moved here from the recipients group because it is a table/model task; an IM identifier must not be forced into `user.email_address`
- [ ] 3.8 One Alembic revision (`040`, down_revision `039`) creating all new tables, widening `channel` and backfilling preferences; TREE: no enum→varchar precedent exists and `018` notes MySQL cannot `DROP TYPE`, so the downgrade must first assert the column holds only the original three values and otherwise refuse with a clear error rather than silently corrupting data
- [ ] 3.9 Register the new models in `src/models/__init__.py:10,43-44`; `tests/conftest.py:323` builds tables from `Base.metadata`, so an unregistered model breaks every backend test
- [ ] 3.10 Tests: the backfill maps `email_enabled=False` to a missing email channel row / the dedupe key is unique / a delivery can be claimed and marked sent / the backfill is idempotent when the revision is re-run. TREE: these need the migration-test strategy from 1.6, not `create_all`

## Stage 2

### 4. Endpoints and secrets

- [ ] 4.1 `src/services/notification/crypto.py`: derive a Fernet key from `SECRET_KEY` and expose `encrypt` / `decrypt` / `redact`
- [ ] 4.2 `src/services/notification/endpoints.py`: CRUD, a `mask()` that replaces every secret with a placeholder, and a save that keeps the stored secret when the placeholder comes back
- [ ] 4.3 Validate an endpoint at save time by kind: URL scheme, host allowlist, timeout range, template compile, TLS/CA options
- [ ] 4.4 `validate_host()`: scheme restricted to http/https, resolved addresses rejected when link-local or loopback unless allowlisted, redirect following disabled
- [ ] 4.5 `redact()` applied to every stored `last_error` and to the test-send report
- [ ] 4.6 Tests: a secret never appears in a read response / a placeholder keeps the stored secret / a `javascript:` URL is rejected / a link-local host is rejected / a quoted credential is redacted from an error

### 5. Rendering

- [ ] 5.1 `src/services/notification/rendering.py`: strict variable substitution over the event's declared fields, with no expression evaluation
- [ ] 5.2 Template lookup: endpoint-specific template first, then the kind default; a missing template is a save-time error for the pair `(event_type, channel_kind)`
- [ ] 5.3 Reject a template naming an unknown variable at save time, reporting the variable
- [ ] 5.4 Per-format output: plain text, Markdown (webhook/IM), HTML plus a text alternative (mail)
- [ ] 5.5 Seed default templates in all three formats for the **two event types that have live call sites**: `review.assigned` and `review.completed` (migration or a first-run helper). DECISION (settled 2026-11-08): the other four declared types get no seeded templates — a template for an event nothing raises would be untestable dead data. TREE: only `review_assigned` / `review_completed` are produced today (`auto_assign_service.py:323`, `multi_reviewer_service.py:850,910`); `review.comment_added`, `release.*` and `task.assigned` have no producer. Adding producers for those types is a separate change, not a task here; 5.2's save-time check must still accept a hand-authored template for a declared type with no seed
- [ ] 5.6 Tests: unknown variable rejected on save / content containing `{{ }}` is inserted verbatim / a rendering failure marks only that delivery / a Markdown template produces the IM body

### 6. Recipients and subscriptions

- [ ] 6.1 `src/services/notification/recipients.py`: resolve explicit usernames through the account directory, loading them in one query per event rather than one per recipient. TREE: there is no directory service; query `User` by `username` directly (`src/models/user.py:39`)
- [ ] 6.2 Use `NotificationContact` (3.7) for addresses; email falls back to `user.email_address`
- [ ] 6.3 Resolve subscriptions by scope: `global`, `project`, `repository`, `release`, intersecting `event_types` and `channels`
- [ ] 6.4 Skip a recipient that has no address for a channel, without affecting their other channels
- [ ] 6.5 Deduplicate a person who is both an account holder and a subscriber for the same scope
- [ ] 6.6 Tests: explicit usernames resolve / an external subscriber receives a project event / an external subscriber does not receive another project's event / a recipient without an address is skipped only for that channel / a person subscribed twice receives once

## Stage 3

### 7. Outbox and delivery worker

- [ ] 7.1 `src/services/notification/outbox.py`: `enqueue()` writing one row per recipient and channel with its `dedupe_key`, tolerating a duplicate key as a no-op
- [ ] 7.2 `claim()` using `SELECT … FOR UPDATE SKIP LOCKED` ordered by `next_attempt_at`, bounded batch, marking `sending` with a lease so a crashed worker's rows recover. TREE: no `with_for_update` precedent exists in `src/`; the project uses `AsyncSession` + `select()`, and 1.6 decides how this is tested
- [ ] 7.3 `mark_sent()` / `mark_failed()` with backoff scheduling (30 s, 2 min, 10 min, 1 h, 6 h) and a terminal `dead` state
- [ ] 7.4 Per-endpoint circuit breaker: consecutive failures open it for a cooling window; deliveries are deferred, not attempted
- [ ] 7.5 Per-endpoint concurrency and QPS caps enforced in the worker
- [ ] 7.6 Worker loop in `src/services/notification/worker.py`, started from the lifespan (`src/main.py:169`) behind `NOTIFICATION_WORKER_ENABLED`, with an adaptive idle backoff and a clean shutdown following the existing `background_tasks` cancel/gather pattern (`main.py:188-193`)
- [ ] 7.7 Wire retention pruning as its own lifespan task. TREE: `NotificationService.cleanup_expired_notifications` (`notification_service.py:377-391`) exists but is never called; `main.py:167-177` currently starts only delegation/PAT/metrics tasks — do not describe this as "alongside the existing cleanups" without adding the call
- [ ] 7.8 Metrics in `src/utils/metrics.py`: `delivery_total{endpoint,status}`, `delivery_latency_seconds`, `endpoint_health`. TREE: `MetricsCollector` uses the global `REGISTRY` (`metrics.py:20-31`); register the new collectors in `_init_metrics` so a second instantiation does not raise a duplicate-registration error
- [ ] 7.9 Tests: a duplicate enqueue creates one row / a claimed row is not claimed twice / a failure schedules the next attempt with backoff / the fourth failure is `dead` with its content preserved / an open breaker defers instead of attempting / a restart recovers a `sending` row past its lease

### 8. Connectors

- [ ] 8.1 `src/services/notification/connectors/base.py`: the protocol (`kind`, `validate`, `render`, `send`) and the registry
- [ ] 8.2 `in_app`: write through `NotificationService` and keep the existing bell-menu transport working. TREE: there is no `SSEBroker.publish` and the bell polls; per the settled 1.5 decision, no SSE work is required
- [ ] 8.3 `webhook`: `httpx` POST, per-endpoint headers, body from the template, optional signing strategy (`none`, `header-token`, `hmac-sha256-timestamp`), no redirect following, response excerpt bounded
- [ ] 8.4 `smtp`: `aiosmtplib` with STARTTLS / SSL / plain as configured (see 10.1), HTML plus text alternative, `From` from `EMAIL_FROM` + `EMAIL_FROM_NAME`, per-endpoint timeout
- [ ] 8.5 Register the three connectors and resolve them by `kind`, so an unknown kind fails validation at save time
- [ ] 8.6 Tests: a webhook posts the rendered body to the configured URL / signing produces the documented header / a non-2xx response fails the delivery with the status in the error / SMTP failure with an unreachable host fails fast within the timeout / in-app still writes when every external connector raises

## Stage 4

### 9. API and admin UI

- [ ] 9.1 Schemas in `src/schemas/notification_gateway.py`; every secret field is write-only and masked on read
- [ ] 9.2 Endpoints in `src/api/v1/endpoints/notification_admin.py` mounted under `/rbac/settings/notifications`: endpoint CRUD, template CRUD, subscription CRUD, delivery log query, replay, test send — all behind `manage settings`, registered per 1.4
- [ ] 9.3 Define the read endpoint that returns the configured/enabled channels. TREE: the preference-page task (9.10) depends on this but no earlier task defined it; `smtpConfigured` / `slackConfigured` are currently hardcoded `false` (`NotificationPreferenceView.vue:130-137`)
- [ ] 9.4 Replay: reset a `dead` delivery to `pending` with a fresh retry budget, keeping its history
- [ ] 9.5 Test send: use the distinct path from 1.7, render a sample event for the endpoint, and return status, latency and a bounded redacted response excerpt
- [ ] 9.6 Delivery log filters: recipient, status, endpoint, event type, time range, with paging
- [ ] 9.7 Extend the existing `frontend/src/api/notifications.ts` (135 lines, 9 methods) with endpoint/template/subscription/delivery types and methods — the file already exists, this is not a new file
- [ ] 9.8 Build the notifications admin UI as a standalone component `frontend/src/components/notification/NotificationSettingsCard.vue` (endpoint list + editor, template editor with variable hints, subscription list, delivery log with replay, test-send button) and mount it as one section in `views/admin/SystemSettingsView.vue`. DECISION (settled 2026-11-08): extract rather than inline. TREE: `SystemSettingsView.vue` is already 1885 lines over 5 sections, and the project already splits domain UI into `components/delegation/DelegationForm.vue` / `components/review/CommentTemplateManagement.vue`; a 400–800 line inline section would make both the view and its 24 KB test file unmanageable. Keep the `el-card` wrapper in `SystemSettingsView.vue` so the new section matches the other five
- [ ] 9.9 Warn in the UI when the deployment still uses the documented default `SECRET_KEY` (`config.py:188`), since endpoint secrets depend on it
- [ ] 9.10 Extend the existing `views/notifications/NotificationPreferenceView.vue` (263 lines) to render the per-channel matrix from 9.3 instead of three fixed switches; replace the hardcoded `smtpConfigured` / `slackConfigured` flags (`:130-137`) and the fixed type-label map (`:171-188`). TREE: that map names `review_assigned`, `review_completed`, `delegation_expiry`, `system_alert`, but the last two have no producing code anywhere in `src/` — keep them as legacy in-app labels, do not promote them into the gateway event list
- [ ] 9.11 Locale strings in `en`, `zh-CN`, `zh-TW`. TREE: the `notifications` namespace starts around line 970 in all three files; the dynamic channel names need a different key strategy than the static `channel_in_app` / `channel_email` / `channel_slack` keys
- [ ] 9.12 Tests: an endpoint save sends the secret only once / the list never renders a secret / a disabled endpoint is not offered as a channel / replay resets a dead delivery / the preference page shows the configured channels. TREE: create `frontend/tests/components/NotificationSettingsCard.test.ts` (per the 9.8 extraction) and `frontend/tests/views/NotificationPreferenceView.test.ts` (no such test exists today); add only a mount assertion for the new card in `frontend/tests/views/SystemSettingsView.test.ts`

### 10. Configuration and documentation

- [ ] 10.1 Add `SMTP_USE_TLS` and `SMTP_USE_SSL` to `Settings` (`src/core/config.py:392`) — they exist in `.env.example:177-178` and are currently dropped by `extra="ignore"` (`config.py:10-12`)
- [ ] 10.2 Add `NOTIFICATION_WORKER_ENABLED`, `NOTIFICATION_WORKER_BATCH_SIZE`, `NOTIFICATION_WORKER_INTERVAL_SECONDS`, `NOTIFICATION_DELIVERY_MAX_ATTEMPTS` next to the four existing `NOTIFICATION_*` settings (`config.py:385-389`), with defaults that behave like today when the feature is unused
- [ ] 10.3 Fix `docs/NOTIFICATION_EMAIL_CONFIGURATION.md`: remove the "⏳ Ready" claim (`:208-209`), state what is actually required to enable delivery now, point at the endpoint registry instead of editing `.env`, and repair the sample code that imports the missing `aiosmtplib` (`:156`) and reads the non-existent `settings.SMTP_USE_TLS` (`:177`) — the doc also still says only in-app is sent (`:217,220`)
- [ ] 10.4 Write `docs/NOTIFICATION_GATEWAY.md`: the event → outbox → connector flow, how to register an intranet IM endpoint, the signing strategies, the SSRF/CA/proxy rules, and how to read the delivery log
- [ ] 10.5 Update `.env.example` to match `Settings` exactly, with a comment that runtime channel configuration lives in the admin page. TREE: apart from the two TLS keys it is already close (`:163-166,170-184`)
- [ ] 10.6 Add the new tables **and the existing notification tables/service** to `docs/PROJECT_STRUCTURE.md`. TREE: that document currently mentions no notification component at all
- [x] 10.7 Update `proposal.md` / `design.md` where they still claim `in_app` publishes to `SSEBroker` (design D3/Context, proposal What Changes). Done 2026-11-08: both now state that the bell menu polls and that realtime push is out of scope. Documentation only — no implementation

## Stage 5

### 11. Verification

- [ ] 11.1 Backend: full `pytest`, `ruff format --check` and `ruff check src tests`
- [ ] 11.2 Frontend: `vitest` suite and `vue-tsc --noEmit`
- [ ] 11.3 Migration: `alembic upgrade head` and `downgrade` against a seeded database holding only the original three channel values
- [ ] 11.4 Manual: with no endpoint configured, assigning a reviewer behaves exactly as before (in-app only, no errors in the log)
- [ ] 11.5 Manual: register a local webhook receiver, assign a reviewer, and confirm a delivery arrives, is logged, and is not duplicated on a forced retry
- [ ] 11.6 Manual: point an endpoint at an unreachable host, confirm the request still returns promptly, the delivery is retried with growing delays, and the admin page shows the failure
- [ ] 11.7 Manual: restart the container with pending deliveries and confirm they are delivered after startup
- [ ] 11.8 Manual: subscribe an external address to a project, publish a release, and confirm only that project's event reaches it
