from __future__ import annotations

from pydantic import BaseModel, Field


class DependencyGraphRef(BaseModel):
    """The ref the graph was consolidated at."""

    name: str = Field(..., description="Tag or branch name as the provider reports it")
    type: str = Field(..., description="tag, branch or commit")
    commit: str | None = Field(default=None, description="Commit the graph belongs to")


class DependencyGraphPackage(BaseModel):
    """One package of the graph: what it ships and what it depends on."""

    id: str = Field(..., description="Package name")
    category: int = Field(..., description="0 = project, 1 = dependency, 2 = shipped module")
    version: str | None = Field(default=None, description="Version of the package in this closure")
    dependencies: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Declared dependencies by package name. The value is the constraint that was "
            "declared; empty when the dependency database records the relationship alone."
        ),
    )


class DependencyGraphRequest(BaseModel):
    """The coordinates a graph is asked for."""

    project_key: str = Field(..., min_length=1, max_length=32)
    repository_slug: str = Field(..., min_length=1, max_length=128)
    ref: str = Field(..., min_length=1, max_length=255, description="Tag or branch to read")
    git_provider: str | None = Field(default=None, description="Provider holding the repository")
    workspace_slug: str | None = Field(
        default=None, description="Bitbucket Cloud only: workspace holding the repository"
    )


class DependencyGraphResponse(BaseModel):
    """The dependency graph of one ref, in the shape the page draws."""

    schema_version: str
    project_key: str
    repository_slug: str
    git_provider: str | None = None
    ref: DependencyGraphRef
    generated_at: str | None = Field(
        default=None, description="When the database recorded the build, when it records one"
    )
    packages: list[DependencyGraphPackage] = Field(default_factory=list)
