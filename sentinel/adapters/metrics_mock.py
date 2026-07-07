"""Mock metrics adapter with seeded, deterministic per-service metrics."""

from __future__ import annotations

from datetime import datetime

from sentinel.adapters.base import ServiceMetrics

# Seeded metrics keyed by service. Values chosen so the sample checkout incident
# lands in SEV2 territory and the media latency alert stays lower severity.
_SEEDED: dict[str, dict[str, float]] = {
    "checkout-service": {
        "error_rate": 0.061,
        "baseline_error_rate": 0.004,
        "requests_per_min": 5400.0,
        "active_users": 18200,
    },
    "media-service": {
        "error_rate": 0.012,
        "baseline_error_rate": 0.006,
        "requests_per_min": 900.0,
        "active_users": 3100,
    },
    "web-frontend": {
        "error_rate": 0.003,
        "baseline_error_rate": 0.002,
        "requests_per_min": 12000.0,
        "active_users": 40000,
    },
}

_DEFAULT = {
    "error_rate": 0.02,
    "baseline_error_rate": 0.005,
    "requests_per_min": 1000.0,
    "active_users": 2000,
}


class MockMetricsAdapter:
    def service_metrics(
        self, service: str, window_start: datetime, window_end: datetime
    ) -> ServiceMetrics:
        m = _SEEDED.get(service, _DEFAULT)
        # affected_users ~= active users * excess error rate over baseline.
        excess = max(0.0, m["error_rate"] - m["baseline_error_rate"])
        active = int(m["active_users"])
        return ServiceMetrics(
            service=service,
            error_rate=float(m["error_rate"]),
            baseline_error_rate=float(m["baseline_error_rate"]),
            requests_per_min=float(m["requests_per_min"]),
            active_users=active,
        )
