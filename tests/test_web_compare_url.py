"""Tests for the browsable revision comparison links of every provider.

Each URL matches what the platform's own compare page generates:

* Bitbucket Cloud keeps both revisions in a single path segment separated by a
  carriage return (``%0D``), newest first;
* Bitbucket Server / Data Center uses the ``compare/commits`` page with the
  ``sourceBranch`` / ``targetBranch`` pair (the same path as the documented REST
  resource, where ``from`` is the newer side);
* GitHub Enterprise uses ``{base}...{head}``.

No HTTP traffic is involved, the URLs are pure string construction.
"""

from __future__ import annotations

from src.core.config import settings
from src.services.git_providers import (
    bitbucket_cloud,
    bitbucket_server,
    get_git_provider,
    github_enterprise,
)


# --------------------------------------------------------------------------- #
# Bitbucket Server / Data Center
# --------------------------------------------------------------------------- #


def test_server_compare_url_points_at_the_compare_page() -> None:
    url = get_git_provider("bitbucket_server").web_compare_url(
        "PROJ", "my-repo", "v1.0.0", "v1.1.0"
    )

    base = settings.BITBUCKET_SERVER_URL.rstrip("/")
    assert url == (
        f"{base}/projects/PROJ/repos/my-repo/compare/commits"
        "?sourceBranch=v1.1.0&targetBranch=v1.0.0"
    )


def test_server_compare_url_encodes_the_revisions() -> None:
    url = bitbucket_server.BitbucketServerProvider().web_compare_url(
        "PROJ", "my-repo", "release/1.0", "feature/login page"
    )

    assert url is not None
    assert url.endswith("?sourceBranch=feature%2Flogin+page&targetBranch=release%2F1.0")


# --------------------------------------------------------------------------- #
# Bitbucket Cloud
# --------------------------------------------------------------------------- #


def test_cloud_compare_url_keeps_both_revisions_in_one_segment() -> None:
    url = get_git_provider("bitbucket_cloud").web_compare_url("acme", "web-app", "v1.0.0", "v1.1.0")

    assert url == "https://bitbucket.org/acme/web-app/branches/compare/v1.1.0%0Dv1.0.0"


def test_cloud_compare_url_encodes_reserved_characters() -> None:
    url = bitbucket_cloud.BitbucketCloudProvider().web_compare_url(
        "acme", "web-app", "@acme/pkg@1.0.0", "feature/login page"
    )

    assert url == (
        "https://bitbucket.org/acme/web-app/branches/compare/"
        "feature%2Flogin%20page%0D%40acme%2Fpkg%401.0.0"
    )


# --------------------------------------------------------------------------- #
# GitHub Enterprise
# --------------------------------------------------------------------------- #


def test_github_compare_url_uses_the_base_head_range(monkeypatch) -> None:
    monkeypatch.setattr(settings, "GITHUB_ENTERPRISE_URL", "https://github.local")

    url = github_enterprise.GitHubEnterpriseProvider().web_compare_url(
        "acme", "pyledger", "v1.0.0", "v1.1.0"
    )

    assert url == "https://github.local/acme/pyledger/compare/v1.0.0...v1.1.0"


def test_github_compare_url_is_omitted_without_a_host(monkeypatch) -> None:
    monkeypatch.setattr(settings, "GITHUB_ENTERPRISE_URL", "")

    provider = github_enterprise.GitHubEnterpriseProvider()

    assert provider.web_compare_url("acme", "pyledger", "v1.0.0", "v1.1.0") is None


# --------------------------------------------------------------------------- #
# Guards shared by every provider
# --------------------------------------------------------------------------- #


def test_compare_urls_are_omitted_when_a_part_is_missing() -> None:
    providers = [
        bitbucket_server.BitbucketServerProvider(),
        bitbucket_cloud.BitbucketCloudProvider(),
        github_enterprise.GitHubEnterpriseProvider(),
    ]

    for provider in providers:
        assert provider.web_compare_url("", "repo", "v1.0.0", "v1.1.0") is None
        assert provider.web_compare_url("PROJ", "", "v1.0.0", "v1.1.0") is None
        assert provider.web_compare_url("PROJ", "repo", "", "v1.1.0") is None
        assert provider.web_compare_url("PROJ", "repo", "   ", "v1.1.0") is None
        assert provider.web_compare_url("PROJ", "repo", "v1.0.0", "") is None
