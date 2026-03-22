#!/bin/bash

# Test: Same reviewer reviews the same file multiple times
# This tests the review iteration mechanism

echo "=========================================="
echo "Test: Multiple Iterations - Same Reviewer"
echo "=========================================="
echo ""

# Clean up any existing test data first
echo "🧹 Cleaning up old test data..."
python3 << 'PYTHON_CLEAN'
from sqlalchemy import create_engine, text

engine = create_engine('mysql+pymysql://root:0000abc!@192.168.64.2:3306/code_review')

with engine.connect() as conn:
    result = conn.execute(text("DELETE FROM pull_request_review WHERE pull_request_id LIKE 'pr-iter-test%'"))
    print(f"   Deleted {result.rowcount} old test review(s)")
    conn.commit()
PYTHON_CLEAN

echo ""
echo "📝 Creating Review 1: diana_reviewer reviews cart.py (Iteration 1)"
echo "---"
RESPONSE1=$(curl -s -X POST "http://localhost:8000/api/v1/reviews" \
  -H "Content-Type: application/json" \
  -d '{
    "pull_request_id": "pr-iter-test",
    "pull_request_commit_id": "commit-v1",
    "project_key": "ECOM",
    "repository_slug": "frontend-store",
    "reviewer": "diana_reviewer",
    "pull_request_user": "alice_dev",
    "source_branch": "feature/shopping-cart",
    "target_branch": "main",
    "source_filename": "src/services/cart.py",
    "ai_suggestions": {"suggestion_1": "Add type hints"},
    "reviewer_comments": "First review: Please add type hints.",
    "score": 7,
    "pull_request_status": "open"
  }')

echo "$RESPONSE1" | python3 -c "import sys, json; d=json.load(sys.stdin); print(f'Review ID: {d.get(\"id\")}, Iteration: {d.get(\"review_iteration\")}, Comments: {d.get(\"reviewer_comments\")}, Is Latest: {d.get(\"is_latest_review\")}')"
echo ""

sleep 1

echo "📝 Creating Review 2: diana_reviewer reviews SAME file again (Should be Iteration 2)"
echo "---"
RESPONSE2=$(curl -s -X POST "http://localhost:8000/api/v1/reviews" \
  -H "Content-Type: application/json" \
  -d '{
    "pull_request_id": "pr-iter-test",
    "pull_request_commit_id": "commit-v1",
    "project_key": "ECOM",
    "repository_slug": "frontend-store",
    "reviewer": "diana_reviewer",
    "pull_request_user": "alice_dev",
    "source_branch": "feature/shopping-cart",
    "target_branch": "main",
    "source_filename": "src/services/cart.py",
    "ai_suggestions": {"suggestion_1": "Add unit tests", "suggestion_2": "Improve error handling"},
    "reviewer_comments": "Second review: Good improvements! Now please add unit tests.",
    "score": 8,
    "pull_request_status": "open"
  }')

echo "$RESPONSE2" | python3 -c "import sys, json; d=json.load(sys.stdin); print(f'Review ID: {d.get(\"id\")}, Iteration: {d.get(\"review_iteration\")}, Comments: {d.get(\"reviewer_comments\")}, Is Latest: {d.get(\"is_latest_review\")}')"
echo ""

sleep 1

echo "📝 Creating Review 3: diana_reviewer reviews SAME file third time (Should be Iteration 3)"
echo "---"
RESPONSE3=$(curl -s -X POST "http://localhost:8000/api/v1/reviews" \
  -H "Content-Type: application/json" \
  -d '{
    "pull_request_id": "pr-iter-test",
    "pull_request_commit_id": "commit-v1",
    "project_key": "ECOM",
    "repository_slug": "frontend-store",
    "reviewer": "diana_reviewer",
    "pull_request_user": "alice_dev",
    "source_branch": "feature/shopping-cart",
    "target_branch": "main",
    "source_filename": "src/services/cart.py",
    "ai_suggestions": {"suggestion_1": "Perfect!"},
    "reviewer_comments": "Third review: Excellent work! Ready to merge.",
    "score": 9,
    "pull_request_status": "approved"
  }')

echo "$RESPONSE3" | python3 -c "import sys, json; d=json.load(sys.stdin); print(f'Review ID: {d.get(\"id\")}, Iteration: {d.get(\"review_iteration\")}, Comments: {d.get(\"reviewer_comments\")}, Is Latest: {d.get(\"is_latest_review\")}')"
echo ""

sleep 1

echo "📊 Querying ALL reviews for this PR and file (should show all 3 iterations)"
echo "---"
curl -s "http://localhost:8000/api/v1/reviews?project_key=ECOM&repository_slug=frontend-store&pull_request_id=pr-iter-test&source_filename=src/services/cart.py" | python3 << 'PYTHON_QUERY'
import sys, json
data = json.load(sys.stdin)
print(f"Total reviews found: {data['total']}")
print("")
for i, review in enumerate(data['items'], 1):
    print(f"{i}. ID: {review['id']}, Iteration: {review['review_iteration']}, Is Latest: {review['is_latest_review']}")
    print(f"   Comments: {review['reviewer_comments']}")
    print(f"   Score: {review['score']}, Status: {review['pull_request_status']}")
    print(f"   Commit: {review['pull_request_commit_id']}")
    print("")
PYTHON_QUERY

echo "=========================================="
echo "✅ Test completed!"
echo "=========================================="
echo ""
echo "Expected Results:"
echo "  ✓ Three separate review records created"
echo "  ✓ Same reviewer (diana_reviewer)"
echo "  ✓ Same file (src/services/cart.py)"
echo "  ✓ Same commit (commit-v1)"
echo "  ✓ Different iterations (1, 2, 3)"
echo "  ✓ Only the latest review marked as is_latest_review=true"
echo "  ✓ Each review has different comments and scores"
echo ""