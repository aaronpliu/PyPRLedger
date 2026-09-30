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

### Requirement: One comparison answers the containment question and the target-side additions

The system SHALL expose a single comparison operation that, for a source release and a target release, returns the containment verdict, the commits the target is missing and the commits the target adds. It MUST NOT require a second endpoint (or a separate "merge check" step) to answer either part, and the added direction SHALL NOT influence the verdict.

#### Scenario: One request returns everything
- **WHEN** a user compares two releases
- **THEN** the response SHALL contain the verdict, the missing commits and the added commits
- **AND** no second request SHALL be needed to obtain them

#### Scenario: The added direction does not decide the verdict
- **WHEN** the target adds commits while containing everything from the source
- **THEN** the verdict SHALL still be contained
- **AND** the added commits SHALL carry their own completeness flag

#### Scenario: Details are capped, counts are not
- **WHEN** a comparison has more difference commits than the render limit
- **THEN** the rendered lists SHALL be capped and flagged
- **AND** the reported counts SHALL remain complete or explicitly inconclusive

### Requirement: The baseline is part of the comparison and stored per repository

The comparison SHALL accept one optional baseline ref. When it is omitted, the baseline stored for the repository SHALL be used unless the caller opts out, and the response SHALL state the effective baseline, whether it came from storage, and how many difference commits it filtered out. The baseline SHALL narrow both the missing and the added direction. Storing and clearing it SHALL require the management permission, and both SHALL be available from the same tool that runs the comparison.

#### Scenario: Baseline narrows both directions
- **WHEN** a baseline is applied
- **THEN** difference commits that already existed at that baseline SHALL be excluded from missing and from added
- **AND** the response SHALL report how many were filtered out

#### Scenario: Stored baseline drives the routine comparison
- **WHEN** a baseline is stored for the repository and the caller supplies none
- **THEN** the comparison SHALL use the stored baseline
- **AND** the response SHALL mark it as coming from storage

#### Scenario: Narrowing can be declined
- **WHEN** the caller opts out of the stored baseline and supplies none
- **THEN** the comparison SHALL run over the whole history of both refs
- **AND** the response SHALL report that no baseline was applied

#### Scenario: Missing commits are actionable
- **WHEN** the verdict is missing
- **THEN** each missing commit SHALL be listed with its identity and a link to the provider page
- **AND** the list SHALL indicate when only part of a larger missing set is rendered

#### Scenario: Inconclusive verdict guides the user
- **WHEN** the verdict is inconclusive
- **THEN** the tool SHALL show the limit that was hit and how to raise it
- **AND** it SHALL NOT suggest that the release is verified

#### Scenario: Management permission to edit the baseline
- **WHEN** a user without the management permission tries to store or clear a baseline
- **THEN** the request SHALL be rejected with `403`

### Requirement: Rendered detail never decides the verdict

Commit lists SHALL be treated as rendered material: the response SHALL cap them for display and flag the cap, while the verdict and the counts MUST NOT depend on them. Every reported count SHALL either be complete or explicitly marked as incomplete.

#### Scenario: Capped detail with a definitive verdict
- **WHEN** a response includes detail lists capped for display while both difference scans completed
- **THEN** the verdict SHALL remain definitive
- **AND** the cap SHALL apply only to the rendered lists

#### Scenario: An incomplete scan is never a pass
- **WHEN** the missing direction could not be enumerated completely
- **THEN** the verdict SHALL be inconclusive
- **AND** the added direction's completeness SHALL be reported separately without turning the verdict into a pass
