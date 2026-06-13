## 1. Backend: Allow page_size=0 sentinel

- [x] 1.1 In `src/api/v1/endpoints/reviews.py` line 634, change `page_size` validation from `ge=1` to `ge=0` to allow `page_size=0` as a sentinel value
- [x] 1.2 In `src/services/review_service.py` in `list_reviews()` around line 1084, add a check: if `page_size == 0`, skip the pagination slice and return all `flattened_reviews` instead of `flattened_reviews[start:end]`

## 2. Frontend: Use page_size=0 for export

- [x] 2.1 In `src/views/reviews/ReviewListView.vue` line 1144, change `page_size: 100` to `page_size: 0` in the `fetchAllDataForExport()` function
