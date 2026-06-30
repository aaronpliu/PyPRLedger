## Why

The application currently exposes raw sequential database primary keys (auto-increment integers) to users in the UI, URLs, and API responses. This violates internal enterprise security policy by leaking business intelligence (data volume, growth rate) and enabling ID enumeration attacks. The review ID specifically appears in the table display, detail page, URL bar, and association dialogs. We need an obfuscation layer that hides real DB IDs while maintaining full reversibility for internal operations.

## What Changes

- **New utility**: `src/utils/id_obfuscator.py` — a thin reversible encoding layer using `hashids`
- **New config**: `ID_OBFUSCATOR_SALT` environment variable for the encoding secret
- **Response schema change**: Add `public_id` field to `ReviewResponse` and related schemas
- **API endpoint change**: Accept obfuscated ID in review lookup endpoints (`GET /reviews/{id}`)
- **Frontend display**: Replace `row.id` with `row.public_id` in all user-facing templates
- **Association search**: Change the associate-review dialog from "type numeric ID" to "search by PR info" (project key, repo, PR number, title) — the old numeric ID search disappears
- **URL routing**: Update review detail route to use obfuscated ID (`/reviews/{public_id}`)
- **Dependency add**: `hashids` Python package

## Capabilities

### New Capabilities

- `id-obfuscation`: Reversible encoding layer that transforms numeric DB IDs into opaque short strings suitable for user-facing display and URLs. Supports multiple entity types (reviews, scores, users, etc.) via prefix-based scoping.

### Modified Capabilities

<!-- No existing specs change — this is a new cross-cutting capability -->

## Impact

- **Backend**: New utility module + config; modified response schemas + endpoint param handling; no database changes
- **Frontend**: Replace ID displays in ReviewListView, ReviewDetailView, ReviewValidationView, associate dialog, delete confirmations, URL navigation
- **Dependencies**: Add `hashids` to `pyproject.toml`
- **No migration**: Zero database changes — encoding is pure computation
- **Backward compatible**: Old numeric ID endpoints continue to work alongside new public ID endpoints
