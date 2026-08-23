"""Tests for the real GitHub adapter.

HTTP calls are faked via ``httpx.MockTransport`` so the suite stays fully
offline, consistent with the rest of Sentinel's tests — no real network call
is made anywhere in this file.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest

from sentinel.adapters.github_real import GitHubAPIError, RealGitHubAdapter

REPO = "acme/checkout-service"
SHA = "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678"

_COMMIT_SUMMARY = {"sha": SHA, "commit": {"message": "unused-by-summary"}}
_COMMIT_DETAIL = {
    "sha": SHA,
    "commit": {
        "message": "Refactor payment retry logic\n\nLonger body explaining why.",
        "author": {"name": "dana", "date": "2026-07-06T14:24:00Z"},
    },
    "author": {"login": "dana-gh"},
    "files": [
        {"filename": "services/checkout/payment.py"},
        {"filename": "services/checkout/retry.py"},
    ],
    "stats": {"additions": 142, "deletions": 88},
}
_DEPLOY_NEW = {
    "id": 8814,
    "sha": SHA,
    "environment": "production",
    "created_at": "2026-07-06T14:28:00Z",
    "creator": {"login": "dana"},
}
_DEPLOY_OLD = {
    "id": 8801,
    "sha": "d4e5f60718293a4b5c6d7e8f9012345678901234",
    "environment": "production",
    "created_at": "2026-07-01T09:45:00Z",
    "creator": {"login": "sam"},
}


def _adapter(handler) -> RealGitHubAdapter:
    return RealGitHubAdapter(
        token="fake-token",
        repo=REPO,
        transport=httpx.MockTransport(handler),
    )


def test_repo_must_be_owner_slash_repo():
    with pytest.raises(ValueError):
        RealGitHubAdapter(token="fake-token", repo="checkout-service")


def test_recent_commits_parses_and_tags_service():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer fake-token"
        if request.url.path == f"/repos/{REPO}/commits":
            return httpx.Response(200, json=[_COMMIT_SUMMARY])
        if request.url.path == f"/repos/{REPO}/commits/{SHA}":
            return httpx.Response(200, json=_COMMIT_DETAIL)
        raise AssertionError(f"unexpected request: {request.url}")

    adapter = _adapter(handler)
    commits = adapter.recent_commits("checkout-service", before=datetime(2026, 7, 7, tzinfo=timezone.utc))

    assert len(commits) == 1
    commit = commits[0]
    assert commit.sha == SHA
    assert commit.message == "Refactor payment retry logic"  # first line only
    assert commit.author == "dana-gh"  # GitHub login preferred over raw name
    assert commit.timestamp == datetime(2026, 7, 6, 14, 24, tzinfo=timezone.utc)
    assert commit.files_changed == ["services/checkout/payment.py", "services/checkout/retry.py"]
    assert commit.services_touched == ["checkout-service"]  # derived from repo name
    assert commit.additions == 142
    assert commit.deletions == 88


def test_recent_deploys_filters_by_cutoff_and_sorts_newest_first():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"/repos/{REPO}/deployments"
        return httpx.Response(200, json=[_DEPLOY_OLD, _DEPLOY_NEW])

    adapter = _adapter(handler)

    # Cutoff excludes nothing.
    deploys = adapter.recent_deploys("checkout-service", before=datetime(2026, 7, 7, tzinfo=timezone.utc))
    assert [d.id for d in deploys] == ["8814", "8801"]  # newest first
    assert deploys[0].service == "checkout-service"
    assert deploys[0].deployed_by == "dana"

    # Cutoff excludes the newer deploy.
    deploys = adapter.recent_deploys("checkout-service", before=datetime(2026, 7, 3, tzinfo=timezone.utc))
    assert [d.id for d in deploys] == ["8801"]


def test_get_commit_returns_none_on_404():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "Not Found"})

    adapter = _adapter(handler)
    assert adapter.get_commit("deadbeef") is None


def test_get_commit_returns_commit_when_found():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_COMMIT_DETAIL)

    adapter = _adapter(handler)
    commit = adapter.get_commit(SHA)
    assert commit is not None
    assert commit.sha == SHA


def test_api_error_raises_github_api_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"message": "server error"})

    adapter = _adapter(handler)
    with pytest.raises(GitHubAPIError):
        adapter.recent_commits("checkout-service", before=datetime(2026, 7, 7, tzinfo=timezone.utc))
