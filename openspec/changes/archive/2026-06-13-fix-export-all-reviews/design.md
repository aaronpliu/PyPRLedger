## Context

The Reviews page "Export" function offers two scopes: "Current Page Only" and "All Filtered Data (across all pages)". The "All Filtered Data" option calls `fetchAllDataForExport()` which sends a request to `GET /api/v1/reviews` with `page_size=100` (the backend's maximum allowed value). It only fetches page 1, so any dataset larger than 100 records is truncated.

The backend's `ReviewService.list_reviews()` already loads ALL matching records from the database into memory before applying a Python pagination slice:

```
DB query → all matching rows loaded → flattened → slice(start, end) → response
                                                      ↑
                                              This is the bottleneck
```

The data is fully available — it's just being sliced off by the pagination logic.

## Goals / Non-Goals

**Goals:**
- Export all filtered reviews regardless of dataset size (100, 1000, or 10000 records)
- Reuse the existing endpoint and filtering logic — no new endpoints
- No fixed ceiling that will need bumping later
- Minimum code changes — leverage existing pagination infrastructure

**Non-Goals:**
- Streaming or async export (data is already loaded in memory, synchronous export is sufficient)
- Backend-generated file download (export is client-side using existing `ExportMenu.vue`)
- Changing the normal paginated UI behavior (only affects export flow)

## Decisions

### 1. `page_size=0` sentinel to signal "return all"

The existing endpoint accepts `page_size` with `ge=1, le=100`. Changing `ge=1` to `ge=0` allows `0` as a sentinel value. When `page_size=0`, the service skips the pagination slice and returns all flattened records.

This is a well-established REST pagination pattern. It:
- Reuses 100% of existing filtering, flattening, and enrichment logic
- Requires minimal backend changes (2 lines) and frontend changes (1 line)
- Has no fixed ceiling — works for any dataset size
- Cannot accidentally be triggered by normal UI pagination (which always sends 10/20/50/100)

**Alternatives considered:**

| Alternative | Why rejected |
|---|---|
| **Frontend pagination loop** — fetch page 1, get total, fetch remaining pages | N+1 roundtrips; slow for large datasets; complex error handling if data changes between requests |
| **Dedicated `/export` endpoint** — like audit logs | Over-engineered for this use case; duplicates filtering logic; export is client-side not server-side |
| **Increase `le=100` to `le=10000`** — fixed large number | Still has a ceiling; will need bumping again as data grows |
| **`all=true` query parameter** — separate boolean flag | Equivalent to `page_size=0` but introduces a new parameter name; `page_size=0` is more REST-idiomatic |

### 2. Validation change: `ge=1` → `ge=0` with `le=100` preserved

Allowing `page_size=0` but keeping `le=100` means:
- Normal UI pagination continues to work exactly as before (10/20/50/100)
- Export can request `page_size=0` to get all records
- The `le=100` cap still applies for any non-zero value, preventing accidental large requests from the UI

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| **Very large export (10,000+ records)** could be slow to transfer and render client-side | The export data is JSON-serialized and downloaded as a file — the browser handles it natively. For extremely large datasets, the bottleneck is network transfer, not the server |
| **Export includes all entity enrichment** (app_name, project info, pin status) which adds per-row processing overhead | This already runs for normal paginated requests. Export processing is identical, just without the slice |
| **Accidental `page_size=0` from UI code** | All normal pagination is driven by `el-pagination` which emits specific page sizes (10/20/50/100). Only `fetchAllDataForExport()` sends `page_size=0` |
