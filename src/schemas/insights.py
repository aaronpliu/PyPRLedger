"""Response models for the repository insights dashboard."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class InsightsScope(BaseModel):
    """What the numbers below were read for."""

    project_key: str | None = Field(None, description="Project the reading is scoped to")
    repository_slug: str | None = Field(
        None,
        description="Repository the reading is scoped to; null means every repository of the project",
    )
    days: int = Field(..., description="How far back the reading looks")
    period: str = Field(..., description="Trend bucket: daily, weekly or monthly")
    generated_at: datetime = Field(..., description="When the reading was computed")


class InsightsKpis(BaseModel):
    """The numbers a reader wants before anything else."""

    reviews_total: int = 0
    reviews_open: int = 0
    reviews_today: int = 0
    avg_score: float = 0.0
    good_suggestion_rate: float = 0.0
    assigned_pending: int = 0
    assigned_in_progress: int = 0
    unassigned_count: int = 0
    active_reviewers: int = 0


class InsightsTrendPoint(BaseModel):
    """One bucket of the trend chart: reviews, quality and assignment in one row."""

    period_start: str
    reviews: int = 0
    avg_score: float = 0.0
    high_scores: int = 0
    assigned: int = 0
    completed: int = 0


class InsightsCount(BaseModel):
    """A named bucket with its count."""

    key: str
    count: int


class InsightsReviewerStat(BaseModel):
    """How much review work one person carried, and how much of it finished."""

    reviewer: str
    assigned: int = 0
    completed: int = 0


class InsightsRecentReview(BaseModel):
    """One row of the recent-activity table."""

    project_key: str
    repository_slug: str
    pull_request_id: str
    pull_request_commit_id: str | None = None
    status: str
    avg_score: float = 0.0
    created_date: datetime


class InsightsBreakdown(BaseModel):
    """The distributions the charts draw."""

    by_status: list[InsightsCount] = Field(default_factory=list)
    by_reviewer: list[InsightsReviewerStat] = Field(default_factory=list)
    by_project: list[InsightsCount] = Field(default_factory=list)


class RepositoryInsights(BaseModel):
    """One reading of a repository (or a project's repositories) at a point in time."""

    scope: InsightsScope
    kpis: InsightsKpis
    trends: list[InsightsTrendPoint] = Field(default_factory=list)
    breakdown: InsightsBreakdown = Field(default_factory=InsightsBreakdown)
    recent: list[InsightsRecentReview] = Field(default_factory=list)
