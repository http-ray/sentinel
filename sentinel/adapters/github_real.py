"""Real GitHub adapter — fetches commits/deploys from the GitHub REST API.

Scoped to a single ``owner/repo`` (``GITHUB_REPO``), matching how Sentinel is
configured today: one adapter instance per pipeline, backing one service. Every
commit/deploy pulled from that repo is tagged with the repo's short name as its
"service" — the same simplification the mock fixtures use, and consistent with
``recent_commits``/``recent_deploys`` accepting but not filtering on ``service``
(see the mock's docstring for why: correlation itself weighs service overlap).

Requires a read-only personal access token (``GITHUB_TOKEN``, ``repo:status`` /
fine-grained "Contents: read" scope is enough — no write access needed).
"""

from __future__ import annotations

from datetime import datetime

import httpx

from sentinel.models import Commit, Deploy

_API_BASE = "https://api.github.com"
_TIMEOUT = 10.0


class GitHubAPIError(RuntimeError):
    """Raised when the GitHub API returns an error response."""


class RealGitHubAdapter:
    """Serves commits/deploys from the live GitHub API for one configured repo."""

    def __init__(
        self,
        token: str,
        repo: str,
        *,
        timeout: float = _TIMEOUT,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if "/" not in repo:
            raise ValueError(f"GITHUB_REPO must be 'owner/repo', got: {repo!r}")
        self._repo = repo
        self._service_label = repo.split("/", 1)[1]
        self._client = httpx.Client(
            base_url=_API_BASE,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=timeout,
            transport=transport,
        )

    def recent_commits(self, service: str, before: datetime, limit: int = 25) -> list[Commit]:
        # `service` is accepted for interface compatibility only — this adapter
        # is scoped to one repo/service already, same as MockGitHubAdapter.
        resp = self._client.get(
            f"/repos/{self._repo}/commits",
            params={"until": before.isoformat(), "per_page": limit},
        )
        self._raise_for_status(resp)
        commits = [self._fetch_commit_detail(item["sha"]) for item in resp.json()]
        commits.sort(key=lambda c: c.timestamp, reverse=True)
        return commits

    def recent_deploys(self, service: str, before: datetime, limit: int = 25) -> list[Deploy]:
        resp = self._client.get(f"/repos/{self._repo}/deployments", params={"per_page": 100})
        self._raise_for_status(resp)
        deploys = [self._parse_deploy(item) for item in resp.json()]
        deploys = [d for d in deploys if d.deployed_at <= before]
        deploys.sort(key=lambda d: d.deployed_at, reverse=True)
        return deploys[:limit]

    def get_commit(self, sha: str) -> Commit | None:
        resp = self._client.get(f"/repos/{self._repo}/commits/{sha}")
        if resp.status_code == 404:
            return None
        self._raise_for_status(resp)
        return self._parse_commit_detail(resp.json())

    def close(self) -> None:
        self._client.close()

    # -- internal ---------------------------------------------------------- #

    def _fetch_commit_detail(self, sha: str) -> Commit:
        resp = self._client.get(f"/repos/{self._repo}/commits/{sha}")
        self._raise_for_status(resp)
        return self._parse_commit_detail(resp.json())

    def _parse_commit_detail(self, data: dict) -> Commit:
        commit_info = data["commit"]
        # Prefer the linked GitHub login when available; fall back to the raw
        # commit-author name (e.g. for commits authored outside GitHub).
        author = (data.get("author") or {}).get("login") or commit_info["author"]["name"]
        timestamp = _parse_github_datetime(commit_info["author"]["date"])
        stats = data.get("stats", {})
        return Commit(
            sha=data["sha"],
            message=commit_info["message"].splitlines()[0],
            author=author,
            timestamp=timestamp,
            files_changed=[f["filename"] for f in data.get("files", [])],
            services_touched=[self._service_label],
            additions=stats.get("additions", 0),
            deletions=stats.get("deletions", 0),
        )

    def _parse_deploy(self, data: dict) -> Deploy:
        return Deploy(
            id=str(data["id"]),
            commit_sha=data["sha"],
            service=self._service_label,
            environment=data.get("environment", "production"),
            deployed_at=_parse_github_datetime(data["created_at"]),
            deployed_by=(data.get("creator") or {}).get("login", ""),
        )

    def _raise_for_status(self, resp: httpx.Response) -> None:
        if resp.status_code >= 400:
            raise GitHubAPIError(
                f"GitHub API {resp.request.method} {resp.request.url} -> "
                f"{resp.status_code}: {resp.text[:200]}"
            )


def _parse_github_datetime(value: str) -> datetime:
    """GitHub timestamps are ISO 8601 with a trailing 'Z'; stdlib wants '+00:00'."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
