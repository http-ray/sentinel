"""Adapter factory — selects mock vs real implementations from config."""

from __future__ import annotations

from sentinel.adapters.base import Adapters, GitHubAdapter
from sentinel.adapters.github_mock import MockGitHubAdapter
from sentinel.adapters.github_real import RealGitHubAdapter
from sentinel.adapters.metrics_mock import MockMetricsAdapter
from sentinel.adapters.runbook_store_mock import MockRunbookStore
from sentinel.adapters.slack_mock import MockSlackAdapter
from sentinel.config import Settings, get_settings


def get_adapters(settings: Settings | None = None) -> Adapters:
    """Return the wired adapter bundle for the current configuration.

    When ``use_mocks`` is true (the default), everything is offline mocks. When
    false, GitHub switches to the real API-backed adapter (requires
    ``GITHUB_TOKEN``/``GITHUB_REPO``). Metrics, runbooks, and Slack don't have
    real adapters yet, so they stay mocked either way until their own roadmap
    items land — this isn't a silent gap, it's the current honest state.
    """
    settings = settings or get_settings()

    if settings.use_mocks:
        github: GitHubAdapter = MockGitHubAdapter(settings.fixtures_dir)
    else:
        if not settings.github_token or not settings.github_repo:
            raise NotImplementedError(
                "SENTINEL_USE_MOCKS=false requires GITHUB_TOKEN and GITHUB_REPO "
                "to be set to use the real GitHub adapter."
            )
        github = RealGitHubAdapter(settings.github_token, settings.github_repo)

    return Adapters(
        github=github,
        metrics=MockMetricsAdapter(),
        runbooks=MockRunbookStore(settings.runbooks_dir),
        slack=MockSlackAdapter(),
    )
