"""Schemas for Bitbucket Cloud workspace suggestions."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CloudWorkspaceOption(BaseModel):
    """A Bitbucket Cloud workspace the UI can offer for a repository."""

    slug: str = Field(..., description="Workspace slug used in Bitbucket Cloud API paths")
    name: str = Field(..., description="Human readable workspace name")
    source: str = Field(
        ...,
        description=(
            "Where the suggestion comes from: 'config' (BITBUCKET_CLOUD_WORKSPACES), "
            "'api' (discovered from Bitbucket Cloud) or 'database' (already synced locally)."
        ),
    )


class CloudWorkspaceListResponse(BaseModel):
    """Workspace suggestions for the repository / release diff forms."""

    workspaces: list[CloudWorkspaceOption] = Field(default_factory=list)
