"""Adapter factory — selects mock vs real implementations from config."""

from __future__ import annotations

from sentinel.adapters.base import Adapters, GitHubAdapter, SlackAdapter
from sentinel.adapters.github_mock import MockGitHubAdapter
from sentinel.adapters.github_real import RealGitHubAdapter
from sentinel.adapters.metrics_mock import MockMetricsAdapter
from sentinel.adapters.runbook_store_mock import MockRunbookStore
from sentinel.adapters.slack_mock import MockSlackAdapter
from sentinel.adapters.slack_real import RealSlackAdapter
from sentinel.config import Settings, get_settings


def get_adapters(settings: Settings | None = None) -> Adapters:
    """Return the wired adapter bundle for the current configuration.

    Each integration is gated independently, not by one combined switch:

    - GitHub: real when ``use_mocks`` is false (requires ``GITHUB_TOKEN``/
      ``GITHUB_REPO``, else raises so misconfiguration fails loudly); mocked
      otherwise.
    - Slack: real whenever ``SLACK_WEBHOOK_URL`` is set, regardless of
      ``use_mocks`` -- you can turn on real Slack posting without also having
      real GitHub credentials, and vice versa.
    - Metrics and runbooks don't have real adapters yet, so they stay mocked
      either way until their own roadmap items land.
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

    slack: SlackAdapter = (
        RealSlackAdapter(settings.slack_webhook_url)
        if settings.slack_enabled
        else MockSlackAdapter()
    )

    return Adapters(
        github=github,
        metrics=MockMetricsAdapter(),
        runbooks=MockRunbookStore(settings.runbooks_dir),
        slack=slack,
    )
