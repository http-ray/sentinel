"""Tests for stage 3 — impact estimation and severity."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from sentinel.adapters.base import MetricsAdapter, ServiceMetrics
from sentinel.models import Alert, Severity
from sentinel.pipeline.impact import estimate_impact


class _StubMetrics:
    """Metrics adapter returning a fixed reading, for threshold tests."""

    def __init__(self, **kwargs: float) -> None:
        self._m = ServiceMetrics(service="svc", **kwargs)

    def service_metrics(self, service, window_start, window_end) -> ServiceMetrics:
        return self._m


def _alert(service="svc", hint=None) -> Alert:
    return Alert(
        id="a",
        title="t",
        service=service,
        severity_hint=hint,
        fired_at=datetime(2026, 7, 6, 14, 32, tzinfo=timezone.utc),
    )


def test_checkout_incident_is_sev2(checkout_alert, adapters):
    # Drop the source hint so we test the metric-driven severity purely.
    checkout_alert.severity_hint = None
    est = estimate_impact(checkout_alert, adapters.metrics)
    assert est.severity == Severity.SEV2
    assert est.affected_users > 0
    assert est.notes


def test_high_error_rate_escalates_to_sev1():
    m = _StubMetrics(
        error_rate=0.25, baseline_error_rate=0.01, requests_per_min=1000, active_users=500
    )
    est = estimate_impact(_alert(), m)
    assert est.severity == Severity.SEV1


def test_low_percentage_but_huge_user_base_escalates():
    # 2% error over baseline but on 1M users -> 20k affected -> SEV1 by users.
    m = _StubMetrics(
        error_rate=0.021, baseline_error_rate=0.001, requests_per_min=50000, active_users=1_000_000
    )
    est = estimate_impact(_alert(), m)
    assert est.affected_users >= 10000
    assert est.severity == Severity.SEV1


def test_negligible_incident_is_sev4():
    m = _StubMetrics(
        error_rate=0.002, baseline_error_rate=0.001, requests_per_min=10, active_users=50
    )
    est = estimate_impact(_alert(), m)
    assert est.severity == Severity.SEV4


def test_source_hint_can_raise_severity():
    m = _StubMetrics(
        error_rate=0.002, baseline_error_rate=0.001, requests_per_min=10, active_users=50
    )
    est = estimate_impact(_alert(hint=Severity.SEV1), m)
    assert est.severity == Severity.SEV1


@pytest.mark.parametrize(
    "error_rate,expected",
    [(0.12, Severity.SEV1), (0.06, Severity.SEV2), (0.02, Severity.SEV3)],
)
def test_error_rate_tiers(error_rate, expected):
    m = _StubMetrics(
        error_rate=error_rate, baseline_error_rate=0.0, requests_per_min=100, active_users=10
    )
    est = estimate_impact(_alert(), m)
    assert est.severity == expected
