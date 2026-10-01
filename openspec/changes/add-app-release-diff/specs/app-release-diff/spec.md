## ADDED Requirements

### Requirement: Compare two application releases at manifest level

The system SHALL compare two application release snapshots and present every dependency of the union of both manifests with its state: added, removed, changed, or unchanged. The default view SHALL hide unchanged entries, and a summary SHALL report the counts per state (changed, added, removed, downgraded).

#### Scenario: Dependency present in both releases with different versions
- **WHEN** `package_a` is `2.2590.3` in the older release and `2.2601.0` in the newer one
- **THEN** the entry SHALL be reported as changed with both versions shown

#### Scenario: Dependency only in the newer release
- **WHEN** a dependency exists in the newer release but not in the older one
- **THEN** the entry SHALL be reported as added

#### Scenario: Dependency dropped in the newer release
- **WHEN** a dependency exists in the older release but not in the newer one
- **THEN** the entry SHALL be reported as removed

#### Scenario: Unchanged entries are hidden by default
- **WHEN** a comparison contains dependencies with identical versions on both sides
- **THEN** those entries SHALL NOT be listed in the default view
- **AND** the user SHALL be able to reveal them

### Requirement: Version changes are classified by direction

The system SHALL classify a changed dependency as upgrade or downgrade using the numeric version components and pre-release precedence (a pre-release sorts before its release: `1.2.0-rc.0 < 1.2.0`). A downgrade SHALL be highlighted as a risk signal. When either version cannot be ordered, the entry SHALL be reported as changed without a direction, and MUST NOT be presented as an upgrade.

#### Scenario: Upgrade
- **WHEN** a dependency goes from `2.2590.3` to `2.2601.0`
- **THEN** the entry SHALL be reported as an upgrade

#### Scenario: Downgrade is highlighted
- **WHEN** a dependency goes from `2.2601.1` to `2.2601.0`
- **THEN** the entry SHALL be reported as a downgrade
- **AND** it SHALL be visually distinguished as a risk signal
- **AND** the summary SHALL include it in the downgrade count

#### Scenario: Pre-release ordering
- **WHEN** a dependency goes from `1.2.0-rc.0` to `1.2.0`
- **THEN** the entry SHALL be reported as an upgrade

#### Scenario: Unorderable version
- **WHEN** one of the two versions cannot be parsed into ordered components
- **THEN** the entry SHALL be reported as changed with no direction indicated

### Requirement: The code axis is reported together with the dependency axis

A comparison response SHALL include the commits that landed between the two compared snapshots (from the older snapshot commit to the newer one), in addition to the dependency matrix. When the dependency axis is empty but the code axis is not, the system SHALL state that explicitly instead of reporting that nothing changed.

#### Scenario: Dependency change with code change
- **WHEN** two snapshots differ both in dependencies and in commits
- **THEN** the response SHALL contain the dependency matrix and the commit delta
- **AND** the commits SHALL be attributable to their repositories

#### Scenario: Rebuilt tag with unchanged dependencies
- **WHEN** a tag was moved to a new commit and the manifest content is identical
- **THEN** the dependency matrix SHALL show no changes
- **AND** the view SHALL state that commits changed while dependencies did not

### Requirement: Drill-down into the repository comparison

For a changed dependency that resolves to a repository, the system SHALL offer a drill-down into the existing repository comparison, prefilled with the repository coordinates and the resolved revisions of both versions as the compared refs. A dependency that is external, unconfirmed, or missing a resolved revision on either side SHALL be labelled as not drillable and MUST NOT offer a link; that absence MUST NOT break the comparison.

#### Scenario: Drill-down from a resolved dependency
- **WHEN** a user activates the drill-down of a changed dependency whose two versions both resolved to a repository and a revision
- **THEN** the repository comparison SHALL open with project, repository, provider and both resolved revisions prefilled
- **AND** the user SHALL be able to navigate back to the app comparison

#### Scenario: Repository resolved but a revision is missing
- **WHEN** a changed dependency resolves to a repository but one of the two versions has no resolved revision
- **THEN** the entry SHALL be labelled as not drillable, stating the reason
- **AND** its version difference SHALL still be displayed

#### Scenario: Unconfirmed resolution
- **WHEN** a changed dependency resolved only weakly and the result has not been confirmed
- **THEN** the entry SHALL NOT offer a drill-down until it is confirmed

#### Scenario: Dependency without a repository mapping
- **WHEN** a changed dependency is external
- **THEN** the entry SHALL be labelled as external / not drillable
- **AND** the rest of the comparison SHALL remain fully usable

### Requirement: Release selection with shareable state

The system SHALL let the user choose an application and two of its releases and SHALL reflect that selection in the URL, including which axis is displayed. Opening such a URL SHALL restore the same comparison. Superseded snapshots of a tag SHALL be selectable, so that a rebuild can be compared against the snapshot it replaced.

#### Scenario: Shareable comparison link
- **WHEN** a user shares the URL of an app comparison
- **THEN** opening it SHALL restore the application, both releases and the displayed axis

#### Scenario: Comparing a rebuild against its predecessor
- **WHEN** a tag has several snapshots
- **THEN** each snapshot SHALL be individually selectable in the release picker
- **AND** selecting two snapshots of the same tag SHALL produce a valid comparison

### Requirement: Comparison access is read-only for users, refreshing is privileged

Viewing an app comparison, its dependency matrix and its code axis SHALL be available to any authenticated user. Refreshing or replacing a snapshot, and confirming a moved tag, SHALL be restricted to users holding `review_admin` or `system_admin`.

#### Scenario: Authenticated user views a comparison
- **WHEN** an authenticated user opens an app comparison
- **THEN** the comparison SHALL be served without requiring a management role

#### Scenario: Management role required to refresh
- **WHEN** a request attempts to refresh or re-snapshot a release without the management role
- **THEN** the request SHALL be rejected with `403`

### Requirement: Release tooling navigation distinguishes entry points

The Releases navigation group SHALL expose three clearly named entries: the application-level comparison, the repository-level comparison, and release notes. The repository-level entry MUST be named so that it cannot be confused with the application-level one.

#### Scenario: Menu labels
- **WHEN** a user opens the Releases menu
- **THEN** the entries SHALL read as the application comparison, the repository comparison, and release notes
- **AND** the labels SHALL be localized in every supported language
