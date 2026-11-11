## Why

The instance produces notifications, but they never leave it. A reviewer is told about a PR in the bell menu of a page they have to open anyway, and the people who need the news most — a release manager waiting on a tag, a product owner who has no account — are told nothing at all.

Three concrete gaps, all verified in the tree:

| Observation | Where |
|---|---|
| Only in-app notifications are delivered; nothing imports `smtplib` / `aiosmtplib` / any HTTP sender | `src/services/notification_service.py:35` (the only writer, `channel="in_app"`) |
| SMTP and Slack values exist as settings but have no consumer, and `SMTP_USE_TLS` / `SMTP_USE_SSL` are documented in `.env.example` yet absent from `Settings` — `extra="ignore"` drops them silently | `src/core/config.py:392`, `.env.example:177` |
| The configuration guide states Email/Slack are "⏳ Ready" | `docs/NOTIFICATION_EMAIL_CONFIGURATION.md:208` |

The reason to build a gateway rather than "add an email sender" is the deployment target: **the system runs on an intranet and usually cannot reach a public messaging service.** Whatever is built must let an operator point the system at an internal SMTP relay, an internal IM gateway, or a vendor product that only exists inside the corporate network — **without a code change or a container rebuild per endpoint.** A per-vendor adapter (`slack.py`, `dingtalk.py`, `wecom.py`, `feishu.py`, …) answers the wrong question and grows without bound.

Two structural obstacles confirm the need for a layer:

1. **Channel is a database enum.** `Notification.channel` is `ENUM('in_app','email','slack')` (`src/models/notification.py:61`), so a fourth channel is a migration, and the three business call sites hardcode `channel="in_app"` (`src/services/auto_assign_service.py:321-332`, `src/services/multi_reviewer_service.py:848-859`, `:908-919`). Channel choice has leaked into business code.
2. **The deployment is a single container with no broker** (`docker-compose.yml`; background work is `asyncio.create_task` in `src/main.py:169-175`). An inline "send on the request path" design therefore has no protection: one unreachable SMTP host with a 15 s timeout stalls the request that assigns reviewers, and a container restart (routine here — `./src` is bind-mounted) loses anything held in memory.

## What Changes

- **One entry point for business code.** `notify(event)` replaces the hardcoded `channel="in_app"` construction at the call sites. Channel selection moves out of business code entirely.
- **A dispatcher that fans out.** Recipient resolution → preference/subscription filtering → per-channel rendering → one outbox row per (recipient, channel).
- **A durable outbox with an in-process worker.** Rows are claimed with `SELECT … FOR UPDATE SKIP LOCKED`, so a restart loses nothing and a second replica is safe. Retried with backoff, parked as `dead` after a bounded number of attempts, replayable from the admin page.
- **A connector registry keyed by protocol, not product.** `in_app` (the existing `notification` table, surfaced by the polling bell menu), `webhook` (a generic HTTP POST with per-endpoint headers, body template and optional signing), and `smtp`. Every intranet IM that accepts an HTTP POST is covered by `webhook`; a genuinely proprietary protocol is one new connector file, never one new endpoint per customer. Realtime push is out of scope: the bell menu already polls, and `SSEBroker` is a `reviews:created`-specific fan-out with no generic publish method.
- **Endpoints as data.** `notification_endpoint` rows (URL/host, credentials, timeout, proxy, CA bundle, TLS verification, QPS) are created and edited in the admin settings page under `manage settings`. Credentials are encrypted at rest and never returned by the API.
- **Templates as data.** Subject/body per (event type, channel), with a whitelisted variable set; a rendering failure parks that one delivery instead of failing the fan-out.
- **Recipients beyond the user table.** A subscription table lets a project owner register an external address (email or IM handle) for a project/repository scope, so people without an account can be notified.
- **`channel` widened to a string.** `ENUM` → `VARCHAR(32)` so the database stops enumerating product names.
- **Configuration drift fixed.** `SMTP_USE_TLS` / `SMTP_USE_SSL` join `Settings`, and the guide stops claiming a delivery path that does not exist.

## Capabilities

### New Capabilities

- `notification-gateway`: how an internal event becomes a delivery to a person over an external channel — recipient resolution (including people with no account), per-channel rendering, endpoint and credential management, durable outbox semantics (idempotency, retry, dead-letter, replay), the connector registry, and the intranet safety rules the outbound calls obey.

### Modified Capabilities

<!-- None: no capability under openspec/specs/ covers notifications today. -->

## Impact

- **Models / migration**: new `notification_endpoint`, `notification_template`, `notification_subscription`, `notification_delivery`; `notification.channel` `ENUM` → `VARCHAR(32)`; `notification_preference` gains a per-channel dimension (the three fixed booleans no longer describe a set of channels).
- **Services**: new package `src/services/notification/` (dispatcher, outbox worker, recipients, rendering, connectors). `NotificationService` keeps its role as the in-app writer and becomes one connector's sink.
- **Call sites**: `auto_assign_service.py` and `multi_reviewer_service.py` switch to `notify(event)`; behaviour for in-app recipients is unchanged.
- **API**: admin CRUD under the existing `manage settings` permission (`/rbac/settings/notifications/*`), a test-send action, and a delivery-log query with replay. The user-facing notification API keeps its contract.
- **Frontend**: `views/admin/SystemSettingsView.vue` mounts a standalone `components/notification/NotificationSettingsCard.vue` (endpoints, templates, subscriptions, test send, delivery log) as one more card section, rather than inlining several hundred lines into an already-large view; `NotificationPreferenceView.vue` renders the per-channel matrix.
- **Configuration**: `SMTP_USE_TLS` / `SMTP_USE_SSL` added to `Settings`; `NOTIFICATION_*` worker settings added; `.env.example` and `docs/NOTIFICATION_EMAIL_CONFIGURATION.md` corrected.
- **Operational**: one new lifespan task (the worker), new Prometheus metrics per endpoint, and a retention policy for `notification_delivery`.
- **Non-goal**: receiving inbound messages from an IM (no callbacks, no bot commands).
