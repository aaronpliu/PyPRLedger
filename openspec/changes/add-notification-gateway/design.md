## Context

The product already tells people things — a reviewer is assigned, a review is added — but only inside the application. `NotificationService.create_notification()` (`src/services/notification_service.py:35`) writes a row and returns; the bell menu polls the notification API for it (`frontend/src/components/common/NotificationBell.vue:85,92-114`). Nothing leaves the process.

What exists today, and what it implies:

| Primitive | State | Implication for this change |
|---|---|---|
| `Notification` model | `channel` is `ENUM('in_app','email','slack')` (`src/models/notification.py:61`) | The schema enumerates products. A fourth channel is a migration; it has to become a string. |
| `NotificationPreference` | three fixed booleans (`channel_enabled`, `email_enabled`, `in_app_enabled`, `slack_enabled`) | Cannot describe an arbitrary channel set; needs a per-channel dimension. |
| Business call sites | `auto_assign_service.py:321-332`, `multi_reviewer_service.py:848-859` and `:908-919`, all hardcoding `channel="in_app"` | Channel choice has leaked into domain code. Three call sites in two services — cheap to converge now. |
| SMTP / Slack settings | `src/core/config.py:392-401`, consumed by nothing; `SMTP_USE_TLS`/`SMTP_USE_SSL` are in `.env.example:177` but not in `Settings` | Delivery is greenfield, not a refactor; the config surface is partly fictional. |
| `SystemSetting` + RBAC | `src/models/system_setting.py`, `rbac_service.get_setting/update_setting`, `manage settings` permission, `/rbac/settings/*` endpoints, admin page `SystemSettingsView.vue` | The runtime-configuration mechanism, the permission and the admin UI pattern all exist. An endpoint registry belongs here, not in `.env`. |
| LLM integration | `load_llm_config()` reads `SystemSetting` rows over environment defaults | Precedent for "DB overrides env, edited in the admin page". |
| Confluence client | env credentials + `*_SYNC_ENABLED` gate + `VERIFY_SSL` + timeout (`config.py:317-363`) | Precedent for an outbound third-party client that must never break the primary flow. |
| Bell menu / `SSEBroker` | The bell polls the notification API (`frontend/src/components/common/NotificationBell.vue:85,92-114`). `SSEBroker` (`src/services/sse_broker.py`) is a Redis pubsub fan-out for the single `reviews:created` channel, hardcodes `event: review_created`, and exposes **no generic publish method** | In-app already has a working transport (polling); `in_app` only needs to keep writing `notification`. Realtime push is out of scope — it would require extending `SSEBroker` with a generic publish/event name and a bell listener (see tasks 1.5 / 8.2). |
| Deployment | single `api` container, MySQL 8 + Redis, no broker, background work is `asyncio.create_task` in `src/main.py:169-175`; `./src` is bind-mounted so restarts are routine | In-process scheduling is the house style, but any queue **must be durable** and restart-safe. |
| Metrics | `MetricsCollector` used by services | Per-endpoint counters and latency fit the existing collector. |

The constraint that shapes the whole design: **the instance lives on an intranet and often cannot reach public services.** The users' mail goes through an internal relay; their chat is an internal or self-hosted product. So the deliverable cannot be "Slack support" — it has to be "any HTTP or SMTP endpoint an operator points us at", configurable without a rebuild.

## Goals / Non-Goals

**Goals:**

- A notification raised by business code reaches an external recipient over a channel that an administrator configured, without the raising request depending on that channel.
- Adding an HTTP-based channel (internal IM gateway, vendor webhook, relay) requires filling a form, not shipping code.
- Delivery survives restarts, is retried, is never duplicated to a recipient, and is auditable and replayable.
- People without an account can subscribe to the events of their project.
- Nothing about the existing in-app behaviour gets worse when nothing is configured.

**Non-Goals:**

- Inbound messaging (IM callbacks, bot commands, replies threaded back into the product).
- Rich interactive payloads per vendor (buttons, cards, actions); `webhook` sends a rendered body, and a vendor needing more gets a connector.
- Replacing `NotificationService` or the existing notification API contract.
- Delivery-time fan-out to arbitrary user groups (distribution lists come later, via subscriptions).
- Guaranteeing exactly-once at the transport level; the guarantee is "no duplicate message per recipient, event and channel", enforced by identity.

## Decisions

### D1 - `notify(event)` is the only entry point

A dataclass event carries `type`, `occurred_at`, a stable `key` (what the event is about — PR id, release id), the payload, and the audience hints (`usernames`, `project_key`, `repository_slug`). Business code calls `notify(event)` and stops there.

