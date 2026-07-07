"""Mock GitHub adapter backed by JSON fixtures."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from sentinel.config import get_settings
from sentinel.models import Commit, Deploy


class MockGitHubAdapter:
    """Serves commits/deploys from ``fixtures/`` for offline runs."""

    def __init__(self, fixtures_dir: Path | None = None) -> None:
        base = fixtures_dir or get_settings().fixtures_dir
        self._commits = [
            Commit(**c) for c in json.loads((base / "sample_commits.json").read_text("utf-8"))
        ]
        self._deploys = [
            Deploy(**d) for d in json.loads((base / "sample_deploys.json").read_text("utf-8"))
        ]

    def recent_commits(self, service: str, before: datetime, limit: int = 25) -> list[Commit]:
        # Return commits at/before the cutoff, newest first. We do not hard-filter
        # by service here — correlation weighs service overlap itself, and an
        # alert can be caused by a commit whose service tag is imperfect.
        commits = [c for c in self._commits if c.timestamp <= before]
        commits.sort(key=lambda c: c.timestamp, reverse=True)
        return commits[:limit]

    def recent_deploys(self, service: str, before: datetime, limit: int = 25) -> list[Deploy]:
        deploys = [d for d in self._deploys if d.deployed_at <= before]
        deploys.sort(key=lambda d: d.deployed_at, reverse=True)
        return deploys[:limit]

    def get_commit(self, sha: str) -> Commit | None:
        for c in self._commits:
            if c.sha == sha or c.sha.startswith(sha):
                return c
        return None
