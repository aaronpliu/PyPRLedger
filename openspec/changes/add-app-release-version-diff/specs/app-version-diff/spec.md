## ADDED Requirements

### Requirement: Compare two or more application releases, the application itself among them

The system SHALL compare two or more releases of one application and present a version matrix: one column per selected release, in the order the releases are dated, and one row per compared entry across all selected releases - **the application's own version first**, then each direct dependency the application declares. A dependency declared in only some of the releases SHALL appear in every column, with an empty cell where it is absent, so the row reads as one package rather than several. A comparison of fewer than two releases SHALL be rejected as a request that cannot be answered.

The application's own version SHALL be read for every selected release and classified exactly as a dependency row is, so that a release which moved its own version while every dependency stayed put is reported as the change it is, rather than as a comparison in which nothing happened.

#### Scenario: The application's own version moved

- **WHEN** the application is `1.0.0` in one release and `1.1.0` in the next, and every dependency carries the same version in both
- **THEN** the application's row SHALL be reported as changed, with its direction
- **AND** the dependency rows SHALL be reported as unchanged

#### Scenario: The application is a row of the matrix

- **WHEN** a comparison is displayed
- **THEN** the application's own version SHALL be the first row
- **AND** that row SHALL be distinguishable from the dependency rows
- **AND** the counts of each pair SHALL cover it together with the dependency rows

#### Scenario: A build number does not carry a direction

- **WHEN** the application moves from `1.0.0_10000` to `1.0.0_20000` - the same version, a later build
- **THEN** the row SHALL be reported as changed with no direction
- **AND** it MUST NOT be reported as an upgrade

#### Scenario: A package present in every release

- **WHEN** `packageA` is `1.0.0` in `1.0.0`, `1.0.0` in `1.1.0` and `1.1.0` in `1.2.0`
- **THEN** the row for `packageA` SHALL carry all three versions, one per column
- **AND** the moves from `1.0.0` to `1.1.0` and from `1.1.0` to `1.2.0` SHALL each be reported

#### Scenario: A package declared in only some releases

- **WHEN** `packageF` is declared in `1.1.0` and `1.2.0` but not in `1.0.0`
- **THEN** the row for `packageF` SHALL carry an empty cell for `1.0.0`
- **AND** the move into `1.1.0` SHALL be reported as added

#### Scenario: Fewer than two releases

- **WHEN** a comparison is requested with a single release
- **THEN** the request SHALL be rejected
- **AND** the page SHALL state that at least two releases are needed

### Requirement: Adjacent releases are compared, and changes are classified by direction

For every pair of adjacent columns the system SHALL report each dependency as unchanged, changed, added or removed. A changed dependency SHALL be classified as an upgrade or a downgrade using the numeric version components and pre-release precedence, so that a pre-release sorts before its release (`1.2.0-rc.0 < 1.2.0`). A downgrade SHALL be highlighted as a risk signal. When either version cannot be ordered the entry SHALL be reported as changed without a direction, and MUST NOT be presented as an upgrade. Each adjacent pair SHALL carry a summary of the counts per state.

#### Scenario: Upgrade

- **WHEN** a dependency goes from `1.0.0` to `1.0.1` between two adjacent releases
- **THEN** the move SHALL be reported as an upgrade

#### Scenario: Downgrade is highlighted

- **WHEN** a dependency goes from `2.2601.1` to `2.2601.0` between two adjacent releases
- **THEN** the move SHALL be reported as a downgrade
- **AND** it SHALL be visually distinguished as a risk signal
- **AND** the interval summary SHALL include it in the downgrade count

#### Scenario: Unorderable version

- **WHEN** one of the two versions of a dependency cannot be parsed into ordered components
- **THEN** the move SHALL be reported as changed with no direction indicated
- **AND** it MUST NOT be counted as an upgrade

#### Scenario: No move between adjacent releases

- **WHEN** the application and every dependency carry the same version in two adjacent releases
- **THEN** that interval SHALL report no changes
- **AND** its summary counts SHALL all be zero

#### Scenario: The dependencies alone are reported for the rebuild reading

- **WHEN** the application's own version moved between two adjacent releases while every dependency carried the same version
- **THEN** the pair SHALL report that a dependency moved as false
- **AND** the application's own move SHALL still be counted in the pair's summary

### Requirement: Releases are ordered along the release datetime timeline

The system SHALL order the selected releases by release datetime, never by the order in which they were supplied, and SHALL show that order. The release datetime of a release SHALL be the time recorded for its dependency record when one exists, otherwise the date of its tag as the git provider reports it. A release for which neither is available SHALL keep its position relative to the other such releases rather than being given an invented date.

#### Scenario: Releases supplied out of order

- **WHEN** a request supplies `1.2.0`, `1.0.0`, `1.1.0`
- **THEN** the columns SHALL be presented as `1.0.0`, `1.1.0`, `1.2.0`
- **AND** the adjacent comparisons SHALL follow that order

#### Scenario: A branch among tags

- **WHEN** a branch with no dependency record is selected next to dated tags
- **THEN** it SHALL keep its position among the undated releases
- **AND** no date SHALL be shown for it

### Requirement: A release with no dependency record makes the comparison incomplete

When the dependency source holds no record for a selected release, the system SHALL mark that release as having no record, SHALL report every adjacent comparison that involves it as incomplete, and SHALL still report the comparisons between the releases that do have records. An incomplete comparison MUST NOT be presented as "no changes", and a missing record MUST NOT fail the whole request. When the dependency source cannot be reached at all, the system SHALL report the failure instead of returning an empty or all-unchanged comparison.

