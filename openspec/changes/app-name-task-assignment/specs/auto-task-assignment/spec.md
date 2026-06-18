## MODIFIED Requirements

### Requirement: conditions support project_key, repository_slug, app_name, PR user, branch, and status matching
The `conditions` JSON field SHALL support these optional keys. All present keys are ANDed. List values are ORed. Missing keys are wildcards. The `app_name` key SHALL resolve the incoming review's app name from ProjectRegistry and match against the condition values.

#### Scenario: Match by project_key only
- **WHEN** a rule has conditions `{"project_key": ["PROJ-A", "PROJ-B"]}`
- **AND** a review arrives for PROJ-A
- **THEN** the rule matches

#### Scenario: Match by project_key AND repository_slug
- **WHEN** a rule has conditions `{"project_key": ["PROJ-A"], "repository_slug": ["frontend"]}`
- **AND** a review arrives for PROJ-A/frontend
- **THEN** the rule matches
- **AND** a review arrives for PROJ-A/backend
- **THEN** the rule does NOT match

#### Scenario: Match by app_name
- **WHEN** a rule has conditions `{"app_name": ["member", "tv"]}`
- **AND** a review arrives for a project registered under the "member" app
- **THEN** the rule matches
- **AND** a review arrives for a project registered under the "football" app
- **THEN** the rule does NOT match

#### Scenario: Unknown reviews never match app_name conditions
- **WHEN** a rule has conditions `{"app_name": ["member"]}`
- **AND** a review arrives for a project that is registered as "Unknown"
- **THEN** the rule does NOT match

#### Scenario: app_name AND project_key conditions are ANDed
- **WHEN** a rule has conditions `{"app_name": ["member"], "project_key": ["PROJ-A"]}`
- **AND** a review arrives for PROJ-A under the "member" app
- **THEN** the rule matches
- **AND** a review arrives for PROJ-B under the "member" app
- **THEN** the rule does NOT match

#### Scenario: Match by source_branch_prefix
- **WHEN** a rule has conditions `{"source_branch_prefix": "hotfix/"}`
- **AND** a review arrives with source_branch `hotfix/critical-fix`
- **THEN** the rule matches
- **AND** a review arrives with source_branch `feature/new-thing`
- **THEN** the rule does NOT match

#### Scenario: Match by pull_request_user
- **WHEN** a rule has conditions `{"pull_request_user": ["alice", "bob"]}`
- **AND** a review arrives where pull_request_user is "alice"
- **THEN** the rule matches

#### Scenario: Match by pull_request_status
- **WHEN** a rule has conditions `{"pull_request_status": ["draft"]}`
- **AND** a review arrives with status "open"
- **THEN** the rule does NOT match