The business call sites drop their `NotificationCreate(channel="in_app", …)` construction. The closed `EventType` list is `review.assigned`, `review.completed`, `review.comment_added`, `release.published`, `release_note.mentioned`, `task.assigned`, so a typo becomes a validation error rather than a message nobody renders.

TREE (2026-11-08): the three live call sites write `type="review_assigned"` (`auto_assign_service.py:323`, `multi_reviewer_service.py:850`) and `type="review_completed"` (`multi_reviewer_service.py:910`). `review.completed` was missing from the original candidate list and is required for parity. The other four declared types have **no producer today**; they exist so subscriptions and templates can be authored ahead of their call sites, but they raise no events until a producer is added in a later change. Default templates are seeded for the two live types only (see tasks 5.5). The preference page's `delegation_expiry` / `system_alert` labels (`NotificationPreferenceView.vue:171-176`) have no producing code in `src/` and stay out of the gateway's event list.

### D2 - Durable outbox + in-process worker, not an in-memory queue

The queue is a table (`notification_delivery`), not an `asyncio.Queue`:

- restarts are routine here (bind-mounted source), and an in-memory queue silently drops whatever was pending;
- a second replica must not double-send, which `SELECT … FOR UPDATE SKIP LOCKED` (MySQL 8) gives for free;
- the table *is* the audit log and the replay surface — the same rows an administrator inspects are the ones the worker consumes.

The worker is one more `asyncio.create_task` in the lifespan, next to the cleanup tasks already there, gated by `NOTIFICATION_WORKER_ENABLED` so a deployment can run it in a dedicated process later without code changes. It polls in small batches, ordered by `next_attempt_at`, with a per-endpoint concurrency cap so one dead host cannot occupy every slot.

**Alternative rejected:** sending inside the request with `BackgroundTasks`. It dies with the process, has no retry, and cannot be inspected.

### D3 - The connector registry is keyed by protocol, not by product

```
Connector (protocol)
  kind: str
  validate(config) -> None            # at save time, so a bad endpoint never queues work
  render(template, event) -> Message  # subject + body, per kind
  send(endpoint, message) -> Result   # raises on failure, returns provider reference
```

Three connectors cover the requirement:

| kind | Covers | Notes |
|---|---|---|
| `in_app` | the existing bell menu | writes `notification`; the bell menu keeps polling. No `SSEBroker` publish — it has no generic publish method (see tasks 1.5 / 8.2) |
| `webhook` | any internal IM gateway, vendor webhook, relay that accepts an HTTP POST | URL + method + headers + body template + optional signing secret; the universal escape hatch |
| `smtp` | internal mail relay, public SMTP, SES | `aiosmtplib`, TLS/SSL/STARTTLS as configured |

DingTalk, WeCom, Feishu, Matrix, Mattermost are all `webhook` from our side. Their differences (a signed timestamp, a token in the query string, a token in the body) are **endpoint data** — a signing strategy field plus a body template — not Python modules. A vendor that truly needs a protocol we do not speak (e.g. a proprietary SDK with its own crypto) gets one connector file; the dispatcher, queue and UI do not change.

### D4 - Endpoints and secrets live in the database, encrypted

`notification_endpoint` holds `kind`, non-secret config (URL, headers, TLS options, timeout, proxy, QPS), and `config_encrypted` for secrets. Encryption uses a key derived from `SECRET_KEY` (Fernet), so the existing deployment already has the material and no new secret has to be distributed to run the feature.

Why not environment variables, which is how Confluence and JIRA are configured today:

- changing them requires touching `.env` and restarting the container — through a bind-mounted restart, with the whole team's sessions in flight;
- an intranet may need **several** endpoints at once (relay + two IM gateways + a per-project bot), which a flat env namespace models badly;
- secrets in env leak into `docker inspect`, logs and support bundles; the API can only ever return a placeholder for a DB column.

The API never returns a decrypted secret: reads return the placeholder, and a save that sends the placeholder back keeps the stored value (so editing a URL does not require re-typing the password).

### D5 - Templates are data with a closed variable set

A template is `(event_type, channel_kind) → subject, body, format`. Rendering is a strict substitution over a whitelist derived from the event schema — no expression evaluation, no attribute traversal beyond the declared fields. A template naming an unknown variable is rejected **when saved**, so a broken template is an edit-time error rather than a runtime surprise at 2 a.m.

Default templates ship for the two event types with live call sites (`review.assigned`, `review.completed`). The four declared-but-unproduced types (`review.comment_added`, `release.published`, `release_note.mentioned`, `task.assigned`) accept hand-authored templates but get no seed: a template for an event nothing raises cannot be exercised. Producers for those types belong to a later change; the save-time validation in D5 must not reject an administrator-authored template merely because no seed exists for that pair.

