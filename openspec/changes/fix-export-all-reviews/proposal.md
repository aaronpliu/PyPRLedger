## Why

The Reviews page has an "Export" function that supports exporting all filtered data to PDF, Excel, CSV, or JSON. However, when the user selects "Export All Filtered Data (across all pages)", the export only returns a maximum of 100 records — the hardcoded `page_size` limit in the export function. With more reviews being added daily, this limit is increasingly hit, causing incomplete exports.

The root cause is that the export function calls the same paginated `GET /api/v1/reviews` endpoint with `page_size=100` and only fetches page 1, never iterating through additional pages. The backend already loads all matching records from the database before applying the pagination slice, so the data is available — it's just being truncated by the page_size cap.

## What Changes

- **Backend**: Allow `page_size=0` as a sentinel value on `GET /api/v1/reviews` meaning "return all matching records without pagination slicing"
- **Frontend**: In `fetchAllDataForExport()`, send `page_size=0` instead of `page_size=100` to get all records in a single request
- No new endpoints — reuses the existing paginated endpoint
- No fixed ceiling — works regardless of how many records exist

## Capabilities

### New Capabilities
- `export-all-reviews`: Export all filtered reviews without pagination limits, using `page_size=0` sentinel on the existing endpoint

### Modified Capabilities
*(No existing specs to modify)*

## Impact

- **Backend**: `src/api/v1/endpoints/reviews.py` — change `page_size` validation from `ge=1` to `ge=0`
- **Backend**: `src/services/review_service.py` — in `list_reviews()`, when `page_size == 0`, skip the pagination slice and return all records
- **Frontend**: `src/views/reviews/ReviewListView.vue` — change `page_size: 100` to `page_size: 0` in `fetchAllDataForExport()`