#### Scenario: One release without a record

- **WHEN** `1.2.0` has no dependency record and `1.0.0` and `1.1.0` do
- **THEN** the `1.2.0` column SHALL be marked as having no record
- **AND** the `1.1.0` to `1.2.0` comparison SHALL be reported as incomplete
- **AND** the `1.0.0` to `1.1.0` comparison SHALL be reported normally

#### Scenario: Neither side of an interval has a record

- **WHEN** two adjacent releases both have no dependency record
- **THEN** their comparison SHALL be reported as incomplete
- **AND** it MUST NOT report that nothing changed

#### Scenario: The dependency source is unreachable

- **WHEN** the dependency source does not answer
- **THEN** the request SHALL report the failure with a dependency source error
- **AND** the page SHALL show the failure rather than an empty comparison

#### Scenario: The repository is not registered

- **WHEN** the repository resolves to the placeholder application and the source therefore holds no record
- **THEN** the comparison SHALL be incomplete with every column marked
- **AND** the page SHALL state that the application has no dependency records

### Requirement: Only direct dependencies of the application are compared

The compared set SHALL be the dependencies the application itself declares. Packages the dependency source reports as pulled in transitively SHALL NOT appear in the matrix, and the page SHALL state that its scope is the application's direct dependencies.

#### Scenario: A transitive package moves

- **WHEN** a package that the application does not declare changes version between two releases
- **THEN** it SHALL NOT appear in the matrix
- **AND** the comparison SHALL be unaffected

#### Scenario: Scope is stated

- **WHEN** a comparison is displayed
- **THEN** the page SHALL state that only the application's direct dependencies are compared

### Requirement: Refresh bypasses the cached reading

The system SHALL accept a refresh flag that reads every selected release from the dependency source again instead of from the cache, and SHALL serve an unrefreshed request from the cache. A refresh SHALL NOT require a management role beyond the authenticated user.

#### Scenario: Refresh reads through

- **WHEN** a request carries the refresh flag
- **THEN** every selected release SHALL be read from the dependency source again

#### Scenario: A repeated view is served from the cache

- **WHEN** the same comparison is requested again without the refresh flag
- **THEN** the releases SHALL be served from the cache

### Requirement: The selection is shareable

The system SHALL reflect the selected application and its releases in the page URL, and opening such a URL SHALL restore the same comparison in the same order.

#### Scenario: Shared comparison link

- **WHEN** a user shares the URL of an App Diff comparison
- **THEN** opening it SHALL restore the application, the selected releases and their order

### Requirement: Comparison access is read-only

Viewing an App Diff comparison SHALL be available to any authenticated user, and the capability SHALL NOT expose any way to write to the dependency source, the git providers or the release records.

#### Scenario: Authenticated user views a comparison

- **WHEN** an authenticated user opens an App Diff comparison
- **THEN** the comparison SHALL be served without requiring a management role

### Requirement: Release tooling navigation distinguishes the entry points

The Releases navigation group SHALL gain an entry for the application-level comparison, labelled App Diff, without changing the labels, routes or behaviour of the existing repository comparison, release notes and dependency graph entries. The new entry's label SHALL be localized in every supported language.

#### Scenario: Menu labels

- **WHEN** a user opens the Releases menu
- **THEN** it SHALL offer App Diff alongside the existing entries
- **AND** the existing labels SHALL read as they did before this change

#### Scenario: The existing pages are undisturbed

- **WHEN** a user opens the repository comparison, release notes or dependency graph
- **THEN** each SHALL behave as it did before this change

### Requirement: The code axis is reported together with the dependency axis

For every pair of adjacent releases whose releases both have a record, the system SHALL report the commits between them, so that a release whose dependencies did not move is not read as a release in which nothing happened: a tag can be moved to a new commit while the versions it pins stay identical, and such a rebuild would otherwise read as an empty comparison. The commit delta SHALL be reported in both directions - what the later release adds, and what it does not contain of the earlier one - and each list SHALL say whether it was capped.

#### Scenario: A pair reports the commits between its releases

- **WHEN** two adjacent releases differ in commits
- **THEN** the commits the later release adds SHALL be reported for that pair
- **AND** the commits of the earlier release the later one does not contain SHALL be reported separately
- **AND** each list SHALL state whether it was capped

#### Scenario: Dependencies unchanged but commits changed

- **WHEN** every dependency carries the same version in two adjacent releases and the later release carries commits
- **THEN** the dependency summary for that pair SHALL report no changes
- **AND** the commits SHALL still be reported for that pair
- **AND** the view SHALL state that commits moved while the dependencies did not

### Requirement: A code axis that cannot be read degrades on its own

When the commits between two adjacent releases cannot be read - the git provider is unreachable, or it does not know one of the release refs, which the dependency source's key for a release need not be - the system SHALL record the reason for that pair, SHALL leave the dependency axis of that pair and every other pair intact, and MUST NOT report such a pair as a pair with no commits. The dependency axis alone SHALL remain a usable answer.

#### Scenario: The provider does not know a release ref

- **WHEN** the git provider cannot resolve one of the release refs
- **THEN** that pair's code axis SHALL carry the reason it could not be read
- **AND** that pair's dependency comparison SHALL still be reported

#### Scenario: The provider is unreachable

- **WHEN** the git provider cannot be reached at all
- **THEN** every pair's code axis SHALL carry the reason
- **AND** the comparison SHALL NOT be presented as a comparison with no commits