Rendering happens per delivery, and a rendering failure parks that one row. It never fails the fan-out, and it never rolls back the in-app row.

### D6 - Recipients: accounts and subscribers

Resolution order:

1. explicit `usernames` on the event → account directory (`user.email_address`, plus a per-user contact table for IM identifiers);
2. subscriptions matching the event's scope (`project`, `repository`, `release` or `global`), including external recipients with no account.

A recipient with no address for a channel is skipped for that channel only. A subscription carries `event_types` and `channels`, so an external product owner can receive `release.published` by mail without ever hearing about review comments.

**Alternative rejected:** requiring an account for everyone. The people who most need a release notification are frequently outside the review loop, and creating accounts for them inflates the RBAC surface for no benefit.

### D7 - Delivery semantics

- **Identity**: `dedupe_key = hash(event_type, event_key, recipient, channel_kind, endpoint_id)`, unique index. A retry, a replay, or a duplicate event collapses onto the same row.
- **Retry**: exponential backoff (30 s, 2 min, 10 min, 1 h, 6 h), bounded attempts, then `dead` with the rendered content preserved.
- **Circuit breaker**: consecutive failures per endpoint open it for a cooling window; deliveries are deferred, not attempted, so a dead relay does not cost one timeout per message.
- **Rate limiting**: per-endpoint QPS and per-recipient daily cap, reusing `NOTIFICATION_MAX_PER_DAY` semantics.
- **Ordering**: not guaranteed. Events carry timestamps; a digest is the mechanism for order-sensitive summaries, not the transport.

### D8 - Intranet safety

| Concern | Decision |
|---|---|
| Egress through a corporate proxy | per-endpoint `proxy_url`, honoured by `httpx`; `NO_PROXY` respected |
| Internal CA | per-endpoint `ca_bundle_path`; `verify_ssl` defaults to **on**, off is an explicit, labelled choice (same shape as `CONFLUENCE_SERVER_VERIFY_SSL`) |
| SSRF | scheme restricted to http/https, redirects not followed, host must be an administrator-configured one; resolved addresses that are link-local/loopback are refused unless the deployment explicitly allows them |
| Secret leakage | encrypted at rest, redacted from errors (the providers quote keys back), placeholder on read |
| Prompt injection through content | templates substitute data; event content is never evaluated |
| Unbounded response bodies | response excerpt bounded to a fixed length for the test-send report and the stored error |

### D9 - `in_app` stays the floor

`in_app` is written **before** external fan-out and does not depend on any endpoint. If every external delivery fails, the recipient still sees the message in the product, and the failures are recorded only against the external rows. This keeps the feature deployable into an instance with zero endpoints configured — today's behaviour, unchanged.

### D10 - `channel` becomes a string, preferences become a matrix

`notification.channel` moves from `ENUM('in_app','email','slack')` to `VARCHAR(32)` (data-preserving: the three existing values remain valid). `notification_preference` gains a per-channel table (`notification_preference_channel`) rather than growing a column per vendor — otherwise each new channel is still a migration, which is the problem being solved.

The user-facing preference page renders whatever channels are enabled, so adding a channel in the admin page also makes it appear as a preference without a frontend release.

## Risks / Trade-offs

- **Our own queue is less capable than a broker.** No delayed visibility windows beyond `next_attempt_at`, no priority queues, no dead-letter topic. Accepted: the volume is tens of messages per hour, and the requirements are retry + audit + replay, which a table satisfies. If throughput ever matters, the same rows can be drained by an external worker.
- **Polling wastes a little CPU.** A short interval with an adaptive idle backoff keeps it negligible; `LISTEN/NOTIFY` does not exist in MySQL.
- **Encryption at rest is only as strong as `SECRET_KEY`.** A deployment that leaves the documented default key is unprotected; the settings page should surface that warning rather than pretend otherwise.
- **`webhook` is a generic POST, so a vendor that changes its payload shape breaks a template, not a release.** That is the intended trade: template edits are runtime operations, code edits are not.
- **Admin-entered URLs are an SSRF surface.** Mitigated by the allowlist and redirect policy in D8, but the residual risk is a deliberate malicious administrator — who already holds `manage settings`.
- **Table growth.** `notification_delivery` grows with every event × recipient × channel. Retention defaults to `NOTIFICATION_RETENTION_DAYS` and prunes terminal rows; the audit requirement may extend it.
- **Two sources of truth for "what a person can receive".** `notification_preference` (account holders) and `notification_subscription` (external) overlap conceptually. Keeping them separate avoids forcing external recipients into the account model; the dispatcher unions them, which is where the duplication is contained.
- **The `webhook` body template will be edited by people who are not developers.** Validation at save time plus a test send are the guardrails; the blast radius of a bad template is one parked delivery.
