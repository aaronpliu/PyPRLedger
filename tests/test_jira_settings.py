"""Tests for the JIRA link settings endpoint.

The frontend uses it to link the ticket keys found in commit messages; no JIRA
traffic or database write is involved, the value comes from the backend settings.
"""

from __future__ import annotations

import pytest

from src.core.config import settings
from src.core.permissions import get_current_user_with_token
from src.main import app
from src.models.auth_user import AuthUser


@pytest.fixture
def authenticated_client(async_client):
    """Test client with an authenticated user dependency override."""

    async def _current_user() -> AuthUser:
        return AuthUser(id=1, username="tester", email="tester@example.com")

    app.dependency_overrides[get_current_user_with_token] = _current_user
    yield async_client
    app.dependency_overrides.pop(get_current_user_with_token, None)


async def test_jira_settings_endpoint_publishes_the_configured_instance(
    monkeypatch, authenticated_client
) -> None:
    monkeypatch.setattr(settings, "JIRA_BASE_URL", "https://jira.local/")
    monkeypatch.setattr(settings, "JIRA_PROJECT_KEYS", "prl, AI")

    response = await authenticated_client.get("/api/v1/rbac/settings/jira")

    assert response.status_code == 200
    # the base URL is normalized, the project keys are upper cased
    assert response.json() == {
        "base_url": "https://jira.local",
        "project_keys": ["PRL", "AI"],
    }


async def test_jira_settings_endpoint_is_empty_without_a_configuration(
    monkeypatch, authenticated_client
) -> None:
    monkeypatch.setattr(settings, "JIRA_BASE_URL", None)
    monkeypatch.setattr(settings, "JIRA_PROJECT_KEYS", "")

    response = await authenticated_client.get("/api/v1/rbac/settings/jira")

    assert response.status_code == 200
    assert response.json() == {"base_url": "", "project_keys": []}
