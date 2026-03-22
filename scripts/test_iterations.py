import requests
import json

BASE_URL = "http://localhost:8000/api/v1"

def create_review(pull_request_id, commit_id, reviewer, comments, score):
    """Helper function to create a review"""
    response = requests.post(f"{BASE_URL}/reviews", json={
        "pull_request_id": pull_request_id,
        "pull_request_commit_id": commit_id,
        "project_key": "ECOM",
        "repository_slug": "frontend-store",
        "reviewer": reviewer,
        "pull_request_user": "alice_dev",
        "source_branch": "feature/shopping-cart",
        "target_branch": "main",
        "source_filename": "src/services/cart.py",
        "ai_suggestions": {"suggestion_1": "Test"},
        "reviewer_comments": comments,
        "score": score,
        "pull_request_status": "open"
    })
    return response.json()

print("==========================================")
print("Test: Multiple Iterations - Same Reviewer")
print("==========================================\n")

COMMIT_ID = "abc123def456"

print("📝 Creating Review 1 (Iteration 1)")
review1 = create_review("pr-test-iter", COMMIT_ID, "diana_reviewer", "First review - iteration 1", 7)
print(f"   ID: {review1.get('id')}, Iteration: {review1.get('review_iteration')}, Is Latest: {review1.get('is_latest_review')}")

print("\n📝 Creating Review 2 (Iteration 2) - Same Commit")
review2 = create_review("pr-test-iter", COMMIT_ID, "diana_reviewer", "Second review - iteration 2", 8)
print(f"   ID: {review2.get('id')}, Iteration: {review2.get('review_iteration')}, Is Latest: {review2.get('is_latest_review')}")

print("\n📝 Creating Review 3 (Iteration 3) - Same Commit")
review3 = create_review("pr-test-iter", COMMIT_ID, "diana_reviewer", "Third review - iteration 3", 9)
print(f"   ID: {review3.get('id')}, Iteration: {review3.get('review_iteration')}, Is Latest: {review3.get('is_latest_review')}")

print("\n📊 Querying all reviews")
response = requests.get(f"{BASE_URL}/reviews", params={
    "project_key": "ECOM",
    "repository_slug": "frontend-store",
    "pull_request_id": "pr-test-iter"
})
data = response.json()
print(f"   Total reviews: {data.get('total')}")
for item in data.get('items', []):
    print(f"   - ID: {item['id']}, Reviewer: {item['reviewer']}, Iteration: {item['review_iteration']}, Is Latest: {item['is_latest_review']}")

print("\n==========================================")
if data.get('total') == 3:
    latest_count = sum(1 for item in data['items'] if item.get('is_latest_review'))
    if latest_count == 1:
        print("✅ Test PASSED! All 3 iterations created, only 1 marked as latest")
    else:
        print(f"❌ Test FAILED! Expected 1 latest review, found {latest_count}")
else:
    print(f"❌ Test FAILED! Expected 3 reviews, found {data.get('total')}")
print("==========================================")