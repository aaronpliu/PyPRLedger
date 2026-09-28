## ADDED Requirements

### Requirement: Missing detection uses a provider-side set difference

The system SHALL determine whether a target release contains a source release by asking the git provider for the commits reachable from the source ref but not from the target ref. It MUST NOT derive that verdict by enumerating a release's commits and intersecting or matching them in memory. The source base ref SHALL be optional and SHALL only narrow the answer; the verdict MUST NOT depend on it being supplied.

#### Scenario: Source release fully contained
- **WHEN** every commit reachable from the source ref is also reachable from the target ref
- **THEN** the difference SHALL be empty and the verdict SHALL be contained
- **AND** the answer SHALL NOT require listing the target release's commits

#### Scenario: Commits missing from the target release
- **WHEN** commits are reachable from the source ref but not from the target ref
- **THEN** those commits SHALL be reported as missing with their ids
- **AND** the verdict SHALL be missing

#### Scenario: Shared history does not pollute the result
- **WHEN** the source and target lines share history older than the fork point
- **THEN** those shared commits SHALL NOT appear in the missing set
- **AND** only work unique to the source line SHALL be reported

#### Scenario: Narrowing with a source base ref
- **WHEN** a source base ref is supplied
- **THEN** only source commits after that base SHALL be considered
- **AND** the response SHALL state that the check was narrowed

#### Scenario: Large target release with a contained commit
- **WHEN** a commit belongs to a target release with more commits than any preview limit
- **THEN** the commit SHALL be reported as contained
- **AND** it MUST NOT be reported as missing because a listing was capped

### Requirement: A verdict is never derived from truncated data

The verdict SHALL be one of contained, missing or inconclusive. It SHALL be inconclusive whenever the difference scan did not complete, for example when the scan limit or a provider page cap was reached. An inconclusive result MUST NOT be reported as contained, and MUST NOT be presented to the user as a pass; it SHALL carry the limit that was hit, the number of commits found so far as a lower bound, and the way to raise the limit.

#### Scenario: Scan completed
- **WHEN** the difference scan reaches the end of the provider's result set
- **THEN** the verdict SHALL be contained or missing, and SHALL be presented as definitive

#### Scenario: Scan limit reached
- **WHEN** the difference scan stops because the scan limit was reached
- **THEN** the verdict SHALL be inconclusive
- **AND** the response SHALL include the scan limit and a lower bound of the missing count
- **AND** the user interface SHALL NOT render a success state for it

#### Scenario: Provider page cap reached
- **WHEN** a provider caps a page such that completeness cannot be proven
- **THEN** the result SHALL be treated as inconclusive rather than as complete

### Requirement: Supplied commits are checked individually against the target ref

When the caller supplies commit ids to check against a target release, the system SHALL ask the provider whether the target ref contains each commit, one query per commit. It MUST NOT answer by enumerating the target release's commits. Short commit ids SHALL be accepted and resolved by the provider.

#### Scenario: Contained commit in a huge release
- **WHEN** a supplied commit is an ancestor of the target ref
- **THEN** the result SHALL report it as included
- **AND** the answer MUST NOT depend on the size of the target release

#### Scenario: Commit not in the target release
- **WHEN** a supplied commit is not reachable from the target ref
- **THEN** the result SHALL report it as missing with a reason stating it is not reachable from the target ref
- **AND** the reason MUST NOT mention a truncation of an enumerated listing

#### Scenario: Short commit id
- **WHEN** a supplied commit id is a short SHA
- **THEN** the provider SHALL resolve it and the containment result SHALL be reported for the resolved commit

### Requirement: The routine check is cheap and payload-free by default

The check SHALL be executable without fetching commit payloads: the default mode SHALL collect commit ids only and SHALL NOT compute the reverse direction. Commit details SHALL be fetched only when requested, and only for the difference set, capped for rendering while the counts stay complete.

#### Scenario: Verdict-only run
- **WHEN** the caller requests a verdict without commit details
- **THEN** no commit details SHALL be fetched
- **AND** the number of missing commits SHALL still be complete or explicitly inconclusive

#### Scenario: Enriched run
- **WHEN** the caller requests commit details
- **THEN** details SHALL be fetched for the difference set only
- **AND** the response SHALL distinguish the complete missing count from the number of entries rendered in a capped preview

### Requirement: The routine per-build check is a preset with a saved baseline

The release comparison page SHALL provide a merge check preset that takes a source release ref, a baseline ref and a target release ref and presents a single verdict card with the missing commits as the actionable list. The baseline SHALL be stored per repository on the server and SHALL be editable from the preset, so the routine check does not require re-entering it.

#### Scenario: Saved baseline drives the routine check
- **WHEN** a baseline is stored for the repository and the user selects a source release and a target release
- **THEN** the preset SHALL run the check using the stored baseline without further input
- **AND** the verdict card SHALL state which baseline was used and whether the check was narrowed by it

#### Scenario: Missing commits are actionable
- **WHEN** the verdict is missing
- **THEN** each missing commit SHALL be listed with its identity and a link to the provider page
- **AND** the list SHALL indicate when only part of a larger missing set is rendered

#### Scenario: Inconclusive verdict guides the user
- **WHEN** the verdict is inconclusive
- **THEN** the card SHALL show the limit that was hit and how to raise it
- **AND** it SHALL NOT suggest that the release is verified

### Requirement: Comparison responses separate display previews from the verdict

Comparison and check responses SHALL keep the verdict independent of any commit preview: commit lists that are capped for display MUST NOT influence the verdict, and the response SHALL state explicitly whether the verdict is complete.

#### Scenario: Truncated preview with a definitive verdict
- **WHEN** a response includes commit lists capped for display while the difference scan completed
- **THEN** the verdict SHALL remain definitive
- **AND** the truncation SHALL apply only to the rendered lists

#### Scenario: Existing status field
- **WHEN** a comparison is served with the new verdict alongside the existing status field
- **THEN** the status SHALL remain consistent with the verdict, and the inconclusive case SHALL be expressed as its own value rather than as a pass
