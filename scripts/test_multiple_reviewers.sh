#!/bin/bash

# Test Script: Multiple Reviewers Review Same File
# This script tests the scenario where multiple reviewers review the same file

BASE_URL="http://localhost:8000"
API_ENDPOINT="${BASE_URL}/api/v1/reviews"

echo "=========================================="
echo "Test: Multiple Reviewers - Same File"
echo "=========================================="
echo ""

# Scenario Setup:
# - Project: ECOM (E-Commerce Platform)
# - Repository: frontend-store
# - PR: pr-test-001
# - File: src/services/cart.py
# - Reviewer 1: diana_reviewer
# - Reviewer 2: eve_senior
# - PR Author: alice_dev

echo "📝 Creating Review 1: diana_reviewer reviews cart.py"
echo "---"

REVIEW1_RESPONSE=$(curl -s -X POST "${API_ENDPOINT}" \
  -H "Content-Type: application/json" \
  -d '{
    "pull_request_id": "pr-test-001",
    "pull_request_commit_id": "abc123def456",
    "project_key": "ECOM",
    "repository_slug": "frontend-store",
    "reviewer": "diana_reviewer",
    "pull_request_user": "alice_dev",
    "source_branch": "feature/shopping-cart",
    "target_branch": "main",
    "git_code_diff": "diff --git a/src/services/cart.py b/src/services/cart.py\n@@ -10,7 +10,12 @@\n+    def calculate_total(self):\n+        # Calculate total price",
    "source_filename": "src/services/cart.py",
    "ai_suggestions": {
      "suggestion_1": "Add type hints for better code clarity",
      "suggestion_2": "Consider adding error handling for edge cases"
    },
    "reviewer_comments": "Great implementation! The logic looks solid. Just consider adding type hints.",
    "score": 8,
    "pull_request_status": "open",
    "metadata": {
      "labels": ["feature", "priority-high"],
      "review_type": "code_quality"
    }
  }')

echo "Response:"
echo "${REVIEW1_RESPONSE}" | python3 -m json.tool 2>/dev/null || echo "${REVIEW1_RESPONSE}"
echo ""
echo ""

# Wait a bit to ensure different timestamps
sleep 1

echo "📝 Creating Review 2: eve_senior reviews the SAME file"
echo "---"

REVIEW2_RESPONSE=$(curl -s -X POST "${API_ENDPOINT}" \
  -H "Content-Type: application/json" \
  -d '{
    "pull_request_id": "pr-test-001",
    "pull_request_commit_id": "abc123def456",
    "project_key": "ECOM",
    "repository_slug": "frontend-store",
    "reviewer": "eve_senior",
    "pull_request_user": "alice_dev",
    "source_branch": "feature/shopping-cart",
    "target_branch": "main",
    "git_code_diff": "diff --git a/src/services/cart.py b/src/services/cart.py\n@@ -10,7 +10,12 @@\n+    def calculate_total(self):\n+        # Calculate total price",
    "source_filename": "src/services/cart.py",
    "ai_suggestions": {
      "suggestion_1": "Excellent structure",
      "suggestion_2": "Add unit tests"
    },
    "reviewer_comments": "Looks good overall. Please add comprehensive unit tests for edge cases.",
    "score": 7,
    "pull_request_status": "open",
    "metadata": {
      "labels": ["feature", "needs-tests"],
      "review_type": "architecture"
    }
  }')

echo "Response:"
echo "${REVIEW2_RESPONSE}" | python3 -m json.tool 2>/dev/null || echo "${REVIEW2_RESPONSE}"
echo ""
echo ""

echo "📊 Querying all reviews for this PR and file"
echo "---"

QUERY_RESPONSE=$(curl -s "${API_ENDPOINT}?project_key=ECOM&repository_slug=frontend-store&pull_request_id=pr-test-001&source_filename=src/services/cart.py")

echo "Query Response:"
echo "${QUERY_RESPONSE}" | python3 -m json.tool 2>/dev/null || echo "${QUERY_RESPONSE}"
echo ""
echo ""

echo "=========================================="
echo "✅ Test completed!"
echo "=========================================="
echo ""
echo "Expected Results:"
echo "  ✓ Two separate review records created"
echo "  ✓ Different reviewers (diana_reviewer, eve_senior)"
echo "  ✓ Same file (src/services/cart.py)"
echo "  ✓ Same commit (commit-abc123)"
echo "  ✓ Both marked as is_latest_review=true"
echo "  ✓ Different review_iteration numbers"
echo ""
echo "You can verify by running:"
echo "  curl \"http://localhost:8000/api/v1/reviews?project_key=ECOM&repository_slug=frontend-store&pull_request_id=pr-test-001\""