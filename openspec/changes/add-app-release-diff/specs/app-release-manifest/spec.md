## ADDED Requirements

### Requirement: Application release refs resolve to immutable commit identities

The system SHALL list an application repository's release tags together with the commit each tag resolves to and its date, using the configured git provider (Bitbucket Server, Bitbucket Cloud, GitHub Enterprise). Annotated tags MUST resolve to the underlying commit rather than to the tag object, and the resolution MUST be delegated to the provider's commit-resolving endpoint. Branch and commit targets MUST NOT be treated as published application releases.

#### Scenario: Listing the release tags of an application repository
- **WHEN** a user selects an application whose repository is hosted on any supported provider
- **THEN** the system SHALL return every release tag with its resolved `commit_sha`, short SHA and commit date
- **AND** the listing SHALL be obtained in a single paginated call per repository

#### Scenario: Annotated tag resolves to its commit
- **WHEN** a release tag is annotated
- **THEN** the recorded identity SHALL be the commit the tag points at
- **AND** the tag object's own SHA MUST NOT be stored as the commit SHA

#### Scenario: Branch target while browsing
- **WHEN** a comparison target resolves to a branch or a raw commit
- **THEN** the system SHALL label it as a point-in-time target with its resolution timestamp
- **AND** it MUST NOT be stored as the current published release of the application

### Requirement: Dependency manifest is retrieved from the application repository

The system SHALL read the application's dependency manifest (`package.json`) from the application repository at the resolved commit of the selected release, using the path configured for that application. Only direct dependency entries SHALL be recorded, each with its scope (runtime, dev, peer, optional). A missing manifest is a valid outcome and MUST NOT fail the request. No lockfile SHALL be required.

#### Scenario: Manifest read for a tagged release
- **WHEN** the manifest exists at the configured path for the resolved commit
- **THEN** the system SHALL record every direct dependency as a `(package_name, version, dep_scope)` entry
- **AND** the recorded versions SHALL be the pinned values declared in the manifest, unmodified

#### Scenario: Manifest missing at the configured path
- **WHEN** the manifest does not exist at the configured path for the resolved commit
- **THEN** the system SHALL store a snapshot with an empty dependency set
- **AND** the UI SHALL present an explicit empty state instead of an error

#### Scenario: Monorepo with several manifests
- **WHEN** the application is configured with a manifest path pointing into a workspace package
- **THEN** only that manifest SHALL be read for the snapshot

### Requirement: Release snapshots are persisted and reused

The system SHALL persist an application release snapshot identified by `(application, tag_name, commit_sha)`, including its dependency rows, content hash, package count and fetch timestamp. A repeated request for an unchanged tag/commit pair SHALL reuse the stored snapshot without re-reading the manifest. Snapshots MUST be append-only: a re-resolve that yields a different commit for an existing tag SHALL create a new snapshot, keep the previous one retrievable, and mark the tag as moved.

#### Scenario: Repeated view reuses the stored snapshot
- **WHEN** a user opens an app comparison for a release that was already snapshotted and whose tag still resolves to the same commit
- **THEN** the stored snapshot SHALL be reused
- **AND** the manifest SHALL NOT be fetched again

#### Scenario: Rebuild under the same tag creates a new snapshot
- **WHEN** the tag of an already snapshotted release resolves to a different commit
- **THEN** a new snapshot SHALL be created for the new commit
- **AND** the previous snapshot SHALL remain unchanged and selectable for comparison
- **AND** a rebuild/viewport counter SHALL distinguish the two snapshots of that tag

### Requirement: Moved tags are flagged and confirmed, never silently rewritten

When a re-resolve detects that an existing tag points at a new commit, the system SHALL record the detection time and surface it to users with the manage role. Creating the replacement snapshot and switching the tag's current pointer SHALL require an explicit confirmation by a user holding `review_admin` or `system_admin`. Until that confirmation, the previously stored snapshot SHALL remain the current one and MUST NOT be modified in place.

