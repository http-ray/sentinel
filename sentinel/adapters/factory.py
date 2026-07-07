"""Adapter factory — selects mock vs real implementations from config."""

from __future__ import annotations

from sentinel.adapters.base import Adapters
from sentinel.adapters.github_mock import MockGitHubAdapter
from sentinel.adapters.metrics_mock import MockMetricsAdapter
from sentinel.adapters.runbook_store_mock import MockRunbookStore
from sentinel.adapters.slack_mock import MockSlackAdapter
from sentinel.config import Settings, get_settings


def get_adapters(settings: Settings | None = None) -> Adapters:
    """Return the wired adapter bundle for the current configuration.

    When ``use_mocks`` is true (the default), everything is offline mocks. Real
    adapters are not implemented yet; requesting them raises so misconfiguration
    fails loudly rather than silently degrading.
    """
    settings = settings or get_settings()

    if settings.use_mocks:
        return Adapters(
            github=MockGitHubAdapter(settings.fixtures_dir),
            metrics=MockMetricsAdapter(),
            runbooks=MockRunbookStore(settings.runbooks_dir),
            slack=MockSlackAdapter(),
        )

    raise NotImplementedError(
        "Real integrations are not wired yet. Set SENTINEL_USE_MOCKS=true to run "
        "the offline pipeline, or implement the real adapters behind the "
        "protocols in sentinel/adapters/base.py."
    )
