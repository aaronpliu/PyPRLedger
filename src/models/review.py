"""Compatibility wrapper for review models.

The canonical review models now live in src.models.pull_request.
"""

from src.models.pull_request import PullRequestReviewAssignment, PullRequestReviewBase


__all__ = ["PullRequestReviewBase", "PullRequestReviewAssignment"]