#### Scenario: Detection surfaces the drift
- **WHEN** a tag that already has a snapshot resolves to a different commit
- **THEN** the system SHALL mark the release as moved, recording the previous and current commit
- **AND** the app comparison view SHALL show a warning naming the old and new commit
- **AND** the stored snapshot's dependency rows SHALL remain untouched

#### Scenario: Privileged confirmation refreshes the current snapshot
- **WHEN** a user with `review_admin` or `system_admin` confirms the refresh
- **THEN** the new snapshot SHALL become the current one for that tag
- **AND** the superseded snapshot SHALL remain selectable in the release picker

#### Scenario: Unprivileged user cannot confirm
- **WHEN** a user without the manage role opens a release whose tag moved
- **THEN** the warning SHALL be visible with the diff summary
- **AND** no control to confirm the refresh SHALL be offered, and a direct API call SHALL be rejected with `403`

### Requirement: Ref resolution stays live while content caching is keyed by commit

The system SHALL resolve release tags on every app comparison view so that a moved tag is reflected without waiting for a cache expiry. File content fetched from a provider SHALL be cached under an identity that includes the commit SHA and path and MUST NOT expire, because content addressed by a commit cannot change. Computed comparisons SHALL be cached under the pair of snapshot commits involved. When a provider is unreachable, the system SHALL fall back to the stored snapshot and report that the refresh failed.

#### Scenario: Page view reflects the current tag target
- **WHEN** a tag was moved between two page views
- **THEN** the second view SHALL resolve the new commit without a stale cached ref
- **AND** the manifest read for that commit SHALL reuse an existing content cache entry when the same commit was read before

#### Scenario: Provider unavailable
- **WHEN** the git provider cannot be reached while listing tags
- **THEN** the system SHALL serve the stored snapshots
- **AND** the response SHALL indicate that the release list could not be refreshed

#### Scenario: Comparison cached by snapshot pair
- **WHEN** the same two snapshots are compared again
- **THEN** the result SHALL be served from the cache key derived from the two commit SHAs
- **AND** no provider call SHALL be required

### Requirement: Package versions are normalized when the snapshot is written

The system SHALL normalize every recorded package identity and version at snapshot time: a case-insensitive key for uniqueness and lookups; and for versions following `X.Y.Z[-prerelease][+build]`, the numeric components plus the pre-release identifier. A version that cannot be parsed SHALL still be stored as-is with empty numeric components.

#### Scenario: Standard version
- **WHEN** a dependency declares `2.2601.1`
- **THEN** the stored record SHALL expose major `2`, minor `2601`, patch `1` and no pre-release

#### Scenario: Pre-release version
- **WHEN** a dependency declares `2.2602.1-demo-rc.2`
- **THEN** the stored record SHALL expose major `2`, minor `2602`, patch `1` and pre-release `demo-rc.2`

#### Scenario: Unparseable version
- **WHEN** a dependency declares a version that does not follow `X.Y.Z`
- **THEN** the version string SHALL still be stored verbatim
- **AND** the numeric components SHALL be empty rather than guessed

#### Scenario: Name casing drift between releases
- **WHEN** the same dependency appears as `Package_A` in one release and `package_a` in another
- **THEN** both SHALL resolve to the same package key
- **AND** the comparison SHALL report one changed entry rather than an added plus a removed entry

### Requirement: Per-application manifest configuration

The system SHALL allow each application to configure where its dependency manifest lives and which dependency scopes are recorded. An application without configuration SHALL NOT present a release picker based on a guessed manifest location.

#### Scenario: Application configured with a custom manifest path
- **WHEN** an administrator sets the manifest path of an application to a non-default location
- **THEN** subsequent snapshots SHALL read that path

#### Scenario: Application without configuration
- **WHEN** an application has no manifest configuration
- **THEN** opening the app comparison SHALL show an explanatory empty state
- **AND** the system SHALL NOT attempt to guess a manifest path
