# Export All Reviews

## Purpose

Allow exporting all filtered review data without pagination limits by using `page_size=0` as a sentinel value on the existing `GET /api/v1/reviews` endpoint, enabling complete exports to PDF, Excel, CSV, or JSON.

## Requirements

### Requirement: Export all filtered reviews via page_size=0 sentinel
The system SHALL support `page_size=0` as a sentinel value on the `GET /api/v1/reviews` endpoint to return ALL matching records without pagination slicing. All existing filters (project, repo, user, status, date range, search, severity, etc.) SHALL still apply.

#### Scenario: Export all reviews without pagination
- **WHEN** a user sends `GET /api/v1/reviews?page_size=0&project_key=PROJ-A`
- **THEN** the system returns ALL reviews matching the filter criteria in a single response
- **AND** the response's `total` field SHALL reflect the total count
- **AND** the response's `page` and `page_size` fields SHALL be 1 and 0 respectively

#### Scenario: page_size=0 returns more than 100 records
- **WHEN** a user sends `GET /api/v1/reviews?page_size=0` and 250 records match the filters
- **THEN** all 250 records SHALL be returned in `items`

#### Scenario: Normal pagination still works
- **WHEN** a user sends `GET /api/v1/reviews?page=1&page_size=20`
- **THEN** only 20 records SHALL be returned (unchanged behavior)

### Requirement: Frontend export uses page_size=0 for "All Filtered Data"
When the user selects "Export All Filtered Data (across all pages)", the system SHALL call `GET /api/v1/reviews` with `page_size=0` to fetch all matching records.

#### Scenario: Export all filtered data
- **WHEN** a user clicks "Export" → "All Filtered Data (across all pages)" → selects a format
- **THEN** the system fetches ALL matching records using `page_size=0`
- **AND** generates the export file with all records, not just the first 100

#### Scenario: Export current page (unchanged)
- **WHEN** a user selects "Current Page Only (N items)"
- **THEN** the system uses the already-loaded table data (unchanged behavior)
