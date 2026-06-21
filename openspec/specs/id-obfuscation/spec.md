## ADDED Requirements

### Requirement: Encode numeric ID to opaque string

The system SHALL provide a reversible encoding function that transforms a numeric database ID into an opaque, non-sequential, URL-safe short string.

- The encoding SHALL use the `hashids` library with a configurable salt from `ID_OBFUSCATOR_SALT`
- The output SHALL be at least 10 characters long (alphanumeric, URL-safe)
- The encoding SHALL be deterministic — same input + same salt → same output
- The function SHALL support decoding back to the original integer
- Invalid encoded strings SHALL return `None` (not throw)

#### Scenario: Encode a review ID

- **WHEN** the system encodes integer `42` with the configured salt
- **THEN** it returns a string matching `^[a-zA-Z0-9]{10,}$` (e.g., `"kM8xP31R"`)
- **AND** decoding that string returns `42`

#### Scenario: Decode an invalid string

- **WHEN** the system attempts to decode `"invalid!"` or `""`
- **THEN** it returns `None`

### Requirement: Prefix-based entity scoping

The system SHALL support entity-type prefixes on encoded IDs so different entity types with the same numeric ID produce different public-facing strings.

- The prefix SHALL be 3 lowercase letters followed by an underscore: `rev_`, `sco_`, `usr_`, `rule_`
- The format function SHALL accept an entity type key and a numeric ID and return `"{prefix}{encoded}"`
- The parse function SHALL accept a prefixed string and return the entity type key and numeric ID

#### Scenario: Format a review public ID

- **WHEN** the system formats entity `"review"` with ID `42`
- **THEN** it returns `"rev_kM8xP31R"` (prefix `rev_` + encoded `42`)

#### Scenario: Parse a prefixed public ID

- **WHEN** the system parses `"rev_kM8xP31R"`
- **THEN** it returns `("review", 42)`

#### Scenario: Different entities with same ID

- **WHEN** the system formats entity `"review"` with ID `42` AND entity `"score"` with ID `42`
- **THEN** the two outputs differ in prefix (`"rev_..."` vs `"sco_..."`)
- **AND** each correctly decodes to its respective entity type and ID

### Requirement: Response schemas include public_id

The system SHALL include a `public_id` field in user-facing response schemas for entities that expose a numeric ID.

- `ReviewResponse` SHALL include `public_id: str` alongside `id: int`
- `ReviewRawResponse` SHALL include `public_id: str`
- Other schemas SHALL add `public_id` when extended to those entities
- The `public_id` SHALL be populated in the endpoint handler after model validation

#### Scenario: Review response includes public_id

- **WHEN** the system returns a review response
- **THEN** the JSON includes `"public_id": "rev_kM8xP31R"` AND `"id": 42`

### Requirement: Lookup by public_id endpoint

The system SHALL provide endpoints that accept `public_id` strings and resolve them to the database entity for lookup.

- `GET /api/v1/reviews/by-public-id/{public_id}` SHALL decode the public_id, look up the review by its real ID, and return the standard review response
- If the public_id is invalid or the review doesn't exist, it SHALL return 404
- If the public_id is a valid hash but decodes to a non-existent ID, it SHALL return 404
- Old `GET /api/v1/reviews/{id}` SHALL continue to accept numeric IDs for backward compatibility

#### Scenario: Lookup by valid public_id

- **WHEN** a client sends `GET /api/v1/reviews/by-public-id/rev_kM8xP31R`
- **AND** that public_id decodes to review ID 42
- **AND** review 42 exists
- **THEN** the response is 200 with the review data (including `public_id: "rev_kM8xP31R"`)

#### Scenario: Lookup by invalid public_id

- **WHEN** a client sends `GET /api/v1/reviews/by-public-id/invalid`
- **THEN** the response is 404

### Requirement: Associate reviews by PR info search

The system SHALL allow users to find and associate reviews by searching on PR-related identifiers instead of numeric review IDs.

- The associate dialog search SHALL find reviews matching typed text in: project key, pull request ID, repository slug, or PR user display name
- The search SHALL return matching reviews as selectable options
- The option label SHALL show project key, pull request ID, and optionally PR user — NOT any review ID (real or public)
- The option value SHALL be the real review ID (used internally for the API call)
- The system SHALL NOT require the user to type or see any review ID during the association flow

#### Scenario: Search for a review to associate

- **WHEN** a user types `"PR-123"` in the associate search box
- **THEN** the system returns reviews whose `pull_request_id` contains `"PR-123"`
- **AND** each option displays as `"FE-Proj/PROJ-A — PR #123 — John"` (no IDs visible)

#### Scenario: Select and associate

- **WHEN** a user selects a review from the search results and clicks "Link"
- **THEN** the system calls `POST /api/v1/reviews/{sourceId}/associate/{targetId}` with the real IDs
- **AND** the association is created successfully

### Requirement: Frontend display uses public_id

The system SHALL display `public_id` instead of raw `id` in all user-facing locations.

- ReviewListView table column SHALL show `public_id` prefixed as `"REV-{public_id}"`
- Review detail page header SHALL show `"Review REV-{public_id}"`
- Browser URL SHALL use `public_id` in the route: `/reviews/{public_id}`
- Delete, retry, and other confirmation dialogs SHALL reference the review by `public_id`
- The old numeric `id` SHALL NOT appear in any user-facing template

#### Scenario: Review list table shows public_id

- **WHEN** the review list page loads
- **THEN** each row's ID column shows `"REV-kM8xP31R"` format
- **AND** the raw numeric ID does not appear in the DOM

#### Scenario: Review detail URL uses public_id

- **WHEN** a user navigates to a review detail
- **THEN** the browser URL is `/reviews/rev_kM8xP31R`
- **AND** clicking "Back" or sharing this URL works correctly
