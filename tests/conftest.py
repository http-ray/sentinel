"""Shared test fixtures."""

from __future__ import annotations

import json

import pytest

from sentinel.adapters import get_adapters
from sentinel.config import get_settings
from sentinel.models import Alert


@pytest.fixture
def settings():
    return get_settings()


@pytest.fixture
def adapters():
    return get_adapters()


@pytest.fixture
def sample_alerts(settings) -> list[Alert]:
    raw = json.loads((settings.fixtures_dir / "sample_alerts.json").read_text("utf-8"))
    return [Alert(**a) for a in raw]


@pytest.fixture
def checkout_alert(sample_alerts) -> Alert:
    return next(a for a in sample_alerts if a.service == "checkout-service")
