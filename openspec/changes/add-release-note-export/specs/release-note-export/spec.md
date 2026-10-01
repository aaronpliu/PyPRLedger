## ADDED Requirements

### Requirement: Export a chosen set of releases

The system SHALL package the stored release notes of the requested releases into one markdown document and return it together with the number of releases it holds and a suggested filename. A single release SHALL produce a document holding exactly that release.

#### Scenario: One release
- **WHEN** a user exports a single release
- **THEN** the returned document SHALL contain that release only
- **AND** the reported count SHALL be one

#### Scenario: Several releases
- **WHEN** a user exports several releases at once
- **THEN** the document SHALL contain one section per release
- **AND** the reported count SHALL match the number of releases written

### Requirement: Export every matching release

The system SHALL be able to export the whole filtered set of releases of a repository - every release, or only the published ones - without requiring the caller to enumerate them first.

#### Scenario: Every published release
- **WHEN** the export asks for every published release of a repository
- **THEN** the document SHALL contain all of them
- **AND** drafts SHALL be left out

#### Scenario: The set exceeds the export bound
- **WHEN** more releases match than one export may hold
- **THEN** the export SHALL write the newest ones up to the bound
- **AND** it SHALL report that the document is not the whole set

### Requirement: The selection mode is explicit

A request SHALL carry either an explicit list of release ids or a request for the whole filtered set, and the system SHALL reject a request that carries neither, or both.

#### Scenario: No selection
- **WHEN** a request carries neither ids nor a request for the whole set
- **THEN** it SHALL be rejected as invalid

#### Scenario: Contradictory selection
- **WHEN** a request carries ids and asks for the whole set at the same time
- **THEN** it SHALL be rejected as invalid

#### Scenario: More ids than one export may hold
- **WHEN** a request lists more ids than the export bound allows
- **THEN** it SHALL be rejected as invalid instead of silently exporting a subset

### Requirement: Document shape

The document SHALL carry a title, a summary line naming the repository, the number of releases and the export date, and one section per release. Each section SHALL start with a heading holding the release name and tag, SHALL state in that heading when the release is a draft or a pre-release, and SHALL then carry the body of the notes; a released version SHALL carry nothing but its notes. Sections SHALL be separated by a horizontal rule.

#### Scenario: A section names its release
- **WHEN** a released version is written into the document
- **THEN** its section SHALL hold only the heading (the release name and its tag) and the notes
- **AND** no per-release metadata (tag, status, release date or author) SHALL be written

#### Scenario: A draft or a pre-release
- **WHEN** a release is a draft or a pre-release
- **THEN** its heading SHALL state which of the two applies
- **AND** the rest of the section SHALL still be the notes alone

#### Scenario: A release without notes
- **WHEN** a release has an empty body
- **THEN** its section SHALL state that no notes were written instead of leaving a gap

### Requirement: Bodies are exported verbatim

The exported body of a release SHALL be the stored markdown, without rewriting, re-linking or re-generating it.

#### Scenario: A body holding JIRA keys and mentions
- **WHEN** a stored body holds plain ticket keys or author mentions
- **THEN** the document SHALL contain them exactly as stored
- **AND** the export SHALL not depend on the JIRA configuration of the deployment

### Requirement: Ordering matches the release list

The document SHALL order the releases the way the release note list orders them for the same repository - newest first - so the export matches what the user saw and the most recent release is the first thing a reader meets.

#### Scenario: Drafts without a release date
- **WHEN** the selected releases include drafts, which have no release date
- **THEN** they SHALL be ordered by the same fallback the list uses
- **AND** the export SHALL be stable across repeated calls

### Requirement: Skipped releases are reported

Release ids that no longer exist or do not belong to the repository SHALL be skipped and reported, and the export SHALL still succeed with the rest.

#### Scenario: A release was deleted after it was selected
- **WHEN** a request holds an id of a release that no longer exists
- **THEN** the export SHALL succeed with the remaining releases
- **AND** the missing id SHALL be reported with the response

#### Scenario: An id of another repository
- **WHEN** a request holds an id belonging to a different repository
- **THEN** it SHALL be skipped and reported, and never written into the document

### Requirement: The export only reads

Exporting SHALL require the same read permission as listing the releases of a repository, SHALL leave the stored releases untouched, and SHALL only export releases that were saved.

#### Scenario: A reader without manage rights
- **WHEN** a user with read permission exports releases
- **THEN** the export SHALL succeed

#### Scenario: Drafts being edited
- **WHEN** a release is being edited but not saved yet
- **THEN** the export SHALL contain the stored notes, not the editor content

### Requirement: Suggested filename

The response SHALL carry a filename that distinguishes one release from several and is safe on every platform, so a tag holding path separators or spaces cannot produce an invalid name.

#### Scenario: A tag with characters that are invalid in a filename
- **WHEN** the exported release has a tag such as `release/1.0.0` or a tag with spaces
- **THEN** the suggested filename SHALL contain no character that is invalid in a filename
- **AND** it SHALL stay recognisable

### Requirement: Choosing the versions in the page

The release notes page SHALL let the user choose which releases to export: a control per release in the list, a way to select every release of the repository without paging through the list, and an action that exports the selection with its count. The page SHALL also offer exporting the release that is currently open, and SHALL report what was skipped.

#### Scenario: Selecting a few releases
- **WHEN** the user selects releases in the list and starts the export
- **THEN** only the selected releases SHALL be requested
- **AND** the download SHALL use the filename the server suggested

#### Scenario: Nothing selected
- **WHEN** no release is selected
- **THEN** the export action SHALL be unavailable

#### Scenario: Exporting the open release
- **WHEN** the user exports the release currently open
- **THEN** a document holding that release SHALL be downloaded without going through the list selection

#### Scenario: Part of the selection is gone
- **WHEN** the export reports skipped releases
- **THEN** the page SHALL still download the document and SHALL tell the user how many releases were skipped

### Requirement: The open release can be copied to the clipboard

For a single release the page SHALL be able to put the exported document on the clipboard instead of downloading it, using the same document the download would produce. Copying SHALL NOT be offered for a batch, and a copy that the platform refuses SHALL be reported rather than appearing to succeed.

#### Scenario: Copying one release
- **WHEN** the user copies the release that is open
- **THEN** the clipboard SHALL hold the same document the download of that release would produce
- **AND** the page SHALL confirm the copy

#### Scenario: The clipboard is unavailable
- **WHEN** the clipboard cannot be written to (a non-secure context, or a denied permission)
- **THEN** the page SHALL report that the copy failed and SHALL point at the download instead
- **AND** the export SHALL not be lost
