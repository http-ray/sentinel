"""Shared test fixtures."""

from __future__ import annotations

import json

import pytest

from sentinel.adapters import get_adapters
from sentinel.config import Settings
from sentinel.models import Alert


@pytest.fixture
def settings():
    # Ignore whatever a developer's local .env has (e.g. SENTINEL_USE_MOCKS=false
    # for a live GitHub smoke test) — the suite must stay hermetic and offline.
    return Settings(_env_file=None)


@pytest.fixture
def adapters(settings):
    return get_adapters(settings)


@pytest.fixture
def sample_alerts(settings) -> list[Alert]:
    raw = json.loads((settings.fixtures_dir / "sample_alerts.json").read_text("utf-8"))
    return [Alert(**a) for a in raw]


@pytest.fixture
def checkout_alert(sample_alerts) -> Alert:
    return next(a for a in sample_alerts if a.service == "checkout-service")
