"""Tests for the adapter factory's mock/real switch."""

from __future__ import annotations

import pytest

from sentinel.adapters.factory import get_adapters
from sentinel.adapters.github_mock import MockGitHubAdapter
from sentinel.adapters.github_real import RealGitHubAdapter
from sentinel.adapters.metrics_mock import MockMetricsAdapter
from sentinel.adapters.slack_mock import MockSlackAdapter
from sentinel.adapters.slack_real import RealSlackAdapter
from sentinel.config import Settings


def _settings(**overrides) -> Settings:
    # _env_file=None: ignore whatever a developer's local .env has (e.g. real
    # GITHUB_TOKEN/SENTINEL_USE_MOCKS=false) -- these tests must be hermetic
    # and only reflect the fields each test explicitly sets.
    return Settings(_env_file=None, **overrides)


def test_use_mocks_true_returns_mock_github():
    settings = _settings(SENTINEL_USE_MOCKS=True)
    adapters = get_adapters(settings)
    assert isinstance(adapters.github, MockGitHubAdapter)


def test_use_mocks_false_without_credentials_raises():
    settings = _settings(SENTINEL_USE_MOCKS=False, GITHUB_TOKEN="", GITHUB_REPO="")
    with pytest.raises(NotImplementedError):
        get_adapters(settings)


def test_use_mocks_false_with_credentials_returns_real_github():
    settings = _settings(
        SENTINEL_USE_MOCKS=False,
        GITHUB_TOKEN="fake-token",
        GITHUB_REPO="acme/checkout-service",
    )
    adapters = get_adapters(settings)
    assert isinstance(adapters.github, RealGitHubAdapter)


def test_use_mocks_false_leaves_metrics_runbooks_mocked():
    # Metrics/runbooks don't have real adapters at all, so they stay mocked
    # regardless of SENTINEL_USE_MOCKS until their own roadmap items land.
    settings = _settings(
        SENTINEL_USE_MOCKS=False,
        GITHUB_TOKEN="fake-token",
        GITHUB_REPO="acme/checkout-service",
    )
    adapters = get_adapters(settings)
    assert isinstance(adapters.metrics, MockMetricsAdapter)


def test_slack_stays_mocked_without_a_webhook_url():
    settings = _settings(SLACK_WEBHOOK_URL="")
    adapters = get_adapters(settings)
    assert isinstance(adapters.slack, MockSlackAdapter)


def test_slack_becomes_real_with_a_webhook_url():
    settings = _settings(SLACK_WEBHOOK_URL="https://hooks.slack.com/services/T/B/x")
    adapters = get_adapters(settings)
    assert isinstance(adapters.slack, RealSlackAdapter)


def test_slack_real_is_independent_of_use_mocks_and_github_creds():
    # Real Slack shouldn't require real GitHub, or vice versa -- each
    # integration is its own opt-in, not one combined switch.
    settings = _settings(
        SENTINEL_USE_MOCKS=True,  # GitHub stays mocked
        SLACK_WEBHOOK_URL="https://hooks.slack.com/services/T/B/x",
    )
    adapters = get_adapters(settings)
    assert isinstance(adapters.github, MockGitHubAdapter)
    assert isinstance(adapters.slack, RealSlackAdapter)
