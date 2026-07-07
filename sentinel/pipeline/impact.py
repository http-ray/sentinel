"""Stage 3 — impact estimation.

Pull service metrics for the alert window and derive an explainable blast-radius
estimate plus a severity (SEV1–SEV4). Severity is the max of two independent
lenses — error-rate magnitude and absolute affected-user count — so a small-but-
total outage and a low-percentage-but-huge-traffic incident both escalate.
"""

from __future__ import annotations

from datetime import timedelta

from sentinel.adapters.base import MetricsAdapter, ServiceMetrics
from sentinel.models import Alert, ImpactEstimate, Severity

# Window we consider "the incident" around the alert firing.
IMPACT_WINDOW = timedelta(minutes=15)

# Error-rate thresholds (fraction of requests failing) -> severity.
_ERROR_RATE_TIERS = [
    (0.10, Severity.SEV1),
    (0.05, Severity.SEV2),
    (0.01, Severity.SEV3),
]

# Affected-user thresholds -> severity.
_AFFECTED_USER_TIERS = [
    (10000, Severity.SEV1),
    (1000, Severity.SEV2),
    (100, Severity.SEV3),
]

_SEVERITY_ORDER = {Severity.SEV1: 3, Severity.SEV2: 2, Severity.SEV3: 1, Severity.SEV4: 0}


def _tier(value: float, tiers: list[tuple[float, Severity]]) -> Severity:
    for threshold, sev in tiers:
        if value >= threshold:
            return sev
    return Severity.SEV4


def _worst(*sevs: Severity) -> Severity:
    return max(sevs, key=lambda s: _SEVERITY_ORDER[s])


def _affected_users(metrics: ServiceMetrics) -> int:
    """Users touched by the *excess* error rate over baseline."""
    excess = max(0.0, metrics.error_rate - metrics.baseline_error_rate)
    return int(round(metrics.active_users * excess))


def estimate_impact(alert: Alert, metrics_adapter: MetricsAdapter) -> ImpactEstimate:
    """Estimate blast radius and severity for ``alert``."""
    window_end = alert.fired_at
    window_start = window_end - IMPACT_WINDOW
    m = metrics_adapter.service_metrics(alert.service, window_start, window_end)

    affected = _affected_users(m)

    sev_by_error = _tier(m.error_rate, _ERROR_RATE_TIERS)
    sev_by_users = _tier(affected, _AFFECTED_USER_TIERS)
    severity = _worst(sev_by_error, sev_by_users)

    # An alert source can hint a higher severity than metrics suggest; respect it.
    if alert.severity_hint is not None:
        severity = _worst(severity, alert.severity_hint)

    notes = [
        f"Error rate {m.error_rate:.1%} vs baseline {m.baseline_error_rate:.1%}",
        f"~{affected:,} users affected of {m.active_users:,} active",
        f"{m.requests_per_min:,.0f} req/min through {alert.service}",
        f"Severity driven by {'error rate' if _SEVERITY_ORDER[sev_by_error] >= _SEVERITY_ORDER[sev_by_users] else 'affected users'}",
    ]

    return ImpactEstimate(
        service=alert.service,
        error_rate=m.error_rate,
        requests_per_min=m.requests_per_min,
        affected_users=affected,
        baseline_error_rate=m.baseline_error_rate,
        severity=severity,
        notes=notes,
    )
