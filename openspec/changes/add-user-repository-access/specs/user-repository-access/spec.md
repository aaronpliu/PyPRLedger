## ADDED Requirements

### Requirement: Visibility grants are repository pairs

A visibility grant SHALL identify exactly one repository by the pair `(project_key, repository_slug)`. The system MUST NOT accept a `repository_slug` without a `project_key` as a grant, and MUST NOT treat a `project_key` alone as permission to see every repository in that project.

#### Scenario: A grant is created
- **WHEN** an administrator grants a subject `(project_key="CORE", repository_slug="ledger-api")`
- **THEN** exactly one grant row SHALL exist for that subject and that pair
- **AND** the subject SHALL have no grant for any other repository in `CORE` unless one was granted explicitly

#### Scenario: The same slug exists in two projects
- **WHEN** `(CORE, ledger-api)` and `(PAY, ledger-api)` both exist in the repository catalogue
- **THEN** a grant for one of them SHALL NOT satisfy a check for the other
- **AND** both pairs SHALL be storable for the same subject without a uniqueness conflict

#### Scenario: A duplicate pair is submitted
- **WHEN** a replacement request contains the same `(project_key, repository_slug)` more than once
- **THEN** the duplicate SHALL be collapsed before persistence
- **AND** the resulting grant count SHALL equal the number of distinct pairs

#### Scenario: An unknown pair is submitted
- **WHEN** a replacement request contains a pair that is absent from the project registry
- **THEN** the request SHALL be rejected with a client error
- **AND** no existing grant of that subject SHALL be modified

### Requirement: Grants belong to a system user or a git user

Every grant SHALL carry a `subject_type` of `auth_user` or `git_user` and a `subject_id` that is the primary key of the corresponding `AuthUser` or `User` row. The external business identifier `User.user_id` MUST NOT be used as `subject_id`. A human-readable `subject_username` snapshot SHALL be stored with the grant.

#### Scenario: A system user is granted repositories
- **WHEN** an administrator saves grants for an account in the system-user page
- **THEN** the rows SHALL use `subject_type="auth_user"` and that account's `AuthUser.id`
- **AND** `subject_username` SHALL hold the account username at save time

#### Scenario: A git user is granted repositories
- **WHEN** an administrator saves grants for an account in the git-user page
- **THEN** the rows SHALL use `subject_type="git_user"` and that account's `User.id`
- **AND** the rows SHALL NOT use `User.user_id`

#### Scenario: An unknown subject is addressed
- **WHEN** a request names a `subject_type`/`subject_id` that does not exist, or a `subject_type` outside the two allowed values
- **THEN** the system SHALL return a not-found or validation error respectively
- **AND** no grant row SHALL be created

### Requirement: A bound system user and its git user are one subject

When `AuthUser.user_id` references a `User`, the effective grant set of that identity SHALL be the union of its `auth_user` grants and the `git_user` grants of the linked `User`. A system account with no binding SHALL be read-only with respect to write authority, while still being able to read the information its own grants describe. `system_admin` SHALL remain unrestricted and writable even without a binding.

#### Scenario: Grants exist on both sides of a binding
- **WHEN** an account is linked to a git user and each side holds different repository pairs
- **THEN** the identity's effective grant set SHALL contain both sets of pairs
- **AND** a pair present on only one side SHALL be effective

#### Scenario: No git user is linked
- **WHEN** an account has `AuthUser.user_id = NULL`
- **THEN** its effective grant set SHALL consist only of its own `auth_user` rows
- **AND** the administrative interface SHALL display the unbound, read-only status

#### Scenario: Stage 0 authority
- **WHEN** this change is deployed
- **THEN** the union and read-only rules SHALL be defined and stored but SHALL NOT be enforced on any request
- **AND** no existing user SHALL gain or lose the ability to update a review

### Requirement: Administrators can read and atomically replace grants

The system SHALL expose a read operation and a full-replacement write operation for one subject's grants. A replacement SHALL delete the previous set and insert the submitted set in a single transaction, and SHALL be idempotent. Only `system_admin` SHALL be allowed to replace grants; reading grants SHALL require user-management permission. The `system_admin` check SHALL NOT rely on a cached permission row alone.

#### Scenario: Grants are replaced
- **WHEN** an administrator submits a replacement containing two pairs for a subject that previously held five
- **THEN** the subject SHALL hold exactly the two submitted pairs afterwards
- **AND** no partial state SHALL be observable if the insert fails

#### Scenario: The same replacement is submitted twice
- **WHEN** an identical replacement request is applied twice
- **THEN** the resulting grant set and row count SHALL be identical to a single application
- **AND** no duplicate row SHALL be created

#### Scenario: A non-admin attempts a replacement
- **WHEN** an authenticated user without `system_admin` submits a replacement
- **THEN** the request SHALL be rejected with a forbidden response
- **AND** the subject's grants SHALL remain unchanged

#### Scenario: An unauthenticated request
- **WHEN** a read or replacement request carries no valid token
- **THEN** the system SHALL reject it as unauthenticated
- **AND** no grant data SHALL be returned

### Requirement: Grant changes are audited

