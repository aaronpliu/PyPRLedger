## ADDED Requirements

### Requirement: Package versions resolve to a repository and a revision

The system SHALL resolve a dependency's package name and pinned version to the source repository it was published from, and to the revision that was published. Resolution SHALL consult, in order: an explicitly maintained mapping; the artifact source (JFrog Artifactory) queried by package name and version; a tag lookup in the resolved repository by version (`2.2601.0`, then `v2.2601.0`, then a repository-name prefixed form such as `pkg-a-2.2601.0`); and finally a naming convention matching the package name against the repository name. A package that none of these resolve SHALL be reported as external.

#### Scenario: Artifact source supplies the repository and the revision
- **WHEN** a package version is found in a locally hosted artifact repository with build information
- **THEN** the resolution SHALL yield the source repository and the published revision taken from the build information
- **AND** the reported refs SHALL be the revisions, not the tag names

#### Scenario: Build information absent
- **WHEN** the package version is found in a locally hosted artifact repository but carries no build information
- **THEN** the system SHALL fall back to resolving the version as a tag in that repository
- **AND** a legacy pre-release tag such as `1.12.0-rc.1` SHALL match a version of the same string

#### Scenario: No candidate found
- **WHEN** neither the artifact source nor the tag lookup nor the naming convention resolves the package
- **THEN** the package SHALL be reported as external
- **AND** its version difference SHALL still be part of the comparison

### Requirement: Only locally hosted artifacts count as internal packages

A package version found only in a remote or virtual artifact repository is a proxied third-party artifact and MUST be treated as external. Only repositories configured as locally hosted MAY produce an internal repository mapping.

#### Scenario: Proxied third-party package
- **WHEN** a package version resolves only inside a remote or virtual artifact repository
- **THEN** the package SHALL be reported as external
- **AND** no drill-down SHALL be offered for it

#### Scenario: Locally published package
- **WHEN** a package version is present in a repository configured as locally hosted
- **THEN** the package MAY be mapped to a repository
- **AND** the artifact repository that produced the conclusion SHALL be recorded with the mapping

### Requirement: Resolution results carry provenance and confirmation state

Every automatic resolution SHALL record where it came from and how confident it is. A manual mapping MUST NOT be overwritten by automatic resolution. A low-confidence result SHALL NOT be authoritative until a user with the management role confirms it, and unresolved or unconfirmed packages SHALL be listed for review.

#### Scenario: Manual mapping wins
- **WHEN** a package already has a manually maintained mapping
- **THEN** automatic resolution SHALL NOT change it
- **AND** the recorded source SHALL remain manual

#### Scenario: Low-confidence result awaits confirmation
- **WHEN** resolution produces only a weak candidate, such as a naming-convention match
- **THEN** the result SHALL be stored as unconfirmed with its confidence
- **AND** the comparison SHALL NOT offer a drill-down based on it until it is confirmed

#### Scenario: Unresolved packages are reviewable
- **WHEN** a package version used in a comparison cannot be resolved
- **THEN** the package SHALL appear in the review list with its package name and version
- **AND** a user with the management role SHALL be able to supply the repository coordinates manually

### Requirement: Resolution is cached and never blocks the comparison

Resolutions SHALL be cached per package and version, with the source and the resolution time recorded. When the artifact source is unconfigured or unavailable, the system SHALL fall back to cached resolutions, then to the tag lookup, then to unresolved, and SHALL still return the comparison.

#### Scenario: Repeat comparison reuses the cached resolution
- **WHEN** the same package version is resolved again
- **THEN** the cached resolution SHALL be reused without querying the artifact source

#### Scenario: Artifact source unavailable
- **WHEN** the artifact source cannot be reached
- **THEN** the comparison SHALL still be served
- **AND** resolutions SHALL come from cache or the tag lookup, with the unresolved ones reported as such

### Requirement: Artifact source configuration

The system SHALL allow an administrator to configure the artifact source: its base URL, a read-only access token, and the ordered list of locally hosted repositories. Credentials MUST be used read-only.

#### Scenario: Administrator configures the artifact source
- **WHEN** an administrator saves the artifact source settings
- **THEN** subsequent resolutions SHALL use that URL, token and repository order

#### Scenario: Feature used before configuration
- **WHEN** no artifact source is configured
- **THEN** the system SHALL NOT query any artifact source
- **AND** resolution SHALL fall back to tag lookup and naming convention, with the results marked accordingly

### Requirement: Mapping maintenance supports bulk onboarding

The review list SHALL support confirming several candidates at once, entering repository coordinates manually, and importing or exporting the mapping set for initial onboarding.

#### Scenario: Bulk confirmation
- **WHEN** a user with the management role confirms several reviewed candidates at once
- **THEN** all confirmed mappings SHALL become authoritative
- **AND** their recorded source SHALL reflect the confirmation

#### Scenario: Import and export
- **WHEN** mappings are exported and re-imported
- **THEN** the imported set SHALL reproduce the exported mappings, with duplicates resolved in favour of manually maintained rows
