"""Tests for stage 2 — runbook retrieval."""

from __future__ import annotations

from sentinel.pipeline.runbook import find_runbook, score_runbook


def test_checkout_alert_matches_checkout_runbook(checkout_alert, adapters):
    match = find_runbook(checkout_alert, adapters.runbooks)
    assert match is not None
    assert match.runbook.id == "checkout-5xx"
    assert match.score > 0


def test_runbooks_load_from_disk(adapters):
    runbooks = adapters.runbooks.all_runbooks()
    ids = {r.id for r in runbooks}
    assert {"checkout-5xx", "service-latency", "database-incident"} <= ids
    # Frontmatter parsed into structured fields.
    checkout = next(r for r in runbooks if r.id == "checkout-5xx")
    assert "checkout-service" in checkout.services
    assert "payments" in checkout.tags
    assert checkout.body  # body preserved


def test_service_match_outranks_generic_overlap(checkout_alert, adapters):
    runbooks = {r.id: r for r in adapters.runbooks.all_runbooks()}
    checkout_score = score_runbook(checkout_alert, runbooks["checkout-5xx"])
    db_score = score_runbook(checkout_alert, runbooks["database-incident"])
    assert checkout_score > db_score


def test_latency_alert_prefers_latency_runbook(sample_alerts, adapters):
    media = next(a for a in sample_alerts if a.service == "media-service")
    match = find_runbook(media, adapters.runbooks)
    assert match is not None
    assert match.runbook.id == "service-latency"


def test_no_match_returns_none(adapters):
    from sentinel.models import Alert

    alert = Alert(id="x", title="Totally unrelated event", service="unknown-service")
    assert find_runbook(alert, adapters.runbooks) is None