Every replacement SHALL write an audit record identifying the actor, the subject, the action and both the previous and the resulting grant sets. A backfill SHALL be recorded as a system action.

#### Scenario: An administrator edits grants
- **WHEN** a replacement adds two pairs and removes one
- **THEN** an audit record SHALL exist with `resource_type="repository_access"` and the subject as `resource_id`
- **AND** the record SHALL contain both the removed and the added pairs

#### Scenario: The change is replayed from the audit log
- **WHEN** an operator inspects the audit record
- **THEN** the before and after grant sets SHALL both be reconstructible from it

### Requirement: Stage 0 does not change read behaviour

Deploying this change SHALL NOT alter which reviews, projects, statistics, notifications or events any user can see, nor the order, total or payload of any existing read response. No existing review query, cache key, SSE fan-out, notification query, search, export or authentication response SHALL consult the new grant table. The feature gate `REPOSITORY_ISOLATION_ENABLED` SHALL exist, SHALL default to `False`, and SHALL NOT be read by any request path in this change.

#### Scenario: A review list is compared before and after
- **WHEN** the same review list request is issued before and after the deployment
- **THEN** the items, their order, the total and the response payload SHALL be identical
- **AND** no additional predicate SHALL have been applied to the query

#### Scenario: The gate is inspected
- **WHEN** an operator reads the configuration after deployment
- **THEN** `REPOSITORY_ISOLATION_ENABLED` SHALL be present with the value `False`
- **AND** no request SHALL behave differently because of it

#### Scenario: A review_admin signs in
- **WHEN** a `review_admin` opens the review list on the day of deployment
- **THEN** the visible reviews SHALL be exactly the same set as before the deployment
- **AND** the new grant table SHALL NOT have filtered any of them

### Requirement: Loose-launch backfill is safe and reportable

A backfill tool SHALL grant every existing `AuthUser` and every existing `User` every distinct `(project_key, repository_slug)` present in the project registry. It SHALL default to a dry run that writes nothing, SHALL be idempotent when applied, and SHALL emit a reconciliation report listing subject count, pair count, expected row count, accounts with no git-user binding and subjects with no grants.

#### Scenario: A dry run is executed
- **WHEN** an operator runs the backfill without an apply flag
- **THEN** no grant row SHALL be written
- **AND** a report SHALL be produced with the expected counts and the unbound-account list

#### Scenario: The backfill is applied twice
- **WHEN** the apply step is executed twice against the same data
- **THEN** the row count SHALL equal subject count multiplied by distinct pair count
- **AND** the second run SHALL NOT increase the row count

#### Scenario: Every current user keeps their reach
- **WHEN** the backfill completes
- **THEN** every existing subject SHALL hold a grant for every repository that existed before the change
- **AND** no subject SHALL be left without grants

### Requirement: Grant rows stay consistent with their subjects

Grant rows SHALL be unique per `(subject_type, subject_id, project_key, repository_slug)`. Deleting a system user or a git user SHALL delete that subject's grant rows. Removing a project-registry entry SHALL NOT cascade-delete historical grants, and a grant SHALL NOT carry a foreign key to either subject table.

#### Scenario: A user is deleted
- **WHEN** an administrator deletes a system user or a git user
- **THEN** no grant row for that `subject_type`/`subject_id` SHALL remain

#### Scenario: A repository leaves the registry
- **WHEN** a project-registry row is removed
- **THEN** the corresponding grants SHALL be retained for audit and reconciliation
- **AND** a later replacement request containing that pair SHALL be rejected as an unknown pair

### Requirement: The old Resource Scope UI is retired

The administrative interfaces SHALL NOT offer Global/Project/Repository scope selection for role assignments or delegations. Role assignment submissions from those screens SHALL always use `resource_type="global"` and a null `resource_id`. Existing stored columns and historical rows SHALL remain, and the backend SHALL keep accepting the fields so older clients are not broken.

#### Scenario: An administrator assigns a role
- **WHEN** the role dialog is opened and submitted
- **THEN** no scope selector or resource-id field SHALL be rendered
- **AND** the submitted assignment SHALL be `global` with a null resource id

#### Scenario: An older client sends a scope
- **WHEN** a legacy client submits `resource_type="project"` and a `resource_id`
- **THEN** the request SHALL still be accepted
- **AND** no migration SHALL have dropped the underlying columns

### Requirement: The repository picker uses the existing catalogue

The grant-selection interface SHALL derive its project and repository choices from the existing project and repository catalogue endpoints, and SHALL present the pair `(project_key, repository_slug)` as the selectable unit. No new catalogue endpoint SHALL be required for this change.

#### Scenario: An administrator opens the picker
- **WHEN** the repository dialog is opened
- **THEN** the available projects and, for each selected project, its repositories SHALL be loaded from the existing catalogue endpoints
- **AND** the selection SHALL be expressed as project/repository pairs

#### Scenario: A replacement is saved
- **WHEN** the dialog is submitted
- **THEN** the UI SHALL show the number of repositories about to be granted
- **AND** the dialog SHALL communicate that saving replaces the entire previous set
