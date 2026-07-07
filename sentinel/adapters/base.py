"""Adapter protocols — the seam between pipeline logic and the outside world.

Each protocol describes the minimal capability a pipeline stage needs. Mock
implementations satisfy them for offline runs; real implementations (GitHub API,
Slack API, Datadog/Prometheus) can be dropped in later without changing callers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from sentinel.models import Commit, Deploy, Runbook


@runtime_checkable
class GitHubAdapter(Protocol):
    """Source-control / deploy history."""

    def recent_commits(self, service: str, before: datetime, limit: int = 25) -> list[Commit]:
        """Commits relevant to ``service`` at or before ``before``, newest first."""
        ...

    def recent_deploys(self, service: str, before: datetime, limit: int = 25) -> list[Deploy]:
        """Deploys touching ``service`` at or before ``before``, newest first."""
        ...

    def get_commit(self, sha: str) -> Commit | None:
        """Fetch a single commit by SHA, or None if unknown."""
        ...


@runtime_checkable
class MetricsAdapter(Protocol):
    """Observability metrics for impact estimation."""

    def service_metrics(self, service: str, window_start: datetime, window_end: datetime) -> "ServiceMetrics":
        """Aggregate metrics for ``service`` over the given window."""
        ...


@runtime_checkable
class RunbookStore(Protocol):
    """Runbook retrieval."""

    def all_runbooks(self) -> list[Runbook]:
        """Every known runbook (used for scoring)."""
        ...


@runtime_checkable
class SlackAdapter(Protocol):
    """Chat notification sink."""

    def post_message(self, channel: str, text: str) -> str:
        """Post ``text`` to ``channel``; return a message timestamp/id."""
        ...


@dataclass
class ServiceMetrics:
    """Raw metrics returned by a MetricsAdapter for one service/window."""

    service: str
    error_rate: float
    baseline_error_rate: float
    requests_per_min: float
    active_users: int


@dataclass
class Adapters:
    """The bundle of adapters the orchestrator depends on."""

    github: GitHubAdapter
    metrics: MetricsAdapter
    runbooks: RunbookStore
    slack: SlackAdapter
