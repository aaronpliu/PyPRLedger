## ADDED Requirements

### Requirement: Tag listing carries revisions

The system SHALL be able to list the tags of a repository together with the revision each tag points at and, when the provider reports one, the commit date. Annotated tags SHALL be resolved to the commit they point at, so a tag object's own identifier is never treated as a commit. The listing SHALL page through the provider's result set and SHALL NOT depend on the provider's ordering.

#### Scenario: Tags with their revisions
- **WHEN** the tags of a repository are listed for scope resolution
- **THEN** every entry SHALL carry the tag name and the commit revision it points at
- **AND** an annotated tag SHALL report the commit it references, not the tag object

#### Scenario: Paging beyond one page of tags
- **WHEN** a repository has more tags than a single provider page returns
- **THEN** the listing SHALL follow the provider's paging until the requested limit is reached
- **AND** the returned order SHALL be treated as arbitrary, not as release order

#### Scenario: A tag without a date
- **WHEN** a provider reports a tag without a commit date
- **THEN** the entry SHALL still carry its name and revision, with no date
- **AND** ordering decisions SHALL fall back to the tag name for that entry

### Requirement: Release scope is resolved on the server

The release scope of a tag (the commits it released) SHALL be resolved by the server from the repository's tags, and MUST NOT be derived from a client-side list of tags that may have been truncated.

#### Scenario: Predecessor outside any client-side window
- **WHEN** a tag's predecessor is not part of the tag list the browser holds
- **THEN** the server SHALL still resolve the predecessor from the provider's tag list
- **AND** the resolved predecessor SHALL be used as the scope base

#### Scenario: Client list smaller than the repository
- **WHEN** a repository has more tags than the client requests
- **THEN** the scope resolution SHALL be unaffected by that limit

### Requirement: A verified predecessor is preferred

The system SHALL prefer a predecessor that it can verify is an ancestor of the released tag. Candidates SHALL be considered in order of commit date, newest first, and a candidate SHALL be accepted only after the provider confirms that the released tag contains it. The number of verification probes SHALL be bounded, and that bound SHALL grow with the number of tags in the repository so that repositories with more release lines may skip over more recent non-ancestor tags.

#### Scenario: Ancestor found among the candidates
- **WHEN** the newest candidate tag is an ancestor of the released tag
- **THEN** it SHALL be used as the predecessor
- **AND** the resolution SHALL be reported as verified

#### Scenario: No candidate is an ancestor
- **WHEN** no probed candidate is an ancestor of the released tag
- **THEN** the system SHALL fall back to the previous tag in version-aware name order
- **AND** that resolution SHALL be reported as unverified

#### Scenario: Probe budget exhausted
- **WHEN** the verification probe budget is reached without a verified candidate
- **THEN** the system SHALL continue with the name-order fallback instead of failing the request

#### Scenario: Probe budget scales with the repository
- **WHEN** a repository carries many tags
- **THEN** the system SHALL allow more verification probes than for a repository with few tags
- **AND** the budget SHALL remain capped by a fixed maximum

#### Scenario: An inferred scope is warned about
- **WHEN** the predecessor was resolved by tag order rather than verified by ancestry
- **THEN** the release notes panel SHALL warn that the scope was inferred
- **AND** the inferred scope SHALL still be used instead of falling back to the whole history

### Requirement: An explicit predecessor is authoritative

When the caller supplies a previous version (or a stored note carries one), the system SHALL use it as the scope base without substituting its own resolution.

#### Scenario: Caller supplied predecessor
- **WHEN** a request supplies a previous version
- **THEN** that ref SHALL be used as the scope base
- **AND** the resolution provenance SHALL report it as supplied by the caller

### Requirement: An unresolved scope is reported, never hidden

Every scope answer SHALL carry how it was obtained and whether it was verified, distinguishing a supplied predecessor, a resolved one, a tag that genuinely has no predecessor, and a resolution that could not be determined.

#### Scenario: First release on a line
- **WHEN** no older tag exists for the released tag
- **THEN** the response SHALL report the scope as a first release with no predecessor
- **AND** the commit listing SHALL fall back to the history reachable from the tag

#### Scenario: Resolution could not be determined
- **WHEN** the tag list cannot be obtained from the provider
- **THEN** the response SHALL report the scope as unresolved, the request SHALL still succeed
- **AND** the fallback listing SHALL be used

#### Scenario: Provenance is exposed to the client
- **WHEN** any scope is answered
- **THEN** the response SHALL state the resolved predecessor, its revision when known, and whether the resolution was verified

#### Scenario: Resolved revisions are displayed
- **WHEN** a scope was resolved from known revisions
- **THEN** the panel SHALL show the short revision next to each ref in the range
- **AND** a ref whose revision is unknown SHALL be shown without one

### Requirement: A capped listing is not a release scope

When the commit list is bounded for display, the system SHALL distinguish that display bound from the scope itself: the reported commit count SHALL remain complete for a resolved scope and SHALL be marked as a lower bound when the fallback history had to be truncated. The fallback SHALL only be reachable for a first release or an unresolved scope.

#### Scenario: Resolved scope with more commits than rendered
- **WHEN** a resolved scope contains more commits than the render limit
- **THEN** the count SHALL reflect the whole scope
- **AND** the listing SHALL be marked as trimmed for display

#### Scenario: Fallback listing trimmed
- **WHEN** the fallback history listing is capped
- **THEN** the count SHALL be reported as a lower bound
- **AND** the response SHALL indicate that the tag has no resolved predecessor, so the trim is not read as a repository problem

#### Scenario: Resolved scope is never truncated by a tag-list limit
- **WHEN** a predecessor was resolved
- **THEN** the scope SHALL be computed from the difference between the predecessor and the tag
- **AND** its completeness SHALL not depend on how many tags the client or the listing returned

### Requirement: Scope resolution is cached and degrades quietly

Repeated lookups of the same tag scope SHALL reuse a cached resolution, and an explicit refresh SHALL bypass that cache. A provider failure during resolution MUST NOT fail the release note request.

#### Scenario: Repeated lookup
- **WHEN** the scope of the same tag is requested again
- **THEN** the cached resolution SHALL be reused
- **AND** the provider SHALL not be asked to list the tags again

#### Scenario: Explicit refresh
- **WHEN** a request asks for a refresh
- **THEN** the cached resolution SHALL be bypassed and the tags re-read
