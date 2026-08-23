"""Tests for the adapter factory's mock/real switch."""

from __future__ import annotations

import pytest

from sentinel.adapters.factory import get_adapters
from sentinel.adapters.github_mock import MockGitHubAdapter
from sentinel.adapters.github_real import RealGitHubAdapter
from sentinel.adapters.metrics_mock import MockMetricsAdapter
from sentinel.adapters.slack_mock import MockSlackAdapter
from sentinel.config import Settings


def test_use_mocks_true_returns_mock_github():
    settings = Settings(SENTINEL_USE_MOCKS=True)
    adapters = get_adapters(settings)
    assert isinstance(adapters.github, MockGitHubAdapter)


def test_use_mocks_false_without_credentials_raises():
    settings = Settings(SENTINEL_USE_MOCKS=False, GITHUB_TOKEN="", GITHUB_REPO="")
    with pytest.raises(NotImplementedError):
        get_adapters(settings)


def test_use_mocks_false_with_credentials_returns_real_github():
    settings = Settings(
        SENTINEL_USE_MOCKS=False,
        GITHUB_TOKEN="fake-token",
        GITHUB_REPO="acme/checkout-service",
    )
    adapters = get_adapters(settings)
    assert isinstance(adapters.github, RealGitHubAdapter)


def test_use_mocks_false_leaves_metrics_slack_runbooks_mocked():
    # Metrics/runbooks/slack don't have real adapters yet, so they should stay
    # mocked regardless of SENTINEL_USE_MOCKS until their own roadmap items land.
    settings = Settings(
        SENTINEL_USE_MOCKS=False,
        GITHUB_TOKEN="fake-token",
        GITHUB_REPO="acme/checkout-service",
    )
    adapters = get_adapters(settings)
    assert isinstance(adapters.metrics, MockMetricsAdapter)
    assert isinstance(adapters.slack, MockSlackAdapter)
