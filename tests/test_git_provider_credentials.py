"""Tests for how the Bitbucket providers turn configuration into an auth header.

The Server and Cloud settings are separate so both platforms can run side by
side; what is asserted here is which pair wins, and that a Server credential can
stand in when the Cloud pair is left unset.
"""

from __future__ import annotations

import base64

import pytest

from src.core.config import settings
from src.services.git_providers.bitbucket_cloud import BitbucketCloudProvider
from src.services.git_providers.bitbucket_server import BitbucketServerProvider


def basic(user: str, password: str) -> str:
    return f"Basic {base64.b64encode(f'{user}:{password}'.encode()).decode()}"


@pytest.fixture(autouse=True)
def no_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """Start every case from a configuration that names nothing.

    The suite runs against whatever `.env` the developer has, so each case has
    to state the credentials it is about rather than inherit them.
    """
    for field in (
        "BITBUCKET_SERVER_TOKEN",
        "BITBUCKET_SERVER_USER",
        "BITBUCKET_SERVER_PASSWORD",
        "BITBUCKET_CLOUD_TOKEN",
        "BITBUCKET_CLOUD_USER",
        "BITBUCKET_CLOUD_APP_PASSWORD",
    ):
        monkeypatch.setattr(settings, field, None)


def authorization(provider: object) -> str | None:
    return provider._headers.get("Authorization")


def test_the_server_reads_the_prefixed_settings(monkeypatch):
    monkeypatch.setattr(settings, "BITBUCKET_SERVER_USER", "aaron")
    monkeypatch.setattr(settings, "BITBUCKET_SERVER_PASSWORD", "secret")

    assert authorization(BitbucketServerProvider()) == basic("aaron", "secret")


def test_a_server_token_is_preferred_over_the_credentials(monkeypatch):
    monkeypatch.setattr(settings, "BITBUCKET_SERVER_TOKEN", "pat")
    monkeypatch.setattr(settings, "BITBUCKET_SERVER_USER", "aaron")
    monkeypatch.setattr(settings, "BITBUCKET_SERVER_PASSWORD", "secret")

    assert authorization(BitbucketServerProvider()) == "Bearer pat"


def test_a_server_without_credentials_sends_no_authorization():
    assert authorization(BitbucketServerProvider()) is None


def test_the_cloud_reads_its_own_settings(monkeypatch):
    monkeypatch.setattr(settings, "BITBUCKET_CLOUD_USER", "aaron@example.com")
    monkeypatch.setattr(settings, "BITBUCKET_CLOUD_APP_PASSWORD", "app-password")
    monkeypatch.setattr(settings, "BITBUCKET_SERVER_USER", "someone")
    monkeypatch.setattr(settings, "BITBUCKET_SERVER_PASSWORD", "else")

    # the Cloud pair wins: the Server pair is only a stand-in
    assert authorization(BitbucketCloudProvider()) == basic("aaron@example.com", "app-password")


def test_the_cloud_falls_back_to_the_server_credentials(monkeypatch):
    monkeypatch.setattr(settings, "BITBUCKET_SERVER_USER", "aaron")
    monkeypatch.setattr(settings, "BITBUCKET_SERVER_PASSWORD", "secret")

    # a single-credential setup may leave the Cloud pair unset
    assert authorization(BitbucketCloudProvider()) == basic("aaron", "secret")


def test_a_cloud_token_is_preferred_over_the_credentials(monkeypatch):
    monkeypatch.setattr(settings, "BITBUCKET_CLOUD_TOKEN", "cloud-token")
    monkeypatch.setattr(settings, "BITBUCKET_CLOUD_USER", "aaron@example.com")
    monkeypatch.setattr(settings, "BITBUCKET_CLOUD_APP_PASSWORD", "app-password")

    assert authorization(BitbucketCloudProvider()) == "Bearer cloud-token"
