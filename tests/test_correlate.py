"""Tests for stage 1 — commit correlation."""

from __future__ import annotations

from sentinel.pipeline.correlate import correlate

# The payment-retry refactor that was deployed to production ~4 min before the
# checkout alert. It should rank first.
CULPRIT_SHA = "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678"


def test_top_suspect_is_the_deployed_checkout_commit(checkout_alert, adapters):
    suspects = correlate(checkout_alert, adapters.github)

    assert suspects, "expected at least one suspect"
    top = suspects[0]
    assert top.commit.sha == CULPRIT_SHA
    assert top.deploy is not None
    assert top.score > 0.7
    assert top.reasons  # explainable


def test_suspects_sorted_by_descending_score(checkout_alert, adapters):
    suspects = correlate(checkout_alert, adapters.github)
    scores = [s.score for s in suspects]
    assert scores == sorted(scores, reverse=True)


def test_unrelated_service_commit_scores_lower(checkout_alert, adapters):
    suspects = correlate(checkout_alert, adapters.github)
    by_sha = {s.commit.sha: s for s in suspects}

    culprit = by_sha[CULPRIT_SHA]
    # The marketing-copy web-frontend commit is unrelated and older.
    web = next(s for s in suspects if "web-frontend" in s.commit.services_touched)
    assert culprit.score > web.score


def test_lookback_excludes_ancient_commits(checkout_alert, adapters):
    # All returned suspects must be within the lookback window before the alert.
    from sentinel.pipeline.correlate import LOOKBACK

    suspects = correlate(checkout_alert, adapters.github)
    window_start = checkout_alert.fired_at - LOOKBACK
    assert all(s.commit.timestamp >= window_start for s in suspects)
