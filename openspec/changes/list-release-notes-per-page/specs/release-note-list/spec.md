## ADDED Requirements

### Requirement: Every release of the page is readable

The reading column SHALL render every release of the current page with its notes, not only the selected one, so a reader can take in a page of releases without selecting each of them.

#### Scenario: A page holding several releases
- **WHEN** the releases tab shows a page of several releases
- **THEN** the reading column SHALL render one entry per release of that page
- **AND** each entry SHALL include the notes of its release

#### Scenario: A single release on the page
- **WHEN** the page holds one release
- **THEN** the reading column SHALL render that one entry

#### Scenario: The order of the entries
- **WHEN** the entries are rendered
- **THEN** they SHALL follow the order of the releases (newest first), the same order as the navigator

### Requirement: Pagination covers the whole set and is reachable from the notes

The reading column SHALL offer pagination for the repository's releases, sharing its page and page size with the navigator, so a reader can move through the whole set from where the notes are read.

#### Scenario: More releases than one page
- **WHEN** the repository holds more releases than one page
- **THEN** a pager SHALL be available in the reading column
- **AND** it SHALL report the total number of releases

#### Scenario: Changing the page from either column
- **WHEN** the reader changes the page or the page size in either column
- **THEN** both columns SHALL show the same page of releases

#### Scenario: Fitting a page to the reader
- **WHEN** a reader picks a smaller page size
- **THEN** the reading column SHALL render at most that many entries

### Requirement: An entry carries the identity of its release

Each entry SHALL name its release and carry its state: the release name and tag, and the latest / pre-release / draft badges that apply to it.

#### Scenario: A draft entry
- **WHEN** an entry belongs to a draft release
- **THEN** the entry SHALL be marked as a draft

#### Scenario: A pre-release entry
- **WHEN** an entry belongs to a pre-release
- **THEN** the entry SHALL be marked as a pre-release

#### Scenario: The latest release
- **WHEN** an entry is the repository's latest release
- **THEN** the entry SHALL be marked as the latest

### Requirement: An entry carries the actions of its release

Each entry SHALL offer the actions that apply to its own release, under the same permissions as the page: editing, publishing, pushing and deleting for the managing roles, and exporting and copying for any reader, together with the provider link when the release has one.

#### Scenario: A reader with read permission
- **WHEN** a reader without managing rights looks at an entry
- **THEN** the entry SHALL offer exporting and copying its notes
- **AND** it SHALL NOT offer editing, publishing or deleting

#### Scenario: Acting without selecting first
- **WHEN** a manager activates an action on an entry that is not the one in focus
- **THEN** the action SHALL apply to that entry's release

### Requirement: The navigator jumps to an entry

Acting on a release in the navigator SHALL bring that release into view in the reading column and mark it, instead of replacing the column's content.

#### Scenario: Jumping to a release
- **WHEN** the reader activates an entry in the navigator
- **THEN** the reading column SHALL scroll to that release's entry
- **AND** the other entries SHALL remain readable

#### Scenario: Jumping to a release on another page
- **WHEN** the reader jumps to a release that is not on the current page
- **THEN** the page holding it SHALL be loaded
- **AND** the reading column SHALL then bring that entry into view

### Requirement: The editor takes over the column

While a release is being drafted or edited the reading column SHALL render the editor, and closing it SHALL return the reader to the list of entries.

#### Scenario: Drafting a release
- **WHEN** the reader starts a draft from the navigator or from an entry
- **THEN** the reading column SHALL render the editor

#### Scenario: Closing the editor
- **WHEN** the reader closes the editor
- **THEN** the reading column SHALL render the entries of the page again

### Requirement: A page never ends up empty while releases exist

After a release is deleted, or the page size changes while a later page is shown, the page SHALL be adjusted so that the reader does not land on an empty list while the repository still holds releases.

#### Scenario: Deleting the last release of the last page
- **WHEN** deleting the only release of the last page leaves no releases on it
- **THEN** the previous page that holds releases SHALL be shown

#### Scenario: Shrinking the page size
- **WHEN** the page size changes so that the current page no longer exists
- **THEN** the last page that holds releases SHALL be shown

### Requirement: The tags tab is unchanged

Switching to the tags tab SHALL keep its column rendering the commits of the selected tag, with its own tag pagination.

#### Scenario: Opening the tags tab
- **WHEN** the reader switches to the tags tab
- **THEN** the reading column SHALL show the commits of the selected tag
- **AND** the releases of the page SHALL not be rendered in it

### Requirement: Loading and empty states

While a page is loading the reading column SHALL say so, and a repository without releases SHALL explain what to do next instead of rendering an empty list.

#### Scenario: Loading a page
- **WHEN** a page of releases is being loaded
- **THEN** the reading column SHALL show a loading state

#### Scenario: A repository without releases
- **WHEN** the repository has no releases at all
- **THEN** the reading column SHALL invite the reader to draft the first release

### Requirement: Long notes are collapsed

An entry whose notes are long SHALL be rendered collapsed with a control that expands them, so a page of long notes stays readable. An entry whose notes fit SHALL NOT offer that control. Collapsing SHALL be a reading aid only: it SHALL NOT change what is stored, and an export SHALL still carry the notes in full.

#### Scenario: A long note
- **WHEN** an entry's notes are longer than the collapse threshold
- **THEN** the entry SHALL render them collapsed
- **AND** it SHALL offer a control that expands them

#### Scenario: A short note
- **WHEN** an entry's notes are within the collapse threshold
- **THEN** the entry SHALL render them in full and SHALL NOT offer an expand control

#### Scenario: Expanding and collapsing again
- **WHEN** the reader expands an entry's notes
- **THEN** the entry SHALL show them in full and the control SHALL collapse them again

#### Scenario: Collapsing does not change the release
- **WHEN** the notes of an entry are collapsed
- **THEN** the stored notes SHALL be unchanged
- **AND** exporting that release SHALL still write the notes in full
